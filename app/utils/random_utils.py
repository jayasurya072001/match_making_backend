import secrets
import re

def generate_random_id(user_id: str) -> str:
    return f"{user_id}-" + "-".join(
        str(secrets.randbelow(100000)).zfill(5)
        for _ in range(4)
    )

def deep_clean_tool_args(obj):
    if isinstance(obj, dict):
        return {
            k: deep_clean_tool_args(v)
            for k, v in obj.items()
            if v not in ("", None)
            and not (isinstance(v, (list, dict)) and len(v) == 0)
        }
    elif isinstance(obj, list):
        return [deep_clean_tool_args(v) for v in obj if v not in ("", None)]
    return obj

def validate_and_clean_tool_args(args: dict, tool_schema: dict) -> dict:
    if not isinstance(args, dict) or not isinstance(tool_schema, dict):
        return args

    properties = tool_schema.get("properties", {})
    cleaned = {}

    for k, v in args.items():
        if k not in properties:
            continue  # key not allowed

        schema_def = properties[k]

        # Remove empty values
        if v in ("", None) or (isinstance(v, (list, dict)) and len(v) == 0):
            continue

        # ✅ ENUM validation (supports list or single value)
        if "enum" in schema_def:
            allowed = schema_def["enum"]

            if isinstance(v, list):
                valid_values = [item for item in v if item in allowed]

                if not valid_values:
                    print(f"⚠️ Invalid values for field '{k}', allowed: {allowed}")
                    continue

                v = valid_values  # clean invalid values

            else:
                if v not in allowed:
                    print(f"⚠️ Invalid value '{v}' for field '{k}', allowed: {allowed}")
                    continue

        # ✅ TYPE validation (optional but recommended)
        expected_type = schema_def.get("type")
        if expected_type == "integer" and not isinstance(v, int):
            continue
        if expected_type == "number" and not isinstance(v, (int, float)):
            continue
        if expected_type == "string":
            if not isinstance(v, (str, list)):
                continue

        # ✅ Nested object validation
        if isinstance(v, dict) and "properties" in schema_def:
            cleaned[k] = validate_and_clean_tool_args(v, schema_def)
        else:
            cleaned[k] = v

    return cleaned



