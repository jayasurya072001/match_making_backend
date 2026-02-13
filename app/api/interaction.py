from fastapi import APIRouter, Path
from app.api.schemas import ChatRequestBody
from app.services.redis_service import redis_service
from app.services.mongo import mongo_service
from app.services.orchestrator import orchestrator_service
from sse_starlette.sse import EventSourceResponse
from app.services.prompts import get_filler_prompt
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()

from app.services.azure_openai_service import call_openai

@router.post("/{user_id}/request", tags=["chat interaction"])
async def chat_request(
    body: ChatRequestBody,
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Initiate a chat request via Orchestrator.
    """
    request_id = await orchestrator_service.handle_request(user_id, body.message, body.session_id, body.person_id, body.personality_id, body.session_type, body.recommendation_ids)
    
    response = {"status": "accepted", "request_id": request_id}
    
    if body.fillers:
        history = await orchestrator_service.get_history(user_id, body.session_id)
        session_summary = await redis_service.get_session_summary(user_id, body.session_id)
        
        summary_text = session_summary.model_dump_json() if session_summary else "No summary available."
        
        prompt = get_filler_prompt(history, body.message, summary_text)
        
        try:
            filler_msg = await asyncio.to_thread(call_openai, prompt)
            if filler_msg:
                response["filler"] = filler_msg
                logger.info(f"Generated filler: {filler_msg}")
        except Exception as e:
            logger.error(f"Failed to generate filler: {e}")
            
    return response

@router.get("/status/{request_id}", tags=["chat interaction"])
async def chat_status(
    request_id: str,
):
    """
    Stream chat status and responses via SSE.
    """
    async def event_generator():
        async for msg in redis_service.listen(f"chat_status:{request_id}"):
            if "step" in msg:
                yield {
                    "event": "message",
                    "data": json.dumps(msg)
                }
            else:
                yield {
                    "event": "status",
                    "data": json.dumps(msg)
                }
                if msg.get("final_answer") or msg.get("error"):
                    break

    return EventSourceResponse(event_generator())

@router.get("/{user_id}/request/{request_id}", tags=["chat interaction"])
async def get_chat_request_logs(
    request_id: str,
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Get the logs and details of a specific chat request from MongoDB.
    """
    log = await mongo_service.get_chat_log(user_id, request_id)
    if not log:
        return {"status": "pending", "complete": False}
    return log
