import os
from pymongo import MongoClient
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import requests

MONGO_URI = os.getenv("MONGO_URI", "mongodb://myuser:mypassword@48.217.49.77:27017/")
MONGO_DB = os.getenv("MONGO_DB", "face-attributes-matrimony-matches")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "labels")

API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1/profiles/930/save")
API_TIMEOUT = 10


client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
collection = db[MONGO_COLLECTION]


def get_profile_by_custom_id(custom_id: str) -> dict | None:
    return collection.find_one({"id": custom_id})

def get_profiles(
    query: dict | None = None,
    limit: int | None = None
):
    cursor = collection.find(query or {})

    if limit:
        cursor = cursor.limit(limit)

    for doc in cursor:
        yield doc


class GeoLocation(BaseModel):
    latitude: float
    longitude: float


class Hair(BaseModel):
    hair_color: Optional[str]
    hair_style: Optional[str]


class FaceGeometry(BaseModel):
    fore_head_height: Optional[str]


class Accessories(BaseModel):
    eyewear: Optional[str]
    headwear: Optional[str]
    earrings: Optional[str]


class FacialFeatures(BaseModel):
    Eyebrow: Optional[str]
    mole: Optional[str]
    scars: Optional[str]


class ImageAttributes(BaseModel):
    face_shape: Optional[str]
    head_hair: Optional[str]
    beard: Optional[str]
    mustache: Optional[str]
    ethnicity: Optional[str]
    emotion: Optional[str]
    age_group: Optional[str]
    gender: Optional[str]
    hair: Hair
    eye_color: Optional[str]
    face_geometry: FaceGeometry
    accessories: Accessories
    facial_features: FacialFeatures
    attire: Optional[str]
    body_shape: Optional[str]
    lip_stick: Optional[str]
    skin_color: Optional[str]
    eye_size: Optional[str]
    face_size: Optional[str]
    face_structure: Optional[str]
    hair_length: Optional[str]
    height: Optional[float]
    weight: Optional[int]
    annual_income: Optional[int]
    brothers: Optional[int]
    sisters: Optional[int]
    diet: Optional[str]
    drinking: Optional[str]
    smoking: Optional[str]
    family_type: Optional[str]
    family_values: Optional[str]
    father_occupation: Optional[str]
    mother_occupation: Optional[str]
    highest_qualification: Optional[str]
    marital_status: Optional[str]
    mother_tongue: Optional[str]
    profession: Optional[str]
    religion: Optional[str]
    speaking_languages: List[str] = []


class Samples(BaseModel):
    voice: List[Any] = []
    audio: List[Any] = []


class Preferences(BaseModel):
    chat_style: List[str] = []
    voice_style: List[str] = []


class ProfilePayload(BaseModel):
    id: str
    customId: str
    image_url: str
    name: str = ""
    age: int = 0
    gender: Optional[str]
    country: Optional[str]
    address: str = ""
    geo_location: GeoLocation
    custom: Dict[str, Any] = {}
    samples: Samples
    preferences: Preferences
    image_attributes: ImageAttributes
    tags: List[str] = []
    created_at: str
    updated_at: str


