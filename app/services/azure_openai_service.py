import json
import re
import logging
from typing import Optional
from openai import AzureOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Azure OpenAI Client
client = AzureOpenAI(
    api_key=settings.AZURE_API_KEY,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_version=settings.AZURE_API_VERSION
)

# ---------------------------------------------
# JSON EXTRACTION
# ---------------------------------------------
def extract_json(text: str):
    """
    Extract JSON safely from mixed output.

    Handles:
    - Raw JSON
    - JSON with text before/after
    - JSON inside ```json ... ```
    - JSON inside ``` ... ```
    - Pretty-printed JSON
    - Extra commentary lines
    """

    if not text:
        return None

    # Remove markdown fences
    text = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()

    # Try pure JSON first
    try:
        return json.loads(text)
    except:
        pass

    # Extract first {...} using regex
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        # No JSON found — return original text
        return text.strip()

    json_str = match.group(0)

    # Cleanup common mistakes
    json_str = (
        json_str
        .replace("\n", "")
        .replace("\r", "")
        .replace(",}", "}")      # trailing comma
        .replace(",]", "]")      # trailing comma
    )

    try:
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"JSON parsing failed: {e}\nExtracted JSON:\n{json_str}")
        raise ValueError(f"JSON parsing failed: {e}\nExtracted JSON:\n{json_str}")


# ---------------------------------------------
# OPENAI CALLS
# ---------------------------------------------
def call_openai(prompt: str, model: str = None) -> str:
    """Standard call – returns CLEANED TEXT ONLY."""
    if model is None:
        model = settings.AZURE_DEPLOYMENT

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "you are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=200
        )
        content = response.choices[0].message.content
        # logger.info(f"OpenAI Response: {content}")
        return content
    except Exception as e:
        logger.error(f"OpenAI Call Error: {e}")
        return ""


def call_openai_json(prompt: str, model: str = None):
    """
    Makes an OpenAI call and returns JSON **if present**.
    If returns text-only, returns plain text.
    """
    cleaned = call_openai(prompt, model)
    try:
        return extract_json(cleaned)
    except ValueError:
        return cleaned
