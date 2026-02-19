import insightface
import numpy as np
import cv2
import httpx
from insightface.app import FaceAnalysis

class EmbeddingService:
    def __init__(self):
        # Initialize FaceAnalysis with arcface
        # enable_detection=True needed to find the face first
        self.app = FaceAnalysis(providers=['CPUExecutionProvider'])
        self.app.prepare(ctx_id=0, det_size=(640, 640))

    async def get_image_from_url(self, url: str) -> np.ndarray:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            resp.raise_for_status()
            image_array = np.asarray(bytearray(resp.content), dtype="uint8")
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            return image

    async def get_embedding(self, image_url: str) -> list[float]:
        try:
            img = await self.get_image_from_url(image_url)
            if img is None:
               raise ValueError("Could not decode image")
            
            # FaceAnalysis inference
            faces = self.app.get(img)
            
            if not faces:
                raise ValueError("No face detected in the image")
            
            # Assuming we take the first face or the most prominent one
            # InsightFace sorts by detection score usually, or we can sort by area
            # For this task, taking the first valid face is standard practice
            embedding = faces[0].embedding
            
            # Normalize? ArcFace embeddings are typically normalized.
            # Convert to list for JSON serialization/Redis storage
            return embedding.tolist()
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise e

embedding_service = EmbeddingService()
