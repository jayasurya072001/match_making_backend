from elevenlabs.client import ElevenLabs
from app.core.config import settings
import uuid
import logging

logger = logging.getLogger(__name__)
class ElevenLabsAudioGenService:
    def __init__(self):
        self.elevenlabs = ElevenLabs(api_key=settings.ELEVEN_LABS_API_KEY)
    
    def text_to_audio(self, text: str, voice_id: str) -> str:
        try:
            """
            Convert text to MP3 using ElevenLabs and upload to Azure Blob Storage.
            Returns the public blob URL.
            """
            # Generate unique filename
            file_name = f"{uuid.uuid4().hex}.mp3"

            # Generate audio in memory
            audio_stream = self.elevenlabs.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128"
            )

            return audio_stream
        except Exception as e:
            logger.error(f"Error converting text to audio: {e}")
            return None
    
eleven_labs_audio_gen_service = ElevenLabsAudioGenService()