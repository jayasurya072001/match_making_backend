from app.services.personality_service import personality_service
from app.api.schemas import PersonalityModel

class CachePersona:
    def __init__(self):
        self.cache = {}
    
    async def get_persona(self, user_id, personality_id):
        if user_id not in self.cache:
            data = await personality_service.get(user_id, personality_id)

            if not data:
                raise ValueError("Personality not found")

            self.cache[user_id] = PersonalityModel(**data).model_dump()
        return self.cache[user_id]
    
    async def update_persona(self, user_id, personality_id):
        if user_id in self.cache:
            data = await personality_service.get(user_id, personality_id)

            if not data:
                raise ValueError("Personality not found")

            self.cache[user_id] = PersonalityModel(**data).model_dump()
    

cache_persona = CachePersona()