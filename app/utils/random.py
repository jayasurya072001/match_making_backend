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
            and not (isinstance(v, (list, dict)) and len(v) > 0 is False)
        }
    elif isinstance(obj, list):
        return [deep_clean_tool_args(v) for v in obj if v not in ("", None)]
    return obj