tools_specific_promtps = {
    "search_person_by_name": """
        EXTRACTION RULES
        1. If user requests for specific name then output {{"name": "name"}}
    """,
    "get_profile_recommendations": """
        EXTRACTION RULES
                EXTRACTION RULES
        1. From the user message, identify ONLY ONE matching descriptive/style keyword from the following fixed list:
            ["traditional", "cute", "beautiful", "elegant", "confident", "bold", "romantic", "mysterious", "cheerful", "serious", "intellectual", "simple", "classy", "modern", "homely", "charming", "graceful", "attractive", "soft_spoken", "royal", "grounded"]
        2. IMPORTANT:
            - Return ONLY ONE keyword.
            - The value MUST be exactly one of the above keys.
            - Do NOT generate synonyms, variations, or multiple values.
            - If multiple styles appear, choose the SINGLE most dominant one.
            - If none match clearly, return null for `query`.
        3. Detect `gender` from context:
            - "girl", "woman", "female" -> "female"
            - "boy", "man", "male" -> "male"
        4. Do NOT include unrelated words.
        5. Output STRICT JSON only:
            {
            "query": "<ONE_ALLOWED_KEY_OR_NULL>",
            "gender": "<male|female>"
            }
    """,
    "cross_location_visual_search": """
        EXTRACTION RULES:
        1. SPLIT request into:
            - **TARGET** (Who/Where we want) 
            - **REFERENCE** (What they look like/Where that look comes from).
        
        2. `gender`: Detect from context.
            - "girl", "woman", "lady" -> "female"
            - "boy", "man", "guy" -> "male"

        3. `source_location`: The location defining the visual style (Reference).
            - "looking like bengali" -> "Kolkata" (Reference City)
            - "looks like north indian" -> "Delhi" or "Chandigarh"
            - "punjabi look" -> "Chandigarh"
            - "looks like kashmiri" -> "Srinagar"
            - If simple "bengali" is mentioned as the visual style, infer "Kolkata".

        4. `target_location`: The location where we want to find the person (Target).
            - "girl from tamilnadu" -> "Chennai"
            - "boy from kerala" -> "Kochi" or "Thiruvananthapuram"
            - "person in mumbai" -> "Mumbai"

        5. OUTPUT JSON:
            {
                "gender": "male" | "female",
                "source_location": "City Name/State Capital",
                "target_location": "City Name/State Capital"
            }

        EXAMPLE: "I want a girl from tamilnadu who is looking like bengali"
        - "girl" -> gender="female"
        - "girl from tamilnadu" -> target_location="Chennai"
        - "looking like bengali" -> source_location="Kolkata"
        OUTPUT:
            {
                "gender": "female",
                "source_location": "Kolkata",
                "target_location": "Chennai"
            }
    """,
    "search_profiles": """
        EXTRACTION RULES
        1. Dont Mix the values of one argument to another argument.
        2. If user asks multiple values for a same filter then put them in list and return, dont use $in operator -> Correct Output {{'eye_size': ['large', 'small']}}
        3. IF the user mentions a NEW attribute (e.g., "also blonde") → Output {{"hair_color": "blonde"}}.
        4. IF the user CHANGES an attribute (e.g., "actually, make it Bangalore") → Output {{"location": "Bangalore"}}.
        5. IF the user REMOVES a filter (e.g., "remove age filter") → Output {{"min_age": null, "max_age": null}}.
        6. IF the user says "reset everything" or "start over" → Output {{"_reset": true}}.
        7. IF the user specifies exact age (e.g., "25 years old", "above 20") → Use `min_age` / `max_age`.
            - "25 years old" -> {{"min_age": 25, "max_age": 25}}
            - "above 20" -> {{"min_age": 20+1=21}} (Always add+1 age)(MANDATORY)
            - "under 30" -> {{"max_age": 30-1=29}} (Always subtract-1 age)(MANDATORY)
            - "between 20 and 30" -> {{"min_age": 20, "max_age": 30}}
        8. WHEN THE USER ASKS FOR MORE MATCHES OR DISLIKES THE CURRENT ONES:
            - Keep all existing user filters and preferences unchanged.
            - Respond as if more options are now available.
            - Never mention pagination, limits, page size, or re-querying.
        9.HEIGHT RULES (MANDATORY)
        - Unit: FEET only
        - Type: FLOAT
        - Always 1 decimal (5.0, 5.5, 6.0)
        - Convert cm → feet (round to 1 decimal)
        - Convert 5 ft 6 in → 5.5
        Logic:
        "5.5 feet" → {"min_height": 5.5, "max_height": 5.5}
        "above 5.5 feet" → {"min_height": 5.6}  (+0.1 mandatory)
        "below 6 feet" → {"max_height": 5.9}  (-0.1 mandatory)
        "between 5.5 and 6 feet" → {"min_height": 5.5, "max_height": 6.0}
        10.WEIGHT RULES (kg)
        "60 kg" → {"min_weight": 60, "max_weight": 60}
        "above 60 kg" → {"min_weight": 61}  (+1 mandatory)
        "below 70 kg" → {"max_weight": 69}  (-1 mandatory)
        "between 60 and 70 kg" → {"min_weight": 60, "max_weight": 70}
        11.INCOME RULES (MANDATORY)
        - Unit: LPA only
        - Type: INTEGER
        - Never use rupees / commas / 1200000 format
        - Convert rupees → LPA (1200000 → 12)
        Logic:
        "12 LPA" → {"min_annual_income": 12, "max_annual_income": 12}
        "above 12 LPA" → {"min_annual_income": 13}  (+1 mandatory)
        "below 20 LPA" → {"max_annual_income": 19}  (-1 mandatory)
        "between 10 and 20 LPA" → {"min_annual_income": 10, "max_annual_income": 20}

        PAGINATION RULE:
            - If user asks for "more", "next", "continue":
              - Check conversation history for the last tool call.
              - Output {{"page": 1}} - along with other previous filter if any.
            - Else dont output page in the response.

        INTENT NORMALIZATION
        - "girl", "girls", "woman", "women", "lady", "ladies" → gender="female"
        - "guy", "man", "men", "guys", "boy", "boys", "male" → gender="male"
        - similar for other fields as well where ever possible.

        STRICT OUTPUT RULES
        - ALWAYS return JSON ONLY.
        - `tool_args` MUST be a dictionary.
        - OMIT any field not present in the LATEST query.
        - DO NOT include empty strings or defaults.

        INVALID OUTPUT EXAMPLES
        ❌ "tool_args": [filters]
        ❌ "tool_args": {{ ...all previous filters... }}
    """,
    "search_by_celebrity_lookalike": """
        EXTRACTION RULES:
        1. Extract `celebrity_name` from the user's request.
        2. Detect `gender`:
            - "he", "him", "man", "boy", "actor" -> "male"
            - "she", "her", "woman", "girl", "actress" -> "female"
            - If not explicit, infer from the celebrity's known gender if possible, or default to most likely.
        3. HANDLING CONFIRMATION ("Yes", "That's him", "Correct"):
            - If the user is confirming a previous celebrity image shown by this tool:
            - Look at the IMMEDIATE PREVIOUS ASSISTANT MESSAGE in history.
            - FIND THE URL used in that message. It might be in markdown like ![image](url) or just a plain url https://...
            - EXTRACT THE EXACT URL found in the text.
            - Set `celebrity_name` = The name mentioned by assistant.
            - Set `confirmed_image_url` = THE ACTUAL EXTRACTED URL.
            - Retain `gender` from context.
            - CRITICAL: DO NOT return placeholders like "<URL_FROM...>" or "URL". You must find the actual https link.
            - IF NO URL IS FOUND IN THE PREVIOUS ASSISTANT MESSAGE:
                - IF user input is strictly "Yes", "Ok", "Sure", "Correct" (Ambiguous):
                    - Set `confirmed_image_url` = `null` (Reset state to avoid loop).
                - ELSE:
                    - OMIT `confirmed_image_url` field (Preserve state for filters/pagination).
        4. HANDLING NEW SEARCH ("I want someone like...", "Show me..."):
            - If the user is asking for a different celebrity or starting a new search:
            - Set `confirmed_image_url` to `null` (Must be explicit null to clear previous state).
        5. OUTPUT JSON:
            {
                "celebrity_name": "Name",
                "gender": "male" | "female",
                "confirmed_image_url": "https://..." | null
            }
    """
}

