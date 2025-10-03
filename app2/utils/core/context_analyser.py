"""
Alice AI Assistant - Context Analyzer (Clean & Optimized)
Single function interface with Groq caching optimization
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

API_KEYS = [
    os.getenv('GROQ_API_KEY'),
    os.getenv('GROQ_API_KEY_ALT_1'), 
    os.getenv('GROQ_API_KEY_ALT_2'),
    os.getenv('GROQ_API_KEY_ALT_3'),
    os.getenv('GROQ_API_KEY_ALT_4')
]

CONTEXT_ANALYZER_API_ORDER = [
    'GROQ_API_KEY',           # Primary for context analysis
    'GROQ_API_KEY_ALT_3',
    'GROQ_API_KEY_ALT_4',
    'GROQ_API_KEY_ALT_1', 
    'GROQ_API_KEY_ALT_2'
]

AVAILABLE_API_KEYS = [key for key in API_KEYS if key and key.strip()]
if not AVAILABLE_API_KEYS:
    raise ValueError("No valid GROQ API keys found in environment variables.")

# ==================== GLOBAL PROMPT VARIABLES (CACHED) ====================

ALICE_SYSTEM_PROMPT = """You are ALICE, an advanced AI assistant with a warm, helpful personality and sophisticated reasoning capabilities.

                        ## YOUR CORE IDENTITY
                        - Personality: Warm, professional, proactive, solution-oriented assistant
                        - Communication: Natural, engaging, keeps users informed during processing
                        - Approach: Think step-by-step, explain reasoning, anticipate user needs
                        - Goal: Maximize user success while building trust and confidence
                        
                        ## YOUR AVAILABLE TOOLS (Think Carefully!)
                        
                        **SEARCH_TOOL**: Web search capabilities
                        - Purpose: Find current information, latest facts, news, data you don't know
                        - Use when: User asks about recent events, current trends, unknown information
                        - Think: "Do I lack current information needed to answer this fully?"
                        
                        **MEMORY_TOOL**: Conversation history access  
                        - Purpose: Recall previous discussions, user preferences, project continuity
                        - Use when: User references past conversations or expects personal context
                        - Think: "Does this query reference our previous interactions?"
                        
                        **COMPUTER_CONTROL**: Complete computer interaction system
                        - Purpose: ANY task involving the user's computer (THIS IS YOUR PRIMARY TOOL)
                        - Capabilities: Programming, debugging, visual inspection, file operations, messaging, scheduling, error fixing, system tasks
                        - Use when: User needs computer assistance of ANY kind
                        - Think: "Does this involve interacting with the user's computer in any way?"
                        
                        ## CRITICAL THINKING PROCESS (Execute for Every Query)
                        1. **Query Analysis**: What is the user really asking for?
                        2. **Capability Assessment**: What tools do I have that can help?
                        3. **Tool Logic**: 
                           - Need current info? → SEARCH
                           - Reference past conversations? → MEMORY  
                           - ANY computer interaction? → COMPUTER_CONTROL (includes programming!)
                        4. **Sequence Planning**: What's the logical order of operations?
                        5. **User Engagement**: How do I keep them informed while processing?
                        
                        ## TASK SEQUENCING
                        - ">" = Sequential (do this, then that)
                        - "=" = Parallel (do these simultaneously)  
                        - "+" = Combined (merge these together)
                        
                        ## USER ENGAGEMENT STRATEGY
                        - Always acknowledge the user's request immediately
                        - Provide engaging status updates during processing
                        - Show confidence in your abilities
                        - Ask for clarification only when genuinely needed
                        - Explain your tool choices briefly
                        
                        ## RECALL SYSTEM
                        If you need more information from the user:
                        - Set recall_needed = true
                        - Provide specific recall_questions
                        - Summarize current state for continuation
                        - Be clear about what you need and why
                        
                        ## OUTPUT REQUIREMENTS
                        Always respond in valid JSON with ALL required fields:
                        - tool_activation (3 booleans only)
                        - task_sequence (using >, =, + symbols)
                        - immediate_response (engaging user message)
                        - recall_needed (if clarification needed)
                        - conversation_summary (REQUIRED FIELD!)
                        - conversation_report (complete report for storage)

                        ## RECALL INFORMATION PROCESSING
                        When recall_req = 1:
                        - If recall_info is provided: Analyze both recall information and user query together
                        - If recall_info is missing: Consider activating memory tool to retrieve needed context
                        - Always acknowledge recall context in your immediate_response
                        - Factor recall information into your tool_reasoning and task_sequence planning
                        
                        RECALL PROCESSING EXAMPLES:
                        - recall_req=1 + recall_info="Previous Python project details..." → Use this context with current query
                        - recall_req=1 + no recall_info → May need memory tool to get missing context
                        - recall_req=0 → Process user query normally without special recall handling
                                                
                        Remember: Programming = computer_control, Error fixing = computer_control, Any computer task = computer_control"""

RECALL_SYSTEM_PROMPT = """
                       ## RECALL SYSTEM ENHANCEMENT
                       
                       When you receive a query with Query Type: "RECALL_REQUEST":
                       - The query contains RECALL CONTEXT followed by USER FOLLOW-UP QUERY
                       - The RECALL CONTEXT provides information previously requested from the user
                       - The USER FOLLOW-UP QUERY is the new user input incorporating that information
                       - Process both pieces of information together for comprehensive analysis
                       - Consider the recall context as fulfilled requirements from previous interaction
                       - Focus on what the user wants to do next with the provided information
                       
                       When you receive a query with Query Type: "INITIAL_REQUEST":
                       - This is a fresh user query without recall context
                       - Process normally according to standard analysis procedures
                       - If you need more information, set recall_needed = true with specific questions
                       
                       RECALL PROCESSING GUIDELINES:
                       - If recall_needed was true in a previous interaction and now you have RECALL_REQUEST, acknowledge the provided information
                       - Use the recall context to enhance your understanding of the user's needs
                       - Combine recall context with the new query to provide more targeted tool recommendations
                       - If the recall context is insufficient, you may still request additional information
                       """

# ALICE TOOLS DESCRIPTION (CACHED PART)
ALICE_TOOLS_EXAMPLES = """
                       ## TOOL USAGE EXAMPLES:
                       
                       ### SEARCH_TOOL Examples:
                       - "What's the weather today?" → use_search=true (need current weather data)
                       - "Latest news about AI?" → use_search=true (need recent information)
                       - "Current stock price of Apple?" → use_search=true (need live data)
                       
                       ### MEMORY_TOOL Examples:
                       - "Remember our Python project?" → use_memory=true (recall previous work)
                       - "What was my preference last time?" → use_memory=true (access user history)
                       - "Continue where we left off" → use_memory=true (get conversation context)
                       
                       ### COMPUTER_CONTROL Examples:
                       - "Help me debug this code" → use_computer_control=true (programming task)
                       - "Create a Python script" → use_computer_control=true (code generation)
                       - "Fix this error message" → use_computer_control=true (troubleshooting)
                       - "Send an email" → use_computer_control=true (system interaction)
                       - "Schedule a meeting" → use_computer_control=true (calendar management)
                       """

# ALICE JSON RESPONSE FORMAT (CACHED PART)
ALICE_JSON_FORMAT = """
                    ## MANDATORY OUTPUT FORMAT
                    You MUST respond in this EXACT JSON format with ALL required fields:
                    
                    {
                        "conversation_id": "string",
                        "user_query": "string", 
                        "analysis_timestamp": "string",
                        
                        "tool_activation": {
                            "use_search": boolean,
                            "use_memory": boolean,
                            "use_computer_control": boolean
                        },
                        
                        "task_sequence": "string (e.g. 'memory>computer', 'search=computer')",
                        "sequence_explanation": "string (why this sequence)",
                        "tool_reasoning": "string (why these specific tools were chosen)",
                        
                        "immediate_response": "string (Alice's engaging response to user)",
                        "response_tone": "string (helpful/enthusiastic/concerned/etc)",
                        
                        "recall_needed": boolean,
                        "recall_reason": "string or null",
                        "recall_questions": ["array of specific clarification questions"],
                        "current_state_summary": "string (current state for continuation)",
                        
                        "error_detected": boolean,
                        "error_details": "string or null",
                        "previous_dissatisfaction": boolean,
                        
                        "conversation_summary": "string (REQUIRED - summary of this conversation)",
                        "key_topics": ["array of main topics"],
                        "user_intent": "string (what user really wants)",
                        "complexity_level": "simple/moderate/complex",
                        "next_steps": ["array of planned actions"],
                        "estimated_completion_time": "string",
                        
                        "variables_needed": {
                            "additional_user_info": ["array"],
                            "context_requirements": ["array"]
                        },
                        
                        "conversation_report": {
                            "conversation_id": "string",
                            "timestamp": "string",
                            "user_query": "string",
                            "tools_required": ["array of tool names needed"],
                            "tasks_performed": ["array of tasks completed"],
                            "tasks_planned": ["array of future tasks"],
                            "conversation_state": "active/waiting_for_user/completed/error",
                            "key_topics": ["array of main topics"],
                            "user_satisfaction_indicators": "positive/neutral/negative/unknown",
                            "outcomes": ["array of results/decisions"],
                            "context_for_future": "string (summary for future reference)",
                            "error_occurred": boolean,
                            "error_description": "string or null",
                            "followup_needed": boolean,
                            "priority_level": "low/medium/high"
                        }
                    }
                    
                    CRITICAL RULES:
                    - NEVER omit any field from the JSON structure above
                    - ALWAYS use exact field names as shown
                    - ALWAYS return valid JSON (no extra text before or after)
                    - If uncertain about a value, use null or empty string/array as appropriate
                    """

# ==================== UTILITY FUNCTIONS ====================

def check_groq_availability() -> bool:
    """Check if Groq is available and at least one API key is configured"""
    try:
        from groq import Groq
        return len(AVAILABLE_API_KEYS) > 0
    except ImportError:
        return False

def get_api_key_by_name(key_name: str) -> str:
    """Get API key by environment variable name"""
    key_map = {
        'GROQ_API_KEY': 0,
        'GROQ_API_KEY_ALT_1': 1,
        'GROQ_API_KEY_ALT_2': 2,
        'GROQ_API_KEY_ALT_3': 3,
        'GROQ_API_KEY_ALT_4': 4
    }
    
    index = key_map.get(key_name)
    if index is not None and index < len(API_KEYS):
        return API_KEYS[index]
    return None

def make_groq_request_with_fallback(messages, model, temperature=0.7, max_tokens=1500, api_key_priority_order=None):
    """
    Universal Groq request with automatic fallback - IMPROVED ERROR HANDLING
    """
    
    # Check if we have any API keys
    if not AVAILABLE_API_KEYS:
        logger.error("❌ No API keys available at all!")
        return None
    
    # Default order if not specified
    if api_key_priority_order is None:
        api_key_priority_order = [
            'GROQ_API_KEY',
            'GROQ_API_KEY_ALT_3',
            'GROQ_API_KEY_ALT_4',
            'GROQ_API_KEY_ALT_1', 
            'GROQ_API_KEY_ALT_2'
        ]
    
    last_error = None
    
    for key_name in api_key_priority_order:
        api_key = get_api_key_by_name(key_name)
        
        if not api_key or not api_key.strip():
            logger.warning(f"⚠️ API key {key_name} not found or empty")
            continue
            
        try:
            logger.info(f"🔑 Trying API key: {key_name}")
            client = Groq(api_key=api_key)
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # CHECK IF RESPONSE IS VALID
            if response and hasattr(response, 'choices') and response.choices:
                logger.info(f"✅ Successfully used API key: {key_name}")
                return response
            else:
                logger.warning(f"⚠️ Invalid response structure from {key_name}")
                continue
            
        except Exception as e:
            error_str = str(e).lower()
            logger.warning(f"❌ API key {key_name} failed: {e}")
            last_error = e
            
            # Check for rate limit errors
            rate_limit_indicators = [
                'rate limit', 'too many requests', 'quota exceeded', 
                'tokens exhausted', '429', 'rate_limit_exceeded',
                'insufficient_quota', 'billing', 'usage limit'
            ]
            
            if any(indicator in error_str for indicator in rate_limit_indicators):
                logger.warning(f"⏳ Rate limit hit on {key_name}, trying next key...")
                continue
            else:
                logger.error(f"🔥 Non-rate-limit error on {key_name}: {e}")
                continue
    
    # All keys failed
    logger.error(f"❌ ALL API KEYS FAILED! Last error: {last_error}")
    return None

def generate_conversation_id() -> str:
    """Generate time-based unique conversation ID"""
    timestamp = int(time.time() * 1000)
    return f"conv_{timestamp}"

def extract_topics(user_query: str) -> List[str]:
    """Extract key topics from user query"""
    query_lower = user_query.lower()
    topics = []
    
    # Weather related
    if any(word in query_lower for word in ['weather', 'temperature', 'rain', 'sunny', 'cloudy']):
        topics.append('weather')
    
    # Programming related
    if any(word in query_lower for word in ['code', 'python', 'javascript', 'programming', 'debug', 'error']):
        topics.append('programming')
    
    # System/computer related
    if any(word in query_lower for word in ['computer', 'system', 'file', 'install', 'setup']):
        topics.append('computer_assistance')
    
    # Communication related  
    if any(word in query_lower for word in ['message', 'email', 'send', 'schedule']):
        topics.append('communication')
    
    # Information seeking
    if any(word in query_lower for word in ['what', 'how', 'when', 'where', 'search', 'find']):
        topics.append('information_request')
    
    # Memory/history related
    if any(word in query_lower for word in ['remember', 'previous', 'before', 'last time']):
        topics.append('memory_access')
    
    return topics if topics else ['general_assistance']

def assess_priority(user_query: str) -> str:
    """Assess priority level based on query content"""
    query_lower = user_query.lower()
    
    # High priority indicators
    if any(word in query_lower for word in ['urgent', 'emergency', 'error', 'broken', 'fix', 'help']):
        return 'high'
    
    # Low priority indicators
    if any(word in query_lower for word in ['maybe', 'sometime', 'when you can', 'no rush']):
        return 'low'
    
    return 'medium'

def format_previous_conversations(conversations: List[Dict]) -> str:
    """Format previous conversations for context"""
    if not conversations:
        return "No previous conversations available"
    
    formatted = []
    for i, convo in enumerate(conversations[-5:]):  # Last 5 conversations
        convo_id = convo.get('conversation_id', 'unknown')
        
        if 'conversation_report' in convo:
            # New format with full report
            full_report = convo['conversation_report']
            formatted.append(
                f"[{i+1}] Conversation ID: {convo_id}\n"
                f"    State: {full_report.get('conversation_state', 'unknown')}\n"
                f"    Topics: {', '.join(full_report.get('all_topics', []))}\n"
                f"    Tools Used: {', '.join(full_report.get('all_tools_used', []))}\n"
                f"    Context: {full_report.get('context_for_future', 'No context')}"
            )
        else:
            # Fallback for old format
            summary = convo.get('summary', 'No summary')
            timestamp = convo.get('timestamp', 'Unknown time')
            topics = convo.get('key_topics', [])
            
            formatted.append(
                f"[{i+1}] ID: {convo_id} | {timestamp}\n"
                f"    Summary: {summary}\n"
                f"    Topics: {', '.join(topics)}"
            )
    
    return "\n\n".join(formatted)

# ==================== MAIN ANALYSIS FUNCTION ====================

async def analyze_query(user_query: str,
                       conversation_id: str = None,
                       user_context: Dict[str, Any] = None,
                       previous_conversations: List[Dict] = None,
                       recall_info: str = None,
                       recall_req: int = 0) -> Dict[str, Any]:
    
    """
    MAIN ALICE CONTEXT ANALYZER FUNCTION - Fixed with proper error handling
    """
    
    # Generate conversation ID if not provided
    if not conversation_id:
        conversation_id = generate_conversation_id()
    
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_details = user_context or {}
    prev_convos = previous_conversations or []
    
    logger.info(f"Alice analyzing query for conversation {conversation_id}")
    
    try:
        # BUILD CACHED SYSTEM PROMPT
        system_prompt = ALICE_SYSTEM_PROMPT + "\n\n" + RECALL_SYSTEM_PROMPT + "\n\n" + ALICE_TOOLS_EXAMPLES + "\n\n" + ALICE_JSON_FORMAT
        
        # BUILD DYNAMIC USER PROMPT
        recall_context = ""
        if recall_req == 1 and recall_info:
            recall_context = f"""
