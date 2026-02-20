from fastapi import APIRouter, HTTPException, Query
from app.api.schemas import LoginRequest, MatchmakingProfileRequest
from app.services.mongo import mongo_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth-profiles"])

@router.post("/match_making_profiles")
async def save_matchmaking_profile(
    user_id: str = Query(..., description="The user ID to save the profile under"),
    profile_data: MatchmakingProfileRequest = None
):
    """
    Save a dynamic matchmaking profile into a user-specific collection.
    Generates a random ID for the profile.
    """
    try:
        if not profile_data:
            raise HTTPException(status_code=400, detail="Profile data is required")
            
        random_id = await mongo_service.save_matchmaking_profile(user_id, profile_data.data)
        return {
            "status": "success",
            "profile_id": random_id,
            "user_id": user_id
        }
    except Exception as e:
        logger.error(f"Error saving matchmaking profile for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login")
async def login(
    email: str = Query(..., description="User email"),
    password: str = Query(..., description="User password"),
    user_id: str = Query(..., description="Target User ID")
):
    """
    Login API to authenticate users against hardcoded or database credentials.
    """
    logging.info(f"Reciever {email} {password} {user_id}")
    try:
        user_details = await mongo_service.verify_user_login(user_id, email, password)
        
        if not user_details:
            raise HTTPException(status_code=404, detail="User not found or invalid credentials")
            
        return user_details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login for {email}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
