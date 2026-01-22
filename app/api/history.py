from fastapi import APIRouter, Path
from app.services.orchestrator import orchestrator_service
from app.services.redis_service import redis_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/{user_id}/all", tags=["chat history"])
async def get_all_sessions(
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Get list of all active chat sessions for the user.
    """
    return await orchestrator_service.get_all_sessions(user_id)

@router.get("/{user_id}/specific", tags=["chat history"])
async def get_chat_history(
    user_id: str = Path(..., title="The ID of the user"),
    session_id: str = None
):
    """
    Get conversation history for a specific session.
    """
    history = await orchestrator_service.get_history(user_id, session_id)
    return {"history": history}

@router.delete("/{user_id}/all", tags=["chat history"])
async def delete_all_history(
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Delete all conversation history for the user.
    """
    await orchestrator_service.delete_history(user_id, None)
    return {"status": "success", "message": "All chat history deleted"}

@router.delete("/{user_id}/specific", tags=["chat history"])
async def delete_session_history(
    user_id: str = Path(..., title="The ID of the user"),
    session_id: str = None
):
    """
    Delete conversation history for a specific session.
    """
    await orchestrator_service.delete_history(user_id, session_id)
    return {"status": "success", "message": "Session history deleted"}
