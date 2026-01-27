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

blob_storage_uploader_service = BlobStorageUploaderService()
