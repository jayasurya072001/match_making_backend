from fastapi import APIRouter
from app.services.personality_service import personality_service
from app.api.schemas import PersonalityModel
from app.utils.cache_persona import cache_persona
from fastapi import HTTPException

router = APIRouter()

@router.post("/{user_id}", tags=["Personality"])
async def create_personality(user_id: str, payload: PersonalityModel):
    try:
        data = await personality_service.create(
            user_id, payload.persona_id, payload.personality
        )
        return {"status": "success", "data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{user_id}/{persona_id}", tags=["Personality"])
async def get_personality(user_id: str, persona_id: str):
    data = await personality_service.get(user_id, persona_id)
    if not data:
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"status": "success", "data": data}


@router.get("/{user_id}", tags=["Personality"])
async def list_personalities(user_id: str):
    return {"status": "success", "data": await personality_service.list(user_id)}


@router.put("/{user_id}/{persona_id}", tags=["Personality"])
async def update_personality(
    user_id: str,
    persona_id: str,
    payload: PersonalityModel
):
    try:
        data = await personality_service.update(user_id, persona_id, payload)
        if data:
            await cache_persona.update_persona(user_id, persona_id)
        return {"status": "success", "data": data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{user_id}/{persona_id}", status_code=204, tags=["Personality"])
async def delete_personality(
    user_id: str,
    persona_id: str,
):
    try:
        await personality_service.delete(user_id, persona_id)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) 


@router.get("/{user_id}/{persona_id}/cache", tags=["Personality"])
async def cache_personality(
    user_id: str,
    persona_id: str,
):
    try:
        data = await cache_persona.get_persona(user_id, persona_id)
        return {"status": "success", "data": data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) 

