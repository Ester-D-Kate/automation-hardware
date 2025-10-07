"""
Alice Search API - Triple Route System
1. /scraper - Raw scraped data only
2. /search - Vector optimized + LLM processed insights  
3. /optimizer - Vector optimized data only (no LLM processing)
"""

from fastapi import APIRouter, HTTPException
import time
import logging
from typing import List, Dict
from pydantic import BaseModel, Field
from api.schemas import SearchRequest, SearchResponse, ScraperRequest, ScraperResponse, ScrapedData
from utils.search.search_engine import search_web_enhanced
from utils.search.scraper import search_and_scrape_complete
from utils.search.scraped_data_optimizer import optimize_scraped_content
from utils.search.llm_organiser import ContentOrganizer
from utils.search.llm_ranker import rank_urls_with_method_selection

logger = logging.getLogger(__name__)
router = APIRouter()
content_organizer = ContentOrganizer()

# ==================== NEW SCHEMA FOR OPTIMIZER ROUTE ====================

class OptimizerResponse(BaseModel):
    """Vector optimizer response schema"""
    query: str = Field(..., description="Original search query")
    optimized_data: List[ScrapedData] = Field(..., description="Vector-optimized scraped data")
    total_original_sources: int = Field(..., description="Number of original sources")
    total_optimized_sources: int = Field(..., description="Number of optimized sources")
    optimization_stats: Dict = Field(..., description="Optimization statistics")
    processing_time_seconds: float = Field(..., description="Processing time")
    url_multiplier_used: int = Field(..., description="URL multiplier used")

# ==================== ROUTE 1: RAW SCRAPER (No Processing) ====================

@router.post("/scraper", response_model=ScraperResponse)
async def scraper(request: ScraperRequest):
    """
    🕷️ ROUTE 1: RAW SCRAPER ENDPOINT
    
    Returns: Raw scraped data with no optimization or LLM processing
    Use Case: When you need unprocessed website content
    
    Flow: Search → Scrape → Return Raw Data
    """
    try:
        start_time = time.time()
        
        logger.info(f"🕷️ Raw scraper request: '{request.query}' (results: {request.max_results}, multiplier: {request.url_multiplier}x)")
        
        # Search and scrape pipeline
        logger.info("🚀 Starting raw search and scrape pipeline...")
        scraped_results, enhanced_query = await search_and_scrape_complete(query=request.query,
                                                                           required_results=request.max_results,
                                                                           url_multiplier=request.url_multiplier)
 
        
        if not scraped_results or len(scraped_results) == 0:
            raise HTTPException(status_code=404, detail="No URLs found to scrape")
        
        # Build raw scraping data response (no processing)
        scraped_data = []
        for result in scraped_results[:request.max_results]:
            scraped_data.append({
                "url": result.get('url', ''),
                "title": result.get('title', ''),
                "content": result.get('content', ''),  # Full raw content with navigation/spam
                "word_count": result.get('word_count', 0),
                "quality_score": result.get('quality_score', 0),
                "quality_tier": result.get('quality_tier', 'UNKNOWN'),
                "scraping_method": result.get('method', 'unknown'),
                "scraping_success": result.get('success', False),
                "domain": result.get('url', '').split('/')[2] if '/' in result.get('url', '') else 'unknown',
                "snippet": result.get('snippet', ''),
                "error_message": result.get('error', '') if not result.get('success', False) else '',
                "relevance_score": result.get('relevance_score', 0)
            })
        
        processing_time = time.time() - start_time
        
        response = ScraperResponse(
            query=request.query,
            scraped_data=scraped_data,
            total_urls=len(scraped_data),
            successful_scrapes=sum(1 for data in scraped_data if data['scraping_success']),
            failed_scrapes=sum(1 for data in scraped_data if not data['scraping_success']),
            processing_time_seconds=round(processing_time, 2),
            url_multiplier_used=request.url_multiplier
        )
        
        logger.info(f"✅ Raw scraping completed in {processing_time:.2f}s: {response.successful_scrapes}/{response.total_urls} successful")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Raw scraping failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Raw scraping failed: {str(e)}")

# ==================== ROUTE 2: FULL SEARCH (Vector + LLM) ====================

