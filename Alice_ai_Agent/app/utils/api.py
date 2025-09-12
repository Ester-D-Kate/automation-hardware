from typing import Optional, Dict
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Header, Request
from fastapi.responses import JSONResponse
from io import BytesIO
import logging

from utils.process_audio import process_audio_input
from utils.search import perform_search
from utils.intelligent_search_engine import IntelligentSearchEngine
from utils.enhanced_search_engine import EnhancedSearchEngine
from utils.models import (
    IntelligentSearchResponse, EnhancedSearchResponse, SimpleScrapeResponse,
    SystemStatusResponse, SearchRequest, ScrapeRequest
)

from mqtt_utils.mqtt_ducky_windows import publish_ducky_script_to_mqtt, reset_last_command
from mqtt_utils.mqtt_appliances import publish_appliance_command_to_mqtt

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize search engines
intelligent_search_engine = IntelligentSearchEngine()
enhanced_search_engine = EnhancedSearchEngine()

conversation_contexts = {}

def update_conversation_summary(user_id: str, user_input: str, ai_action: str, ai_response: str, ai_output_data: dict = None):
    """Update conversation summary with detailed context and learning"""
    if user_id not in conversation_contexts:
        conversation_contexts[user_id] = []
    
    # Analyze user intent and extract key details
    user_intent = analyze_user_intent(user_input, ai_output_data)
    
    # Create detailed conversation entry
    new_entry = {
        "user_said": user_input,
        "user_intent": user_intent,
        "ai_did": ai_action,
        "ai_responded": ai_response[:150] + "..." if len(ai_response) > 150 else ai_response,
        "corrections_feedback": extract_corrections_and_feedback(user_input),
        "specific_requirements": extract_specific_requirements(user_input),
        "ducky_script_generated": ai_output_data.get("output_ducky_script", "") if ai_output_data else ""
    }
    
    # Add to conversation list
    conversation_contexts[user_id].append(new_entry)
    
    # Keep only last 5 conversations
    if len(conversation_contexts[user_id]) > 5:
        conversation_contexts[user_id] = conversation_contexts[user_id][-5:]
    
    logger.info(f"💾 Updated conversation summary for {user_id}. Total conversations: {len(conversation_contexts[user_id])}")

def analyze_user_intent(user_input: str, ai_output_data: dict = None) -> str:
    """Analyze what the user really wants to achieve"""
    user_input_lower = user_input.lower()
    
    # Detect correction/feedback intent
    if any(word in user_input_lower for word in ['forgot', 'wrong', 'should be', 'instead', 'correct', 'fix', 'mistake']):
        return "correction_feedback"
    
    # Detect repeat/same action intent
    if any(phrase in user_input_lower for phrase in ['do it again', 'same thing', 'again', 'repeat', 'that command']):
        return "repeat_previous_action"
    
    # Detect computer control intent
    if any(word in user_input_lower for word in ['open', 'close', 'run', 'launch', 'execute', 'type', 'write']):
        return "computer_control"
    
    # Detect search/information intent  
    if any(word in user_input_lower for word in ['what', 'how', 'when', 'where', 'search', 'find', 'weather']):
        return "information_search"
    
    return "general_conversation"

def extract_corrections_and_feedback(user_input: str) -> dict:
    """Extract specific corrections and feedback from user input"""
    corrections = {}
    user_input_lower = user_input.lower()
    
    # Extract delay corrections
    import re
    delay_matches = re.findall(r'delay.*?(\d+).*?ms|(\d+).*?millisecond', user_input_lower)
    if delay_matches:
        for match in delay_matches:
            delay_value = match[0] or match[1]
            corrections['delay_requirement'] = f"DELAY {delay_value}"
    
    # Extract specific application corrections
    if 'notepad' in user_input_lower and ('forgot' in user_input_lower or 'should' in user_input_lower):
        corrections['app_correction'] = 'notepad'
    
    # Extract sequence corrections
    if any(word in user_input_lower for word in ['after opening', 'then', 'before']):
        corrections['sequence_requirement'] = user_input
    
    return corrections

