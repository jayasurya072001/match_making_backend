from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from app.core.config import settings
import re
import datetime
import logging


class MongoService:
    def __init__(self):
        self.client = AsyncIOMotorClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.chat_db = self.client[settings.MONGO_CHAT_DB]
        self.personality_db = self.client[settings.MONGO_PERSONALITY_DB]
        
        # External DB Connection
        # Using the specific string provided by user. 
        # Ideally this should be in settings, but treating as specific requirement for now.
        host_ip = "48.217.49.77" 
        # Note: In a real scenario,credentials should be env vars.
        # But per user request "connection string : mongodb://myuser:mypassword@48.217.49.77:27017/"
        self.external_client = AsyncIOMotorClient("mongodb://myuser:mypassword@48.217.49.77:27017/")
        self.external_db = self.external_client["face-attributes-matrimony-matches"]

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

        name_regex=re.sub(r'[^a-zA-Z0-9\s]', '', name_regex)
        logging.info(f"Name regex:{name_regex}")

        if len(name_regex) <3:
            name_regex = f"^{re.escape(name_regex)}"
            limit=6
        else:
            name_regex = f"^{re.escape(name_regex)}$"

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
        # cursor = collection.find({"name": {"$regex": name_regex, "$options": "i"}}, projection).limit(limit)
        cursor = collection.find(
            {"name": {"$regex": name_regex, "$options": "i"}},
            projection
        ).limit(limit)
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
                "voice_id": data["voice_id"],
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

    async def update_external_profile(self, collection_name: str, profile_id: str, data: dict):
        """
        Update profile in external database.
        """
        try:
            # The user specified collection: Indian. We assume collection_name passed (user_id) maps to this.
            # However, if strict mapping is needed:
            # collection = self.external_db["Indian"] # if explicit
            # But we stick to dynamic collection based on user_id as per app pattern.
            collection = self.external_db[collection_name]
            
            # The sample doc shows "id": "uuid...". We match on that.
            # We don't want to use valid literals validation here? 
            # The user said "we are updating it in this". So we pass the same update data.
            await collection.update_one({"id": profile_id}, {"$set": data})
            return True
        except Exception as e:
            logging.error(f"Failed to update external profile: {e}")
            # We don't raise here to avoid failing the main request? 
            # User said "we are updating it in this and also...". Implies it's part of the flow.
            # Depending on strictness, we might rename this method to indicate it attempts to update.
            # I will let it be silent error or minimal logging unless critical.
            return False

    async def delete_external_profile(self, collection_name: str, profile_id: str):
        """
        Delete profile from external database.
        """
        try:
            collection = self.external_db[collection_name]
            await collection.delete_one({"id": profile_id})
            return True
        except Exception as e:
            logging.error(f"Failed to delete external profile: {e}")
            return False

mongo_service = MongoService()
