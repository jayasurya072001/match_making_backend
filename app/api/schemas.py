from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
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
    eyewear: str
    headwear: str

class FacialFeatures(BaseModel):
    Eyebrow: str

class ImageAttributes(BaseModel):
    face_shape: str
    head_hair: str
    beard: str
    mustache: str
    ethnicity: str
    emotion: str
    age_group: str
    gender: str
    hair: Hair
    eye_color: str
    face_geometry: FaceGeometry
    accessories: Accessories
    facial_features: FacialFeatures

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

class SessionSummary(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    important_points: List[str] = []
    user_details: List[str] = []
    last_updated: float = 0.0
