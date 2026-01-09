from fastapi import APIRouter
from app.api.profiles import router as profiles_router
from app.api.chat import router as chat_router

router = APIRouter()

router.include_router(profiles_router)
router.include_router(chat_router)
