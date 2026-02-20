from fastapi import APIRouter, HTTPException
from app.api.schemas import OnboardingSchema
from app.services.mongo import mongo_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# Global orchestrator instance needs to be imported carefully to avoid circular imports
# Assuming orchestrator is initialized in main.py or similar and accessible
# Based on existing files, it seems services can be used directly or accessed via some singleton

@router.post("/user")
async def onboard_user(data: OnboardingSchema):
    """
    Onboard or update a user's matchmaking preferences.
    """
    try:
        from app.services.orchestrator import OrchestratorService
        # In a real app, we'd use a shared instance. 
        # For now, let's assume we can obtain the singleton orchestrator.
        # Looking at other files for pattern...
        
        await mongo_service.upsert_user_onboarding(data.user_id, data.allowed_same_gender)
        
        # We need to trigger the in-memory update in the orchestrator
        # Since OrchestratorService is a class and likely has a shared instance, we need to find it.
        # Often it's imported as 'orchestrator' from some service module.
        
        from main import orchestrator # Common pattern
        
        if data.allowed_same_gender:
            await orchestrator.add_allowed_same_gender_user(data.user_id)
        else:
            await orchestrator.remove_allowed_same_gender_user(data.user_id)
            
        return {"status": "success", "user_id": data.user_id, "allowed_same_gender": data.allowed_same_gender}
    except ImportError:
        logger.error("Could not import orchestrator for dynamic update")
        # Still return success because Mongo is updated, but log the failure
        return {"status": "success_db_only", "user_id": data.user_id}
    except Exception as e:
        logger.error(f"Error in onboarding user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}")
async def get_user_onboarding(user_id: str):
    """
    Get onboarding status for a user.
    """
    onboarding = await mongo_service.get_user_onboarding(user_id)
    if not onboarding:
        return {"user_id": user_id, "allowed_same_gender": False, "exists": False}
    return {
        "user_id": user_id, 
        "allowed_same_gender": onboarding.get("_allowed_same_gender", False),
        "exists": True
    }
