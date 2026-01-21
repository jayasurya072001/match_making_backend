from fastapi import APIRouter, Path
from app.services.orchestrator import orchestrator_service
from app.services.redis_service import redis_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/{user_id}/all", tags=["chat summary"])
async def get_all_summaries(
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Get all session summaries for the user.
    """
    return await orchestrator_service.get_all_session_summaries(user_id)

@router.get("/{user_id}/specific", tags=["chat summary"])
async def get_session_summary(
    user_id: str = Path(..., title="The ID of the user"),
    session_id: str = None
):
    """
    Get the session summary for a specific session.
    """
    return await redis_service.get_session_summary(user_id, session_id)

@router.delete("/{user_id}/all", tags=["chat summary"])
async def delete_all_summaries(
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Delete all session summaries for the user.
    """
    await redis_service.delete_all_session_summaries(user_id)
    return {"status": "success", "message": "All session summaries deleted"}

@router.delete("/{user_id}/specific", tags=["chat summary"])
async def delete_session_summary(
    user_id: str = Path(..., title="The ID of the user"),
    session_id: str = None
):
    """
    Delete the session summary for a specific session.
    """
    await redis_service.delete_session_summary(user_id, session_id)
    return {"status": "success", "message": "Session summary deleted"}