RECALL INFORMATION PROVIDED:
{recall_info}

COMBINED QUERY CONTEXT:
The user has provided additional recall information above. Analyze both the recall information and the user query together to provide comprehensive assistance.
"""
        elif recall_req == 1 and not recall_info:
            recall_context = """
RECALL REQUEST NOTED:
User has indicated they need recall assistance (recall_req=1) but no specific recall information was provided. Consider if memory tool activation is needed.
"""
        
        user_prompt = f"""
CONTEXT VARIABLES:
- Conversation ID: {conversation_id}
- Current Date/Time: {current_datetime}
- User Details: {json.dumps(user_details, indent=2) if user_details else 'None available'}
- Previous Conversations: {len(prev_convos)} complete conversation reports available
- Recall Request Status: {'ACTIVE (recall_req=1)' if recall_req == 1 else 'INACTIVE (recall_req=0)'}
- Recall Information: {'PROVIDED' if recall_info else 'NOT PROVIDED'}

{recall_context}

PREVIOUS CONVERSATION CONTEXT:
{format_previous_conversations(prev_convos)}

USER QUERY TO ANALYZE:
"{user_query}"

ANALYZE THIS QUERY AS ALICE AND RESPOND IN EXACT JSON FORMAT
"""

        # Make Groq request with error handling
        response = make_groq_request_with_fallback( 
            messages=[
                {"role": "system", "content": system_prompt},    
                {"role": "user", "content": user_prompt}       
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=1500,
            api_key_priority_order=CONTEXT_ANALYZER_API_ORDER
        )
        
        # CHECK IF RESPONSE IS NONE
        if response is None:
            logger.error("❌ Groq API returned None - all API keys failed")
            return create_fallback_response(user_query, conversation_id)
        
        # CHECK IF RESPONSE HAS CHOICES
        if not hasattr(response, 'choices') or not response.choices:
            logger.error("❌ Groq response has no choices")
            return create_fallback_response(user_query, conversation_id)
        
        # CHECK IF FIRST CHOICE HAS MESSAGE
        if not hasattr(response.choices[0], 'message') or not response.choices[0].message:
            logger.error("❌ Groq response choice has no message")
            return create_fallback_response(user_query, conversation_id)
        
        alice_response = response.choices[0].message.content
        
        # CHECK IF CONTENT IS EMPTY
        if not alice_response or not alice_response.strip():
            logger.error("❌ Groq response content is empty")
            return create_fallback_response(user_query, conversation_id)
        
        alice_response = response.choices[0].message.content
        
        # CHECK IF CONTENT IS EMPTY
        if not alice_response or not alice_response.strip():
            logger.error("❌ Groq response content is empty")
            return create_fallback_response(user_query, conversation_id)
        
        alice_response = alice_response.strip()
        analysis_result = parse_alice_response(alice_response, conversation_id, user_query)
        
        # CHECK IF PARSING RETURNED NONE - CRITICAL FIX
        if analysis_result is None:
            logger.error("❌ Failed to parse Alice response - using fallback")
            analysis_result = create_fallback_response(user_query, conversation_id)
        
        # SAFE creation of conversation update
        try:
            analysis_result['full_conversation_update'] = create_conversation_update(
                conversation_id, user_query, analysis_result, prev_convos
            )
        except Exception as e:
            logger.error(f"❌ Failed to create conversation update: {e}")
            analysis_result['full_conversation_update'] = None
        
        logger.info(f"✅ Alice analysis complete for conversation {conversation_id}")
        return analysis_result
        
    except Exception as e:
        logger.error(f"❌ Alice context analysis failed: {e}")
        logger.exception("Full error details:")
        return create_fallback_response(user_query, conversation_id)

# ==================== HELPER FUNCTIONS ====================

def parse_alice_response(response: str, conversation_id: str, user_query: str) -> Dict[str, Any]:
    """Parse Alice's JSON response with error handling"""
    try:
        # Find JSON in response
        start_idx = response.find('{')
        end_idx = response.rfind('}') + 1
        
        if start_idx >= 0 and end_idx > start_idx:
            json_str = response[start_idx:end_idx]
            analysis = json.loads(json_str)
            
            # Ensure required fields exist
            analysis['conversation_id'] = conversation_id
            analysis['user_query'] = user_query
            analysis['analysis_timestamp'] = datetime.now().isoformat()
            
            # Ensure conversationsummary exists
            if 'conversation_summary' not in analysis:
                analysis['conversation_summary'] = f"User requested: {user_query}"
            
            # Ensure variablesneeded exists
            if 'variables_needed' not in analysis:
                analysis['variables_needed'] = {
                    "additional_user_info": [],
                    "context_requirements": []
                }
            
            # Ensure conversationreport exists
            if 'conversation_report' not in analysis:
                analysis['conversation_report'] = create_default_report(conversation_id, user_query, analysis)
            
            return analysis
        else:
            raise ValueError("No JSON found in Alice response")
            
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse Alice response: {e}")
        logger.debug(f"Raw Alice response: {response}")
        
        # ✅ CRITICAL: Always return a valid dict, never None!
        return create_fallback_response(user_query, conversation_id)

