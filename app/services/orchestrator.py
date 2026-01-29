import asyncio
import logging
import json
import os
import time
import random
from typing import Dict, Any, List, Optional
from aiokafka import AIOKafkaConsumer
import json

from app.core.config import settings
from app.services.kafka_service import kafka_service
from app.services.redis_service import redis_service
from app.services.mongo import mongo_service
from app.api.schemas import LLMRequest, SessionSummary, SessionType
from app.services.prompts import get_summary_update_prompt, get_tool_check_prompt, get_tool_selection_prompt, get_tool_args_prompt, format_history_for_prompt, get_no_tool_summary_prompt, get_clarification_summary_prompt, get_base_prompt, get_tool_summary_prompt, get_inappropriate_summary_prompt, get_gibberish_summary_prompt
from app.services.mcp_service import MCPClient
from app.services.metrics_service import metrics_service
from app.utils.random_utils import generate_random_id, deep_clean_tool_args, validate_and_clean_tool_args, get_tool_specific_prompt, persona_json_to_system_prompt
from app.utils.cache_persona import cache_persona
from app.services.eleven_labs_audio_gen_service import eleven_labs_audio_gen_service
from app.services.blob_storage_uploader_service import blob_storage_uploader_service

logger = logging.getLogger(__name__)

# Path to our MCP server


FALLBACK_MESSAGES = [
    "I'm having a bit of trouble connecting right now. Could you please try asking that again?",
    "It seems my thoughts got a little tangled. Mind repeating that?",
    "I didn't quite catch that due to a technical hiccup. Please try again.",
    "Sorry, I encountered a temporary issue. Let's try that one more time.",
    "I'm experiencing a brief service interruption. Please ask me again in a moment."
]

