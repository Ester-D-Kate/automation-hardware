"""
Alice Search API - Unified Input, Different Outputs
Both endpoints use same input format
"""

from fastapi import APIRouter, HTTPException
import time
import logging
from api.schemas import SearchRequest, SearchResponse, ScraperRequest, ScraperResponse
from utils.search.search_engine import search_web_enhanced
from utils.search.scraper import search_and_scrape_complete
from utils.search.llm_organiser import ContentOrganizer
from utils.search.llm_ranker import rank_urls_with_method_selection

logger = logging.getLogger(__name__)
router = APIRouter()
content_organizer = ContentOrganizer()

@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    🔍 SEARCH ENDPOINT
    
    Input: { query, max_results, url_multiplier }
    Output: LLM-processed insights (key points, summary, unified content)
    
    Process:
    1. Search web for query
    2. Find (max_results × url_multiplier) URLs 
    3. Rank URLs with LLM
    4. Scrape top max_results URLs
    5. Use LLM to analyze and organize content
    6. Return insights + source URLs
    """
    try:
        start_time = time.time()
        
        logger.info(f"🔍 Search request: '{request.query}' (results: {request.max_results}, multiplier: {request.url_multiplier}x)")
        
        # Use complete search and scrape pipeline
        logger.info("🚀 Starting search and scrape pipeline...")
        scraped_results = await search_and_scrape_complete(
            query=request.query,
            required_results=request.max_results,
            url_multiplier=request.url_multiplier
        )
        
        if not scraped_results:
            raise HTTPException(status_code=404, detail="No search results found")
        
        # LLM organize and extract insights
        logger.info("🧠 Processing content with LLM for insights...")
        organized_content = await content_organizer.organize_scraped_content(
            scraped_results, request.query
        )
        
        # Build source URLs list
        source_urls = []
        for result in scraped_results[:request.max_results]:
            source_urls.append({
                "url": result.get('url', ''),
                "title": result.get('title', ''),
                "domain": result.get('url', '').split('/')[2] if '/' in result.get('url', '') else 'unknown'
            })
        
        processing_time = time.time() - start_time
        
        # Return LLM insights only
        response = SearchResponse(
            query=request.query,
            source_urls=source_urls,
            key_points=organized_content.get('key_facts', []) if organized_content else [],
            summary=organized_content.get('main_findings', '') if organized_content else '',
            unified_content=organized_content.get('unified_content', '') if organized_content else '',
            total_sources=len(source_urls),
            processing_time_seconds=round(processing_time, 2),
            url_multiplier_used=request.url_multiplier
        )
        
        logger.info(f"✅ Search completed in {processing_time:.2f}s - LLM insights returned")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.post("/scraper", response_model=ScraperResponse)
async def scraper(request: ScraperRequest):
    """
    🕷️ SCRAPER ENDPOINT
    
    Input: { query, max_results, url_multiplier }
    Output: Raw scraped data for each URL (full content, word counts, quality scores)
    
    Process:
    1. Search web for query  
    2. Find (max_results × url_multiplier) URLs
    3. Rank URLs with LLM
    4. Scrape top max_results URLs
    5. Return raw scraping data for each URL
    """
    try:
        start_time = time.time()
        
        logger.info(f"🕷️ Scraper request: '{request.query}' (results: {request.max_results}, multiplier: {request.url_multiplier}x)")
        
        # Use same search and scrape pipeline
        logger.info("🚀 Starting search and scrape pipeline...")
        scraped_results = await search_and_scrape_complete(
            query=request.query,
            required_results=request.max_results,
            url_multiplier=request.url_multiplier
        )
        
        if not scraped_results:
            raise HTTPException(status_code=404, detail="No URLs found to scrape")
        
        # Build raw scraping data response
        scraped_data = []
        for result in scraped_results[:request.max_results]:
            scraped_data.append({
                "url": result.get('url', ''),
                "title": result.get('title', ''),
                "content": result.get('content', ''),  # Full raw content
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
        
        # Return raw scraping data
        response = ScraperResponse(
            query=request.query,
            scraped_data=scraped_data,
            total_urls=len(scraped_data),
            successful_scrapes=sum(1 for data in scraped_data if data['scraping_success']),
            failed_scrapes=sum(1 for data in scraped_data if not data['scraping_success']),
            processing_time_seconds=round(processing_time, 2),
            url_multiplier_used=request.url_multiplier
        )
        
        logger.info(f"✅ Scraping completed in {processing_time:.2f}s: {response.successful_scrapes}/{response.total_urls} successful - Raw data returned")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Scraping failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")
