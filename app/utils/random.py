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
            - Keep all existing user filters and preferences unchanged.
            - Respond as if more options are now available.
            - Never mention pagination, limits, page size, or re-querying.
        
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
        ❌ "tool_args": ["gender=female"]
        ❌ "tool_args": {{ ...all previous filters... }}
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

    if persona.get("response_language"):
        lines.append(f"MANDATORY RESPONSE LANGUAGE: {persona['response_language']}")

    return "\n".join(lines)
