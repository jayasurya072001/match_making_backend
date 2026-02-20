from fastapi import APIRouter
from app.api.profiles import router as profiles_router
from app.api.interaction import router as interaction_router
from app.api.history import router as history_router
from app.api.summaries import router as summaries_router
from app.api.tools import router as tools_router
from app.api.personality import router as personality_router
from app.api.onboarding import router as onboarding_router
from app.api.ui_schemas import router as ui_schemas_router
from app.api.auth_profiles import router as auth_profiles_router

router = APIRouter()

router.include_router(profiles_router, prefix="/profiles")
router.include_router(interaction_router, prefix="/chat")
router.include_router(tools_router, prefix="/tools")
router.include_router(history_router, prefix="/history")
router.include_router(summaries_router, prefix="/sessions")
router.include_router(personality_router, prefix="/personality")
router.include_router(onboarding_router)
router.include_router(ui_schemas_router)
router.include_router(auth_profiles_router)

