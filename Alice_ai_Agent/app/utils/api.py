from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Header
from fastapi.responses import JSONResponse
import logging

from utils.process_audio import process_audio_input
from utils.search import perform_search 

logger = logging.getLogger(__name__)

router = APIRouter()

conversation_contexts = {}

@router.post("/process_audio")
async def api_process_audio(
    audio_file: UploadFile = File(...),
    user_id: Optional[str] = Header("anonymous_user")
):
    """Process audio input and return AI response"""
    try:
        previous_context = conversation_contexts.get(user_id, "")
        result = await process_audio_input(audio_file, previous_context)
        return JSONResponse(content=result)
    
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        logger.exception("Detailed exception information:")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "output_natural_response": f"I'm sorry, but I encountered an error: {str(e)}. Please try again.",
                "output_ducky_script": "",
                "output_appliances_response": {},
                "output_search_required": 0,
                "output_search_query": "",
                "previous_relation": 0,
                "new_previous_convo": ""
            }
        )

@router.post("/reset_conversation")
async def reset_conversation(user_id: Optional[str] = Header("anonymous_user")):
    """Reset the conversation context for a user"""
    if user_id in conversation_contexts:
        conversation_contexts[user_id] = ""
    
    return {"status": "success", "message": "Conversation context reset"}

@router.get("/test_search")
async def test_search(query: str = "current weather in Amritsar"):
    """Test the search engine functionality"""
    
    try:
        result = perform_search(query)
        return JSONResponse(content={
            "query": query,
            "result": result
        })
    except Exception as e:
        logger.error(f"Error testing search: {e}")
        logger.exception("Detailed exception information:")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": str(e)}
        )
    