def extract_specific_requirements(user_input: str) -> dict:
    """Extract specific technical requirements from user input"""
    requirements = {}
    user_input_lower = user_input.lower()
    
    # Extract delay requirements
    import re
    delay_matches = re.findall(r'(\d+)\s*ms|\bdelay\s+(\d+)', user_input_lower)
    if delay_matches:
        for match in delay_matches:
            delay_value = match[0] or match[1]
            requirements['preferred_delay'] = delay_value
    
    # Extract application preferences
    apps = ['notepad', 'chrome', 'firefox', 'calculator', 'cmd', 'powershell']
    for app in apps:
        if app in user_input_lower:
            requirements['target_application'] = app
    
    # Extract text to type
    text_patterns = [
        r'write\s+"([^"]+)"',
        r'type\s+"([^"]+)"',
        r'write\s+([^.!?]+)',
        r'type\s+([^.!?]+)'
    ]
    for pattern in text_patterns:
        match = re.search(pattern, user_input_lower)
        if match:
            requirements['text_to_type'] = match.group(1).strip()
    
    return requirements

def get_conversation_context(user_id: str) -> str:
    """Get formatted conversation context for AI with detailed learning context"""
    if user_id not in conversation_contexts or not conversation_contexts[user_id]:
        return "No previous conversations."
    
    # Build comprehensive context
    context_parts = []
    user_preferences = extract_user_preferences(conversation_contexts[user_id])
    
    # Add user preferences summary
    if user_preferences:
        pref_parts = []
        if user_preferences.get('preferred_delays'):
            pref_parts.append(f"Prefers delays: {user_preferences['preferred_delays']}")
        if user_preferences.get('corrections_made'):
            pref_parts.append(f"Past corrections: {user_preferences['corrections_made']}")
        if user_preferences.get('specific_apps'):
            pref_parts.append(f"Uses apps: {user_preferences['specific_apps']}")
        
        if pref_parts:
            context_parts.append(f"USER PREFERENCES: {' | '.join(pref_parts)}")
    
    # Add detailed conversation history
    for i, conv in enumerate(conversation_contexts[user_id], 1):
        conv_summary = f"Conv {i}: '{conv['user_said']}'"
        
        if conv.get('user_intent') == 'correction_feedback':
            conv_summary += " [CORRECTION]"
        
        if conv.get('corrections_feedback'):
            corrections = conv['corrections_feedback']
            if corrections.get('delay_requirement'):
                conv_summary += f" → Wanted: {corrections['delay_requirement']}"
        
        if conv.get('specific_requirements'):
            req = conv['specific_requirements']
            if req.get('preferred_delay'):
                conv_summary += f" → DELAY {req['preferred_delay']} ms"
            if req.get('target_application'):
                conv_summary += f" → App: {req['target_application']}"
        
        conv_summary += f" → I did: {conv['ai_did']}"
        
        if conv.get('ducky_script_generated'):
            # Show key parts of the generated script
            script = conv['ducky_script_generated']
            if 'DELAY' in script:
                delays = [line for line in script.split('\n') if 'DELAY' in line]
                if delays:
                    conv_summary += f" → Generated delays: {', '.join(delays[:2])}"
        
        context_parts.append(conv_summary)
    
    return " | ".join(context_parts)

