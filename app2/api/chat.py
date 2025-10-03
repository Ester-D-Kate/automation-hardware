"""
Alice Chat API - Complete Universal Orchestrator
Single endpoint handling all workflows with proper error handling
"""

from fastapi import APIRouter, HTTPException
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from api.schemas import VariablesNeeded
from api.schemas import SimpleChatRequest, SimpleChatResponse, generate_conversation_id, ConversationReport, FullConversationReport, LLMReport, ToolActivation
from utils.core.context_analyser import analyze_query
import json
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory storage for conversation states
conversation_states = {}

@router.post("/chat", response_model=SimpleChatResponse)  # ✅ Single route declaration
async def chat_with_alice(request: SimpleChatRequest):
    """
    🌐 UNIVERSAL ALICE ORCHESTRATOR
    
    Single endpoint for ALL user interactions with proper conversation management
    """
    try:
        start_time = time.time()
        
        # Check user conversation state
        user_conversation_state = conversation_states.get(request.user_id)
        
        recall_req = 0
        recall_info = None
        conversation_id = None
        
        if user_conversation_state and user_conversation_state.get('req_info', False):
            # This is a recall response - user is providing requested information
            recall_req = 1
            recall_info = user_conversation_state.get('stored_context', '')
            conversation_id = user_conversation_state.get('conversation_id')
            
            logger.info(f"📝 Processing recall response for user {request.user_id} | Conv: {conversation_id}")
            logger.info(f"Recall info: {recall_info[:100]}...")
            logger.info(f"User response: {request.user_query[:100]}...")
        else:
            # This is a new query - create new conversation
            conversation_id = generate_conversation_id()
            logger.info(f"🆕 Starting new conversation for user {request.user_id} | Conv: {conversation_id}")
            logger.info(f"Query: {request.user_query[:100]}...")
        
        # Call Alice context analyzer with recall parameters
        analysis_result = await analyze_query(
            user_query=request.user_query,
            conversation_id=conversation_id,
            user_context={"user_id": request.user_id},
            previous_conversations=None,  # Simplified for now
            recall_info=recall_info,
            recall_req=recall_req
        )
        
        processing_time = time.time() - start_time
        
        # Update conversation state based on Alice's response
        if analysis_result.get('recall_needed', False):
            # Alice needs more information - store conversation state
            conversation_states[request.user_id] = {
                'conversation_id': conversation_id,
                'req_info': True,
                'stored_context': f"Previous query: {request.user_query}\nAlice's questions: {json.dumps(analysis_result.get('recall_questions', []))}",
                'analysis_result': analysis_result.copy(),
                'created_at': time.time()
            }
            logger.info(f"💾 Stored conversation state for user {request.user_id} - waiting for recall")
        else:
            # Conversation is complete or doesn't need recall - clear state
            if request.user_id in conversation_states:
                del conversation_states[request.user_id]
                logger.info(f"🧹 Cleared conversation state for user {request.user_id} - conversation complete")
        
        # Add processing time to analysis result
        analysis_result['processing_time'] = processing_time
        
        # Create simplified response
        response = SimpleChatResponse(**analysis_result)
        
        logger.info(f"✅ Alice response complete in {processing_time:.2f}s | Recall: {analysis_result.get('recall_needed', False)}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Alice chat failed: {str(e)}")
        
        # Clear conversation state on error
        if request.user_id in conversation_states:
            del conversation_states[request.user_id]
            
        # Return fallback response
        return create_fallback_response(request, str(e), time.time() - start_time)

# ==================== HELPER FUNCTIONS ====================

def create_fallback_response(request: SimpleChatRequest, error_msg: str, processing_time: float) -> SimpleChatResponse:
    """Create fallback response when system fails"""
    fallback_conversation_id = generate_conversation_id()
    
    return SimpleChatResponse(
        conversation_id=fallback_conversation_id,
        user_query=request.user_query,
        analysis_timestamp=datetime.now().isoformat(),
        tool_activation=ToolActivation(use_search=False, use_memory=False, use_computer_control=True),
        task_sequence="computer",
        sequence_explanation="Using fallback computer assistance due to system error",
        tool_reasoning="Error occurred, defaulting to general computer help",
        immediate_response="I encountered a technical issue, but I'm still here to help! Could you please rephrase your request?",
        response_tone="helpful",
        recall_needed=True,
        recall_reason="System error occurred",
        recall_questions=["Could you please rephrase your request?"],
        current_state_summary="Error recovery mode",
        error_detected=True,
        error_details=error_msg,
        previous_dissatisfaction=False,
        conversation_summary=f"Error processing: {request.user_query}",
        key_topics=["error_recovery"],
        user_intent="request_assistance",
        complexity_level="simple",
        next_steps=["await_user_clarification"],
        estimated_completion_time="immediate",
        variables_needed=VariablesNeeded(
            additional_user_info=["clearer request"],
            context_requirements=[]
        ),
        conversation_report=ConversationReport(
            conversation_id=fallback_conversation_id,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_query=request.user_query,
            tools_required=[],
            tasks_performed=["error_handling"],
            tasks_planned=["await_clarification"],
            conversation_state="waiting_for_user",
            key_topics=["error_recovery"],
            user_satisfaction_indicators="unknown",
            outcomes=["fallback_response_provided"],
            context_for_future=f"System error occurred with query: {request.user_query}",
            error_occurred=True,
            error_description=error_msg,
            followup_needed=True,
            priority_level="medium"
        ),
        full_conversation_update=FullConversationReport(
            conversation_id=fallback_conversation_id,
            conversation_start=datetime.now().isoformat(),
            conversation_end=None,
            conversation_state="waiting_for_user",
            total_llm_calls=0,
            all_user_queries=[request.user_query],
            all_tools_used=[],
            all_topics=["error_recovery"],
            llm_reports=[],
            user_satisfaction_indicators="unknown",
            priority_level="medium",
            followup_needed=True,
            context_for_future=f"System error: {error_msg}"
        ),
        processing_time=processing_time,
        llm_calls=0
    )

# ==================== ADMIN ENDPOINTS (OPTIONAL) ====================

@router.get("/chat/status/{user_id}")
async def get_user_conversation_status(user_id: str):
    """Get current conversation status for a user"""
    try:
        user_state = conversation_states.get(user_id)
        
        if not user_state:
            return {
                "user_id": user_id,
                "has_active_conversation": False,
                "req_info_active": False,
                "conversation_id": None
            }
        
        return {
            "user_id": user_id,
            "has_active_conversation": True,
            "req_info_active": user_state.get('req_info', False),
            "conversation_id": user_state.get('conversation_id'),
            "waiting_for_response_since": user_state.get('created_at'),
            "stored_context_preview": user_state.get('stored_context', '')[:200] + "..." if len(user_state.get('stored_context', '')) > 200 else user_state.get('stored_context', '')
        }
        
    except Exception as e:
        logger.error(f"Failed to get user status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/chat/clear/{user_id}")
async def clear_user_conversation(user_id: str):
    """Clear/Reset user's conversation state"""
    try:
        if user_id in conversation_states:
            del conversation_states[user_id]
            logger.info(f"🧹 Manually cleared conversation state for user {user_id}")
            return {"message": f"Conversation state cleared for user {user_id}"}
        else:
            return {"message": f"No active conversation found for user {user_id}"}
            
    except Exception as e:
        logger.error(f"Failed to clear user conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
