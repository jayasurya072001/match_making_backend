from app.services.mongo import mongo_service
from app.api.schemas import PersonalityModel

class PersonalityService:
    def __init__(self):
        self.mongo_service = mongo_service

    def create(self, user_id: str, persona_id: str, data: dict) -> PersonalityModel:
        return self.mongo_service.create_personality(user_id, persona_id, data)

    def get(self, user_id: str, persona_id: str) -> PersonalityModel:
        return self.mongo_service.get_personality(user_id, persona_id)

    def update(self, user_id: str, persona_id: str, data: dict) -> PersonalityModel:
        return self.mongo_service.update_personality(user_id, persona_id, data)

    def delete(self, user_id: str, persona_id: str) -> bool:
        return self.mongo_service.delete_personality(user_id, persona_id)

    def list(self, user_id: str) -> list[PersonalityModel]:
        return self.mongo_service.list_personality(user_id)

    def delete_all(self, user_id: str) -> bool:
        return self.mongo_service.delete_all_personality(user_id)

personality_service = PersonalityService()