def extract_user_preferences(conversations: list) -> dict:
    """Extract user preferences and patterns from conversation history"""
    preferences = {
        'preferred_delays': [],
        'corrections_made': [],
        'specific_apps': [],
        'common_phrases': []
    }
    
    for conv in conversations:
        # Extract delay preferences
        if conv.get('corrections_feedback') and conv['corrections_feedback'].get('delay_requirement'):
            delay_req = conv['corrections_feedback']['delay_requirement']
            if delay_req not in preferences['preferred_delays']:
                preferences['preferred_delays'].append(delay_req)
        
        if conv.get('specific_requirements') and conv['specific_requirements'].get('preferred_delay'):
            delay_val = f"DELAY {conv['specific_requirements']['preferred_delay']}"
            if delay_val not in preferences['preferred_delays']:
                preferences['preferred_delays'].append(delay_val)
        
        # Extract correction patterns
        if conv.get('user_intent') == 'correction_feedback':
            preferences['corrections_made'].append(conv['user_said'][:50])
        
        # Extract app preferences  
        if conv.get('specific_requirements') and conv['specific_requirements'].get('target_application'):
            app = conv['specific_requirements']['target_application']
            if app not in preferences['specific_apps']:
                preferences['specific_apps'].append(app)
    
    return preferences

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
        # Get formatted conversation context
        previous_context = get_conversation_context(user_id)
        
        # Get transcribed text for context update
        audio_buffer = BytesIO(await audio_file.read())
        audio_file.file = audio_buffer  # Reset file pointer
        
        result = await process_audio_input(audio_file, previous_context)
        
        # 🧠 Update conversation summary with new interaction
        transcribed_text = result.get("transcribed_text", "")
        if transcribed_text:  # Only update if we got valid input
            # Determine what AI action was taken
            ai_action = "provided information"
            if result.get("output_ducky_script"):
                ai_action = f"executed computer command: {result['output_ducky_script'][:50]}..."
            elif result.get("output_appliances_response"):
                ai_action = f"controlled appliances: {result['output_appliances_response']}"
            elif result.get("output_search_required"):
                ai_action = f"searched for: {result.get('output_search_query', 'information')}"
            
            update_conversation_summary(
                user_id=user_id,
                user_input=transcribed_text,
                ai_action=ai_action,
                ai_response=result.get("output_natural_response", ""),
                ai_output_data=result
            )
        
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
        conversation_contexts[user_id] = []
    
    return {"status": "success", "message": "Conversation history cleared"}

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
            # 🔧 DEBUG: Log what the web interface is sending
            logger.warning(f"🌐 WEB INTERFACE REQUEST: ducky_script='{data['ducky_script']}', password='{data.get('password')}', repeat={data.get('repeat', False)}")
            
            # Accept password and repeat from request if provided
            ducky_payload = {
                "script": data["ducky_script"],
                "password": data.get("password"),
                "repeat": data.get("repeat", False)
            }
            success = publish_ducky_script_to_mqtt(ducky_payload)
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

@router.post("/reset_last_command")
async def reset_last_command_endpoint():
    """Reset the last executed command to allow re-execution"""
    try:
        reset_last_command()
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": "Last command reset successfully"}
        )
    except Exception as e:
        logger.error(f"Error resetting last command: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@router.get("/conversation_history")
async def get_conversation_history(user_id: Optional[str] = Header("anonymous_user")):
    """Get current conversation history for a user with detailed analysis"""
    try:
        conversations = conversation_contexts.get(user_id, [])
        formatted_context = get_conversation_context(user_id)
        preferences = extract_user_preferences(conversations) if conversations else {}
        
        return JSONResponse(
            status_code=200,
            content={
                "user_id": user_id,
                "conversation_summaries": conversations,
                "formatted_context": formatted_context,
                "extracted_preferences": preferences,
                "total_conversations": len(conversations),
                "has_context": bool(conversations),
                "learning_analysis": {
                    "has_corrections": any(conv.get('user_intent') == 'correction_feedback' for conv in conversations),
                    "preferred_delays_learned": len(preferences.get('preferred_delays', [])),
                    "apps_used": len(preferences.get('specific_apps', [])),
                    "corrections_count": len(preferences.get('corrections_made', []))
                }
            }
        )
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@router.post("/test_ducky_format")
async def test_ducky_format():
    """Test the exact ducky script format that ESP32 expects"""
    try:
        test_payload = {
            "script": "GUI r\nDELAY 300\nSTRING notepad\nENTER",
            "password": "E1s2t3e4r5",
            "repeat": True
        }
        success = publish_ducky_script_to_mqtt(test_payload)
        return JSONResponse(
            status_code=200,
            content={
                "status": "success" if success else "failed",
                "message": "Test ducky script sent with correct format",
                "payload": test_payload
            }
        )
    except Exception as e:
        logger.error(f"Error testing ducky format: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@router.post("/demo_conversation")
async def demo_conversation(user_id: Optional[str] = Header("demo_user")):
    """Demonstrate conversation system with sample data"""
    try:
        # Clear existing conversation
        conversation_contexts[user_id] = []
        
        # Add sample conversations with realistic correction scenario
        sample_conversations = [
            {
                "user_input": "open notepad and write hello world", 
                "ai_action": "executed computer command: GUI r\\nDELAY 300\\nSTRING notepad\\nENTER\\nDELAY 500\\nSTRING hello world",
                "ai_response": "I'll open notepad and write 'hello world' for you.",
                "ai_output_data": {"output_ducky_script": "GUI r\\nDELAY 300\\nSTRING notepad\\nENTER\\nDELAY 500\\nSTRING hello world"}
            },
            {
                "user_input": "hey you forgot the delay part which I said after opening should be 2000ms", 
                "ai_action": "executed computer command with correction: GUI r\\nDELAY 300\\nSTRING notepad\\nENTER\\nDELAY 2000\\nSTRING hello world",
                "ai_response": "You're absolutely right! I'll use 2000ms delay after opening as you requested. Let me correct that.",
                "ai_output_data": {"output_ducky_script": "GUI r\\nDELAY 300\\nSTRING notepad\\nENTER\\nDELAY 2000\\nSTRING hello world"}
            },
            {
                "user_input": "do it again", 
                "ai_action": "executed computer command: GUI r\\nDELAY 300\\nSTRING notepad\\nENTER\\nDELAY 2000\\nSTRING hello world",
                "ai_response": "Opening notepad again with the 2000ms delay you prefer.",
                "ai_output_data": {"output_ducky_script": "GUI r\\nDELAY 300\\nSTRING notepad\\nENTER\\nDELAY 2000\\nSTRING hello world"}
            }
        ]
        
        for conv in sample_conversations:
            update_conversation_summary(
                user_id, 
                conv["user_input"], 
                conv["ai_action"], 
                conv["ai_response"],
                conv["ai_output_data"]
            )
        
        context = get_conversation_context(user_id)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Demo conversation history created",
                "conversation_context": context,
                "total_conversations": len(conversation_contexts[user_id])
            }
        )
    except Exception as e:
        logger.error(f"Error creating demo conversation: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@router.post("/intelligent-search")
async def intelligent_search_endpoint(request: SearchRequest) -> IntelligentSearchResponse:
    """
    NEW intelligent search endpoint with AI URL scoring + parallel processing.
    
    Features:
    - Collects 5x more URLs than requested
    - Uses AI (Llama 3.3 70B primary, Llama Scout fallback) to score URL relevance
    - Uses hardware-aware parallel scraping for efficient results
    - Returns comprehensive results with AI insights and performance metrics
    """
    try:
        logger.info(f"Intelligent search request: {request.query}")
        
        result = await intelligent_search_engine.intelligent_search_and_scrape(
            query=request.query,
            num_results=request.num_results,
            use_ai_scoring=request.use_ai_scoring
        )
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Intelligent search error: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "error": str(e),
                "query": request.query,
                "results": [],
                "ai_insights": {"summary": "Search failed", "recommendations": str(e)},
                "performance_metrics": {"total_duration": 0, "error": True},
                "hardware_stats": {},
                "search_metadata": {},
                "intelligent_features": {}
            }
        )

