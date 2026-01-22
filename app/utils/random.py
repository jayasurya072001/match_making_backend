import secrets

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
    """
    Validates and cleans tool arguments against a given JSON schema.
    Keeps only keys defined in the schema properties and removes empty values.
    """
    if not isinstance(args, dict) or not isinstance(tool_schema, dict):
        return args

    properties = tool_schema.get("properties", {})
    allowed_keys = set(properties.keys())
    
    # We always allow 'user_id' for our internal handling if it's not in schema but we inject it
    # However, MCP tools usually have user_id in their schema anyway.
    
    cleaned = {}
    for k, v in args.items():
        if k in allowed_keys:
            # Clean value (standard logic)
            if v not in ("", None) and not (isinstance(v, (list, dict)) and len(v) == 0):
                if isinstance(v, dict) and "properties" in properties.get(k, {}):
                    # Recursive clean for nested objects if defined in schema
                     cleaned[k] = validate_and_clean_tool_args(v, properties[k])
                else:
                    cleaned[k] = v
                    
    return cleaned


tools_specific_promtps = {
    "search_person_by_name": """
        EXTRACTION RULES
        1. If user requests for specific name then output {{"name": "name"}}
    """,
    "search_profiles": """
        EXTRACTION RULES
        1. Dont Mix the values of one argument to another argument.
        2. IF the user mentions a NEW attribute (e.g., "also blonde") → Output {{"hair_color": "blonde"}}.
        3. IF the user CHANGES an attribute (e.g., "actually, make it Bangalore") → Output {{"location": "Bangalore"}}.
        4. IF the user REMOVES a filter (e.g., "remove age filter") → Output {{"age_group": null, "min_age": null, "max_age": null}}.
        5. IF the user says "reset everything" or "start over" → Output {{"_reset": true}}.
        6. IF the user specifies exact age (e.g., "25 years old", "above 20") → Use `min_age` / `max_age`.
            - "25 years old" -> {{"min_age": 25, "max_age": 25}}
            - "above 20" -> {{"min_age": 20}}
            - "under 30" -> {{"max_age": 30}}
            - "between 20 and 30" -> {{"min_age": 20, "max_age": 30}}
        7. WHEN THE USER ASKS FOR MORE MATCHES OR DISLIKES THE CURRENT ONES:
            - Keep all existing user filters and preferences unchanged
            - Increase result depth silently
            - Respond as if more options are now available
            - Never mention pagination, limits, page size, or re-querying
            - Invite light refinement only if it feels natural
        
        PAGINATION RULE:
            - If user asks for "more", "next", "continue":
              - Check conversation history for the last tool call.
              - Output {{"page": (previous_page + 1)}}. 
              - If no page found, default to {{"page": 1}}.

        INTENT NORMALIZATION
        - "girl", "girls", "woman", "women", "lady", "ladies" → gender="female"
        - "guy", "man", "men", "guys", "boy", "boys", "male" → gender="male"

        STRICT OUTPUT RULES
        - ALWAYS return JSON ONLY.
        - `tool_args` MUST be a dictionary.
        - OMIT any field not present in the LATEST query.
        - DO NOT include empty strings or defaults.

        INVALID OUTPUT EXAMPLES
        ❌ "tool_args": ["gender=female"]
        ❌ "tool_args": {{ ...all previous filters... }}
    """
}

def get_tool_specific_prompt(selected_tool):
    return tools_specific_promtps.get(selected_tool, "")