def create_fallback_response(user_query: str, conversation_id: str) -> Dict[str, Any]:
    """Fallback response when Alice fails - NEVER returns None"""
    return {
        "conversation_id": conversation_id,
        "user_query": user_query,
        "analysis_timestamp": datetime.now().isoformat(),
        "tool_activation": {
            "use_search": False,
            "use_memory": False,
            "use_computer_control": True
        },
        "task_sequence": "computer",
        "sequence_explanation": "Using computer control for general assistance",
        "tool_reasoning": "Defaulting to computer control as it covers most user needs",
        "immediate_response": "I'm here to help! Let me use my computer capabilities to assist you.",
        "response_tone": "helpful",
        "recall_needed": True,
        "recall_reason": "Need more details to provide specific assistance",
        "recall_questions": ["Could you provide more details about what you need help with?"],
        "current_state_summary": "Ready to assist with computer control capabilities",
        "error_detected": True,
        "error_details": "Failed to parse Alice's analysis, using fallback response",
        "previous_dissatisfaction": False,
        "conversation_summary": f"User requested: {user_query}",
        "key_topics": extract_topics(user_query),
        "user_intent": "request_assistance",
        "complexity_level": "moderate",
        "next_steps": ["await_user_clarification", "provide_computer_assistance"],
        "estimated_completion_time": "depends on specific request",
        "variables_needed": {
            "additional_user_info": [],
            "context_requirements": []
        },
        "conversation_report": create_default_report(conversation_id, user_query),
        "full_conversation_update": create_conversation_update(conversation_id, user_query, {
            "conversation_report": create_default_report(conversation_id, user_query),
            "key_topics": extract_topics(user_query),
            "error_detected": True,
            "error_details": "Fallback response",
            "recall_needed": True
        }, [])
    }

