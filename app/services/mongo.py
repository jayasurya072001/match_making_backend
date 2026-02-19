from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from pymongo import UpdateOne
from app.core.config import settings
import re
import datetime
import logging


class MongoService:
    def __init__(self):
        self.client = AsyncIOMotorClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.accounts_db = self.client[settings.MONGO_ACCOUNTS_DB]
        self.personality_db = self.client[settings.MONGO_PERSONALITY_DB]
        self.matchmaking_profiles_db = self.client[settings.MONGO_MATCHMAKING_PROFILES_DB]

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

    async def get_user_profile(self, user_id: str, profile_id: str, projection: dict = None):
        collection = self.matchmaking_profiles_db[user_id]
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

    async def get_all_whitelisted_users(self) -> list:
        """Fetch all users who are allowed same-gender matches."""
        collection = self.accounts_db["onboarding"]
        cursor = collection.find({"_allowed_same_gender": True}, {"user_id": 1})
        users = await cursor.to_list(length=None)
        return [u["user_id"] for u in users if "user_id" in u]

    async def upsert_user_onboarding(self, user_id: str, allowed_same_gender: bool):
        """Save or update user onboarding settings."""
        collection = self.accounts_db["onboarding"]
        await collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "_allowed_same_gender": allowed_same_gender,
                "updated_at": datetime.datetime.utcnow()
            }},
            upsert=True
        )
        return True

    async def get_user_onboarding(self, user_id: str):
        """Get onboarding settings for a user."""
        collection = self.accounts_db["onboarding"]
        return await collection.find_one({"user_id": user_id})

    # --- UI Schema Methods ---
    async def get_ui_schemas(self, user_id: str) -> list:
        """Fetch all UI fields for a specific user."""
        collection = self.accounts_db["ui_schemas"]
        cursor = collection.find({"user_id": user_id}, {"_id": 0})
        return await cursor.to_list(length=None)

    async def upsert_ui_field(self, user_id: str, field_data: dict):
        """Create or update a single UI field for a user."""
        collection = self.accounts_db["ui_schemas"]
        field_id = field_data.get("id")
        await collection.update_one(
            {"user_id": user_id, "id": field_id},
            {"$set": {**field_data, "user_id": user_id, "updated_at": datetime.datetime.utcnow()}},
            upsert=True
        )
        return True

    async def delete_ui_field(self, user_id: str, field_id: str):
        """Delete a UI field for a specific user."""
        collection = self.accounts_db["ui_schemas"]
        result = await collection.delete_one({"user_id": user_id, "id": field_id})
        return result.deleted_count > 0

    # --- Matchmaking Profile Methods ---
    async def save_matchmaking_profile(self, user_id: str, data: dict):
        """Save a dynamic matchmaking profile with a random ID."""
        import uuid
        random_id = str(uuid.uuid4())
        data["_id"] = random_id
        data["profile_id"] = random_id # Also keep as a field for ease
        data["created_at"] = datetime.datetime.utcnow()
        
        collection = self.matchmaking_profiles_db[user_id]
        await collection.insert_one(data)
        return random_id

    async def verify_user_login(self, user_id: str, email: str, password: str):
        """Verify user login against hardcoded and DB credentials."""
        # Hardcoded users
        hardcoded_users = {
            "admin": {"password": "admin@123", "name": "Admin User", "location": "Headquarters"},
            "test": {"password": "test@123", "name": "Test User", "location": "Test Lab"}
        }

        if email in hardcoded_users and hardcoded_users[email]["password"] == password:
            return {
                "user_id": user_id, 
                "name": hardcoded_users[email]["name"], 
                "location": hardcoded_users[email]["location"]
            }

        # Check DB
        collection = self.accounts_db["users"]
        user = await collection.find_one({
            "email": email, 
            "password": password,
            "user_id": user_id
        })

        if user:
            return {
                "user_id": user_id,
                "name": user.get("name", "Unknown"),
                "location": user.get("location", "Unknown")
            }
        
        return None

    async def bulk_upsert_ui_fields(self, user_id: str, fields_list: list):
        """Bulk upsert multiple UI fields for a user."""
        collection = self.accounts_db["ui_schemas"]
        operations = []
        for field in fields_list:
            field_id = field.get("id")
            operations.append(
                UpdateOne(
                    {"user_id": user_id, "id": field_id},
                    {"$set": {**field, "user_id": user_id, "updated_at": datetime.datetime.utcnow()}},
                    upsert=True
                )
            )
        if operations:
            await collection.bulk_write(operations)
        return True

    async def bulk_delete_ui_fields(self, user_id: str, field_ids: list):
        """Delete multiple UI fields for a user."""
        collection = self.accounts_db["ui_schemas"]
        result = await collection.delete_many({"user_id": user_id, "id": {"$in": field_ids}})
        return result.deleted_count

    async def clear_all_ui_schemas(self, user_id: str):
        """Delete all UI fields for a specific user."""
        collection = self.accounts_db["ui_schemas"]
        result = await collection.delete_many({"user_id": user_id})
        return result.deleted_count

mongo_service = MongoService()
