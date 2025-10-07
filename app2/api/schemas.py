"""
Alice Search Engine - Enhanced Conversation Schemas
Complete conversation tracking with full reports + Simplified Chat API
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime
import time

class QualityTier(str, Enum):
    """Content quality tiers"""
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD" 
    ACCEPTABLE = "ACCEPTABLE"
    POOR = "POOR"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"

# ==================== NEW SIMPLIFIED CHAT SCHEMAS ====================

class SimpleChatRequest(BaseModel):
    """
    Simplified chat request - only user_id and user_query needed
    System automatically handles recall detection
    """
    user_id: str = Field(..., min_length=1, max_length=100, description="Unique user identifier")
    user_query: str = Field(..., min_length=1, max_length=2000, description="User's message to Alice")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or not v.strip():
            raise ValueError('User ID cannot be empty')
        return v.strip()
    
    @validator('user_query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('User query cannot be empty')
        return v.strip()

class ToolActivation(BaseModel):
    """Tool activation flags"""
    use_search: bool = Field(False, description="Whether to use search tool")
    use_memory: bool = Field(False, description="Whether to use memory tool")
    use_computer_control: bool = Field(False, description="Whether to use computer control")

class VariablesNeeded(BaseModel):
    additional_user_info: List[str] = Field(default_factory=list)
    context_requirements: List[str] = Field(default_factory=list)

class ConversationReport(BaseModel):
    conversation_id: str
    timestamp: str
    user_query: str
    tools_required: List[str] = Field(default_factory=list)
    tasks_performed: List[str] = Field(default_factory=list)
    tasks_planned: List[str] = Field(default_factory=list)
    conversation_state: str = "active"
    key_topics: List[str] = Field(default_factory=list)
    user_satisfaction_indicators: str = "unknown"
    outcomes: List[str] = Field(default_factory=list)
    context_for_future: str = ""
    error_occurred: bool = False
    error_description: Optional[str] = None
    followup_needed: bool = False
    priority_level: str = "medium"

class SimpleChatResponse(BaseModel):
    """Complete response matching context analyzer output"""
    conversation_id: str
    user_query: str
    analysis_timestamp: str
    tool_activation: ToolActivation
    task_sequence: str
    sequence_explanation: str
    tool_reasoning: str
    immediate_response: str
    response_tone: str
    recall_needed: bool = False
    recall_reason: Optional[str] = None
    recall_questions: List[str] = Field(default_factory=list)
    current_state_summary: str = ""
    error_detected: bool = False
    error_details: Optional[str] = None
    previous_dissatisfaction: bool = False
    conversation_summary: str
    key_topics: List[str] = Field(default_factory=list)
    user_intent: str
    complexity_level: str = "moderate"
    next_steps: List[str] = Field(default_factory=list)
    estimated_completion_time: str = ""
    variables_needed: VariablesNeeded
    conversation_report: ConversationReport
    processing_time: float = 0.0
    llm_calls: int = 1
    full_conversation_update: Optional[Dict[str, Any]] = None

# ==================== UNIFIED INPUT FOR SEARCH/SCRAPER ====================

class UnifiedRequest(BaseModel):
    """Unified request schema for both search and scraper endpoints"""
    query: str = Field(..., min_length=2, max_length=500, description="Search query")
    max_results: int = Field(5, ge=1, le=15, description="Maximum number of results")
    url_multiplier: int = Field(4, ge=2, le=10, description="URL multiplier for ranking (2-10x)")
    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('Query cannot be empty')
        return v.strip()

SearchRequest = UnifiedRequest
ScraperRequest = UnifiedRequest

# ==================== SEARCH ENDPOINT OUTPUT ====================

class SourceUrl(BaseModel):
    """Source URL information"""
    url: str = Field(..., description="Website URL")
    title: str = Field("", description="Page title")
    domain: str = Field("", description="Website domain")

class SearchResponse(BaseModel):
    """Search response - LLM processed insights only"""
    query: str = Field(..., description="Original search query")
    source_urls: List[SourceUrl] = Field(..., description="List of source URLs used")
    key_points: List[str] = Field(..., description="LLM-extracted key points")
    summary: str = Field("", description="LLM-generated summary")
    unified_content: str = Field("", description="LLM-organized unified content")
    total_sources: int = Field(..., description="Number of sources used")
    processing_time_seconds: float = Field(..., description="Processing time")
    url_multiplier_used: int = Field(..., description="URL multiplier used")
    enhanced_query: str = Field(..., description="LLM-enhanced query used for optimization")
    query_enhancement_applied: bool = Field(..., description="Whether query enhancement was applied")


# ==================== SCRAPER ENDPOINT OUTPUT ====================

class ScrapedData(BaseModel):
    """Individual scraped website data"""
    url: str = Field(..., description="Website URL")
    title: str = Field("", description="Page title")
    content: str = Field("", description="Extracted text content")
    word_count: int = Field(0, description="Number of words")
    quality_score: int = Field(0, ge=0, le=100, description="Content quality score")
    quality_tier: QualityTier = Field(QualityTier.UNKNOWN, description="Quality tier")
    scraping_method: str = Field("unknown", description="Method used (beautifulsoup/crawl4ai/playwright)")
    scraping_success: bool = Field(False, description="Whether scraping succeeded")
    domain: str = Field("", description="Website domain")
    snippet: str = Field("", description="Content snippet")
    error_message: str = Field("", description="Error message if scraping failed")
    relevance_score: int = Field(0, description="LLM relevance score")

class ScraperResponse(BaseModel):
    """Scraper response - raw scraped data for each URL"""
    query: str = Field(..., description="Search query used")
    scraped_data: List[ScrapedData] = Field(..., description="Raw scraping results for each URL")
    total_urls: int = Field(..., description="Total URLs processed")
    successful_scrapes: int = Field(..., description="Number of successful scrapes")
    failed_scrapes: int = Field(..., description="Number of failed scrapes")
    processing_time_seconds: float = Field(..., description="Processing time")
    url_multiplier_used: int = Field(..., description="URL multiplier used")

class OptimizerResponse(BaseModel):
    """Vector optimizer response schema"""
    query: str = Field(..., description="Original search query")
    enhanced_query: str = Field(..., description="LLM-enhanced query for vector search")  # NEW
    optimized_data: List[ScrapedData] = Field(..., description="Vector-optimized scraped data")
    total_original_sources: int = Field(..., description="Number of original sources")
    total_optimized_sources: int = Field(..., description="Number of optimized sources")
    optimization_stats: Dict = Field(..., description="Optimization statistics")
    processing_time_seconds: float = Field(..., description="Processing time")
    url_multiplier_used: int = Field(..., description="URL multiplier used")
    query_enhancement_applied: bool = Field(..., description="Whether query enhancement was applied")  # NEW
    
# ==================== ENHANCED CONVERSATION SYSTEM ====================

class LLMReport(BaseModel):
    """Individual LLM call report within a conversation"""
    llm_type: str = Field(..., description="Type of LLM (context_analyzer, search_llm, organizer_llm, etc.)")
    timestamp: str = Field(..., description="LLM call timestamp")
    user_query: str = Field(..., description="User query for this LLM call")
    tools_required: List[str] = Field(default_factory=list, description="Tools required by this LLM")
    tasks_performed: List[str] = Field(default_factory=list, description="Tasks performed by this LLM")
    tasks_planned: List[str] = Field(default_factory=list, description="Tasks planned by this LLM")
    key_topics: List[str] = Field(default_factory=list, description="Topics identified by this LLM")
    outcomes: List[str] = Field(default_factory=list, description="Results from this LLM")
    error_occurred: bool = Field(False, description="Whether this LLM had errors")
    error_description: Optional[str] = Field(None, description="Error details if any")
    processing_time_seconds: float = Field(0.0, description="Time taken by this LLM")

class FullConversationReport(BaseModel):
    """Complete conversation report with multiple LLM calls"""
    conversation_id: str = Field(..., description="Unique conversation identifier")
    conversation_start: str = Field(..., description="When conversation started")
    conversation_end: Optional[str] = Field(None, description="When conversation ended (if completed)")
    conversation_state: str = Field(..., description="active/waiting_for_user/completed/error")
    total_llm_calls: int = Field(0, description="Number of LLM calls in this conversation")
    all_user_queries: List[str] = Field(default_factory=list, description="All user queries in conversation")
    all_tools_used: List[str] = Field(default_factory=list, description="All tools used in conversation")
    all_topics: List[str] = Field(default_factory=list, description="All topics discussed")
    llm_reports: List[LLMReport] = Field(default_factory=list, description="Reports from each LLM call")
    user_satisfaction_indicators: str = Field("unknown", description="positive/neutral/negative/unknown")
    priority_level: str = Field("medium", description="low/medium/high priority")
    followup_needed: bool = Field(False, description="Whether followup is required")
    context_for_future: str = Field("", description="Summary for future conversation context")

class UserContext(BaseModel):
    """User context information"""
    user_id: Optional[str] = Field(None, description="User identifier")
    name: Optional[str] = Field(None, description="User name")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    location: Optional[str] = Field(None, description="User location")
    timezone: Optional[str] = Field(None, description="User timezone")

class PreviousConversation(BaseModel):
    """Previous conversation with complete report - ENHANCED"""
    conversation_id: str = Field(..., description="Previous conversation ID")
    conversation_report: FullConversationReport = Field(..., description="Complete conversation report")

class ChatRequest(BaseModel):
    """Alice chat request - ENHANCED"""
    user_query: str = Field(..., min_length=1, max_length=2000, description="User's message/query to Alice")
    conversation_id: Optional[str] = Field(None, description="Conversation ID (auto-generated if not provided)")
    user_context: Optional[UserContext] = Field(None, description="User context information")
    previous_conversations: Optional[List[PreviousConversation]] = Field(None, description="Last 5 conversation reports")
    
    @validator('user_query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('User query cannot be empty')
        return v.strip()

class ChatResponse(BaseModel):
    """Alice's comprehensive response - ENHANCED"""
    conversation_id: str = Field(..., description="Conversation identifier")
    user_query: str = Field(..., description="Original user query")
    analysis_timestamp: str = Field(..., description="When analysis was performed")
    tool_activation: ToolActivation = Field(..., description="Which tools Alice will use")
    task_sequence: str = Field(..., description="Task execution sequence")
    sequence_explanation: str = Field(..., description="Explanation of chosen sequence")
    immediate_response: str = Field(..., description="Alice's immediate response to keep user engaged")
    response_tone: str = Field(..., description="Tone of Alice's response")
    recall_needed: bool = Field(False, description="Whether Alice needs clarification from user")
    recall_reason: Optional[str] = Field(None, description="Why recall is needed")
    recall_questions: List[str] = Field(default_factory=list, description="Questions for user clarification")
    current_state_summary: str = Field(..., description="Current state summary for continuation")
    error_detected: bool = Field(False, description="Whether any errors were detected")
    error_details: Optional[str] = Field(None, description="Details of detected errors")
    previous_dissatisfaction: bool = Field(False, description="User dissatisfaction detected from previous convos")
    conversation_summary: str = Field(..., description="Summary of this conversation for future reference")
    key_topics: List[str] = Field(default_factory=list, description="Main topics in conversation")
    user_intent: str = Field(..., description="Alice's understanding of user intent")
    complexity_level: str = Field(..., description="Complexity level: simple/moderate/complex")
    next_steps: List[str] = Field(default_factory=list, description="Alice's planned next actions")
    estimated_completion_time: str = Field(..., description="Estimated time to complete request")
    variables_needed: VariablesNeeded = Field(default_factory=VariablesNeeded, description="Additional variables needed")
    conversation_report: ConversationReport = Field(..., description="This LLM call report")
    full_conversation_update: FullConversationReport = Field(..., description="Updated full conversation report")

# Utility function to generate time-based conversation ID
def generate_conversation_id() -> str:
    """Generate unique conversation ID based on timestamp"""
    timestamp = int(time.time() * 1000)  # Milliseconds for uniqueness
    return f"conv_{timestamp}"

# Update model forward references
SimpleChatResponse.model_rebuild()
