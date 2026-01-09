from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from app.core.config import settings
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

class KafkaService:
    def __init__(self):
        self.producer = None
    
    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        logger.info("Kafka Producer started")

    async def stop(self):
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka Producer stopped")

    async def send_request(self, topic: str, request_data: dict):
        if not self.producer:
             # In case start wasn't called (e.g. dev mode without startup event)
             await self.start()
        
        try:
            await self.producer.send_and_wait(topic, request_data)
        except Exception as e:
            logger.error(f"Error sending to Kafka: {e}")
            raise e


kafka_service = KafkaService()
