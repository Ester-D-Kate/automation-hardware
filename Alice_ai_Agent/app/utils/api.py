from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Header, Request
from fastapi.responses import JSONResponse
import logging

from utils.process_audio import process_audio_input
from utils.search import perform_search 

from mqtt_utils.mqtt_ducky_windows import publish_ducky_script_to_mqtt
from mqtt_utils.mqtt_appliances import publish_appliance_command_to_mqtt

logger = logging.getLogger(__name__)

router = APIRouter()

conversation_contexts = {}

def clean_response(data: dict) -> dict:
    # Only keep non-empty fields
    result = {}
    if data.get("ducky_script"):
        result["ducky_script"] = data["ducky_script"]
    if data.get("appliance_controls") and isinstance(data["appliance_controls"], dict) and len(data["appliance_controls"]) > 0:
        result["appliance_controls"] = data["appliance_controls"]
    return result

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

@router.post("/execute_command")
async def execute_command(request: Request):
    try:
        data = await request.json()
        if data.get("ducky_script"):
            success = publish_ducky_script_to_mqtt({"ducky_script": data["ducky_script"]})
        elif data.get("appliance_controls"):
            success = publish_appliance_command_to_mqtt({"appliance_controls": data["appliance_controls"]})
        else:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "No valid command found in payload"}
            )
        if success:
            return JSONResponse(
                status_code=200,
                content={"status": "success", "message": "Command sent via MQTT"}
            )
        else:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "Failed to publish command to MQTT"}
            )
    except Exception as e:
        logger.error(f"Error sending command to MQTT: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@router.post("/upload_screenshot")
async def upload_screenshot(screenshot: UploadFile = File(...), user_id: Optional[str] = Header("anonymous_user")):
    try:
        # Save screenshot or process as needed
        content = await screenshot.read()
        # You can save to disk, or pass to OCR/vision pipeline here
        # For now, just acknowledge receipt
        # Save to a temp folder if you want to process later
        with open(f"/tmp/{user_id}_latest_screen.png", "wb") as f:
            f.write(content)
        return {"status": "success", "message": "Screenshot uploaded"}
    except Exception as e:
        logger.error(f"Failed to upload screenshot: {e}")
        return {"status": "error", "message": str(e)}