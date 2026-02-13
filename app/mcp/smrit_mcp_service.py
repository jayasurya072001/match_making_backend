from mcp.server.fastmcp import FastMCP
import httpx
import logging  
import asyncio
from typing import Any
import aiohttp
from typing import Optional, Tuple, Literal
import json
import os


LOGGING_FORMAT = "[%(asctime)s] %(levelname)s %(name)s:%(lineno)d - %(message)s"

logging.basicConfig(
    level=logging.INFO,
    format=LOGGING_FORMAT
)

logger = logging.getLogger("smritdb")

OPENCAGE_API_KEY = "54737ced623247dca150315f0a471adc"
BASE_URL = "https://api.opencagedata.com/geocode/v1/json"
API_BASE_URL = "http://localhost:8000/api/v1/profiles"

# Initialize FastMCP Server
mcp = FastMCP("SmritDB Search Service")

def normalize_range(min_val, max_val, min_default, max_default, cast_type):
    if min_val is None and max_val is None:
        return None

    if min_val is None:
        min_val = min_default

    if max_val is None:
        max_val = max_default

    return {
        "min": cast_type(min_val),
        "max": cast_type(max_val)
    }

async def geocode_location(
    location: str,
    api_key: str = OPENCAGE_API_KEY
) -> Optional[Tuple[float, float]]:
    """
    Convert a location/address to latitude & longitude using OpenCage API.
    """
    params = {
        "q": location,
        "key": api_key,
        "limit": 1,
        "no_annotations": 1
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

    if not data.get("results"):
        return None

    geometry = data["results"][0]["geometry"]
    return geometry["lat"], geometry["lng"]

# def build_filters(attrs: SearchFilters) -> dict:
#     return {
#         k: v
#         for k, v in attrs.model_dump().items()
#         if v is not None
#     }


@mcp.tool()
async def search_profiles(
    user_id: str,
    name: str | None = None,
    image_url: str | None = None,
    location: str | None = None,
    distance: int | None = 10,
    page: int | None = 1,
    # Flattened Attributes
    min_age: int | None = None,
    max_age: int | None = None,
    gender: Optional[Literal["male", "female"]] = None,
    age_group: Optional[Literal["teen", "adult", "senior"]] = None,
    ethnicity: Optional[Literal["white", "black", "asian", "brown"]] = None,
    hair_color: Optional[Literal["black", "blonde", "white", "grey", "others"]] = None,
    eye_color: Optional[Literal["blue", "green", "grey", "black"]] = None,
    face_shape: Optional[Literal["oval", "round", "square", "diamond"]] = None,
    head_hair: Optional[Literal["present", "absent"]] = None,
    beard: Optional[Literal["stubble", "full", "goatee"]] = None,
    mustache: Optional[Literal["thin", "thick", "handlebar"]] = None,
    hair_style: Optional[Literal["straight", "curly"]] = None,
    emotion: Optional[Literal["happy", "sad", "neutral", "angry", "surprised", "romantic"]] = None,
    fore_head_height: Optional[Literal["low", "high"]] = None,
    eyewear: Optional[Literal["prescription_glasses", "sunglasses"]] = None,
    headwear: Optional[Literal["hat", "cap", "turban"]] = None,
    eyebrow: Optional[Literal["present", "absent"]] = None,
    
    # New Fields
    mole: Optional[Literal["Normal", "Unibrow"]] = None, 
    scars: Optional[str] = None,
    earrings: Optional[str] = None,

    attire: Optional[Literal["casual", "western", "traditional", "formal"]] = None, 
    body_shape: Optional[Literal["fit", "slim", "fat", "none"]] = None, 
    lip_stick: Optional[Literal["no", "yes", "none"]] = None, 
    skin_color: Optional[Literal["white", "black", "none", "brown"]] = None,
    eye_size: Optional[Literal["normal", "large", "small", "None"]] = None, 
    face_size: Optional[Literal["large", "medium", "small"]] = None, 
    face_structure: Optional[Literal["symmetric", "asymmetric"]] = None, 
    hair_length: Optional[Literal["long", "medium", "short"]] = None,

    # Numeric Ranges
    min_height: Optional[float] = None,
    max_height: Optional[float] = None,
    min_weight: Optional[int] = None,
    max_weight: Optional[int] = None,
    min_annual_income: Optional[int] = None,
    max_annual_income: Optional[int] = None,

    # Categorical
    diet: Optional[Literal["veg", "nonveg", "egg", "jain"]] = None, 
    drinking: Optional[Literal["yes", "no"]] = None, 
    smoking: Optional[Literal["yes", "no"]] = None, 
    family_type: Optional[Literal["nuclear", "joint"]] = None, 
    family_values: Optional[Literal["traditional", "moderate", "liberal"]] = None, 
    father_occupation: Optional[Literal["doctor", "engineer", "finance", "tech", "teacher", "others"]] = None, 
    mother_occupation: Optional[Literal["doctor", "engineer", "finance", "tech", "teacher", "others"]] = None, 
    highest_qualification: Optional[Literal["phd", "graduate", "post graduate", "diploma"]] = None, 
    marital_status: Optional[Literal["single"]] = None, 
    mother_tongue: Optional[Literal["tamil", "telugu", "kannada", "malayalam", "marathi", "english", "hindi"]] = None, 
    profession: Optional[Literal["doctor", "engineer", "finance", "tech", "teacher", "others"]] = None, 
    religion: Optional[Literal["hindu", "muslim", "christian", "sikh", "jain", "buddhist", "jewish", "parsi", "no religion"]] = None, 
    
    # Simple strings/lists but typed as str for MCP simplicity (comma-sep)
    # The prompt actually lists specific options for speaking_languages too but as a list example.
    speaking_languages: Optional[str] = None, 
    tags: Optional[str] = None # comma separated tags


) -> Any:
    """
        Search and filter people profiles using structured attributes and optional image similarity.

        Use this tool when the user wants to:
        - Find, search, list, or filter people or profiles
        - Apply appearance-based attributes (age, gender, hair, face, emotion, etc.)
        - Filter by location and distance
        - Refine or continue a previous profile search
        - Request more results from an existing search
        - Filter by tags (e.g. "verified", "active")

        Behavior:
        - All filters are OPTIONAL and can be combined
        - Only provided arguments are applied
        - Pagination is controlled using `page` (increment page to get more results)
        - This tool does NOT perform name-based lookup
        - `tags` should be a comma-separated string if multiple

        Do NOT use this tool when:
        - The user is only chatting or asking general questions
        - The user provides a person’s name (use `search_person_by_name` instead)
        - The input is ambiguous or requires clarification

        Notes:
        - Use `min_age` and `max_age` for numeric age constraints
        - Use `page` ONLY when the user asks for more / next results
    """

    # 1. Construct Filters Dict from flattened args
    # We map local args to the SearchFilters schema structure expected by the API

    # Normalize numeric ranges
    age_range = normalize_range(min_age, max_age, 18, 80, int)

    height_range = normalize_range(
        min_height, max_height, 0.0, 9.0, float
    )

    weight_range = normalize_range(
        min_weight, max_weight, 0, 300, int
    )

    income_range = normalize_range(
        min_annual_income, max_annual_income, 0, 1000, int
    )

    # Convert tags string to list if present
    tags_list = [t.strip() for t in tags.split(',')] if tags else None
    
    # Convert speaking_languages to list if present and comma-sep
    # Check if speaking_languages is intended as single or list? 
    # Usually speaking_languages is a list in DB, but query might be single.
    # The prompt comment says `speaking_languages: Optional[str] = None #["tamil", ...]`
    # I'll pass it as is (str) or list if needed. Existing code passed it directly.

    attributes_dict = {
        "name": name,
        "gender": gender,
        # We need to construct age filter carefully
        "age": age_range,
        "age_group": age_group,
        "ethnicity": ethnicity,
        "face_shape": face_shape,
        "head_hair": head_hair,
        "beard": beard,
        "mustache": mustache,
        "hair_color": hair_color,
        "hair_style": hair_style,
        "eye_color": eye_color,
        "emotion": emotion,
        "fore_head_height": fore_head_height,
        "eyewear": eyewear,
        "headwear": headwear,
        "eyebrow": eyebrow,
        
        "mole": mole,
        "scars": scars,
        "earrings": earrings,
        
        "attire": attire,
        "body_shape": body_shape,
        "lip_stick": lip_stick,
        "skin_color": skin_color,
        "eye_size": eye_size,
        "face_size": face_size,
        "face_structure": face_structure,
        "hair_length": hair_length,
        
        "height": height_range,
        "weight": weight_range,
        "annual_income": income_range,
        
        "diet": diet,
        "drinking": drinking,
        "smoking": smoking,
        "family_type": family_type,
        "family_values": family_values,
        "father_occupation": father_occupation,
        "mother_occupation": mother_occupation,
        "highest_qualification": highest_qualification,
        "marital_status": marital_status,
        "mother_tongue": mother_tongue,
        "profession": profession,
        "religion": religion,
        "speaking_languages": speaking_languages,
        "tags": tags_list


    }
    
    # Filter out None values
    filters = {k: v for k, v in attributes_dict.items() if v is not None}

    geo_location = None
    if location:
        coords = await geocode_location(location)
        if coords:
            lat, lng = coords
            geo_location = {
                "latitude": lat,
                "longitude": lng
            }
            if distance:
                geo_location["radius_km"] = distance
    
    logger.info(f"Geo Location Fetched {geo_location}")

    payload = {
        "image_url": image_url,
        "filters": filters or None,
        "geo_filter": geo_location,
        "k": 6,
        "page": page
    }

    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/{user_id}/search",
                json=payload,
                timeout=30
        )
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as e:
        return f"Error calling API: {e.response.text}"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def search_person_by_name(
    user_id: str,
    name: str,
    limit: int = 1
) -> Any:
    """
        Search for a specific person by name using text-based matching.

        Use this tool when the user:
        - Mentions a specific person’s name
        - Asks to find someone by name or partial name
        - Wants to look up an individual directly

        Behavior:
        - Matches full or partial names using text/regex search
        - Returns up to `limit` results
        - Does NOT support attribute-based filtering

        Do NOT use this tool when:
        - The user wants to filter by appearance, age, gender, or location
        - The user requests browsing or discovery of profiles
        - The user asks for “girls”, “people”, or general profile searches

        Notes:
        - This tool is name-driven ONLY
        - For discovery or filtering, use `search_profiles`
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/{user_id}/search_by_name",
                params={"name": name, "limit": limit},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data
    
    except httpx.HTTPStatusError as e:
        return f"Error calling API: {e.response.text}"
    except Exception as e:
        return f"Error: {str(e)}"




def load_recommendations():
    """Load recommendations from the JSON file."""
    try:
        # Construct path relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, 'recommendations.json')
        
        if not os.path.exists(json_path):
            logger.error(f"Recommendations file not found at: {json_path}")
            return {}
            
        with open(json_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading recommendations: {e}")
        return {}

@mcp.tool()
async def get_profile_recommendations(
    query: str,
    gender: Optional[Literal["male", "female"]] = None
) -> Any:
    """
    Get generic visual profile recommendations (archetypes) based on subjective descriptions or 'vibes'.

    This tool bridges the gap between vague user requests (e.g. "I want a simple girl", "Show me corporate types") 
    and specific search attributes. It returns curated 'visual archetypes' that the user can select 
    to trigger a specific search.

    USE THIS TOOL WHEN the user's request contains subjective or descriptive terms related to:
    1. LIFESTYLE / VIBE (Maps to 'Homely', 'Professional', 'Modern', 'Traditional'):
       - "Homely", "Simple", "Down to earth", "Family oriented" -> Returns 'Homely/Simple' archetype.
       - "Modern", "Stylish", "Trendy", "Fashionable", "Western" -> Returns 'Modern/Trendy' archetype.
       - "Professional", "Corporate", "Working", "Career oriented" -> Returns 'Professional' archetype.
       - "Traditional", "Orthodox", "Ethnic" -> Returns 'Traditional' archetype.
    
    2. APPEARANCE DESCRIPTORS (Maps to 'Cute', 'Beautiful'):
       - "Cute", "Bubbly", "Chocolate boy" -> Returns 'Cute' archetype.
       - "Beautiful", "Handsome", "Good looking", "Pretty", "Dashing" -> Returns 'Beautiful' archetype.

    DO NOT USE THIS TOOL IF:
    - The user provides ONLY specific, objective filters like "Age 24-28", "Height 5'5", "Location Chennai". 
      In that case, use `search_profiles` directly.
    - The user asks for a specific person by name.

    Returns:
    - A list of visual cards (archetypes) containing an image_url and a set of predefined attributes 
      corresponding to that style.
    """
    query = query.lower()
    
    # Load recommendations data dynamically
    RECOMMENDATIONS = load_recommendations()
    
    recommendations = []
    
    # Simple keyword matching
    target_styles = []
    
    # 1. Homely / Simple
    if any(k in query for k in ["homely", "simple", "family", "down to earth", "traditional"]):
        target_styles.append("homely")
        # Traditional is often synonymous with homely in this context, but we can keep them distinct if needed.
        # If user explicitly asks for "traditional", we can add both.
        if "traditional" in query:
             target_styles.append("traditional")
    
    # 2. Professional / Corporate
    if any(k in query for k in ["professional", "corporate", "working", "job", "career", "educated", "office"]):
        target_styles.append("professional")

    # 3. Modern / Stylish / Trendy
    if any(k in query for k in ["modern", "stylish", "trendy", "fashion", "western", "cool"]):
        target_styles.append("modern")

    # 4. Cute
    if "cute" in query or "bubbly" in query or "chocolate" in query:
        target_styles.append("cute")
        
    # 5. Beautiful / Handsome
    if any(k in query for k in ["beautiful", "handsome", "good looking", "pretty", "attractive", "radiant", "dashing"]):
        target_styles.append("beautiful")
        
    # Determine gender from query if not provided
    if not gender:
        if any(k in query for k in ["girl", "woman", "female", "lady", "bride", "wife", "partner"]):
            gender = "female"
        elif any(k in query for k in ["boy", "man", "male", "guy", "groom", "husband"]):
            gender = "male"
            
    # Collect recommendations
    for style in target_styles:
        if style in RECOMMENDATIONS:
            style_data = RECOMMENDATIONS[style]
            
            # If gender is known, return only that gender
            if gender and gender in style_data:
                 recommendations.extend(style_data[gender])
            
            # If gender is unknown, return both
            elif not gender:
                 if "female" in style_data:
                     recommendations.extend(style_data["female"])
                 if "male" in style_data:
                     recommendations.extend(style_data["male"])

    if not recommendations:
        # Fallback if no specific style matches, maybe return a mix or ask for clarification?
        # For this tool, better to return empty or a suggestion message.
        return {
            "message": "No specific style recommendations found. Try keywords like 'traditional', 'modern', 'cute'.",
            "docs": []
        }
        
    return {
        "message": f"Here are some visual styles based on '{query}':",
        "recommendation": True,
        "docs": recommendations,
        "instruction": "Select a profile to continue search with these visual attributes."
    }

@mcp.tool()
async def cross_location_visual_search(
    user_id: str,
    filters: dict,
    source_location: str,
    target_location: str,   
    limit: int = 5
) -> Any:
    """
    This tool finds profiles from one location that visually resemble profiles from another location, while applying the same identity filters (such as gender or age).

    It is designed to answer queries like:

    “Find Tamil girl who looks like Punjabi girl”

    “Kannada boy who looks like North Indian boy”

    “People in Chennai who look like people from Delhi”
    """
    logger.info(
        f"[CrossLocationVisualSearch] filters={filters}, "
        f"source={source_location}, target={target_location}"
    )

    async def geo(location: str):
        coords = await geocode_location(location)
        if not coords:
            return None
        lat, lng = coords
        return {"latitude": lat, "longitude": lng}

    async def search(payload: dict):
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{API_BASE_URL}/{user_id}/search",
                json=payload,
                timeout=30
            )
            res.raise_for_status()
            return res.json()

    try:
        # STEP 1 — get ONE reference image from source location
        source_geo = await geo(source_location)

        source_payload = {
            "filters": filters,
            "geo_filter": source_geo,
            "k": 1   # ✅ only one image
        }

        source_payload = {k: v for k, v in source_payload.items() if v}
        source_result = await search(source_payload)

        source_docs = source_result.get("docs", [])
        if not source_docs:
            return {
                "message": f"No reference profile found in {source_location}.",
                "docs": []
            }

        reference_image = source_docs[0].get("image_url")
        if not reference_image:
            return {
                "message": "Reference profile found but image_url is missing.",
                "docs": []
            }

        logger.info(f"[CrossLocationVisualSearch] Reference image: {reference_image}")

        # STEP 2 — search target location using reference image
        target_geo = await geo(target_location)

        target_payload = {
            "image_url": reference_image,  # ✅ only one image_url
            "filters": filters,
            "geo_filter": target_geo,
            "k": limit
        }

        target_payload = {k: v for k, v in target_payload.items() if v}
        target_result = await search(target_payload)

        target_docs = target_result.get("docs", [])

        return {
            "message": f"Profiles in {target_location} visually similar to {source_location}.",
            "reference_image": reference_image,
            "count": len(target_docs),
            "docs": target_docs
        }

    except Exception as e:
        logger.exception("Cross-location visual search failed")
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()