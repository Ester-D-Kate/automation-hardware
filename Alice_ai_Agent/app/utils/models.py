from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class SearchResult(BaseModel):
    """Individual search result model."""
    title: str
    url: str
    description: Optional[str] = ""
    content: Optional[str] = ""
    source: Optional[str] = ""
    ai_score: Optional[float] = None
    ai_reasoning: Optional[str] = None
    scrape_status: Optional[str] = None
    content_length: Optional[int] = None

class AIInsights(BaseModel):
    """AI-generated insights about search results."""
    summary: str
    recommendations: str
    quality_assessment: str

class HardwareStats(BaseModel):
    """Current hardware performance statistics."""
    cpu_usage: float
    memory_usage: float
    available_memory_gb: float
    recommended_workers: int
    performance_level: str

class PerformanceMetrics(BaseModel):
    """Search performance metrics."""
    total_duration: float
    urls_collected: int
    urls_scored: int
    final_results: int
    ai_scoring_enabled: bool
    hardware_performance: Dict[str, Any]

class IntelligentFeatures(BaseModel):
    """Features used in intelligent search."""
    multi_engine_search: bool
    ai_url_scoring: bool
    hardware_aware_processing: bool
    parallel_scraping: bool
    content_extraction: bool

class IntelligentSearchResponse(BaseModel):
    """Response model for intelligent search endpoint."""
    status: str
    query: str
    results: List[SearchResult]
    ai_insights: AIInsights
    performance_metrics: PerformanceMetrics
    hardware_stats: HardwareStats
    search_metadata: Dict[str, Any]
    intelligent_features: IntelligentFeatures
    error: Optional[str] = None

class EnhancedSearchResponse(BaseModel):
    """Response model for enhanced search endpoint."""
    status: str
    query: str
    results: List[SearchResult]
    metadata: Dict[str, Any]
    search_insights: Dict[str, Any]
    error: Optional[str] = None

class SimpleScrapeResponse(BaseModel):
    """Response model for simple URL scraping."""
    status: str
    url: str
    content: str
    metadata: Dict[str, Any]
    error: Optional[str] = None

class SystemStatusResponse(BaseModel):
    """Response model for system status endpoint."""
    status: str
    components: Dict[str, str]
    current_performance: Dict[str, Any]
    hardware_info: Dict[str, Any]
    recommendations: Dict[str, str]
    capabilities: Dict[str, Any]
    error: Optional[str] = None

class SearchRequest(BaseModel):
    """Request model for search endpoints."""
    query: str = Field(..., description="Search query")
    num_results: Optional[int] = Field(10, description="Number of results to return")
    use_ai_scoring: Optional[bool] = Field(True, description="Enable AI URL scoring")

class ScrapeRequest(BaseModel):
    """Request model for scrape endpoint."""
    url: str = Field(..., description="URL to scrape")
    extract_clean_content: Optional[bool] = Field(True, description="Extract clean readable content")