class OrchestratorService:
    def __init__(self):
        self._tasks = []
        self._mcp_client: MCPClient = None
        self.running = False
        
        # Futures for checking request completion
        self._pending: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()

    async def start(self):
        if self.running: return
        self.running = True
        logger.info("OrchestratorService starting...")
        
        # 1. Init MCP
        await self.init_mcp()
        
        # 2. Start Response Consumer
        self._tasks.append(asyncio.create_task(self._response_consumer_loop()))
        
        # 3. Start Ping Scheduler
        self._tasks.append(asyncio.create_task(self._ping_loop()))
        
        logger.info("OrchestratorService started")

    async def stop(self):
        self.running = False
        for t in self._tasks: t.cancel()
            
        async with self._lock:
            for fut in self._pending.values():
                if not fut.done():
                    fut.cancel()
            self._pending.clear()

        if self._mcp_client:
            await self._mcp_client.__aexit__(None, None, None)
            self._mcp_client = None
            
        logger.info("OrchestratorService stopped")

    async def init_mcp(self):
        logger.info("MCP Initialization")
        self._mcp_client = MCPClient(settings.MCP_SERVER_SCRIPT)
        await self._mcp_client.__aenter__()
        await self._mcp_client.fetch_all_members()
        logger.info("MCP Initialization Completed")

    # --------------------------
    # Messaging Helpers
    # --------------------------
    async def _send_status(self, request_id: str, status: str, extra: Dict = None):
        """Emit status events to Kafka for SSE consumer"""
        msg = {
            "request_id": request_id, 
            "status": status,
            "extra": extra or {},
            "source": "orchestrator"
        }
        # Send to response topic so SSE picks it up
        # NOTE: SSE listens to Redis channel f"chat_status:{request_id}"
        await redis_service.publish(f"chat_status:{request_id}", msg)

    async def _wait_for_llm(self, request_id: str) -> Optional[Dict]:
        """Create a future and wait for consumer to resolve it"""
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        async with self._lock:
            self._pending[request_id] = fut
        
        try:
            # Wait for response with timeout
            resp = await asyncio.wait_for(fut, timeout=60.0)
            return resp
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for LLM: {request_id}")
            return None
        finally:
            async with self._lock:
                self._pending.pop(request_id, None)

    async def _dispatch_llm_request(self, req: LLMRequest):
        metrics_service.record_llm_job_start()
        await kafka_service.send_request(settings.KAFKA_CHAT_TOPIC, req.model_dump())

    # --------------------------
    # Core Logic
    # --------------------------
    async def handle_request(self, user_id: str, query: str, session_id: Optional[str] = None, person_id: Optional[str] = None, personality_id: Optional[str] = None, session_type: Optional[str] = None) -> str:
        """
        Public API: Spawns the orchestration task.
        """
        request_id = f"REQCHAT-{generate_random_id(user_id)}"
        
        # Store initial history
        user_msg = {"role": "user", "content": query}
        await self.append_history(user_id, user_msg, session_id)
        
        # Metrics: Start Request
        metrics_service.record_request_start()

        # Spawn the orchestration flow
        asyncio.create_task(self._orchestrate(request_id, user_id, query, session_id, person_id, personality_id, session_type))
        
        return request_id

    async def _orchestrate(self, request_id: str, user_id: str, query: str, session_id: Optional[str] = None, person_id: Optional[str] = None, personality_id: Optional[str] = None, session_type: Optional[str] = None):
        tool_result_str = ""
        tool_args = None
        structured_result = None
        try:
            logger.info(f"Orchestration started for {request_id} and user {user_id} and session {session_id}")
            await self._send_status(request_id, "RECEIVED")
            
            # 1. Prepare Context
            history, session_summary, session = await self._prepare_context(user_id, session_id)

            # 1.1 Fetch Person Profile if person_id provided
            user_profile = None
            if person_id:
                try:
                    # 1. Check Redis Cache
                    user_profile = await redis_service.get_person_profile(user_id, person_id)
                    
                    if user_profile:
                        logger.info(f"Cache hit for person profile {person_id}")
                    else:
                        # 2. Fetch from Mongo
                        logger.info(f"Cache miss for person profile {person_id}, fetching from Mongo")
                        projection = {"name": 1, "age": 1, "gender": 1, "address": 1, "country": 1, "tags": 1}
                        user_profile = await mongo_service.get_profile(user_id, person_id, projection)
                        
                        if user_profile:
                            # 3. Save to Redis Cache (TTL 1 day)
                            # Convert _id to str if present to ensure JSON serialization
                             if "_id" in user_profile:
                                 user_profile["_id"] = str(user_profile["_id"])
                                 
                             await redis_service.save_person_profile_cache(user_id, person_id, user_profile)
                             logger.info(f"Cached person profile for {person_id}")

                except Exception as e:
                    logger.error(f"Failed to fetch person profile {person_id}: {e}")

            
            # 2. Step 1: Check Decision -> "no_tool", "tool_required", "ask_clarification, "inappropriate_block"
            tool_required = await self._step_check_tool(request_id, user_id, query, history, session)

            decision = tool_required.get("decision") if tool_required else None
            logger.info(f"Step 1 result: Desicion {decision}")

            if not decision:
                logger.warning("Tool decision missing from LLM response")

            elif decision == "tool":
                # 3. New Step 2: Select Tool
                selected_tool = await self._step_select_required_tool(
                    request_id,
                    user_id,
                    query,
                    history,
                    session,
                    session_id
                )
                logger.info(f"Step 2 result: Selected Tool {selected_tool}")

                if selected_tool:
                    # 4. Refactored Step 3: Tool Execution (Argument Extraction + Call)
                    tool_result_str, tool_args, structured_result = await self._step_tool_execution(
                        request_id,
                        user_id,
                        query,
                        history,
                        session,
                        selected_tool,
                        session_id
                    )
                else:
                    logger.warning("No tool selected in Step 2, skipping execution")
            
            elif decision in ("no_tool", "ask_clarification", "inappropriate_block", "gibberish"):
                logger.info(f"Decision={decision}, skipping tool execution")

            else:
                logger.warning(f"Invalid tool decision received: {decision}")

            await self._step_summarize(
                request_id, user_id, query, history, session_summary, 
                tool_result_str, tool_args, structured_result, session_id, tool_required, decision, user_profile, personality_id, session_type
            )
                

        except Exception as e:
            logger.exception(f"Orchestration Error {request_id}: {e}")
            await self._handle_error_response(request_id, user_id, session_id, query, str(e))

    # --------------------------
    # Orchestration Steps
    # --------------------------
    async def _prepare_context(self, user_id: str, session_id: Optional[str] = None):
        """Fetches history and session summary to build context string."""
        history = await self.get_history(user_id, session_id) 
        session_summary = await redis_service.get_session_summary(user_id, session_id)

        if session_summary:
            return history, session_summary, session_summary
        
        return history, None, None

    async def _step_check_tool(self, request_id: str, user_id: str, query: str, history: List[Dict], session: Any) -> bool:
        """Step 1: Determine if tool is required."""
        # Inject History
        formatted_history = format_history_for_prompt(history)
        check_system_prompt = get_tool_check_prompt(formatted_history)

        llm_req = LLMRequest(
            request_id=request_id,
            step="check_tool_required",
            message=query,
            system_prompt=check_system_prompt,
            json_response=True,
            response_topic=settings.KAFKA_RESPONSE_TOPIC,
            metadata={"user_id": user_id}
        )
        t0 = time.time()
        await self._dispatch_llm_request(llm_req)
        await self._send_status(request_id, "LLM_CHECKING_TOOLS")

        resp = await self._wait_for_llm(request_id)
        if not resp:
            raise Exception("Timeout waiting for Tool Check Step")
        
        metrics_service.record_step_duration("check_tool_required", time.time() - t0)
        
        if resp.get("error"):
            raise Exception(f"LLM Error in Tool Check: {resp.get('error')}")

        tool_required = resp.get("tool_required", "")
        return tool_required

    async def _step_select_required_tool(self, request_id: str, user_id: str, query: str, history: List[Dict], session: Any, session_id: Optional[str] = None) -> Optional[str]:
        """Step 2: If tool is required, select the most appropriate tool."""
        tool_list = self._mcp_client.get_sections("tools")
        formatted_tool_descriptions = self._mcp_client.format_tool_descriptions_for_llm(tool_list)

        formatted_history = format_history_for_prompt(history)
        selection_prompt = get_tool_selection_prompt(formatted_tool_descriptions, formatted_history)

        llm_req = LLMRequest(
            request_id=request_id,
            step="select_tool",
            message=query,
            system_prompt=selection_prompt,
            json_response=True,
            response_topic=settings.KAFKA_RESPONSE_TOPIC,
            metadata={"user_id": user_id}
        )
        t0 = time.time()
        await self._dispatch_llm_request(llm_req)
        await self._send_status(request_id, "LLM_SELECTING_TOOL")

        resp = await self._wait_for_llm(request_id)
        if not resp:
            raise Exception("Timeout waiting for Tool Selection Step")
        
        metrics_service.record_step_duration("select_tool", time.time() - t0)
        
        if resp.get("error"):
            raise Exception(f"LLM Error in Tool Selection: {resp.get('error')}")

        return resp.get("selected_tool")
    
    def _get_selected_tool_meta(self, tool_list, selected_tool):
        meta = next((t for t in tool_list if t.get("name") == selected_tool), None)
        if not meta:
            raise Exception(f"Selected tool {selected_tool} not found in MCP tools")
        return meta

    
    def _parse_mcp_output(self, res_mcp):
        if not isinstance(res_mcp, dict):
            return None

        output = res_mcp.get("output")
        if not output:
            return None

        if getattr(output, "structuredContent", None):
            return output.structuredContent

        if getattr(output, "content", None):
            for item in output.content:
                if getattr(item, "type", None) == "text":
                    return json.loads(item.text)

        return None
    
    async def _prepare_and_validate_tool_args(self, user_id, session_id, selected_tool, tool_args, tool_list ):
        # Merge deterministic state
        final_tool_args = await self._merge_tool_args(
            user_id, session_id, selected_tool, tool_args
        )

        tool_meta = self._get_selected_tool_meta(tool_list, selected_tool)
        tool_schema = tool_meta.get("input_schema", {})

        # Inject user_id
        final_tool_args["user_id"] = user_id

        # Validate & clean
        final_tool_args = validate_and_clean_tool_args(final_tool_args, tool_schema)

        # Persist cleaned state
        full_state = await redis_service.get_tool_state(user_id, session_id)
        full_state[selected_tool] = final_tool_args
        await redis_service.save_tool_state(user_id, full_state, session_id)

        return final_tool_args
    
    async def _check_result_already_fetched( self, structured_result, selected_tool, user_id, session_id):
        if not structured_result or not isinstance(structured_result, dict):
            return False

        docs = structured_result.get("docs", [])
        if not docs:
            return False

        full_state = await redis_service.get_tool_state(user_id, session_id)

        # Tool-scoped namespace
        seen_docs_state = full_state.setdefault("_seen_docs", {})
        seen_docs = set(seen_docs_state.get(selected_tool, []))

        seen = False
        all_ids = []
        count=0

        for doc in docs:
            doc_id = doc.get("_id")
            if not doc_id:
                continue

            if doc_id in seen_docs:
                count=count+1
            
            all_ids.append(doc_id)

        if count>4:
            seen=True

        # Persist updated state
        if all_ids:
            seen_docs.update(all_ids)
            seen_docs_state[selected_tool] = list(seen_docs)
            full_state["_seen_docs"] = seen_docs_state
            await redis_service.save_tool_state(user_id, full_state, session_id)

        return seen


    async def _handle_auto_reset_and_pagination( self, structured_result, selected_tool, user_id, session_id, final_tool_args):
        if not isinstance(structured_result, dict):
            return structured_result

        docs = structured_result.get("docs", [])

        # ----------------------------------------
        # AUTO-RESET LOGIC
        # ----------------------------------------
        if len(docs) == 0:
            logger.info(
                f"Tool {selected_tool} returned 0 results. Auto-resetting state."
            )
            full_state = await redis_service.get_tool_state(user_id, session_id)
            full_state.pop(selected_tool, None)
            await redis_service.save_tool_state(user_id, full_state, session_id)
            return structured_result

        # ----------------------------------------
        # PAGINATION WITH BOUNDED RETRIES
        # ----------------------------------------
        MAX_PAGINATION_RETRIES = 4
        attempts = 0
        current_result = structured_result

        while attempts < MAX_PAGINATION_RETRIES:
            if not await self._check_result_already_fetched(
                current_result,
                selected_tool,
                user_id,
                session_id
            ):
                # Fresh results found
                return current_result

            logger.info(
                f"Duplicate results detected for tool={selected_tool}. "
                f"Retry {attempts + 1}/{MAX_PAGINATION_RETRIES}"
            )

            # Increment page safely (page 1 → 2 → 3 ...)
            final_tool_args["page"] = final_tool_args.get("page", 1) + 1

            new_res = await self._mcp_client.call_tool(
                selected_tool, final_tool_args
            )
            current_result = self._parse_mcp_output(new_res)

            if not current_result or not isinstance(current_result, dict):
                break

            attempts += 1
        
        #save page back to state
        full_state = await redis_service.get_tool_state(user_id, session_id)
        full_state[selected_tool] = final_tool_args
        await redis_service.save_tool_state(user_id, full_state, session_id)
        # Best-effort return
        return current_result


    async def _step_tool_execution(self, request_id: str, user_id: str, query: str, history: List[Dict], session: Any, selected_tool: str, session_id: Optional[str] = None):
        """Step 3: Extract args for the SELECTED tool and execute."""
        final_tool_args = {}
        tool_result_str = None
        structured_result = None

        tool_list = self._mcp_client.get_sections("tools")
        selected_tool_meta = next((t for t in tool_list if t.get("name") == selected_tool), None)
        
        if not selected_tool_meta:
            raise Exception(f"Selected tool {selected_tool} not found in MCP tools")

        tool_schema = json.dumps(selected_tool_meta.get("input_schema", {}), indent=2)
        formatted_history = format_history_for_prompt(history)
        
        # Get Prompt for targeted argument extraction
        tool_specific_prompt = get_tool_specific_prompt(selected_tool)

        args_system_prompt = get_tool_args_prompt(selected_tool, tool_specific_prompt, tool_schema, formatted_history)

        # Dispatch Request
        llm_req = LLMRequest(
            request_id=request_id,
            step="get_tool_args",
            message=query,
            system_prompt=args_system_prompt,
            json_response=True,
            response_topic=settings.KAFKA_RESPONSE_TOPIC,
            metadata={"user_id": user_id}
        )
        t0 = time.time()
        await self._dispatch_llm_request(llm_req)
        await self._send_status(request_id, "LLM_EXTRACTING_ARGS")
        
        # Wait Response
        resp = await self._wait_for_llm(request_id)
        if not resp:
            raise Exception("Timeout waiting for Tool Args Step")
        
        # logger.info(f"Tool Args Response: {resp}")
        
        metrics_service.record_step_duration("get_tool_args", time.time() - t0)
        tool_args = resp.get("tool_args", {})

        if not tool_args:
            logger.info(f"No tool args returned: {resp}")
            tool_args = {}

        if isinstance(tool_args, str):
            tool_args = json.loads(tool_args)
        
        await self._send_status(request_id, f"TOOL_SELECTED: {selected_tool}")
        
        if tool_args:
            try:
                final_tool_args = await self._prepare_and_validate_tool_args(
                    user_id, session_id, selected_tool, tool_args, tool_list
                )
                
                logger.info(f"Executing tool {selected_tool} with args {final_tool_args}")

                res_mcp = await self._mcp_client.call_tool(selected_tool, final_tool_args)

                structured_result = self._parse_mcp_output(res_mcp)

                structured_result = await self._handle_auto_reset_and_pagination(
                    structured_result,
                    selected_tool,
                    user_id,
                    session_id,
                    final_tool_args
                )

                tool_result_str = json.dumps(structured_result, default=str)

                await self.append_history(
                    user_id,
                    {"role": "tool", "name": selected_tool, "args": final_tool_args},
                    session_id
                )
                await self._send_status(request_id, "TOOL_EXECUTED")
                
            except Exception as e:
                tool_result_str = f"Error: {str(e)}"
                await self._send_status(request_id, "TOOL_ERROR", {"error": str(e)})
        else:
            logger.info(f"No tool received from the model due to some reason debug using this {resp}")
        return tool_result_str, final_tool_args, structured_result

        

    async def _step_summarize(self, request_id: str, user_id: str, query: str, history: List[Dict], session_summary: Any, tool_result_str: Optional[str], tool_args: Any, structured_result: Any, session_id: Optional[str] = None, tool_required: bool = False, decision: Optional[str] = None, user_profile: Optional[Dict] = None, personality_id: Optional[str] = None, session_type: Optional[str] = None):
        """Step 3: Generate final answer."""
        # Prepare Context
        formatted_history = format_history_for_prompt(history)

        personality = get_base_prompt()
        voice_id = None
        language=""
        identity=None
        if personality_id:
            persona = await cache_persona.get_persona(user_id, personality_id)
            if persona:
                logger.info(f"Personality found for {user_id} and {personality_id}")
                personality = persona_json_to_system_prompt(persona.get("personality"))
                voice_id = persona.get("voice_id")
                identity = persona.get("personality", {}).get("identity", {})
                if identity:
                    language = f"- Languages: {', '.join(identity['languages'])}"

        if decision == 'ask_clarification':
            default_prompt = get_clarification_summary_prompt(formatted_history, personality, session_summary, user_profile)
        elif decision == 'tool':
            if structured_result and isinstance(structured_result, dict):
                is_tool_result_check = len(structured_result.get("docs", [])) > 0
            else:
                is_tool_result_check = False
            default_prompt = get_tool_summary_prompt(formatted_history, is_tool_result_check, tool_result_str, personality, session_summary, user_profile)
        elif decision == 'inappropriate_block':
            default_prompt = get_inappropriate_summary_prompt(formatted_history, personality, session_summary, user_profile)
        elif decision == 'gibberish':
            default_prompt = get_gibberish_summary_prompt(formatted_history, personality, session_summary, user_profile)
        else:
            default_prompt = get_no_tool_summary_prompt(formatted_history, personality, session_summary, user_profile)

        SHORT_ANSWER_PROMPT="MANDATORY: ANSWER IN ONE SENTENCE. IF ABSOLUTELY NECESSARY, USE TWO SENTENCES. DO NOT ELABORATE OR PROVIDE UNNECESSARY DETAILS."
        # LANGUAGE_PROMPT=f"MANDATORY: RESPOND ONLY IN {language}. DO NOT USE ANY OTHER LANGUAGE OR MIX LANGUAGES IN YOUR RESPONSE."
        if language:
            LANGUAGE_PROMPT = f"MANDATORY: SPEAK ONLY IN {', '.join(identity['languages'])}. DO NOT USE ANY OTHER LANGUAGE OR MIX LANGUAGES IN YOUR RESPONSE."
        else:
            LANGUAGE_PROMPT = "MANDATORY: SPEAK ONLY IN ENGLISH. DO NOT USE ANY OTHER LANGUAGE OR MIX LANGUAGES IN YOUR RESPONSE."

        default_prompt=default_prompt+SHORT_ANSWER_PROMPT+LANGUAGE_PROMPT

        llm_req = LLMRequest(
            request_id=request_id,
            step="summarize",
            message=query,
            system_prompt=default_prompt,
            json_response=False,
            response_topic=settings.KAFKA_RESPONSE_TOPIC,
            metadata={"user_id": user_id}
        )
        t0 = time.time()
        await self._dispatch_llm_request(llm_req)
        await self._send_status(request_id, "LLM_SUMMARIZING")

        resp = await self._wait_for_llm(request_id)
        metrics_service.record_step_duration("summarize", time.time() - t0)
        
        logger.info(f"Step 3 result: Summarize {resp}")
        if resp and resp.get("final_answer"):
            await self._complete_request(user_id, request_id, resp.get("final_answer"), structured_result, tool_args, session_id, query, tool_required, None, session_type, voice_id)
        else:
            await self._send_status(request_id, "NO_SUMMARY")
            await self._handle_error_response(request_id, user_id, session_id, query, "No Summary Generated")

    async def _complete_request(self, user_id: str, request_id: str, answer: str, structured, tool_args=None, session_id: Optional[str] = None, query: str = None, tool_required: bool = False, error: Optional[str] = None, session_type: Optional[str] = None, voice_id: Optional[str] = None) :
        # Save to history
        await self.append_history(user_id, {"role": "assistant", "content": answer}, session_id)
        # Publish final event (mimic what SSE expects for closure)
        # SSE expects msg.final_answer to break loop
        msg = {
            "request_id": request_id,
            "step": "summarize",
            "final_answer": answer,
            "metadata": {"user_id": user_id, "session_id": session_id},
            "tool_result": structured,
            "source": "orchestrator"
        }
        await redis_service.publish(f"chat_status:{request_id}", msg)
        logger.info(f"Completed request {request_id}")
        if session_type == "2":
            # msg["audio_clip"]=text_to_audio(answer,voice_id)
            audio_stream = eleven_labs_audio_gen_service.text_to_audio(answer, voice_id)
            if audio_stream:
                audio_url = blob_storage_uploader_service.generate_url(audio_stream)
                if audio_url:
                    msg["audio_clip"] = audio_url
        
        # Log to MongoDB
        log_data = {
            "request_id": request_id,
            "session_id": session_id,
            "user_id": user_id,
            "user_query": query,
            "tool_required": tool_required,
            "status": "completed",
            "complete": True,
            "final_answer": answer,
            "tool_result": structured,
            "voice_clip": msg.get("audio_clip", ""),
            "error": error,
            "metadata": {"user_id": user_id},
            "timestamp": time.time()
        }
        asyncio.create_task(mongo_service.save_chat_log(user_id, log_data))
        
        # Metrics: Complete
        # We don't have exact duration here easily unless we passed start time. 
        # For end-to-end, we can track it if we stored start time in a map or context.
        # But for now let's just mark completion to balance active_requests.
        # Ideally, we should add `timestamp` to `handle_request` return or separate tracking.
        # Let's assume we want E2E. Logic: `time.time() - log_data['timestamp']` (approx, since timestamp is creation time)
        
        metrics_service.record_request_complete(duration=0.0) # Placeholder duration or calc if possible
        
        # Trigger Background Summary Update
        asyncio.create_task(self._background_summary_update(user_id, answer, tool_args, session_id))

    async def _background_summary_update(self, user_id: str, answer: str, tool_args: Any, session_id: Optional[str] = None):
        try:
            # 1. Get current summary
            summary = await redis_service.get_session_summary(user_id, session_id)
            
            # 2. Construct Prompt
            prompt = get_summary_update_prompt()
            input_ctx = f"""
            Current Summary: {summary.model_dump_json()}
            Last Assistant Answer: {answer}
            """
            
            # 3. Call LLM (using the same Kafka/Response flow is hard because it's async background)
            # Easier: Just fire a one-off request if we have a direct client, BUT we only have Kafka Loop.
            # We must spawn a new RequestID for this "internal" maintenance task.
            
            update_req_id = f"SUMMARY-{generate_random_id(user_id)}"
            
            llm_req = LLMRequest(
                request_id=update_req_id,
                step="custom",
                message=input_ctx,
                system_prompt=prompt,
                json_response=True,
                response_topic=settings.KAFKA_RESPONSE_TOPIC,
                metadata={"user_id": user_id, "type": "session_update", "session_id": session_id}                                                                                                         
            )
            await self._dispatch_llm_request(llm_req)
            logger.info("Summary Update Dispatched")
            # The response will verify in _response_consumer_loop? 
            # Yes, we need to handle it there.
             
        except Exception as e:
            logger.error(f"Background Update Error: {e}")

    # --------------------------
    # Ping Scheduler
    # --------------------------
    async def _ping_loop(self):
        logger.info("Starting Ping Scheduler")
        while self.running:
            try:
                await asyncio.sleep(30) # 30 seconds interval
                msg = {
                    "type": "ping",
                    "source": "orchestrator", 
                    "timestamp": time.time(),
                    "response_topic": settings.KAFKA_RESPONSE_TOPIC
                }
                # We use send_request to push to the chat topic
                await kafka_service.send_request(settings.KAFKA_CHAT_TOPIC, msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ping Loop Error: {e}") 

    # --------------------------
    # Consumer Loop
    # --------------------------
    async def _response_consumer_loop(self):
        consumer = AIOKafkaConsumer(
            settings.KAFKA_RESPONSE_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        try:
            await consumer.start()
            async for msg in consumer:
                data = msg.value
                rid = data.get("request_id")
                
                # Check if it's a status message we sent ourselves (ignore)
                if data.get("source") == "orchestrator":
                    continue
                    
                # If it's an LLM response, find the waiting future
                if rid:
                    async with self._lock:
                        fut = self._pending.get(rid)
                        if fut and not fut.done():
                            fut.set_result(data)
                            
                            # Metrics: LLM Job End
                            # Check usage
                            usage = data.get("usage", {})
                            tokens = usage.get("token_count", 0) if usage else 0
                            duration = usage.get("total_duration", 0) if usage else 0
                            metrics_service.increment_tokens(tokens, duration)
                            metrics_service.record_llm_job_end(duration, tokens)

                # Check for Session Update Response
                if rid and rid.startswith("SUMMARY-") and data.get("custom_response"):
                    session_id = data.get("metadata", {}).get("session_id")
                    custom_response = data.get("custom_response")
                    custom_response['user_id'] = data.get('metadata', {}).get('user_id', None)
                    custom_response['session_id'] = session_id
                    await self._handle_summary_update(custom_response, session_id)

                # Check for Pong
                if data.get("type") == "pong":
                    pass
                            
        except Exception as e:
            logger.error(f"Consumer Loop Error: {e}")
        finally:
            await consumer.stop()

    # --------------------------
    # History Helpers (Unchanged)
    # --------------------------
    async def get_history(self, user_id: str, session_id: Optional[str] = None) -> List[Dict]:
        key = f"chat_history:{user_id}"
        if session_id:
             key = f"{key}:{session_id}"
        items = await redis_service.client.lrange(key, 0, 4)
        history = []
        if items:
            for item in items:
                try: history.append(json.loads(item))
                except: pass
        return history[::-1]

    async def append_history(self, user_id: str, message: Dict, session_id: Optional[str] = None):
        key = f"chat_history:{user_id}"
        if session_id:
             key = f"{key}:{session_id}"
        data = json.dumps(message)
        await redis_service.client.lpush(key, data)
        await redis_service.client.ltrim(key, 0, 4)

    async def delete_history(self, user_id: str, session_id: Optional[str] = None):
        await redis_service.delete_history(user_id, session_id)

    async def get_all_sessions(self, user_id: str) -> List[Dict]:
        return await redis_service.get_user_chat_sessions(user_id)
        
    async def get_all_session_summaries(self, user_id: str) -> List[SessionSummary]:
        return await redis_service.get_all_session_summaries(user_id)

    async def _handle_summary_update(self, data: Dict, session_id: Optional[str] = None):
        try:
            uid = data.get("user_id")
            if not uid:
                logger.warning("Session summary update skipped: missing user_id")
                return

            # Validate directly from dict (no JSON parsing needed)
            new_summary = SessionSummary.model_validate(data)

            # Update timestamp
            new_summary.last_updated = time.time()

            await redis_service.save_session_summary(uid, new_summary, session_id)
            logger.info(f"Updated Session Summary for {uid}")

        except Exception as e:
            logger.error(f"Failed to save session summary: {e}", exc_info=True)

    async def _handle_error_response(self, request_id: str, user_id: str, session_id: Optional[str], query: str, error_msg: str):
        """Handle orchestration errors by sending a fallback response."""
        fallback_msg = random.choice(FALLBACK_MESSAGES)
        logger.info(f"Sending fallback response for {request_id}: {fallback_msg}")
        
        # We reuse _complete_request to ensure logs, history, and status events are consistent
        # We pass tool_required=False and empty structured result
        await self._complete_request(
            user_id=user_id,
            request_id=request_id,
            answer=fallback_msg,
            structured=None,
            tool_args=None,
            session_id=session_id,
            query=query,
            tool_required=False,
            error=error_msg
        )
        metrics_service.record_request_complete(duration=0.0, error=True)

    async def _merge_tool_args(self, user_id: str, session_id: Optional[str], selected_tool: str, new_args: dict) -> dict:
        """
        Helper method to merge new tool args with persisted state.
        Returns the final merged dictionary for the SPECIFIC tool.
        """
        final_tool_args = {}
        final_tool_args = new_args.copy()  # Start with what LLM extracted

        # 1. Load full nested state
        full_state = await redis_service.get_tool_state(user_id, session_id)
        
        # 2. Extract specific tool section
        current_tool_args = full_state.get(selected_tool, {})

        # 🔹 NEW: Normalize page intent
        if "page" in final_tool_args:
            prev_page = current_tool_args.get("page", 1)

            if final_tool_args["page"] > 0:
                # Next page intent
                final_tool_args["page"] = prev_page + 1
            elif final_tool_args["page"] == 0:
                # page: 0 or anything else → reset
                final_tool_args["page"] = 1
        
        # 3. Check for Reset
        if new_args.get("_reset"):  # Reset if _reset is present
            current_tool_args = {}
            final_tool_args.pop("_reset", None)
        
        # 4. Merge Logic
        # Start with current (baseline for this tool)
        merged = current_tool_args.copy()
        
        # Apply updates from LLM (new_args)
        for k, v in final_tool_args.items():
            if v is None:
                # Explicit removal
                merged.pop(k, None)
            else:
                # Update/Add
                merged[k] = v
        
        # 5. Check for Filter Changes (Reset Page)
        # If any attribute changed EXCEPT 'page' or '_reset' or 'user_id', we must reset page to 1.
        filters_changed = False
        for k in final_tool_args:
            if k in ["page", "_reset", "user_id"]:
                continue
            filters_changed = True
            break
        
        if filters_changed:
            merged["page"] = 1
        
        return merged

orchestrator_service = OrchestratorService()