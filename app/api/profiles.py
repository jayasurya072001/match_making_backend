from fastapi import APIRouter, HTTPException, Path
from datetime import datetime
from app.api.schemas import UserProfile, SearchRequest, UpdateProfileSchema
from app.services.mongo import mongo_service
from app.services.redis_service import redis_service
from app.services.embedding import embedding_service
from app.utils.random_utils import generate_random_id
import logging

logger = logging.getLogger(__name__)

# Mapping from flat field name to MongoDB dot-notation path
FIELD_MAPPING = {
    "gender": ["gender", "image_attributes.gender"], 
    "ethnicity": "image_attributes.ethnicity",
    "hair_color": "image_attributes.hair.hair_color",
    "eye_color": "image_attributes.eye_color",
    "face_shape": "image_attributes.face_shape",
    "head_hair": "image_attributes.head_hair",
    "beard": "image_attributes.beard",
    "mustache": "image_attributes.mustache",
    "hair_style": "image_attributes.hair.hair_style",
    "eyewear": "image_attributes.accessories.eyewear",
    "headwear": "image_attributes.accessories.headwear",
    "eyebrow": "image_attributes.facial_features.Eyebrow",
    "attire": "image_attributes.attire",
    "body_shape": "image_attributes.body_shape",
    "skin_color": "image_attributes.skin_color",
    "eye_size": "image_attributes.eye_size",
    "face_size": "image_attributes.face_size",
    "face_structure": "image_attributes.face_structure",
    "hair_length": "image_attributes.hair_length",
    "caste": "image_attributes.caste"
}

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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting profile counts for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}/attributes/{profile_id}", tags=["profile update"])
async def get_profile_attributes(
    profile_id: str,
    user_id: str = Path(..., title="The ID of the user")
):
    """
    Get profile attributes formatted for UpdateProfileSchema.
    """
    try:
        # 1. Fetch from Mongo
        profile = await mongo_service.get_profile(user_id, profile_id)
        if not profile:
             raise HTTPException(status_code=404, detail="Profile not found")

        # 2. Map Mongo fields to Schema fields
        attributes = {}
        attributes["id"] = profile_id
        attributes["collection_name"] = user_id 
        
        def get_nested_value(doc, path):
            keys = path.split(".")
            val = doc
            for key in keys:
                if isinstance(val, dict):
                    val = val.get(key)
                else:
                    return None
            return val

        for field, mapping in FIELD_MAPPING.items():
            # Initialize to None to ensure all fields are present in response
            attributes[field] = None
            
            # If mapping is a list, try the first one that exists or specific priority
            # For 'gender', ["gender", "image_attributes.gender"], we prefer root 'gender' 
            # or maybe 'image_attributes.gender' if we want to be consistent with other attrs?
            # Let's try to find a non-None value.
            val = None
            if isinstance(mapping, list):
                for path in mapping:
                    val = get_nested_value(profile, path)
                    if val is not None:
                        break
            else:
                val = get_nested_value(profile, mapping)
            
            if val is not None:
                attributes[field] = val

        return {
            "status": "success",
            "data": attributes
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting profile attributes {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{user_id}/update_attributes", tags=["profile update"])
async def update_profile_attributes(
    data: UpdateProfileSchema,
    user_id: str = Path(..., title="The ID of the user (collection name)")
):
    """
    Update profile attributes with strict Literal validation and sync to Redis.
    """
    try:
        profile_id = data.id
        # Note: data.collection_name is optional in schema but user_id in path is required. 
        # We can enforce they match or just use user_id from path which is more RESTful.
        # If user passes different collection_name in body, we might want to warn or just use path variable.
        # I will use path variable 'user_id' as the collection target.
        
        # Filter out None values and map to Mongo paths
        update_doc = {}
        input_data = data.model_dump(exclude_unset=True, exclude={"id", "collection_name"})
        
        if not input_data:
             raise HTTPException(status_code=400, detail="No fields provided for update")

        for field, value in input_data.items():
            if field in FIELD_MAPPING:
                mongo_path = FIELD_MAPPING[field]
                if isinstance(mongo_path, list):
                    for path in mongo_path:
                        update_doc[path] = value
                else:
                    update_doc[mongo_path] = value

        if not update_doc:
             raise HTTPException(status_code=400, detail="No valid fields to update")

        logger.info(f"Updating profile attributes for {profile_id} in {user_id}: {update_doc}")
        
        # 1. Check existence in Mongo
        existing_mongo = await mongo_service.get_profile(user_id, profile_id)
        if not existing_mongo:
             raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found in MongoDB")

        # 2. Update Mongo
        await mongo_service.update_profile(user_id, profile_id, update_doc)
        
        # 3. Validation/Sync to Redis
        # Fetch updated document from Mongo to get the Full structure for Redis
        # logic: get full doc -> convert to string (for Redis schema compatibility if needed) -> save
        updated_mongo = await mongo_service.get_profile(user_id, profile_id)
        
        # Need to handle embeddings. If not changed, use existing.
        # redis_service.save_profile expects dict and embeddings list
        embeddings = updated_mongo.get("embeddings", [])
        
        # Redis service 'save_profile' usually expects a flat-ish dict or handles it?
        # looking at 'save_profile' usage in this file: 
        # await redis_service.save_profile(user_id, profile.model_dump(mode='json'), profile.embeddings)
        # So it expects the full profile dict.
        
        # Convert datetime objects to string for Redis serialization
        redis_profile_data = updated_mongo.copy()
        if "created_at" in redis_profile_data and isinstance(redis_profile_data["created_at"], datetime):
             redis_profile_data["created_at"] = redis_profile_data["created_at"].isoformat()
        if "updated_at" in redis_profile_data and isinstance(redis_profile_data["updated_at"], datetime):
             redis_profile_data["updated_at"] = redis_profile_data["updated_at"].isoformat()
        
        await redis_service.save_profile(user_id, redis_profile_data, embeddings)
        
        return {
            "status": "success", 
            "message": "Profile updated in Mongo and Redis", 
            "updated_fields": list(update_doc.keys())
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating profile attributes: {e}")
        raise HTTPException(status_code=500, detail=str(e))
