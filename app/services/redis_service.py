import redis.asyncio as redis
import asyncio
from redis.commands.search.field import TagField, VectorField, GeoField, TextField, NumericField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from app.core.config import settings
from app.api.schemas import SessionSummary
import numpy as np
import json
import logging

logger = logging.getLogger(__name__)

class RedisService:
    def __init__(self):
        self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def check_connection(self):
        try:
            return await self.client.ping()
        except Exception:
            return False

    async def create_index(self, user_id: str):
        index_name = f"idx:{user_id}"
        prefix = f"doc:{user_id}:"
        
        try:
            await self.client.ft(index_name).info()
            # Index exists
        except:
            # Create index
            schema = [
                # Vector Field
                VectorField(
                    "$.embeddings",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": 512, 
                        "DISTANCE_METRIC": "COSINE"
                    },
                    as_name="embeddings"
                ),
                # Geo Location
                GeoField("$.geo_location", as_name="geo_location"),

                # Numeric Age
                NumericField("$.age", as_name="age"),
                
                # Name (Root level)
                TagField("$.name", as_name="name"),
                
                # Image Attributes - Flattened Indexing
                TagField("$.image_attributes.face_shape", as_name="face_shape"),
                TagField("$.image_attributes.head_hair", as_name="head_hair"),
                TagField("$.image_attributes.beard", as_name="beard"),
                TagField("$.image_attributes.mustache", as_name="mustache"),
                TagField("$.image_attributes.ethnicity", as_name="ethnicity"),
                TagField("$.image_attributes.emotion", as_name="emotion"),
                TagField("$.image_attributes.age_group", as_name="age_group"),
                TagField("$.image_attributes.gender", as_name="gender"),
                
                # Nested Attributes
                TagField("$.image_attributes.hair.hair_color", as_name="hair_color"),
                TagField("$.image_attributes.hair.hair_style", as_name="hair_style"),
                TagField("$.image_attributes.eye_color", as_name="eye_color"),
                TagField("$.image_attributes.face_geometry.fore_head_height", as_name="fore_head_height"),
                TagField("$.image_attributes.accessories.eyewear", as_name="eyewear"),
                TagField("$.image_attributes.accessories.headwear", as_name="headwear"),
                TagField("$.image_attributes.facial_features.Eyebrow", as_name="eyebrow"),
                TagField("$.image_attributes.facial_features.mole", as_name="mole"),
                TagField("$.image_attributes.facial_features.scars", as_name="scars"),
                TagField("$.image_attributes.accessories.earrings", as_name="earrings"),

                # New Numeric Fields
                NumericField("$.image_attributes.height", as_name="height"),
                NumericField("$.image_attributes.weight", as_name="weight"),
                NumericField("$.image_attributes.annual_income", as_name="annual_income"),
                NumericField("$.image_attributes.brothers", as_name="brothers"),
                NumericField("$.image_attributes.sisters", as_name="sisters"),

                # New Tag Fields 
                TagField("$.image_attributes.attire", as_name="attire"),
                TagField("$.image_attributes.body_shape", as_name="body_shape"),
                TagField("$.image_attributes.lip_stick", as_name="lip_stick"),
                TagField("$.image_attributes.skin_color", as_name="skin_color"),
                TagField("$.image_attributes.eye_size", as_name="eye_size"),
                TagField("$.image_attributes.face_size", as_name="face_size"),
                TagField("$.image_attributes.face_structure", as_name="face_structure"),
                TagField("$.image_attributes.hair_length", as_name="hair_length"),
                TagField("$.image_attributes.diet", as_name="diet"),
                TagField("$.image_attributes.drinking", as_name="drinking"),
                TagField("$.image_attributes.smoking", as_name="smoking"),
                TagField("$.image_attributes.family_type", as_name="family_type"),
                TagField("$.image_attributes.family_values", as_name="family_values"),
                TagField("$.image_attributes.father_occupation", as_name="father_occupation"),
                TagField("$.image_attributes.mother_occupation", as_name="mother_occupation"),
                TagField("$.image_attributes.highest_qualification", as_name="highest_qualification"),
                TagField("$.image_attributes.marital_status", as_name="marital_status"),
                TagField("$.image_attributes.mother_tongue", as_name="mother_tongue"),
                TagField("$.image_attributes.profession", as_name="profession"),
                TagField("$.image_attributes.religion", as_name="religion"),
                TagField("$.image_attributes.speaking_languages", as_name="speaking_languages")
            ]
            
            definition = IndexDefinition(prefix=[prefix], index_type=IndexType.JSON)
            await self.client.ft(index_name).create_index(schema, definition=definition)

    async def save_profile(self, user_id: str, profile_data: dict, embedding: list[float]):
        # Ensure index exists
        await self.create_index(user_id)
        
        # Prepare data for RedisJSON
        # We need to make sure the embedding is part of the JSON document
        # And geo_location is formatted correctly for Redis (lon, lat string) OR RedisJSON supports object
        # RedisJSON supports object if mapped to GeoField: "13.11,12.11" string format is common for older versions, 
        # but modern RediSearch with JSON supports GeoJSON or "lon, lat" string.
        # Let's ensure geo_location is in a compatible format for query if needed, 
        # but pure JSON object {"latitude": x, "longitude": y} might need transformation for GEO indexing if the backend expects "lon,lat".
        # Standard Redis Geo uses "lon,lat". Let's inject a "lon,lat" string field for simpler usage if standard JSON object fails,
        # but for now let's hope the mapping works or convert it.
        # Actually, for RediSearch on JSON, GeoField expects a string "lon,lat".
        
        geo = profile_data.get('geo_location', {})
        if geo:
             # Add a specific field for indexing if the object structure doesn't match auto-detection
             # But we mapped "$.geo_location" to GeoField. 
             # If `geo_location` is `{"latitude": 12, "longitude": 13}`, RediSearch JSON might not auto-parse that to GEO.
             # Safe bet: transform it to string "lon,lat" for a specific index field, or rely on client side convention.
             # Let's convert the object to a string format for safe indexing:
             profile_data['geo_location'] = f"{geo.get('longitude')},{geo.get('latitude')}"
            
        profile_data['embeddings'] = embedding
        
        key = f"doc:{user_id}:{profile_data['id']}"
        await self.client.json().set(key, "$", profile_data)

    async def search(self, user_id: str, query_vector: list[float] = None, filters: dict = None, geo_filter: dict = None, k: int = 5, page: int = 1):
        index_name = f"idx:{user_id}"
        
        # Base Query
        # If vector presnet: KNN
        # If filters present: Pre-filter
        
        query_parts = []
        
        # 1. Attribute Filters
        if filters is not None:
            for field, value in filters.items():
                if value:
                     if isinstance(value, dict) and ("min" in value or "max" in value):
                         # Numeric Range: @field:[min max]
                         min_val = value.get("min", "-inf")
                         max_val = value.get("max", "+inf")
                         query_parts.append(f"@{field}:[{min_val} {max_val}]")
                     else:
                         # Simple TAG support: @field:{value}
                         query_parts.append(f"@{field}:{{{value}}}")
        # logging.info(filters.items())
        # 2. Geo Filter
        if geo_filter:
            # Syntax: @geo_field:[lon lat radius unit]
            # unit: m, km, ft, mi
            query_parts.append(
                f"@geo_location:[{geo_filter['longitude']} {geo_filter['latitude']} {geo_filter['radius_km']} km]"
            )
        
        # Combine filters or default to *
        filter_str = " ".join(query_parts) if query_parts else "*"
        print(filter_str)
        # 2. Vector Search
        # Query: filter_str => [KNN k @embeddings $vec_blob AS score]
        
        if query_vector:
            q_str = f"({filter_str})=>[KNN {k} @embeddings $vec_blob AS score]"
            q = Query(q_str).sort_by("score").dialect(2).return_fields("id", "customId", "score", "image_url")
            
            params = {
                "vec_blob": np.array(query_vector, dtype=np.float32).tobytes()
            }

            res = await self.client.ft(index_name).search(q, query_params=params)
        else:
            page = max(1, page)
            offset = (page - 1) * k
            # Just filter search
            print("searching in else condition")
            q = Query(filter_str).paging(offset, k).return_fields("id", "customId", "score", "image_url").dialect(2)
            res = await self.client.ft(index_name).search(q)
            
        return res

    async def get_doc(self, user_id: str, doc_id: str):
        key = f"doc:{user_id}:{doc_id}"
        return await self.client.json().get(key)
        
    async def delete_doc(self, user_id: str, doc_id: str):
        key = f"doc:{user_id}:{doc_id}"
        return await self.client.delete(key)
        
    async def delete_index(self, user_id: str):
        index_name = f"idx:{user_id}"
        try:
            # Delete index and documents
            # FT.DROPINDEX index [DD]
            # DD = Delete Documents
            await self.client.ft(index_name).dropindex(delete_documents=True)
            return True
        except Exception as e:
            print(str(e))
            return False

    async def publish(self, channel: str, message: dict):
        """Publish a message to a specific Redis channel"""
        await self.client.publish(channel, json.dumps(message))

    async def save_session_summary(self, user_id: str, summary: SessionSummary, session_id: str = None):
        key = f"session_summary:{user_id}"
        print("user_id sessin summary save", user_id)
        if session_id:
            key = f"{key}:{session_id}"
        # Store as simple JSON string for simplicity, or RedisJSON
        print("key", key)
        await self.client.set(key, summary.model_dump_json())

    async def get_session_summary(self, user_id: str, session_id: str = None) -> SessionSummary:
        key = f"session_summary:{user_id}"
        if session_id:
            key = f"{key}:{session_id}"
        data = await self.client.get(key)
        if data:
            try:
                return SessionSummary.model_validate_json(data)
            except:
                pass
        return SessionSummary(user_id=user_id)

    async def delete_session_summary(self, user_id: str, session_id: str = None):
        key = f"session_summary:{user_id}"
        if session_id:
            key = f"{key}:{session_id}"
        await self.client.delete(key)
        return True

    async def delete_all_session_summaries(self, user_id: str) -> bool:
        """Deletes all session summaries for a user."""
        pattern = f"session_summary:{user_id}*"
        async for key in self.client.scan_iter(match=pattern):
            await self.client.delete(key)
        return True

    async def save_tool_state(self, user_id: str, tool_args: dict, session_id: str = None):
        key = f"tool_state:{user_id}"
        if session_id:
            key = f"{key}:{session_id}"
        await self.client.json().set(key, "$", tool_args)

    async def get_tool_state(self, user_id: str, session_id: str = None) -> dict:
        key = f"tool_state:{user_id}"
        if session_id:
            key = f"{key}:{session_id}"
        data = await self.client.json().get(key)
        # return empty dict if None
        return data if data else {}

    async def delete_tool_state(self, user_id: str, session_id: str = None) -> bool:
        key = f"tool_state:{user_id}"
        if session_id:
            key = f"{key}:{session_id}"
        await self.client.delete(key)
        return True

    async def delete_all_tool_states(self, user_id: str) -> bool:
        """Deletes all tool states for a user."""
        pattern = f"tool_state:{user_id}*"
        async for key in self.client.scan_iter(match=pattern):
            await self.client.delete(key)
        return True

    async def count_user_profiles(self, user_id: str) -> int:
        # Use RediSearch index info if possible, otherwise keys scan (slow)
        # FT.INFO idx:{user_id} provides "num_docs"
        index_name = f"idx:{user_id}"
        try:
            info = await self.client.ft(index_name).info()
            return int(info.get("num_docs") or 0)
        except:
             return 0

    async def listen(self, channel: str):
        """
        Async generator to listen to a Redis channel
        """
        async with self.client.pubsub() as pubsub:
            await pubsub.subscribe(channel)
            try:
                async for message in pubsub.listen():
                    if message['type'] == 'message':
                        try:
                            data = json.loads(message['data'])
                            yield data
                        except json.JSONDecodeError:
                            continue
            except asyncio.CancelledError:
                 pass
            finally:
                await pubsub.unsubscribe(channel)

    async def get_user_chat_sessions(self, user_id: str) -> list[dict]:
        """
        Scan for chat history keys and return session IDs and message counts.
        Keys format: chat_history:{user_id} or chat_history:{user_id}:{session_id}
        """
        pattern = f"chat_history:{user_id}*"
        sessions = []
        
        async for key in self.client.scan_iter(match=pattern):
            parts = key.split(":") 
            session_id = None
            if len(parts) > 2:
                session_id = parts[2]
            
            count = await self.client.llen(key)
            sessions.append({
                "session_id": session_id,
                "count": count
            })
            
        return sessions

    async def delete_history(self, user_id: str, session_id: str = None):
        """
        Delete specific session history or all history if session_id is None.
        """
        if session_id:
            key = f"chat_history:{user_id}:{session_id}"
            await self.client.delete(key)
        else:
            pattern = f"chat_history:{user_id}*"
            async for key in self.client.scan_iter(match=pattern):
                await self.client.delete(key)
        return True

    async def get_all_session_summaries(self, user_id: str) -> list[SessionSummary]:
        """
        Scan for session summary keys and return parsed summaries.
        Keys format: session_summary:{user_id} or session_summary:{user_id}:{session_id}
        """
        pattern = f"session_summary:{user_id}*"
        summaries = []
        
        async for key in self.client.scan_iter(match=pattern):
            # Parse session_id
            parts = key.split(":")
            session_id = None
            if len(parts) > 2:
                session_id = parts[2]
                
            data = await self.client.get(key)
            if data:
                try:
                    summary = SessionSummary.model_validate_json(data)
                    # If session_id not in object, add it from key
                    if not summary.session_id and session_id:
                        summary.session_id = session_id
                        
                    summaries.append(summary)
                except Exception as e:
                    print(f"Error parsing session summary for key {key}: {e}")
                    pass
        return summaries

    async def get_all_tool_states(self, user_id: str) -> list[dict]:
        """
        Scan for tool state keys and return parsed states.
        Keys format: tool_state:{user_id} or tool_state:{user_id}:{session_id}
        """
        pattern = f"tool_state:{user_id}*"
        states = []
        
        async for key in self.client.scan_iter(match=pattern):
            # Parse session_id
            parts = key.split(":")
            session_id = None
            if len(parts) > 2:
                session_id = parts[2]
                
            data = await self.client.json().get(key)
            if data:
                states.append({
                    "session_id": session_id,
                    "tool_args": data
                })
        return states

    async def get_person_profile(self, user_id: str, person_id: str) -> dict:
        """
        Get cached person profile.
        """
        key = f"person_profile:{user_id}:{person_id}"
        data = await self.client.get(key)
        if data:
            try:
                return json.loads(data)
            except:
                pass
        return None

    async def save_person_profile_cache(self, user_id: str, person_id: str, profile_data: dict, ttl: int = 86400):
        """
        Cache person profile with TTL (default 1 day).
        """
        key = f"person_profile:{user_id}:{person_id}"
        await self.client.set(key, json.dumps(profile_data), ex=ttl)
    
    async def close(self):
        if self.client:
            logger.info("Redis Connection Stopped")
            await self.client.close()


redis_service = RedisService()
