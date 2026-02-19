from app.services.personality_service import personality_service
from app.api.schemas import PersonalityModel

class CachePersona:
    def __init__(self):
        self.cache = {}
    
    async def get_persona(self, user_id, personality_id):
        cache_key = f"{user_id}:{personality_id}"  # composite key

        if cache_key not in self.cache:
            data = await personality_service.get(user_id, personality_id)

            if not data:
                raise ValueError("Personality not found")

            self.cache[cache_key] = PersonalityModel(**data).model_dump()

        return self.cache[cache_key]
    
    async def update_persona(self, user_id, personality_id):
        cache_key = f"{user_id}:{personality_id}"

        data = await personality_service.get(user_id, personality_id)

        if not data:
            raise ValueError("Personality not found")

        self.cache[cache_key] = PersonalityModel(**data).model_dump()

        return self.cache[cache_key]

    async def delete_persona(self, user_id, personality_id):
        cache_key = f"{user_id}:{personality_id}"
        self.cache.pop(cache_key, None)  
    

cache_persona = CachePersona()