@router.post("/real-search")
async def real_search_endpoint(request: SearchRequest) -> EnhancedSearchResponse:
    """
    Enhanced search with multiple engines endpoint.
    
    Features:
    - Multiple search engine aggregation
    - Parallel content scraping
    - Hardware-aware processing
    - Performance metrics
    """
    try:
        logger.info(f"Enhanced search request: {request.query}")
        
        result = await enhanced_search_engine.enhanced_search(
            query=request.query,
            num_results=request.num_results
        )
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Enhanced search error: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "error": str(e),
                "query": request.query,
                "results": [],
                "metadata": {},
                "search_insights": {}
            }
        )

@router.get("/search")
async def legacy_search_endpoint(query: str = "current weather") -> Dict:
    """
    Legacy direct search endpoint (maintains backward compatibility).
    """
    try:
        logger.info(f"Legacy search request: {query}")
        result = perform_search(query)
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Legacy search error: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "error": str(e)}
        )

@router.post("/scrape")
async def scrape_endpoint(request: ScrapeRequest) -> SimpleScrapeResponse:
    """
    Direct URL scraping endpoint.
    
    Features:
    - Direct URL content extraction
    - Clean content processing
    - Metadata extraction
    """
    try:
        logger.info(f"Scrape request: {request.url}")
        
        result = await enhanced_search_engine.simple_scrape(request.url)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Scrape error: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "error": str(e),
                "url": request.url,
                "content": "",
                "metadata": {}
            }
        )

@router.get("/system-status")
async def system_status_endpoint() -> SystemStatusResponse:
    """
    Get intelligent search engine system status.
    
    Returns:
    - Component status
    - Hardware performance
    - Capabilities and recommendations
    """
    try:
        logger.info("System status request")
        
        result = await intelligent_search_engine.get_system_status()
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"System status error: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "error": str(e),
                "components": {},
                "current_performance": {},
                "hardware_info": {},
                "recommendations": {},
                "capabilities": {}
            }
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