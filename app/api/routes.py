from fastapi import APIRouter
from app.api.profiles import router as profiles_router
from app.api.interaction import router as interaction_router
from app.api.history import router as history_router
from app.api.summaries import router as summaries_router
from app.api.tools import router as tools_router

router = APIRouter()

router.include_router(profiles_router, prefix="/profiles")
router.include_router(interaction_router, prefix="/chat")
router.include_router(tools_router, prefix="/tools")
router.include_router(history_router, prefix="/history")
router.include_router(summaries_router, prefix="/sessions")
