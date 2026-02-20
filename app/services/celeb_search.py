import os
import requests
import json
from dotenv import load_dotenv
from urllib.parse import quote

load_dotenv()

API_URL = "https://api.perplexity.ai/chat/completions"


class PerplexityError(Exception):
    pass


def identify_celebrity(name: str):
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return {"error": "Missing API key"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "sonar-pro",
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an entity normalization API. "
                    "Determine if the input refers to a real public celebrity. "
                    "Correct spelling if necessary."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Input: '{name}'\n\n"
                    "If this refers to a real public celebrity, return JSON:\n"
                    "{ \"is_celebrity\": true, \"correct_name\": \"Full Correct Name\" }\n\n"
                    "If not a celebrity:\n"
                    "{ \"is_celebrity\": false }\n\n"
                    "Return only JSON."
                )
            }
        ]
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            start = content.index("{")
            end = content.rindex("}") + 1
            parsed = json.loads(content[start:end])

        return parsed

    except Exception as e:
        return {"error": str(e)}

def get_wikipedia_image(name: str):
    headers = {
        "User-Agent": "CelebrityImagePipeline/1.0 (https://yourwebsite.com; contact@yourdomain.com)"
    }
    
    params = {
        "action": "query",
        "titles": name,
        "prop": "pageimages",
        "piprop": "original",
        "pilicense": "any",   # KEY FIX: Allows non-free images to be returned
        "format": "json",
        "redirects": 1        # KEY FIX: Follows redirects automatically
    }

    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            headers=headers,
            params=params,
            timeout=10
        )
        r.raise_for_status()
        data = r.json()

        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            # Check if there is an image URL
            if "original" in page_data:
                return page_data["original"].get("source")
            
        return None
    except Exception as e:
        print(f"Wikipedia Error: {e}")
        return None

def get_celebrity_image_pipeline(input_name: str):
    result = identify_celebrity(input_name)

    if "error" in result:
        return result

    if not result.get("is_celebrity"):
        return False

    corrected_name = result.get("correct_name")

    image_url = get_wikipedia_image(corrected_name)

    return {
        "celebrity": True,
        "correct_name": corrected_name,
        "image_url": image_url
    }

# if __name__ == "__main__":
#     name = input("Enter name: ")
#     output = get_celebrity_image_pipeline(name)
#     print(output)
