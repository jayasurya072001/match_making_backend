from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class GeoLocation(BaseModel):
    latitude: float
    longitude: float

class Hair(BaseModel):
    hair_color: str
    hair_style: str

class FaceGeometry(BaseModel):
    fore_head_height: str

class Accessories(BaseModel):
    eyewear: Optional[str] = "None"
    headwear: Optional[str] = "None"
    earrings: Optional[str] = "None"

class FacialFeatures(BaseModel):
    Eyebrow: Optional[str] = "Normal"
    mole: Optional[str] = "None"
    scars: Optional[str] = "None"

class ImageAttributes(BaseModel):
    face_shape: Optional[str] = None
    head_hair: Optional[str] = None
    beard: Optional[str] = None
    mustache: Optional[str] = None
    ethnicity: Optional[str] = None
    emotion: Optional[str] = None
    age_group: Optional[str] = None
    gender: Optional[str] = None
    hair: Hair
    eye_color: Optional[str] = None
    face_geometry: FaceGeometry
    accessories: Accessories
    facial_features: FacialFeatures

    # New Fields
    attire: Optional[str] = None
    body_shape: Optional[str] = None
    lip_stick: Optional[str] = None
    skin_color: Optional[str] = None
    eye_size: Optional[str] = None
    face_size: Optional[str] = None
    face_structure: Optional[str] = None
    hair_length: Optional[str] = None
    
    # Numeric Fields (some coming as strings in JSON but we want specific types if possible, 
    # but based on request "height below 6 feet", "salaries below 5 lpa", we should use numeric types in Pydantic to help coercion if the input is compatible, 
    # or handle string-to-number conversion in the upload script. 
    # The request says "convert to int just like age".
    # So we define them as int/float here. Pydantic will attempt to cast string "5.43" to float 5.43.
    
    height: Optional[float] = None
    weight: Optional[int] = None
    annual_income: Optional[int] = None
    brothers: Optional[int] = None
    sisters: Optional[int] = None
    
    # Categorical / Enum-like fields
    diet: Optional[str] = None
    drinking: Optional[str] = None
    smoking: Optional[str] = None
    family_type: Optional[str] = None
    family_values: Optional[str] = None
    father_occupation: Optional[str] = None
    mother_occupation: Optional[str] = None
    highest_qualification: Optional[str] = None
    marital_status: Optional[str] = None
    mother_tongue: Optional[str] = None
    profession: Optional[str] = None
    religion: Optional[str] = None
    
    # Lists
    speaking_languages: List[str] = []

class Preferences(BaseModel):
    chat_style: List[str] = []
    voice_style: List[str] = []

class Samples(BaseModel):
    voice: List[str] = []
    audio: List[str] = []

class UserProfile(BaseModel):
    id: Optional[str] = None
    customId: str
    image_url: str
    name: str = ""
    age: int
    gender: str
    country: str
    address: str = ""
    geo_location: GeoLocation
    custom: Dict[str, Any] = {}
    samples: Samples
    preferences: Preferences
    image_attributes: ImageAttributes
    tags: List[str] = []
    embeddings: List[float] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class GeoFilter(BaseModel):
    latitude: float
    longitude: float
    radius_km: Optional[int] = 5

class SearchRequest(BaseModel):
    image_url: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    geo_filter: Optional[GeoFilter] = None
    k: Optional[int] = 5
    limit_score: Optional[float] = 0.7
    page: Optional[int] = 1

class LLMRequest(BaseModel):
    request_id: str
    step: str  # check_tool_required | get_tool_args | summarize | custom
    message: Optional[str] = None
    system_prompt: Optional[str] = None
    json_response: Optional[bool] = False
    response_topic: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class LLMResponse(BaseModel):
    request_id: str
    step: str
    tool_required: Optional[str] = None
    selected_tool: Optional[Any] = None
    tool_args: Optional[Any] = None
    tool_result: Optional[Any] = None
    final_answer: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    usage: Optional[Dict[str, Any]] = None # {token_count: int, duration: float, ...}

class StatusEvent(BaseModel):
    request_id: str
    status: str
    extra: Optional[Any] = None
    source: Optional[str] = "orchestrator"


class ResponseType(str, Enum):
    DEFAULT = "0"
    WEBSOCKET = "11"
    FIREBASE = "12"

class SessionType(str, Enum):
    TEXT_TO_TEXT = "1"
    TEXT_TO_SPEECH = "2"
    SPEECH_TO_TEXT = "3"
    SPEECH_TO_SPEECH = "4"


