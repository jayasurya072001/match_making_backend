from fastapi import APIRouter, Path, UploadFile, File, Form, HTTPException
from app.api.schemas import ChatRequestBody
from app.services.redis_service import redis_service
from app.services.mongo import mongo_service
from app.services.orchestrator import orchestrator_service
from sse_starlette.sse import EventSourceResponse
from app.services.prompts import get_filler_prompt
from app.services.blob_storage_uploader_service import blob_storage_uploader_service
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()

from app.services.azure_openai_service import call_openai

@router.post("/{user_id}/request", tags=["chat interaction"])
async def chat_request(
    body: ChatRequestBody,
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Initiate a chat request via Orchestrator.
    """
    request_id = await orchestrator_service.handle_request(
        user_id, 
        body.message, 
        body.session_id, 
        body.person_id, 
        body.personality_id, 
        body.session_type, 
        body.recommendation_ids,
        body.selected_filters,
        body.image_url
    )
    
    response = {"status": "accepted", "request_id": request_id}
    
    if body.fillers:
        history = await orchestrator_service.get_history(user_id, body.session_id)
        session_summary = await redis_service.get_session_summary(user_id, body.session_id)
        
        summary_text = session_summary.model_dump_json() if session_summary else "No summary available."
        
        prompt = get_filler_prompt(history, body.message, summary_text)
        
        try:
            filler_msg = await asyncio.to_thread(call_openai, prompt)
            if filler_msg:
                response["filler"] = filler_msg
                logger.info(f"Generated filler: {filler_msg}")
        except Exception as e:
            logger.error(f"Failed to generate filler: {e}")
            
    return response

    return response

@router.post("/{user_id}/request/image", tags=["chat interaction"])
async def chat_request_with_image(
    user_id: str = Path(..., title="The ID of the user"),
    file: UploadFile = File(None),
    body: str = Form(...)
):
    """
    Initiate a chat request with an optional image file.
    """
    try:
        # Parse JSON body
        chat_body = ChatRequestBody.model_validate_json(body)
        
        # Handle file upload if present
        if file:
            content = await file.read()
            url = blob_storage_uploader_service.upload_file(
                content, 
                file.filename, 
                file.content_type
            )
            if url:
                chat_body.image_url = url
                logger.info(f"Uploaded image to {url}")
            else:
                logger.error("Failed to upload image")
                # Should we fail or continue without image? 
                # Let's fail if file was provided but upload failed
                raise HTTPException(status_code=500, detail="Failed to upload image")

        # Reuse existing logic
        return await chat_request(chat_body, user_id)

    except Exception as e:
        logger.exception(f"Error in chat_request_with_image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{request_id}", tags=["chat interaction"])
async def chat_status(
    request_id: str,
):
    """
    Stream chat status and responses via SSE.
    """
    async def event_generator():
        async for msg in redis_service.listen(f"chat_status:{request_id}"):
            if "step" in msg:
                yield {
                    "event": "message",
                    "data": json.dumps(msg)
                }
            else:
                yield {
                    "event": "status",
                    "data": json.dumps(msg)
                }
                if msg.get("final_answer") or msg.get("error"):
                    break

    return EventSourceResponse(event_generator())

@router.get("/{user_id}/request/{request_id}", tags=["chat interaction"])
async def get_chat_request_logs(
    request_id: str,
    user_id: str = Path(..., title="The ID of the user"),
):
    """
    Get the logs and details of a specific chat request from MongoDB.
    """
    log = await mongo_service.get_chat_log(user_id, request_id)
    if not log:
        return {"status": "pending", "complete": False}
    return log