def get_tool_specific_prompt(selected_tool):
    return tools_specific_promtps.get(selected_tool, "")



def persona_json_to_system_prompt(persona: dict) -> str:
    """
    Converts a persona JSON into a system instruction prompt.
    Uses ONLY fields present in the JSON.
    No inferred behavior, no added rules.
    """

    identity = persona.get("identity", {})
    professional = persona.get("professional", {})
    academics = persona.get("academics", {})
    family = persona.get("family", {})
    lifestyle = persona.get("lifestyle", {})
    strengths = persona.get("strengths_and_weaknesses", {})

    lines = []

    # Core identity
    lines.append(f"You are {identity.get('full_name')}.")

    # Identity
    lines.append("\nIDENTITY:")
    lines.append(f"- Full Name: {identity.get('full_name')}")
    lines.append(f"- Age: {identity.get('age')}")
    lines.append(f"- Location: {identity.get('location')}")
    if identity.get("languages"):
        lines.append(f"- Languages: {', '.join(identity['languages'])}")
    if identity.get("physical_description"):
        lines.append(f"- Physical Description: {identity['physical_description']}")

    # Professional
    lines.append("\nPROFESSIONAL BACKGROUND:")
    lines.append(f"- Current Role: {professional.get('current_role')}")
    lines.append(f"- Company: {professional.get('company')}")
    lines.append(f"- Years of Experience: {professional.get('years_of_experience')}")
    if professional.get("areas_of_expertise"):
        lines.append(f"- Areas of Expertise: {', '.join(professional['areas_of_expertise'])}")

    # Academics
    if academics:
        lines.append("\nACADEMICS:")
        if academics.get("school"):
            lines.append(f"- School: {', '.join(academics['school'])}")
        if academics.get("university"):
            lines.append(f"- University: {', '.join(academics['university'])}")

    # Family
    if family:
        lines.append("\nFAMILY:")
        lines.append(f"- Marital Status: {family.get('marital_status')}")
        lines.append(f"- Spouse Name: {family.get('spouse_name')}")
        lines.append(f"- Children Count: {family.get('children_count')}")
        lines.append(f"- Siblings Count: {family.get('siblings_count')}")
        lines.append(f"- Father Name: {family.get('father_name')}")
        lines.append(f"- Mother Name: {family.get('mother_name')}")

    # Lifestyle
    if lifestyle:
        lines.append("\nLIFESTYLE:")
        if lifestyle.get("hobbies"):
            lines.append(f"- Hobbies: {', '.join(lifestyle['hobbies'])}")
        if lifestyle.get("personal_interests"):
            lines.append(f"- Personal Interests: {', '.join(lifestyle['personal_interests'])}")
        if lifestyle.get("lifestyle_description"):
            lines.append(f"- Lifestyle Description: {lifestyle['lifestyle_description']}")

    # Strengths & weaknesses
    if strengths:
        lines.append("\nSTRENGTHS AND WEAKNESSES:")
        if strengths.get("strengths"):
            lines.append(f"- Strengths: {', '.join(strengths['strengths'])}")
        if strengths.get("weaknesses"):
            lines.append(f"- Weaknesses: {', '.join(strengths['weaknesses'])}")

    # Domain expertise
    if persona.get("expertise"):
        lines.append("\nEXPERTISE:")
        lines.append(f"- {', '.join(persona['expertise'])}")

    # Meta attributes
    if persona.get("humor"):
        lines.append(f"\nHUMOR STYLE: {persona['humor']}")
    if persona.get("expert_level"):
        lines.append(f"EXPERT LEVEL: {persona['expert_level']}")

    return "\n".join(lines)


