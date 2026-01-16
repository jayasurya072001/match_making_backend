from fastapi import FastAPI
from app.api.routes import router
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.services.kafka_service import kafka_service
from app.services.orchestrator import orchestrator_service
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import sys

# Setup logging before app creation or via lifepan
setup_logging()

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import logging
from app.services.mongo import mongo_service
from app.services.redis_service import redis_service

logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    # 1. Check MongoDB
    exit_check = False
    if await mongo_service.check_connection():
        logger.info("✅ MongoDB Connected")
    else:
        exit_check = True
        logger.error("❌ MongoDB Connection Failed")

    # 2. Check Redis
    if await redis_service.check_connection():
        logger.info("✅ Redis Connected")
    else:
        exit_check = True
        logger.error("❌ Redis Connection Failed")

    # 3. Start Kafka & Orchestrator
    try:
        await kafka_service.start()
        logger.info("✅ Kafka Producer Started")
        await orchestrator_service.start()
    except Exception as e:
        exit_check = True
        logger.error(f"❌ Kafka/Orchestrator Startup Failed: {e}")
    
    if exit_check:
        sys.exit()

@app.on_event("shutdown")
async def shutdown_event():
    await kafka_service.stop()
    await orchestrator_service.stop()

app.include_router(router, prefix="/api/v1")
from app.api.monitoring import router as monitoring_router
app.include_router(monitoring_router, prefix="/api/v1/monitoring")

@app.get("/")
async def root():
    return {"message": "Match Making Server is running"}
