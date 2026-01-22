from fastapi import APIRouter, Path
from app.api.schemas import ChatRequestBody
from app.services.redis_service import redis_service
from app.services.mongo import mongo_service
from app.services.orchestrator import orchestrator_service
from sse_starlette.sse import EventSourceResponse
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{user_id}/request", tags=["chat interaction"])
async def chat_request(
    body: ChatRequestBody,
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Initiate a chat request via Orchestrator.
    """
    request_id = await orchestrator_service.handle_request(user_id, body.message, body.session_id, body.person_id)
    return {"status": "accepted", "request_id": request_id}

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