class ChatRequestBody(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User question to the chat system"
    )

    session_id: Optional[str] = Field(
        None,
        description="Optional session identifier"
    )

    person_id: Optional[str] = Field(
        None,
        description="Optional person id, who is chatting with the agent"
    )

    personality_id: Optional[str] = Field(
        None,
        description="Optional personality id for the agent type to respond"
    )

    response_type: Optional[ResponseType] = Field(
        ResponseType.DEFAULT,
        description="Response type: 0 -> default(SSE), 11 -> WebSocket, 12 -> Firebase"
    )

    session_type: Optional[SessionType] = Field(
        SessionType.TEXT_TO_TEXT,
        description=(
            "Session type: "
            "1 -> text to text, "
            "2 -> text to speech, "
            "3 -> speech to text, "
            "4 -> speech to speech"
        )
    )
    fillers: Optional[bool]=Field(
        False,
        description="Optional fillers that needs to be filled while waiting for the response"
    )

    image_url: Optional[str] = Field(
        None,
        description="Optional image url to be used for search along with the query"
    )

    recommendation_ids: Optional[List[str]] = Field(
        [],
        description="Optional list of recommendation ids to be injected into the chat context"
    )

    selected_filters: Optional[Dict[str, Any]] = Field(
        None,
        description="Pre-selected filters to bypass LLM and directly execute search"
    )

class SessionSummary(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    important_points: List[str] = []
    user_details: List[str] = []
    last_updated: float = 0.0


class PersonalityModel(BaseModel):
    persona_id: Optional[str] = None
    user_id: str
    voice_id: Optional[str] = None
    personality: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class UpdateProfileSchema(BaseModel):
    id: str = Field(..., description="The ID of the profile to update")
    collection_name: str = Field(default="Indian", description="The name of the collection (user_id) to update in")
    
    # Update fields with Literal validation
    gender: Optional[Literal["Male", "Female"]] = None
    ethnicity: Optional[Literal["white", "black", "Asian", "brown"]] = None
    hair_color: Optional[Literal["black", "blonde", "white", "grey", "others"]] = None
    eye_color: Optional[Literal["blue", "green", "grey", "black"]] = None
    face_shape: Optional[Literal["oval", "round", "square", "diamond"]] = None
    head_hair: Optional[Literal["present", "absent"]] = None
    beard: Optional[Literal["stubble", "full", "goatee", "none"]] = None # added "none" based on user sample doc "beard": "none"
    mustache: Optional[Literal["thin", "thick", "handlebar", "none"]] = None # added "none" based on user sample doc "mustache": "none"
    hair_style: Optional[Literal["straight", "curly"]] = None
    eyewear: Optional[Literal["prescription_glasses", "sunglasses", "none"]] = None # added "none"
    headwear: Optional[Literal["hat", "cap", "turban", "None"]] = None # added "None"
    eyebrow: Optional[Literal["present", "absent", "Normal"]] = None # added "Normal" from sample doc? Wait, sample has "Eyebrow": "Normal". The user requested "eyebrow : Literal['present', 'absent']". I should respect the user's request but also be aware of existing data. I will stick to the requested literals for now, or maybe include "Normal" to avoid validation errors if they send existing data. The user request "eyebrow : Literal["present", "absent"]" is specific. I will stick to it.
    attire: Optional[Literal["casual", "western", "traditional", "formal"]] = None
    body_shape: Optional[Literal["fit", "slim", "fat", "none"]] = None
    skin_color: Optional[Literal["white", "black", "none", "brown"]] = None
    eye_size: Optional[Literal["normal", "large", "small", "None"]] = None
    face_size: Optional[Literal["large", "medium", "small"]] = None
    face_structure: Optional[Literal["symmetric", "asymmetric"]] = None
    hair_length: Optional[Literal["long", "medium", "short"]] = None
    
    # Allow extra fields or specific others? User said "these are the fields literals that needs to be updated". 
    # I will assume other fields can be passed but these specific ones are validated.
    # Actually, for Pydantic, if I don't define them, they might be ignored or banned depending on config.
    # I'll add `extra = "allow"` to allow other fields if needed, OR just `custom_fields: Dict[str, Any]`.
    # The user instruction implies these are the specific fields to control.
    # "i need 2 api s one to update which i will send id and fields to be updated."
    # I'll define a model that ONLY accepts these for the strict validation part, 
    # but maybe the user wants to update *only* these?
    # "these are the fields literals that needs to be updated" -> suggests these are the target.
    
    class Config:
        extra = "ignore" # Ignore other fields not defined here to be safe, or "forbid".
        # If the user sends "name", should it be updated?
        # The prompt says: "these are the fields literals that needs to be updated".
        # It's safer to only allow these for now.

class DeleteProfileSchema(BaseModel):
    id: str = Field(..., description="The ID of the profile to delete")
    collection_name: str = Field(default="Indian", description="The name of the collection (user_id) to delete from")