def mongo_to_api_payload(doc: Dict[str, Any]) -> ProfilePayload:
    return ProfilePayload(
        id=doc["id"],
        customId=doc["customId"],
        image_url=doc["image_url"],
        name=doc.get("name", ""),
        age=int(doc.get("age", 0)),
        gender=doc.get("gender"),
        country=doc.get("country"),

        address=", ".join(
            filter(
                None,
                [
                    doc.get("address", {}).get("place"),
                    doc.get("address", {}).get("city"),
                ],
            )
        ),

        geo_location={
            "latitude": float(doc["geo_location"]["latitude"]),
            "longitude": float(doc["geo_location"]["longitude"]),
        },

        custom=doc.get("custom", {}),

        samples={
            "voice": doc.get("samples", {}).get("voice", []),
            "audio": doc.get("samples", {}).get("audio", []),
        },

        preferences={
            "chat_style": doc.get("preferences", {}).get("chat_style", []),
            "voice_style": doc.get("preferences", {}).get("voice_style", []),
        },

        image_attributes={
            "face_shape": doc["image_attributes"].get("face_shape"),
            "head_hair": doc["image_attributes"].get("head_hair"),
            "beard": doc["image_attributes"].get("beard"),
            "mustache": doc["image_attributes"].get("mustache"),
            "ethnicity": doc["image_attributes"].get("ethnicity"),
            "emotion": doc["image_attributes"].get("emotion"),
            "age_group": doc["image_attributes"].get("age_group"),
            "gender": doc.get("gender"),

            "hair": doc["image_attributes"].get("hair", {}),

            "eye_color": doc["image_attributes"].get("eye_color"),

            "face_geometry": doc["image_attributes"].get("face_geometry", {}),

            "accessories": {
                "eyewear": doc["image_attributes"]
                .get("accessories", {})
                .get("eyewear"),
                "headwear": doc["image_attributes"]
                .get("accessories", {})
                .get("headwear"),
                "earrings": doc["image_attributes"]
                .get("accessories", {})
                .get("earrings"),
            },

            "facial_features": {
                "Eyebrow": doc["image_attributes"]
                .get("facial_features", {})
                .get("Eyebrow"),
                "mole": doc["image_attributes"]
                .get("facial_features", {})
                .get("mole"),
                "scars": doc["image_attributes"]
                .get("facial_features", {})
                .get("scars"),
            },
            
            "attire": doc["image_attributes"].get("attire"),
            "body_shape": doc["image_attributes"].get("body_shape"),
            "lip_stick": doc["image_attributes"].get("lip_stick"),
            "skin_color": doc["image_attributes"].get("skin_color"),
            "eye_size": doc["image_attributes"].get("eye_size"),
            "face_size": doc["image_attributes"].get("face_size"),
            "face_structure": doc["image_attributes"].get("face_structure"),
            "hair_length": doc["image_attributes"].get("hair_length"),
            
            # Numeric conversions
            "height": float(doc["image_attributes"].get("height", 0) or 0) if doc["image_attributes"].get("height") else 0.0,
            "weight": int(float(doc["image_attributes"].get("weight", 0) or 0)),
            "annual_income": int(float(doc["image_attributes"].get("annual_income", 0) or 0)),
            "brothers": int(float(doc["image_attributes"].get("brothers", 0) or 0)),
            "sisters": int(float(doc["image_attributes"].get("sisters", 0) or 0)),
            
            "diet": doc["image_attributes"].get("diet"),
            "drinking": doc["image_attributes"].get("drinking"),
            "smoking": doc["image_attributes"].get("smoking"),
            "family_type": doc["image_attributes"].get("family_type"),
            "family_values": doc["image_attributes"].get("family_values"),
            "father_occupation": doc["image_attributes"].get("father_occupation"),
            "mother_occupation": doc["image_attributes"].get("mother_occupation"),
            "highest_qualification": doc["image_attributes"].get("highest_qualification"),
            "marital_status": doc["image_attributes"].get("marital_status"),
            "mother_tongue": doc["image_attributes"].get("mother_tongue"),
            "profession": doc["image_attributes"].get("profession"),
            "religion": doc["image_attributes"].get("religion"),
            
            "speaking_languages": doc["image_attributes"].get("speaking_languages", []),
        },

        tags=doc.get("tags", []),

        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )

def send_profile(payload: ProfilePayload) -> dict:
    response = requests.post(
        API_URL,
        json=payload.model_dump(),
        timeout=API_TIMEOUT,
    )

    response.raise_for_status()
    return response.json()

def send_profile_safe(payload: ProfilePayload) -> dict:
    try:
        response = requests.post(
            API_URL,
            json=payload.model_dump(),
            timeout=API_TIMEOUT,
        )
        response.raise_for_status()
        return {
            "success": True,
            "data": response.json()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def run_bulk_sync(
    query: dict | None = None,
    limit: int | None = None,
):
    stats = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "errors": []
    }

    for doc in get_profiles(query=query, limit=limit):
        stats["total"] += 1

        try:
            payload = mongo_to_api_payload(doc)
            result = send_profile_safe(payload)

            print(result)

            if result["success"]:
                stats["success"] += 1
            else:
                stats["failed"] += 1
                stats["errors"].append({
                    "id": doc.get("id"),
                    "customId": doc.get("customId"),
                    "error": result["error"]
                })

        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append({
                "id": doc.get("id"),
                "customId": doc.get("customId"),
                "error": str(e)
            })

    return stats

def main():
    # custom_id = "3be5f406-3971-4217-aa7e-bbb4ee2ed1c1"

    # mongo_doc = get_profile_by_custom_id(custom_id)
    # if not mongo_doc:
    #     raise ValueError("Profile not found")

    # payload = mongo_to_api_payload(mongo_doc)

    # response = send_profile(payload)
    # print("API response:", response)

    query = {
        "country": "India",
        "image_attributes.diet": {
        "$exists": True,
        "$ne": ""
        },
        "name": {
        "$exists": True,
        "$ne": ""
        }
    }

    result = run_bulk_sync(query)
    print(result)


if __name__ == "__main__":
    main()
