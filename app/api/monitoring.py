from fastapi import APIRouter
from app.services.metrics_service import metrics_service
import asyncio

router = APIRouter()

@router.get("/metrics", tags=["monitoring"])
async def get_metrics():
    """
    Get current application metrics snapshot.
    """
    return metrics_service.get_metrics_snapshot()