def create_default_report(conversation_id: str, user_query: str, analysis: Dict = None) -> Dict[str, Any]:
    """Create default conversation report"""
    tools_used = []
    if analysis and 'tool_activation' in analysis:
        tools_used = [k.replace('use_', '') for k, v in analysis['tool_activation'].items() if v]
    
    return {
        "conversation_id": conversation_id,
        "timestamp": datetime.now().isoformat(),
        "user_query": user_query,
        "tools_required": tools_used,
        "tasks_performed": [],
        "tasks_planned": analysis.get('next_steps', []) if analysis else ["analyze_user_request"],
        "conversation_state": "active",
        "key_topics": extract_topics(user_query),
        "user_satisfaction_indicators": "unknown",
        "outcomes": [],
        "context_for_future": f"User requested: {user_query[:150]}...",
        "error_occurred": analysis.get('error_detected', False) if analysis else False,
        "error_description": analysis.get('error_details') if analysis else None,
        "followup_needed": analysis.get('recall_needed', True) if analysis else True,
        "priority_level": assess_priority(user_query)
    }

def create_conversation_update(conversation_id: str, 
                               user_query: str, 
                               analysis_result: Dict, 
                               previous_conversations: List) -> Dict[str, Any]:
    
    """Create or update full conversation report - FIXED None handling"""
    
    current_time = datetime.now().isoformat()
    
    # CHECK IF analysis_result is None
    if not analysis_result:
        logger.warning("⚠️ analysis_result is None in create_conversation_update")
        analysis_result = {}
    
    # Check if this conversation already exists
    existing_conversation = None
    if previous_conversations:
        for prev_convo in previous_conversations:
            if prev_convo and prev_convo.get('conversation_id') == conversation_id:
                existing_conversation = prev_convo.get('conversation_report', {})
                break
    
    if existing_conversation:
        # Update existing conversation
        llm_reports = existing_conversation.get('llm_reports', [])
        all_user_queries = existing_conversation.get('all_user_queries', [])
        all_tools_used = existing_conversation.get('all_tools_used', [])
        all_topics = existing_conversation.get('all_topics', [])
        total_llm_calls = existing_conversation.get('total_llm_calls', 0) + 1
    else:
        # New conversation
        llm_reports = []
        all_user_queries = []
        all_tools_used = []
        all_topics = []
        total_llm_calls = 1
    
    # SAFE access to analysis_result fields
    conversation_report = analysis_result.get('conversation_report', {}) if analysis_result else {}
    key_topics = analysis_result.get('key_topics', []) if analysis_result else []
    
    # Add current LLM report
    current_llm_report = {
        "llm_type": "context_analyzer",
        "timestamp": current_time,
        "user_query": user_query,
        "tools_required": conversation_report.get('tools_required', []) if conversation_report else [],
        "tasks_performed": conversation_report.get('tasks_performed', []) if conversation_report else [],
        "tasks_planned": conversation_report.get('tasks_planned', []) if conversation_report else [],
        "key_topics": key_topics,
        "outcomes": conversation_report.get('outcomes', []) if conversation_report else [],
        "error_occurred": analysis_result.get('error_detected', False) if analysis_result else True,
        "error_description": analysis_result.get('error_details') if analysis_result else "Analysis failed",
        "processing_time_seconds": 0.0  # Will be updated by caller
    }
    
    llm_reports.append(current_llm_report)
    all_user_queries.append(user_query)
    
    # SAFE extend operations
    if conversation_report and conversation_report.get('tools_required'):
        all_tools_used.extend(conversation_report.get('tools_required', []))
    if key_topics:
        all_topics.extend(key_topics)
    
    # Remove duplicates safely
    all_tools_used = list(set(all_tools_used)) if all_tools_used else []
    all_topics = list(set(all_topics)) if all_topics else []
    
    return {
        "conversation_id": conversation_id,
        "conversation_start": existing_conversation.get('conversation_start', current_time) if existing_conversation else current_time,
        "conversation_end": None,
        "conversation_state": conversation_report.get('conversation_state', 'active') if conversation_report else 'active',
        "total_llm_calls": total_llm_calls,
        "all_user_queries": all_user_queries,
        "all_tools_used": all_tools_used,
        "all_topics": all_topics,
        "llm_reports": llm_reports,
        "user_satisfaction_indicators": conversation_report.get('user_satisfaction_indicators', 'unknown') if conversation_report else 'unknown',
        "priority_level": conversation_report.get('priority_level', 'medium') if conversation_report else 'medium',
        "followup_needed": analysis_result.get('recall_needed', False) if analysis_result else False,
        "context_for_future": conversation_report.get('context_for_future', '') if conversation_report else ''
    }

