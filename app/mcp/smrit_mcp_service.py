from mcp.server.fastmcp import FastMCP
import httpx
import logging  
import asyncio
from typing import Any
import aiohttp
from typing import Optional, Tuple, Literal


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
    image_url: str | None = None,
    location: str | None = None,
    distance: int | None = 10,
    page: int | None = 0,
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
    eyebrow: Optional[Literal["present", "absent"]] = None
) -> Any:
    """
        Search and filter people profiles using structured attributes and optional image similarity.

        Use this tool when the user wants to:
        - Find, search, list, or filter people or profiles
        - Apply appearance-based attributes (age, gender, hair, face, emotion, etc.)
        - Filter by location and distance
        - Refine or continue a previous profile search
        - Request more results from an existing search

        Behavior:
        - All filters are OPTIONAL and can be combined
        - Only provided arguments are applied
        - Pagination is controlled using `page` (increment page to get more results)
        - This tool does NOT perform name-based lookup

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
    attributes_dict = {
        "gender": gender,
        # We need to construct age filter carefully
        "age": {"min": min_age, "max": max_age} if (min_age is not None or max_age is not None) else None,
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
        "eyebrow": eyebrow
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



if __name__ == "__main__":
    mcp.run()