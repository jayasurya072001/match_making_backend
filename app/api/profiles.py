from fastapi import APIRouter, HTTPException, Path
from app.api.schemas import UserProfile, SearchRequest
from app.services.mongo import mongo_service
from app.services.redis_service import redis_service
from app.services.embedding import embedding_service
from app.utils.random import generate_random_id
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{user_id}/save", tags=["profile store"])
async def save_profile(
    profile: UserProfile, 
    user_id: str = Path(..., title="The ID of the user owning this data")
):
    """
    Save user profile data.
    """
    try:
        logger.info(f"Saving profile for user: {user_id}, profile_id: {profile.id}")
        
        # 1. Generate Embedding
        if profile.image_url:
            embedding = await embedding_service.get_embedding(profile.image_url)
            profile.embeddings = embedding
        else:
             logger.error("No image_url provided")
             raise HTTPException(status_code=400, detail="Image URL is required for embedding generation")
        
        profile_id = generate_random_id(user_id)
        profile.id = profile_id

        # 2. Save to Mongo
        await mongo_service.save_profile(user_id, profile.model_dump())

        # 3. Save/Index in Redis
        await redis_service.save_profile(user_id, profile.model_dump(mode='json'), profile.embeddings)

        logger.info(f"Successfully saved profile {profile.id} for user {user_id}")
        return {"status": "success", "id": profile.id, "message": "Profile saved and indexed."}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error saving profile for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.post("/{user_id}/search", tags=["profile search"])
async def search_profiles(
    request: SearchRequest,
    user_id: str = Path(..., title="The ID of the user to search within")
):
    """
    Search profiles.
    """
    try:
        query_vector = None
        if request.image_url:
             query_vector = await embedding_service.get_embedding(request.image_url)

        logger.info("filters received")
        logger.info(request)
        
        results = await redis_service.search(
            user_id=user_id,
            query_vector=query_vector,
            filters=request.filters,
            geo_filter=request.geo_filter.model_dump() if request.geo_filter else None,
            k=request.k,
            page=request.page
        )
        
        count = results.total
        docs = results.docs
        
        results_list = []
        projection = {
            "_id": 1,
            "customId": 1,
            "image_url": 1,
            "name": 1,
            "gender": 1,
            "tags": 1,
            "address": 1,
            "age": 1
        }
        
        for doc in docs:
            # fetch full profile from mongo
            # trim id from redis
            id = doc.id.split(":")[-1]
            profile = await mongo_service.get_profile(user_id, id, projection)
            if profile:
                results_list.append(profile)
        
        return {"count": results.total, "docs": results_list}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/search_by_name", tags=["profile search"])
async def search_profiles_by_name(
    name: str,
    limit: int = 1,
    user_id: str = Path(..., title="The ID of the user")
):
    """
    Search profiles by name (regex).
    """
    try:
        profiles = await mongo_service.search_profiles_by_name(user_id, name, limit)
        return {
            "status": "success",
            "count": len(profiles),
            "docs": profiles,
            "query": name
        }
    except Exception as e:
        logger.exception(f"Error searching profiles by name for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/profile/{profile_id}", tags=["profile"])
async def get_profile(
    profile_id: str,
    user_id: str = Path(..., title="The ID of the user")
):
    """
    Get profile by ID from Mongo and Redis.
    """
    try:
        projection = {
            "_id": 1,
            "customId": 1,
            "image_url": 1,
            "name": 1
        }
        mongo_doc = await mongo_service.get_profile(user_id, profile_id, projection)
        redis_doc = await redis_service.get_doc(user_id, profile_id)
        
        if not mongo_doc:
            raise HTTPException(status_code=404, detail="Profile not found in MongoDB")
            
        return {
            "status": "found",
            "mongo_data": mongo_doc,
            "redis_data": redis_doc
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/profiles", tags=["profile"])
async def list_profiles(
    user_id: str = Path(..., title="The ID of the user"),
    skip: int = 0,
    limit: int = 20
):
    """
    List profiles from MongoDB with pagination.
    """
    try:
        projection = {
            "_id": 1,
            "customId": 1,
            "image_url": 1,
            "name": 1
        }
        profiles = await mongo_service.list_profiles(user_id, skip, limit, projection)
        count = await mongo_service.count_profiles(user_id)
        return {
            "total": count,
            "skip": skip,
            "limit": limit,
            "data": profiles
        }
    except Exception as e:
        logger.exception(f"Error listing profiles for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{user_id}/profile/{profile_id}", tags=["profile"])
async def delete_profile(
    profile_id: str,
    user_id: str = Path(..., title="The ID of the user")
):
    """
    Delete profile from Mongo and Redis.
    """
    try:
        # Delete from Mongo
        mongo_deleted = await mongo_service.delete_profile(user_id, profile_id)
        
        # Delete from Redis
        redis_deleted = await redis_service.delete_doc(user_id, profile_id)
        
        if not mongo_deleted:
            raise HTTPException(status_code=404, detail="Profile not found in mongo")
        
        if not redis_deleted:
            raise HTTPException(status_code=404, detail="Profile not found in redis")
        
        return {"status": "deleted", "id": profile_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{user_id}/all", tags=["profile"])
async def delete_all_profiles(
    user_id: str = Path(..., title="The ID of the user")
):
    """
    Bulk delete all profiles for a user (Drop Collection and Index).
    """
    try:
        await mongo_service.delete_all(user_id)
        await redis_service.delete_index(user_id)
        return {"status": "deleted_all", "message": f"All data for user {user_id} deleted."}
    except Exception as e:
        logger.exception(f"Error deleting all profiles for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{user_id}/profile/{profile_id}", tags=["profile"])
async def update_profile(
    profile_id: str,
    update_data: dict,
    user_id: str = Path(..., title="The ID of the user")
):
    """
    Update profile fields.
    """
    try:
        # Check existence
        existing = await mongo_service.get_profile(user_id, profile_id)
        if not existing:
             raise HTTPException(status_code=404, detail="Profile not found")
        
        await mongo_service.update_profile(user_id, profile_id, update_data)
        
        if "image_url" in update_data:
             # Logic to regen embedding
             new_embedding = await embedding_service.get_embedding(update_data["image_url"])
             update_data["embeddings"] = new_embedding
             
        await redis_service.save_profile(user_id, update_data, update_data.get("embeddings", existing.get("embeddings")))
        
        return {"status": "updated", "id": profile_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/profiles/count", tags=["profile"])
async def get_profile_counts(
    user_id: str = Path(..., title="The ID of the user")
):
    """
    Get the count of profiles in Mongo and Redis for the user.
    """
    try:
        mongo_count = await mongo_service.count_profiles(user_id)
        redis_count = await redis_service.count_user_profiles(user_id)
        
        return {
            "status": "success",
            "mongo_count": mongo_count,
            "redis_count": redis_count
        }
    except Exception as e:
        logger.exception(f"Error getting profile counts for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
