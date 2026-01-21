from fastapi import APIRouter, Path
from app.api.schemas import LLMRequest, StatusEvent, ChatRequestBody, SessionSummary
from app.services.kafka_service import kafka_service
from app.services.redis_service import redis_service
from app.services.mongo import mongo_service
from app.core.config import settings
from app.utils.random import generate_random_id
from sse_starlette.sse import EventSourceResponse
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

from app.services.orchestrator import orchestrator_service

@router.post("/{user_id}/chat/request", tags=["chat"])
async def chat_request(
    body: ChatRequestBody,
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Initiate a chat request via Orchestrator.
    Returns a request_id immediately and processes in background.
    """
    request_id = await orchestrator_service.handle_request(user_id, body.message, body.session_id)
    
    return {"status": "accepted", "request_id": request_id}

@router.delete("/{user_id}/chat/history", tags=["chat"])
async def delete_chat_history(
    user_id: str = Path(..., title="The ID of the user"),
    session_id: str = None
):
    """
    Delete conversation history for the user from Redis.
    """
    await orchestrator_service.delete_history(user_id, session_id)
    return {"status": "success", "message": "Chat history deleted"}

@router.get("/{user_id}/chat/sessions", tags=["chat"])
async def get_chat_sessions(
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Get list of active chat sessions for the user.
    """
    return await orchestrator_service.get_all_sessions(user_id)

@router.get("/{user_id}/chat/history", tags=["chat"])
async def get_chat_history(
    user_id: str = Path(..., title="The ID of the user"),
    session_id: str = None
):
    """
    Get conversation history for the user from Redis.
    """
    history = await orchestrator_service.get_history(user_id, session_id)
    return {"history": history}


@router.get("/{user_id}/session/summary", tags=["chat"])
async def get_session_summary(
    user_id: str = Path(..., title="The ID of the user"),
    session_id: str = None
):
    """
    Get the current session summary (memory) for the user.
    """
    summary = await redis_service.get_session_summary(user_id, session_id)
    return summary

@router.get("/{user_id}/session/summaries", tags=["chat"])
async def get_all_session_summaries(
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Get all session summaries for the user.
    """
    return await orchestrator_service.get_all_session_summaries(user_id)

@router.delete("/{user_id}/session/summary", tags=["chat"])
async def delete_session_summary(
    user_id: str = Path(..., title="The ID of the user"),
    session_id: str = None
):
    """
    Clear the session summary for the user.
    """
    await redis_service.delete_session_summary(user_id, session_id)
    return {"status": "success", "message": "Session summary deleted"}

@router.get("/{user_id}/session/tool_state", tags=["chat"])
async def get_tool_state(
    user_id: str = Path(..., title="The ID of the user"),
    session_id: str = None
):
    """
    Get the current tool state (arguments) for the user.
    """
    state = await redis_service.get_tool_state(user_id, session_id)
    return {"session_id": session_id, "tool_args": state}

@router.get("/{user_id}/session/tool_states", tags=["chat"])
async def get_all_tool_states(
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Get all tool states for the user across sessions.
    """
    return await redis_service.get_all_tool_states(user_id)

@router.get("/{user_id}/chat/status/{request_id}", tags=["chat"])
async def chat_status(
    request_id: str,
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Stream chat status and responses via SSE.
    """
    async def event_generator():
        # Consume from Redis channel
        async for msg in redis_service.listen(f"chat_status:{request_id}"):
            # If msg mimics LLMResponse
            # If msg mimics LLMResponse
            if "step" in msg:
                # It's an LLM Response / Update - yield it but DO NOT process as final answer
                yield {
                    "event": "message",
                    "data": json.dumps(msg)
                }
            else:
                # It's likely a StatusEvent or the authoritative final answer
                yield {
                    "event": "status", # calling it status, but client handles "final_answer" logic too
                    "data": json.dumps(msg)
                }
                
                # Check for completion only on authoritative messages (no step, or source=orchestrator)
                if msg.get("final_answer") or msg.get("error"):
                    break

    return EventSourceResponse(event_generator())


@router.get("/{user_id}/chat/request/{request_id}", tags=["chat"])
async def get_chat_request_status(
    request_id: str,
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Get the status and details of a specific chat request.
    """
    log = await mongo_service.get_chat_log(user_id, request_id)
    
    if not log:
        return {
            "status": "pending",
            "complete": False
        }
    
    return log

