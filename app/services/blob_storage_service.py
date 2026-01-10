from elevenlabs.client import ElevenLabs
from azure.storage.blob import BlobServiceClient, ContentSettings
from io import BytesIO
import uuid
from app.core.config import settings

# Initialize clients using your existing config
eleven_client = ElevenLabs(api_key=settings.ELEVEN_LABS_API_KEY)

BLOB_CONNECTION_STRING=settings.BLOB_STORAGE_CONNECTION
BLOB_CONTAINER_NAME=settings.BLOB_STORAGE_CONTAINER

blob_service = BlobServiceClient.from_connection_string(
    BLOB_CONNECTION_STRING
)
container_client = blob_service.get_container_client(BLOB_CONTAINER_NAME)

# Ensure container exists
if not container_client.exists():
    container_client.create_container()

def text_to_audio(text: str, voice_id: str) -> str:
    """
    Convert text to MP3 using ElevenLabs and upload to Azure Blob Storage.
    Returns the public blob URL.
    """
    # Generate unique filename
    file_name = f"{uuid.uuid4().hex}.mp3"

    # Generate audio in memory
    audio_stream = eleven_client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128"
    )

    audio_bytes = BytesIO()
    for chunk in audio_stream:
        audio_bytes.write(chunk)
    audio_bytes.seek(0)

    # Upload to blob
    blob_client = container_client.get_blob_client(file_name)
    blob_client.upload_blob(
        audio_bytes.getvalue(),
        overwrite=True,
        content_settings=ContentSettings(content_type="audio/mpeg")
    )

    # Return URL
    return blob_client.url
