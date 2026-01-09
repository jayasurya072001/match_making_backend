from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional

class Gender(str, Enum):
    male = "male"
    female = "female"


class AgeGroup(str, Enum):
    teen = "teen"
    adult = "adult"
    senior = "senior"


class Ethnicity(str, Enum):
    white = "white"
    black = "black"
    asian = "asian"
    brown = "brown"


class HairColor(str, Enum):
    black = "black"
    blonde = "blonde"
    white = "white"
    grey = "grey"
    others = "others"


class HairStyle(str, Enum):
    straight = "straight"
    curly = "curly"


class EyeColor(str, Enum):
    blue = "blue"
    green = "green"
    grey = "grey"
    black = "black"


class Emotion(str, Enum):
    happy = "happy"
    sad = "sad"
    neutral = "neutral"
    angry = "angry"
    surprised = "surprised"
    romantic = "romantic"


class BeardStyle(str, Enum):
    stubble = "stubble"
    full = "full"
    goatee = "goatee"


class MustacheStyle(str, Enum):
    thin = "thin"
    thick = "thick"
    handlebar = "handlebar"


class FaceShape(str, Enum):
    oval = "oval"
    round = "round"
    square = "square"
    diamond = "diamond"


class ForeheadHeight(str, Enum):
    low = "low"
    high = "high"


class Eyewear(str, Enum):
    prescription_glasses = "prescription_glasses"
    sunglasses = "sunglasses"


class Headwear(str, Enum):
    hat = "hat"
    cap = "cap"
    turban = "turban"

class SearchFilters(BaseModel):
    # Direct TAG fields
    gender: Optional[Gender] = Field(None, description="Gender of the person")
    age_group: Optional[AgeGroup] = Field(None, description="Age group")
    ethnicity: Optional[Ethnicity] = Field(None, description="Ethnicity")

    face_shape: Optional[FaceShape] = Field(None, description="Face shape")
    head_hair: Optional[str] = Field(None, description="Hair presence on head")

    beard: Optional[BeardStyle] = Field(None, description="Beard style")
    mustache: Optional[MustacheStyle] = Field(None, description="Mustache style")

    hair_color: Optional[HairColor] = Field(None, description="Hair color")
    hair_style: Optional[HairStyle] = Field(None, description="Hair style")

    eye_color: Optional[EyeColor] = Field(None, description="Eye color")
    emotion: Optional[Emotion] = Field(None, description="Facial emotion")

    fore_head_height: Optional[ForeheadHeight] = Field(
        None, description="Forehead height"
    )

    eyewear: Optional[Eyewear] = Field(None, description="Eyewear type")
    headwear: Optional[Headwear] = Field(None, description="Headwear type")

    eyebrow: Optional[str] = Field(None, description="Eyebrow description")