def get_tool_execution_order(analysis: Dict[str, Any]) -> List[List[str]]:
    """Parse task sequence into execution order"""
    sequence = analysis.get('task_sequence', '')
    if not sequence:
        return []
    
    # Parse sequence symbols
    steps = []
    sequential_parts = sequence.split('>')
    
    for part in sequential_parts:
        if '=' in part:
            parallel_tools = part.split('=')
            step_tools = []
            for tool in parallel_tools:
                if '+' in tool:
                    step_tools.extend([t.strip() for t in tool.split('+')])
                else:
                    step_tools.append(tool.strip())
            steps.append(step_tools)
        else:
            if '+' in part:
                step_tools = [t.strip() for t in part.split('+')]
            else:
                step_tools = [part.strip()]
            steps.append(step_tools)
    
    # Map tool names to activation keys
    tool_mapping = {
        'search': 'use_search',
        'memory': 'use_memory', 
        'computer': 'use_computer_control'
    }
    
    execution_order = []
    for step in steps:
        mapped_step = []
        for tool in step:
            mapped_tool = tool_mapping.get(tool.lower(), tool)
            if analysis.get('tool_activation', {}).get(mapped_tool, False):
                mapped_step.append(mapped_tool)
        if mapped_step:
            execution_order.append(mapped_step)
    
    return execution_order

# ==================== CONVENIENCE FUNCTION ====================

async def analyze_user_query(query: str,
                           conversation_id: str = None,
                           user_context: Dict = None,
                           previous_conversations: List = None,
                           recall_info: str = None,
                           recall_req: int = 0) -> Dict[str, Any]:
    """Quick function to analyze user query - backward compatibility with recall support"""
    return await analyze_query(query, conversation_id, user_context, previous_conversations, recall_info, recall_req)