def normalize_decision_tool(value):
    if isinstance(value, str):
        value = value.strip()

        # remove accidental JSON quotes
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]

        return {"decision": value}

    if isinstance(value, dict):
        return value


    return {"decision": "no_tool"}

# def strip_json_comments(json_str: str) -> str:
#     """
#     Strips // and /* */ comments from a JSON string while being careful 
#     not to strip comments inside strings.
#     """
#     import re
#     # Pattern to match strings, // comments, and /* */ comments
#     # We use [^\r\n]* instead of .* for // to avoid matching newlines even with re.DOTALL
#     pattern = r'("(?:\\.|[^"\\])*")|//[^\r\n]*|/\*.*?\*/'
    
#     def replacer(match):
#         # If it's a string, return it as is
#         if match.group(1) is not None:
#             return match.group(1)
#         # If it's a comment, return empty string
#         return ""
    
#     # We use flags=re.DOTALL for /* */ comments that potentially span multiple lines
#     cleaned = re.sub(pattern, replacer, json_str, flags=re.DOTALL)
    
#     # Also handle some edge cases like trailing commas before closing brackets
#     cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
    
#     return cleaned.strip()

# def try_extract_json_from_error(error_msg: str) -> str:
#     """
#     Attempts to extract JSON from a parsing error message that contains "Extracted JSON:".
#     """
#     if not error_msg or "Extracted JSON:" not in error_msg:
#         return None
    
#     try:
#         if "Extracted JSON:" in error_msg:
#             parts = error_msg.split("Extracted JSON:")
#             json_part = parts[1].strip()
#             # If it's wrapped in '...', strip them
#             if json_part.startswith("'") and json_part.endswith("'"):
#                 json_part = json_part[1:-1]
#             return json_part
#     except Exception:
#         pass
#     return None

def strip_json_comments(json_str: str) -> str:
    """
    Strips // and /* */ comments from a JSON string while being careful 
    not to strip comments inside strings.
    """
    # Remove // comments (everything after // until end of line)
    json_str = re.sub(r'//.*', '', json_str)

    # Remove /* */ comments (multiline)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)

    # Remove trailing commas before } or ]
    json_str = re.sub(r',\s*([\]}])', r'\1', json_str)

    return json_str.strip()

def try_extract_json_from_error(error_msg: str) -> str:
    """
    Attempts to extract JSON from a parsing error message that contains "Extracted JSON:".
    """
    if not error_msg or "Extracted JSON:" not in error_msg:
        return None

    match = re.search(r'Extracted JSON:\s*(\{.*\})', error_msg, re.DOTALL)
    if match:
        return match.group(1)

    return None