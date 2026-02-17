from azure.storage.blob import BlobServiceClient, ContentSettings
from io import BytesIO
import uuid
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class BlobStorageUploaderService:
    def __init__(self):
        self.blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
        self.container_client = self.blob_service_client.get_container_client(settings.AZURE_STORAGE_CONTAINER_NAME)
    
    def generate_url(self, audio_stream):
        try:
            audio_bytes = BytesIO()
            for chunk in audio_stream:
                audio_bytes.write(chunk)
            audio_bytes.seek(0)

            file_name = f"{uuid.uuid4().hex}.mp3"

            # Upload to blob
            blob_client = self.container_client.get_blob_client(file_name)
            blob_client.upload_blob(
                audio_bytes.getvalue(),
                overwrite=True,
                content_settings=ContentSettings(content_type="audio/mpeg")
            )

            # Return URL
            return blob_client.url
        except Exception as e:
            logger.error(f"Error uploading audio to blob storage: {e}")
            return None

    def upload_file(self, file_data: bytes, file_name: str, content_type: str = "image/jpeg") -> str | None:
        try:
            # Generate unique filename if not provided or to ensure uniqueness? 
            # The prompt implies we might just want to use a unique name.
            # Let's use uuid to be safe and avoid collisions
            extension = file_name.split(".")[-1] if "." in file_name else "jpg"
            unique_file_name = f"{uuid.uuid4().hex}.{extension}"
            
            blob_client = self.container_client.get_blob_client(unique_file_name)
            blob_client.upload_blob(
                file_data,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type)
            )
            return blob_client.url
        except Exception as e:
            logger.error(f"Error uploading file to blob storage: {e}")
            return None

blob_storage_uploader_service = BlobStorageUploaderService()