@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    🎯 ROUTE 2: FULL SEARCH ENDPOINT (Vector Optimized + LLM Processed)
    
    Returns: LLM-processed insights from vector-optimized content
    Use Case: When you need Alice's intelligent synthesis and insights
    
    Flow: Search → Scrape → Vector Optimize → LLM Process → Return Insights
    """
    try:
        start_time = time.time()
        
        logger.info(f"🎯 Full search request: '{request.query}' (results: {request.max_results}, multiplier: {request.url_multiplier}x)")
        
        # STEP 1: Search and scrape pipeline
        logger.info("🚀 Starting search and scrape pipeline...")
        scraped_results, enhanced_query = await search_and_scrape_complete(query=request.query,
                                                                           required_results=request.max_results,
                                                                           url_multiplier=request.url_multiplier)
 
        
        if not scraped_results or len(scraped_results) == 0:
            raise HTTPException(status_code=404, detail="No URLs found to scrape")
        
        # STEP 2: Vector optimization
        logger.info("🎯 Optimizing content with Vector Similarity...")
        try:
            optimized_results = await optimize_scraped_content(scraped_results=scraped_results,
                                                               user_query=request.query,
                                                               enhanced_query=enhanced_query,  # NEW: Pass enhanced query
                                                               target_budget=25000)
            
            logger.info(f"✅ Vector optimization: {len(scraped_results)} → {len(optimized_results)} sources optimized")
            
        except Exception as vector_error:
            logger.warning(f"⚠️ Vector optimization failed: {vector_error}")
            logger.info("🔄 Falling back to original scraped results...")
            optimized_results = scraped_results
        
        # STEP 3: LLM processing
        logger.info("🧠 Processing optimized content with LLM...")
        organized_content = await content_organizer.organize_scraped_content_optimized(
            optimized_results,
            request.query
        )
        
        # Build response
        source_urls = []
        for result in optimized_results[:request.max_results]:
            source_urls.append({
                "url": result.get('url', ''),
                "title": result.get('title', ''),
                "domain": result.get('url', '').split('/')[2] if '/' in result.get('url', '') else 'unknown'
            })
        
        processing_time = time.time() - start_time
        
        response = SearchResponse(query=request.query,
                                  enhanced_query=enhanced_query,  # NEW
                                  query_enhancement_applied=True,  # NEW
                                  source_urls=source_urls,
                                  key_points=organized_content.get('key_facts', []) if organized_content else [],
                                  summary=organized_content.get('main_findings', '') if organized_content else '',
                                  unified_content=organized_content.get('unified_content', '') if organized_content else '',
                                  total_sources=len(source_urls),
                                  processing_time_seconds=round(processing_time, 2),
                                  url_multiplier_used=request.url_multiplier)

        
        logger.info(f"✅ Full search completed in {processing_time:.2f}s - Vector-optimized + LLM-processed insights returned")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Full search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Full search failed: {str(e)}")

# ==================== ROUTE 3: OPTIMIZER ONLY ====================

@router.post("/optimizer", response_model=OptimizerResponse)
async def optimizer(request: ScraperRequest):
    """
    🔍 ROUTE 3: VECTOR OPTIMIZER ENDPOINT (Vector Optimized Data Only)
    
    Returns: Vector-optimized scraped data without LLM processing
    Use Case: When you need clean, relevant content but not Alice's synthesis
    
    Flow: Search → Scrape → Vector Optimize → Return Optimized Data
    """
    try:
        start_time = time.time()
        
        logger.info(f"🔍 Vector optimizer request: '{request.query}' (results: {request.max_results}, multiplier: {request.url_multiplier}x)")
        
        # STEP 1: Search and scrape pipeline
        logger.info("🚀 Starting search and scrape pipeline...")
        scraped_results, enhanced_query = await search_and_scrape_complete(query=request.query,
                                                                           required_results=request.max_results,
                                                                           url_multiplier=request.url_multiplier)
        
        if not scraped_results or len(scraped_results) == 0:
            raise HTTPException(status_code=404, detail="No URLs found to scrape")
        
        # STEP 2: Vector optimization
        logger.info("🎯 Optimizing content with Vector Similarity...")
        try:
            optimized_results = await optimize_scraped_content(scraped_results=scraped_results,
                                                               user_query=request.query,
                                                               enhanced_query=enhanced_query,  # NEW: Pass enhanced query
                                                               target_budget=25000)
            
            logger.info(f"✅ Vector optimization: {len(scraped_results)} → {len(optimized_results)} sources optimized")
            
        except Exception as vector_error:
            logger.error(f"❌ Vector optimization failed: {vector_error}")
            raise HTTPException(status_code=500, detail=f"Vector optimization failed: {vector_error}")
        
        # STEP 3: Build optimized data response (no LLM processing)
        optimized_data = []
        total_original_chars = sum(len(r.get('content', '')) for r in scraped_results)
        total_optimized_chars = 0
        
        for result in optimized_results:
            content_length = len(result.get('content', ''))
            total_optimized_chars += content_length
            
            optimized_data.append({
                "url": result.get('url', ''),
                "title": result.get('title', ''),
                "content": result.get('content', ''),  # Vector-optimized content (no spam/navigation)
                "word_count": result.get('word_count', 0),
                "quality_score": result.get('quality_score', 75),  # Higher due to optimization
                "quality_tier": "GOOD",  # Vector-optimized = good quality
                "scraping_method": result.get('method', 'VectorOptimized'),
                "scraping_success": True,
                "domain": result.get('url', '').split('/')[2] if '/' in result.get('url', '') else 'unknown',
                "snippet": result.get('content', '')[:200] + "..." if len(result.get('content', '')) > 200 else result.get('content', ''),
                "error_message": "",
                "relevance_score": int(result.get('relevance_score', 0.8) * 100)  # Convert to percentage
            })
        
        # Calculate optimization statistics
        compression_ratio = (1 - total_optimized_chars/total_original_chars) * 100 if total_original_chars > 0 else 0
        avg_relevance = sum(r.get('relevance_score', 0.8) for r in optimized_results) / len(optimized_results) if optimized_results else 0
        
        optimization_stats = {
            "original_content_chars": total_original_chars,
            "optimized_content_chars": total_optimized_chars,
            "compression_ratio_percent": round(compression_ratio, 1),
            "average_relevance_score": round(avg_relevance * 100, 1),
            "spam_filtering_applied": True,
            "semantic_chunking_applied": True,
            "sources_filtered": len(scraped_results) - len(optimized_results),
            "optimization_method": "vector_similarity_search"
        }
        
        processing_time = time.time() - start_time
        
        response = OptimizerResponse(query=request.query,
                                     enhanced_query=enhanced_query,  # NEW
                                     query_enhancement_applied=bool(enhanced_query and enhanced_query != request.query),  # NEW
                                     optimized_data=optimized_data,
                                     total_original_sources=len(scraped_results),
                                     total_optimized_sources=len(optimized_results),
                                     optimization_stats=optimization_stats,
                                     processing_time_seconds=round(processing_time, 2),
                                     url_multiplier_used=request.url_multiplier)

        logger.info(f"✅ Vector optimization completed in {processing_time:.2f}s: {len(optimized_results)} optimized sources, {compression_ratio:.1f}% compression")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Vector optimization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Vector optimization failed: {str(e)}")

# ==================== ROUTE INFO ====================

@router.get("/routes")
async def get_route_info():
    """📋 ROUTE INFORMATION"""
    return {
        "available_routes": {
            "/scraper": {
                "description": "Raw scraped content from websites",
                "processing": "Search → Scrape → Return Raw Data",
                "use_case": "Need unprocessed website content",
                "content": "Full raw content with navigation/ads",
                "speed": "Fast (10-25s)"
            },
            "/search": {
                "description": "Full Alice AI pipeline with vector optimization + LLM synthesis",
                "processing": "Search → Scrape → Vector Optimize → LLM Process → Return Insights",
                "use_case": "Need Alice's intelligent analysis and insights",
                "content": "AI-synthesized insights and comprehensive analysis",
                "speed": "Comprehensive (15-35s)"
            },
            "/optimizer": {
                "description": "Vector-optimized scraped data without LLM processing",
                "processing": "Search → Scrape → Vector Optimize → Return Clean Data",
                "use_case": "Need clean, relevant content but no AI synthesis",
                "content": "Vector-filtered, spam-free, high-relevance content",
                "speed": "Medium (12-28s)"
            }
        }
    }
