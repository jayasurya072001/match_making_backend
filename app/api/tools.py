from fastapi import APIRouter, Path
from app.services.redis_service import redis_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/{user_id}/all", tags=["chat tools"])
async def get_all_tool_states(
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Get all tool states for the user across sessions.
    """
    return await redis_service.get_all_tool_states(user_id)

@router.get("/{user_id}/specific", tags=["chat tools"])
async def get_tool_state(
    user_id: str = Path(..., title="The ID of the user"),
    session_id: str = None
):
    """
    Get the current tool state for a specific session.
    """
    state = await redis_service.get_tool_state(user_id, session_id)
    return {"session_id": session_id, "tool_args": state}

@router.delete("/{user_id}/all", tags=["chat tools"])
async def delete_all_tool_states(
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Delete all tool states for the user across all sessions.
    """
    await redis_service.delete_all_tool_states(user_id)
    return {"status": "success", "message": "All tool states deleted"}

@router.delete("/{user_id}/specific", tags=["chat tools"])
async def delete_tool_state(
    user_id: str = Path(..., title="The ID of the user"),
    session_id: str = None
):
    """
    Delete the tool state for a specific session.
    """
    await redis_service.delete_tool_state(user_id, session_id)
    return {"status": "success", "message": "Tool state deleted"}
