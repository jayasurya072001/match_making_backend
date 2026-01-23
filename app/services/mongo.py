from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from app.core.config import settings

import datetime


class MongoService:
    def __init__(self):
        self.client = AsyncIOMotorClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.chat_db = self.client[settings.MONGO_CHAT_DB]
        self.personality_db = self.client[settings.MONGO_PERSONALITY_DB]

    async def check_connection(self):
        try:
            await self.client.admin.command('ping')
            return True
        except Exception:
            return False

    async def save_profile(self, user_id: str, data: dict):
        """
        Save user profile to a collection named after the user_id.
        """
        collection = self.db[user_id]
        # We might want to upsert based on the profile ID or just insert
        if data["id"]:
            await collection.update_one(
                {"_id": data["id"]}, 
                {"$set": data}, 
                upsert=True
            )
        else:
            await collection.insert_one(data)

    async def get_profile(self, user_id: str, profile_id: str, projection: dict = None):
        collection = self.db[user_id]
        return await collection.find_one({"id": profile_id}, projection)

    async def list_profiles(self, user_id: str, skip: int = 0, limit: int = 20, projection: dict = None):
        collection = self.db[user_id]
        cursor = collection.find({}, projection).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_profiles(self, user_id: str):
        collection = self.db[user_id]
        return await collection.count_documents({})

    async def delete_profile(self, user_id: str, profile_id: str):
        collection = self.db[user_id]
        result = await collection.delete_one({"id": profile_id})
        return result.deleted_count > 0

    async def delete_all(self, user_id: str):
        collection = self.db[user_id]
        await collection.drop()
        return True

    async def update_profile(self, user_id: str, profile_id: str, data: dict):
        collection = self.db[user_id]
        await collection.update_one({"id": profile_id}, {"$set": data})
        return True

    async def save_chat_log(self, user_id: str, data: dict):
        collection = self.chat_db[user_id]
        if data.get("request_id"):
            data["_id"] = data["request_id"]
            await collection.update_one(
                {"request_id": data["request_id"]},
                {"$set": data},
                upsert=True
            )
        else:
            await collection.insert_one(data)

    async def get_chat_log(self, user_id: str, request_id: str):
        collection = self.chat_db[user_id]
        return await collection.find_one({"request_id": request_id}, {"_id": 0})

    async def search_profiles_by_name(self, user_id: str, name_regex: str, limit: int = 1):
        projection = {
            "_id": 1,
            "customId": 1,
            "image_url": 1,
            "name": 1,
            "country": 1,
            "age": 1,
            "address": 1,
            "image_attributes": 1,
            "image_url": 1,
            "preferences": 1,
            "tags": 1
        }
        collection = self.db[user_id]
        cursor = collection.find({"name": {"$regex": name_regex, "$options": "i"}}, projection).limit(limit)
        return await cursor.to_list(length=limit)

    async def create_personality(self, user_id: str, persona_id: str, data: dict) -> dict:
        """
        Create a new personality for a user.
        """
        try:
            collection = self.personality_db[user_id]
            document = {
                "_id": persona_id,
                "user_id": user_id,
                "persona_id": persona_id,
                "personality": data,
                "created_at": datetime.datetime.utcnow(),
                "updated_at": datetime.datetime.utcnow()
            }
            await collection.insert_one(document)
            return document
        except DuplicateKeyError:
            raise ValueError("Personality already exists for this user")

    async def get_personality(self, user_id: str, persona_id: str):
        collection = self.personality_db[user_id]
        return await collection.find_one({"persona_id": persona_id}, {"_id": 0})

    async def update_personality(self, user_id: str, persona_id: str, data: dict):
        collection = self.personality_db[user_id]
        #updated_at should be updated
        data = data.model_dump()
        data["updated_at"] = datetime.datetime.utcnow()
        data["user_id"] = user_id
        data["persona_id"] = persona_id
        await collection.update_one({"persona_id": persona_id}, {"$set": data})
        return True

    async def delete_personality(self, user_id: str, persona_id: str):
        collection = self.personality_db[user_id]
        await collection.delete_one({"persona_id": persona_id})
        return True

    async def list_personality(self, user_id: str):
        collection = self.personality_db[user_id]
        cursor = collection.find({}, {"_id": 0})
        return await cursor.to_list(length=10)

    async def delete_all_personality(self, user_id: str):
        collection = self.personality_db[user_id]
        await collection.drop()
        return True

mongo_service = MongoService()
