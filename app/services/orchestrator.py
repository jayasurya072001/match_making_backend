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
from app.api.schemas import LLMRequest, SessionSummary
from app.services.prompts import get_default_system_prompt, get_tool_system_prompt, get_summary_update_prompt, get_tool_check_prompt, get_tool_args_prompt
from app.services.mcp_service import MCPClient
from app.utils.random import generate_random_id, deep_clean_tool_args


logger = logging.getLogger(__name__)

# Path to our MCP server
MCP_SERVER_SCRIPT = "/home/jayasurya/SmritDB/app/mcp/smrit_mcp_service.py"

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
        self._mcp_client = MCPClient(MCP_SERVER_SCRIPT)
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
        await kafka_service.send_request(settings.KAFKA_CHAT_TOPIC, req.model_dump())

    # --------------------------
    # Core Logic
    # --------------------------
    async def handle_request(self, user_id: str, query: str, session_id: Optional[str] = None) -> str:
        """
        Public API: Spawns the orchestration task.
        """
        request_id = f"REQCHAT-{generate_random_id(user_id)}"
        
        # Store initial history
        user_msg = {"role": "user", "content": query}
        await self.append_history(user_id, user_msg, session_id)
        
        # Spawn the orchestration flow
        asyncio.create_task(self._orchestrate(request_id, user_id, query, session_id))
        
        return request_id

    async def _orchestrate(self, request_id: str, user_id: str, query: str, session_id: Optional[str] = None):
        try:
            logger.info(f"Orchestration started for {request_id}")
            await self._send_status(request_id, "RECEIVED")
            
            # 1. Prepare Context
            history, session_summary, session = await self._prepare_context(user_id, session_id)
            
            # 2. Step 1: Check Tool Required
            tool_required = await self._step_check_tool(request_id, user_id, query, history, session)
            logger.info(f"Step 1 result: Tool Required {tool_required}")
            
            # 3. Step 2: Tool Execution (if needed)
            tool_result_str, tool_args, structured_result = await self._step_tool_execution(
                request_id, user_id, query, history, session, tool_required, session_id
            )

            logger.info(f"Step 2 result: Tool Result {tool_result_str}")
            
            # 4. Step 3: Summarize
            await self._step_summarize(
                request_id, user_id, query, history, session_summary, 
                tool_result_str, tool_args, structured_result, session_id, tool_required
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
        check_system_prompt = get_tool_check_prompt(history)
        
        llm_req = LLMRequest(
            request_id=request_id,
            step="check_tool_required",
            message=query,
            system_prompt=check_system_prompt,
            conversation_history=history,
            response_topic=settings.KAFKA_RESPONSE_TOPIC,
            metadata={"user_id": user_id}
        )
        await self._dispatch_llm_request(llm_req)
        await self._send_status(request_id, "LLM_CHECKING_TOOLS")

        resp = await self._wait_for_llm(request_id)
        if not resp:
            raise Exception("Timeout waiting for Tool Check Step")
        
        if resp.get("error"):
            raise Exception(f"LLM Error in Tool Check: {resp.get('error')}")

        tool_required = resp.get("tool_required", False)
        return tool_required

    async def _step_tool_execution(self, request_id: str, user_id: str, query: str, history: List[Dict], session: Any, tool_required: bool, session_id: Optional[str] = None):
        """Step 2: If required, identify tool, extract args, and execute."""
        if not tool_required:
            return None, None, None

        tool_list = self._mcp_client.get_sections("tools")
        formatted_tools = self._mcp_client.format_tools_for_llm(tool_list)
        args_system_prompt = get_tool_args_prompt(history, session.current_tool_args)
        
        logger.info(f"Sending for tool")
        # Dispatch Request
        llm_req = LLMRequest(
            request_id=request_id,
            step="get_tool_args",
            message=query,
            system_prompt=args_system_prompt,
            conversation_history=history,
            tool_list=formatted_tools,
            response_topic=settings.KAFKA_RESPONSE_TOPIC,
            metadata={"user_id": user_id}
        )
        await self._dispatch_llm_request(llm_req)
        await self._send_status(request_id, "LLM_EXTRACTING_ARGS")
        
        # Wait Response
        resp = await self._wait_for_llm(request_id)
        if not resp:
            raise Exception("Timeout waiting for Tool Args Step")
        
        logger.info(f"Tool Args Response: {resp}")

        selected_tool = resp.get("selected_tool")
        tool_args = resp.get("tool_args", {})
        
        tool_result_str = None
        structured_result = None
        
        if selected_tool:
            await self._send_status(request_id, f"TOOL_SELECTED: {selected_tool}")
            try:
                if isinstance(tool_args, str): tool_args = json.loads(tool_args)

                tool_args['user_id'] = user_id

                tool_args = deep_clean_tool_args(tool_args)

                logger.info(f"Tool executing {selected_tool} with args {tool_args}")

                # EXECUTE TOOL
                res_mcp = await self._mcp_client.call_tool(selected_tool, tool_args)

                logger.info(f"Tool Execution Result: {res_mcp}")
                
                if isinstance(res_mcp, dict):
                    output = res_mcp.get("output")
                    if output and hasattr(output, "structuredContent"):
                        structured_result = output.structuredContent
                tool_result_str = json.dumps(structured_result, default=str)
                
                # Append Tool Execution to History
                await self.append_history(user_id, {
                    "role": "tool",
                    "name": selected_tool,
                    "args": tool_args
                }, session_id)
                await self._send_status(request_id, "TOOL_EXECUTED")
                
            except Exception as e:
                tool_result_str = f"Error: {str(e)}"
                await self._send_status(request_id, "TOOL_ERROR", {"error": str(e)})

        return tool_result_str, tool_args, structured_result

    async def _step_summarize(self, request_id: str, user_id: str, query: str, history: List[Dict], session_summary: Any, tool_result_str: Optional[str], tool_args: Any, structured_result: Any, session_id: Optional[str] = None, tool_required: bool = False):
        """Step 3: Generate final answer."""
        default_prompt = get_default_system_prompt()
        if session_summary.important_points:
             default_prompt += f"\n\nImportant Points: {session_summary.important_points}\n User Details: {session_summary.user_details}\n"

        llm_req = LLMRequest(
            request_id=request_id,
            step="summarize",
            message=query,
            system_prompt=default_prompt,
            conversation_history=history,
            tool_result=tool_result_str,
            response_topic=settings.KAFKA_RESPONSE_TOPIC,
            metadata={"user_id": user_id}
        )
        await self._dispatch_llm_request(llm_req)
        await self._send_status(request_id, "LLM_SUMMARIZING")

        resp = await self._wait_for_llm(request_id)
        logger.info(f"Step 3 result: Summarize {resp}")
        if resp and resp.get("final_answer"):
            await self._complete_request(user_id, request_id, resp.get("final_answer"), structured_result, tool_args, session_id, query, tool_required)
        else:
            await self._send_status(request_id, "NO_SUMMARY")
            await self._handle_error_response(request_id, user_id, session_id, query, "No Summary Generated")

    async def _complete_request(self, user_id: str, request_id: str, answer: str, structured, tool_args=None, session_id: Optional[str] = None, query: str = None, tool_required: bool = False, error: Optional[str] = None):
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
            "error": error,
            "metadata": {"user_id": user_id},
            "timestamp": time.time()
        }
        asyncio.create_task(mongo_service.save_chat_log(user_id, log_data))
        
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
            New Tool Args: {tool_args}
            """
            
            # 3. Call LLM (using the same Kafka/Response flow is hard because it's async background)
            # Easier: Just fire a one-off request if we have a direct client, BUT we only have Kafka Loop.
            # We must spawn a new RequestID for this "internal" maintenance task.
            
            update_req_id = f"SUMMARY-{generate_random_id(user_id)}"
            
            llm_req = LLMRequest(
               request_id=update_req_id,
               step="custom",
               system_prompt=prompt,
               message=input_ctx,
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

                # Check for Session Update Response
                if rid and rid.startswith("SUMMARY-") and data.get("custom_response"):
                    session_id = data.get("metadata", {}).get("session_id")
                    await self._handle_summary_update(data.get("custom_response"), session_id)

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
        key = f"chat_history:{user_id}"
        if session_id:
             key = f"{key}:{session_id}"
        await redis_service.client.delete(key)

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
            # logger.info(f"Updated Session Summary for {uid}")

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

orchestrator_service = OrchestratorService()