"""
Filter Suggestion Generator for No-Results Scenarios

This module generates validated alternative filter combinations when search queries
return no results. It uses predefined locations and validates each suggestion to
ensure results exist before presenting them to users.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
import random
import json

logger = logging.getLogger(__name__)

# Predefined major cities for location-based suggestions
PREDEFINED_LOCATIONS = ["Chennai", "Mumbai", "Delhi", "Bangalore", "Hyderabad"]

# Filter categories for prioritization
HIGH_PRIORITY_FILTERS = ["gender", "location"]
APPEARANCE_FILTERS = [
    "age", "ethnicity", "hair_color", "hair_style", "eye_color", 
    "face_shape", "emotion", "beard", "mustache", "eyewear", "headwear",
    "attire", "body_shape", "skin_color", "hair_length"
]
LIFESTYLE_FILTERS = [
    "diet", "drinking", "smoking", "religion", "profession", 
    "highest_qualification", "mother_tongue", "family_type", "family_values"
]


def _determine_combination_size(tool_args: dict) -> int:
    """
    Determine the number of filters to include in each suggestion based on
    the size of the original tool_args.
    
    Args:
        tool_args: Original tool arguments from the failed search
        
    Returns:
        Number of filters to include (2-5)
    """
    # Count actual filters (exclude user_id, page, _reset)
    filter_count = len([k for k in tool_args.keys() 
                       if k not in ["user_id", "page", "_reset"]])
    
    if filter_count <= 3:
        return random.randint(2, 3)  # Small query: 2-3 filters
    else:
        return random.randint(3, 5)  # Large query: 3-5 filters


def _extract_filters_by_category(tool_args: dict) -> Dict[str, List[Tuple[str, Any]]]:
    """
    Categorize filters from tool_args into priority groups.
    
    Args:
        tool_args: Original tool arguments
        
    Returns:
        Dictionary with categorized filters
    """
    categories = {
        "high_priority": [],
        "appearance": [],
        "lifestyle": [],
        "other": []
    }
    
    for key, value in tool_args.items():
        # Skip internal keys
        if key in ["user_id", "page", "_reset"]:
            continue
            
        # Handle range filters (age, height, weight, etc.)
        if isinstance(value, dict) and ("min" in value or "max" in value):
            # Convert range to simple filter for suggestions
            if "min_" + key in tool_args or "max_" + key in tool_args:
                continue  # Skip if we have the min/max versions
            categories["other"].append((key, value))
        elif key in HIGH_PRIORITY_FILTERS:
            categories["high_priority"].append((key, value))
        elif key in APPEARANCE_FILTERS or key.startswith("min_") or key.startswith("max_"):
            categories["appearance"].append((key, value))
        elif key in LIFESTYLE_FILTERS:
            categories["lifestyle"].append((key, value))
        else:
            categories["other"].append((key, value))
    
    return categories


def _create_location_based_combinations(
    tool_args: dict, 
    categorized_filters: Dict[str, List[Tuple[str, Any]]], 
    size: int
) -> List[Dict[str, Any]]:
    """
    Create filter combinations using predefined locations.
    Scales combination size based on original query complexity.
    
    Args:
        tool_args: Original tool arguments
        categorized_filters: Filters organized by category
        size: Base number of filters per combination
        
    Returns:
        List of filter combinations with varying sizes
    """
    combinations = []
    
    # Extract gender if present
    gender = tool_args.get("gender")
    
    # Get appearance and lifestyle filters
    appearance = categorized_filters["appearance"]
    lifestyle = categorized_filters["lifestyle"]
    other = categorized_filters["other"]
    
    # Pool of additional filters to choose from
    additional_filters = appearance + lifestyle + other
    
    # Determine combination strategy based on available filters
    # For larger queries, create larger combinations to maintain intent
    num_additional_filters = len(additional_filters)
    
    if num_additional_filters == 0:
        # No filters available: all size-2 (gender + location)
        num_large_combos = 0
        num_medium_combos = 0
        filters_per_large = 0
        filters_per_medium = 0
    elif num_additional_filters <= 2:
        # Small query: 3 size-3 combos, 2 size-2 combos
        num_large_combos = 3
        num_medium_combos = 2
        filters_per_large = 1  # Add 1 filter
        filters_per_medium = 0
    else:
        # Large query: 3 size-4/5 combos, 2 size-3 combos
        num_large_combos = 3
        num_medium_combos = 2
        filters_per_large = min(2, num_additional_filters)  # Add 2-3 filters
        filters_per_medium = 1  # Add 1 filter
    
    for idx, location in enumerate(PREDEFINED_LOCATIONS):
        combo = {"location": location}
        
        # Always include gender if available
        if gender:
            combo["gender"] = gender
        
        # Determine how many filters to add based on position
        if idx < num_large_combos and additional_filters:
            # Large combinations: add multiple filters
            num_to_add = filters_per_large
            selected = random.sample(additional_filters, min(num_to_add, len(additional_filters)))
            for key, value in selected:
                combo[key] = value
        elif idx < (num_large_combos + num_medium_combos) and additional_filters:
            # Medium combinations: add one filter
            num_to_add = filters_per_medium
            if num_to_add > 0:
                selected = random.sample(additional_filters, min(num_to_add, len(additional_filters)))
                for key, value in selected:
                    combo[key] = value
        # else: small combinations (just gender + location)
        
        combinations.append(combo)
    
    return combinations


async def _validate_combination(
    filters: Dict[str, Any],
    user_id: str,
    mcp_client
) -> Tuple[bool, int]:
    """
    Validate a filter combination by performing a test search.

    Args:
        filters: Filter combination to validate
        user_id: User ID for the search
        mcp_client: MCP client instance to call search tool

    Returns:
        Tuple of (has_results: bool, count: int)
    """
    try:
        # Prepare minimal tool args for validation
        test_args = filters.copy()
        test_args["user_id"] = user_id
        test_args["page"] = 1

        # Call search with k=1 to check if results exist
        result = await mcp_client.call_tool(
            "search_profiles",
            {**test_args, "k": 1}
        )

        # ---- Validate top-level response ----
        if not isinstance(result, dict) or not result.get("success"):
            return False, 0

        output = result.get("output")
        if not output:
            return False, 0

        structured = None

        # ---- 1️⃣ Preferred: structuredContent ----
        if getattr(output, "structuredContent", None):
            structured = output.structuredContent

        # ---- 2️⃣ Fallback: content[text] containing JSON ----
        elif getattr(output, "content", None):
            for item in output.content:
                if getattr(item, "type", None) == "text":
                    try:
                        structured = json.loads(item.text)
                    except Exception:
                        logger.exception(
                            f"Failed to parse JSON tool output for filters {filters}"
                        )
                    break

        # ---- 3️⃣ Fallback: already a dict ----
        elif isinstance(output, dict):
            structured = output

        # ---- Final validation ----
        if not isinstance(structured, dict):
            return False, 0

        docs = structured.get("docs", [])
        count = structured.get("count", len(docs))

        return count > 0, count

    except Exception as e:
        logger.exception(
            f"Error validating combination {filters}: {e}"
        )
        return False, 0


def _generate_description(filters: Dict[str, Any]) -> str:
    """
    Generate a human-readable description for a filter combination.
    Uses natural language with dynamic prefixes like 'with' and separators like 'and'.
    Handles array values by extracting first element or joining multiple values.
    
    Args:
        filters: Filter combination
        
    Returns:
        Human-readable description
    """
    parts = []
    
    # Gender
    if "gender" in filters:
        parts.append(f"{filters['gender']}s")
    else:
        parts.append("profiles")
    
    # Location
    if "location" in filters:
        parts.append(f"in {filters['location']}")
    
    # Collect notable appearance/lifestyle filters
    notable_filters = []
    for key, value in filters.items():
        if key in ["gender", "location", "user_id", "page"]:
            continue
        
        # Format the filter nicely
        if key.startswith("min_") or key.startswith("max_"):
            continue  # Skip range filters for description
        
        if isinstance(value, dict):
            continue  # Skip complex filters
        
        # Handle array values
        if isinstance(value, list):
            if len(value) == 0:
                continue  # Skip empty arrays
            elif len(value) == 1:
                value = value[0]  # Use single value
            else:
                value = " or ".join(str(v) for v in value)  # Join multiple values
        
        # Add to notable filters with natural phrasing
        readable_key = key.replace("_", " ")
        notable_filters.append(f"{readable_key} {value}")
    
    # Add notable filters with natural language
    if notable_filters:
        # Use dynamic prefixes for variety
        prefixes = ["with", "having", "who have"]
        prefix = random.choice(prefixes)
        
        # Join multiple filters with 'and'
        if len(notable_filters) == 1:
            parts.append(f"{prefix} {notable_filters[0]}")
        else:
            # Join all but last with commas, last with 'and'
            filters_text = ", ".join(notable_filters[:-1]) + f" and {notable_filters[-1]}"
            parts.append(f"{prefix} {filters_text}")
    
    return " ".join(parts)


async def generate_filter_suggestions(
    tool_args: dict,
    user_id: str,
    mcp_client,
    max_suggestions: int = 5
) -> List[Dict[str, Any]]:
    """
    Generate validated filter suggestions when no results are found.
    
    This function:
    1. Analyzes the current tool_args
    2. Determines appropriate combination size
    3. Creates combinations using predefined locations
    4. Validates each combination to ensure results exist
    5. Returns only validated suggestions
    
    Args:
        tool_args: Original tool arguments that returned no results
        user_id: User ID for validation searches
        mcp_client: MCP client instance
        max_suggestions: Maximum number of suggestions to return (default: 5)
        
    Returns:
        List of validated filter suggestions, each containing:
        - filters: Dict of filter key-value pairs
        - description: Human-readable description
        - result_count: Number of results available (from validation)
    """
    logger.info(f"Generating filter suggestions for tool_args: {tool_args}")
    
    # Determine combination size
    combo_size = _determine_combination_size(tool_args)
    logger.info(f"Using combination size: {combo_size}")
    
    # Categorize existing filters
    categorized = _extract_filters_by_category(tool_args)
    
    # Create location-based combinations
    combinations = _create_location_based_combinations(
        tool_args, 
        categorized, 
        combo_size
    )
    logger.info(f"Created {len(combinations)} initial combinations based on predefined locations")
    # Validate each combination and collect successful ones
    validated_suggestions = []
    
    for combo in combinations:
        has_results, count = await _validate_combination(combo, user_id, mcp_client)
        
        if has_results:
            logger.info(f"Validated suggestion: {combo} ({count} results)")
            suggestion = {
                "filters": combo,
                "description": _generate_description(combo),
                "result_count": count
            }
            validated_suggestions.append(suggestion)
        else:
            logger.debug(f"Skipping combination (no results): {combo}")
        
        # Stop if we have enough suggestions
        if len(validated_suggestions) >= max_suggestions:
            break
    
    logger.info(f"Generated {len(validated_suggestions)} validated suggestions")
    return validated_suggestions
