from fastapi import APIRouter, HTTPException
from typing import List
from app.api.schemas import UIFieldSchema, UIFieldUpdateSchema
from app.services.mongo import mongo_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui_schemas", tags=["ui-schemas"])

@router.get("/{user_id}", response_model=List[UIFieldSchema])
async def get_ui_schemas(user_id: str):
    """
    Get all dynamic UI fields defined for a specific user.
    """
    try:
        schemas = await mongo_service.get_ui_schemas(user_id)
        return schemas
    except Exception as e:
        logger.error(f"Error fetching UI schemas for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{user_id}")
async def create_ui_field(user_id: str, field: UIFieldSchema):
    """
    Create or fully update a UI field for a user.
    """
    if field.user_id != user_id:
        raise HTTPException(status_code=400, detail="User ID mismatch")
    
    try:
        await mongo_service.upsert_ui_field(user_id, field.model_dump())
        return {"status": "success", "user_id": user_id, "field_id": field.id}
    except Exception as e:
        logger.error(f"Error creating UI field for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{user_id}/{field_id}")
async def update_ui_field(user_id: str, field_id: str, update_data: UIFieldUpdateSchema):
    """
    Partially update an existing UI field.
    """
    try:
        # First check if exists
        existing = await mongo_service.get_ui_schemas(user_id)
        field_to_update = next((f for f in existing if f.get("id") == field_id), None)
        
        if not field_to_update:
            raise HTTPException(status_code=404, detail="UI field not found")
        
        # Merge updates
        updates = update_data.model_dump(exclude_unset=True)
        field_to_update.update(updates)
        
        await mongo_service.upsert_ui_field(user_id, field_to_update)
        return {"status": "success", "user_id": user_id, "field_id": field_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating UI field {field_id} for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{user_id}/{field_id}")
async def delete_ui_field(user_id: str, field_id: str):
    """
    Delete a specific UI field.
    """
    try:
        success = await mongo_service.delete_ui_field(user_id, field_id)
        if not success:
            raise HTTPException(status_code=404, detail="UI field not found")
        return {"status": "success", "message": "Field deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting UI field {field_id} for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{user_id}/bulk")
async def bulk_create_ui_fields(user_id: str, fields: List[UIFieldSchema]):
    """
    Bulk create or update multiple UI fields for a user.
    """
    try:
        # Validate all fields belong to the user
        for field in fields:
            if field.user_id != user_id:
                raise HTTPException(status_code=400, detail=f"User ID mismatch in field {field.id}")
        
        field_dicts = [f.model_dump() for f in fields]
        await mongo_service.bulk_upsert_ui_fields(user_id, field_dicts)
        return {"status": "success", "count": len(fields)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk creating UI fields for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{user_id}/bulk")
async def bulk_delete_ui_fields(user_id: str, field_ids: List[str]):
    """
    Bulk delete specific UI fields for a user.
    """
    try:
        count = await mongo_service.bulk_delete_ui_fields(user_id, field_ids)
        return {"status": "success", "deleted_count": count}
    except Exception as e:
        logger.error(f"Error in bulk deleting UI fields for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{user_id}/clear")
async def clear_all_ui_fields(user_id: str):
    """
    Delete all dynamic UI fields for a user.
    """
    try:
        count = await mongo_service.clear_all_ui_schemas(user_id)
        return {"status": "success", "cleared_count": count}
    except Exception as e:
        logger.error(f"Error clearing UI fields for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
