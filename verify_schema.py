
import sys
import os
import json
from datetime import datetime

# Add app to path
sys.path.append(os.getcwd())

from app.utils.upload_mongo import mongo_to_api_payload, ProfilePayload
from app.api.schemas import ImageAttributes

# Add parent directory to path to allow imports from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

try:
    from app.utils.upload_mongo import mongo_to_api_payload
    print("Successfully imported upload_mongo")
except ImportError as e:
    print(f"Import error: {e}")
    # Try adjusting path if needed, but the workspace root is usually sufficient
    sys.exit(1)

# Sample Mongo Document with new fields
mongo_doc = {
  "_id": {
    "$oid": "694a3a5e33daca79ca2ba7b9"
  },
  "original_filename": "test.jpg",
  "address": {
    "city": "Bangalore",
    "place": "Koramangala"
  },
  "age": "23",
  "country": "India",
  "created_at": "2025-12-23T10:06:02.540623Z",
  "custom": {},
  "customId": "910",
  "gender": "Female",
  "geo_location": {
    "latitude": "12.9352",
    "longitude": "77.6245"
  },
  "id": "3be5f406-3971-4217-aa7e-bbb4ee2ed1c1",
  "image_attributes": {
    "face_shape": "Diamond",
    "head_hair": "None",
    "beard": "None",
    "mustache": "None",
    "ethnicity": "White",
    "emotion": "Neutral",
    "age_group": "Adult",
    "gender": "None",
    "hair": {
      "hair_color": "Black",
      "hair_style": "Straight"
    },
    "eye_color": "Black",
    "face_geometry": {
      "fore_head_height": "High"
    },
    "accessories": {
      "eyewear": "None",
      "headwear": "None",
      "earrings": "Gold" 
    },
    "facial_features": {
      "Eyebrow": "Normal",
      "mole": "Chin",
      "scars": "None"
    },
    "attire": "casual",
    "body_shape": "fit",
    "lip_stick": "yes",
    "skin_color": "white",
    "eye_size": "normal",
    "face_size": "medium",
    "face_structure": "symmetric",
    "hair_length": "medium",
    
    "annual_income": "13",
    "brothers": "0",
    "diet": "non-vegetarian",
    "drinking": "yes",
    "family_type": "nuclear",
    "family_values": "moderate",
    "father_occupation": "teacher",
    "height": "5.43",
    "highest_qualification": "post graduate",
    "marital_status": "single",
    "mother_occupation": "teacher",
    "mother_tongue": "kannada",
    "profession": "finance",
    "religion": "hindu",
    "sisters": "1",
    "smoking": "no",
    "speaking_languages": [
      "hindi",
      "telugu",
      "kannada",
      "english"
    ],
    "weight": "50"
  },
  "name": "Kiranmayi",
  "preferences": {
    "chat_style": [],
    "voice_style": []
  },
  "review": "approved",
  "samples": {
    "voice": [],
    "audio": []
  },
  "tags": [
    "Outdoor Lover"
  ],
  "updated_at": "2025-12-23T10:06:02.540623Z",
  "image_url": "https://example.com/test.jpg"
}

print("converting...")
try:
    payload = mongo_to_api_payload(mongo_doc)
    print("Conversion successful!")
    
    # Verify mapping
    attrs = payload.image_attributes
    print(f"Height: {attrs.height} (Type: {type(attrs.height)})")
    print(f"Weight: {attrs.weight} (Type: {type(attrs.weight)})")
    print(f"Income: {attrs.annual_income} (Type: {type(attrs.annual_income)})")
    print(f"Languages: {attrs.speaking_languages}")
    print(f"Earrings: {attrs.accessories.earrings}")
    print(f"Mole: {attrs.facial_features.mole}")
    
    # Assertions
    assert attrs.height == 5.43
    assert attrs.weight == 50
    assert attrs.annual_income == 13
    assert "hindi" in attrs.speaking_languages
    assert attrs.accessories.earrings == "Gold"
    
    print("All assertions passed.")
    
except Exception as e:
    print(f"Verification Failed: {e}")
    import traceback
    traceback.print_exc()
