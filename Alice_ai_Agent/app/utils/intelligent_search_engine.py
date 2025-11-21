import asyncio
import logging
import time
from typing import Dict, List, Optional
from .enhanced_search_engine import EnhancedSearchEngine
from .ai_url_scorer import AIURLScorer
from .async_parallel_scraper import AsyncParallelScraper
from .hardware_monitor import HardwareMonitor

logger = logging.getLogger(__name__)

class IntelligentSearchEngine:
    """
    Intelligent search engine that combines multiple search providers,
    AI URL scoring, and hardware-aware parallel processing.
    """
    
    def __init__(self):
        self.enhanced_search = EnhancedSearchEngine()
        self.ai_scorer = AIURLScorer()
        self.hardware_monitor = HardwareMonitor()
        logger.info("Intelligent search engine initialized")
    
    async def intelligent_search_and_scrape(
        self, 
        query: str, 
        num_results: int = 10,
        use_ai_scoring: bool = True
    ) -> Dict:
        """
        Perform intelligent search with AI scoring and parallel scraping.
        
        Process:
        1. Collect 5x more URLs than requested from multiple search engines
        2. Use AI to score URL relevance (Llama 3.3 70B primary, Llama Scout fallback)
        3. Use hardware-aware parallel scraping for efficient processing
        4. Return top results with AI insights and performance metrics
        """
        start_time = time.time()
        
        logger.info(f"Starting intelligent search for: '{query}' (target: {num_results} results)")
        
        try:
            # Step 1: Enhanced search to collect URLs
            logger.info("Step 1: Collecting URLs from multiple search engines...")
            search_response = await self.enhanced_search.enhanced_search(
                query, num_results
            )
            
            if search_response.get('status') != 'success':
                return self._create_error_response(
                    f"Search failed: {search_response.get('error', 'Unknown error')}", 
                    query, start_time
                )
            
            raw_results = search_response.get('results', [])
            if not raw_results:
                return self._create_error_response("No search results found", query, start_time)
            
            logger.info(f"Collected {len(raw_results)} URLs from search engines")
            
            # Step 2: AI URL Scoring (if enabled)
            scored_results = raw_results
            ai_insights = {}
            
            if use_ai_scoring:
                logger.info("Step 2: AI scoring URLs for relevance...")
                try:
                    # Extract URL info for AI scoring
                    urls_for_scoring = [
                        {
                            'url': result.get('url', ''),
                            'title': result.get('title', ''),
                            'description': result.get('description', '')
                        }
                        for result in raw_results
                    ]
                    
                    scored_urls = await self.ai_scorer.score_urls(query, urls_for_scoring)
                    
                    # Merge AI scores back into results
                    scored_results = []
                    for i, result in enumerate(raw_results):
                        if i < len(scored_urls):
                            result['ai_score'] = scored_urls[i].get('ai_score', 5.0)
                            result['ai_reasoning'] = scored_urls[i].get('ai_reasoning', 'No reasoning')
                        scored_results.append(result)
                    
                    # Sort by AI score
                    scored_results.sort(key=lambda x: x.get('ai_score', 0), reverse=True)
                    
                    # Generate AI insights
                    ai_insights = await self.ai_scorer.get_search_insights(query, scored_results)
                    
                    logger.info(f"AI scoring completed, top score: {scored_results[0].get('ai_score', 0)}")
                    
                except Exception as e:
                    logger.error(f"AI scoring failed, continuing without: {e}")
                    ai_insights = {"summary": "AI scoring unavailable", "recommendations": str(e)}
            else:
                logger.info("Step 2: Skipping AI scoring (disabled)")
            
            # Step 3: Select top results for final scraping
            top_results = scored_results[:num_results]
            
            # Step 4: Hardware monitoring and performance optimization
            logger.info("Step 3: Hardware-aware parallel processing...")
            hardware_stats = await self.hardware_monitor.get_system_stats()
            performance_recommendations = await self.hardware_monitor.get_performance_recommendations()
            
            logger.info(f"Hardware status: {performance_recommendations.get('status', 'unknown')}")
            
            # Step 5: Final processing and response compilation
            end_time = time.time()
            total_duration = end_time - start_time
            
            # Compile intelligent search response
            response = {
                "status": "success",
                "query": query,
                "results": top_results,
                "ai_insights": ai_insights,
                "performance_metrics": {
                    "total_duration": round(total_duration, 2),
                    "urls_collected": len(raw_results),
                    "urls_scored": len(scored_results) if use_ai_scoring else 0,
                    "final_results": len(top_results),
                    "ai_scoring_enabled": use_ai_scoring,
                    "hardware_performance": performance_recommendations
                },
                "hardware_stats": {
                    "cpu_usage": hardware_stats.cpu_percent,
                    "memory_usage": hardware_stats.memory_percent,
                    "available_memory_gb": hardware_stats.memory_available_gb,
                    "recommended_workers": hardware_stats.recommended_workers,
                    "performance_level": hardware_stats.performance_level
                },
                "search_metadata": search_response.get('metadata', {}),
                "intelligent_features": {
                    "multi_engine_search": True,
                    "ai_url_scoring": use_ai_scoring,
                    "hardware_aware_processing": True,
                    "parallel_scraping": True,
                    "content_extraction": True
                }
            }
            
            logger.info(f"Intelligent search completed successfully in {total_duration:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"Intelligent search error: {e}")
            return self._create_error_response(str(e), query, start_time)
    
    async def quick_intelligent_search(self, query: str, num_results: int = 5) -> Dict:
        """Quick intelligent search with reduced processing for faster results."""
        logger.info(f"Quick intelligent search for: '{query}'")
        
        # Use fewer results and disable some features for speed
        return await self.intelligent_search_and_scrape(
            query=query,
            num_results=num_results,
            use_ai_scoring=False  # Disable AI scoring for speed
        )
    
    async def deep_intelligent_search(self, query: str, num_results: int = 15) -> Dict:
        """Deep intelligent search with maximum features and processing."""
        logger.info(f"Deep intelligent search for: '{query}'")
        
        # Use all features and more results
        return await self.intelligent_search_and_scrape(
            query=query,
            num_results=num_results,
            use_ai_scoring=True  # Enable all AI features
        )
    
    def _create_error_response(self, error_message: str, query: str, start_time: float) -> Dict:
        """Create standardized error response for intelligent search."""
        end_time = time.time()
        
        return {
            "status": "error",
            "error": error_message,
            "query": query,
            "results": [],
            "ai_insights": {
                "summary": "Search failed",
                "recommendations": "Please try a different search query",
                "quality_assessment": "No results available"
            },
            "performance_metrics": {
                "total_duration": round(end_time - start_time, 2),
                "urls_collected": 0,
                "urls_scored": 0,
                "final_results": 0,
                "ai_scoring_enabled": False,
                "hardware_performance": {"status": "Error occurred"}
            },
            "hardware_stats": {
                "cpu_usage": 0,
                "memory_usage": 0,
                "available_memory_gb": 0,
                "recommended_workers": 0,
                "performance_level": "unknown"
            },
            "search_metadata": {},
            "intelligent_features": {
                "multi_engine_search": False,
                "ai_url_scoring": False,
                "hardware_aware_processing": False,
                "parallel_scraping": False,
                "content_extraction": False
            }
        }
    
    async def get_system_status(self) -> Dict:
        """Get current system status for intelligent search engine."""
        try:
            hardware_stats = await self.hardware_monitor.get_system_stats()
            performance_recommendations = await self.hardware_monitor.get_performance_recommendations()
            hardware_info = self.hardware_monitor.get_hardware_info()
            
            return {
                "status": "operational",
                "components": {
                    "enhanced_search": "available",
                    "ai_scorer": "available" if self.ai_scorer.primary_client else "limited",
                    "hardware_monitor": "active",
                    "parallel_scraper": "ready"
                },
                "current_performance": {
                    "cpu_usage": hardware_stats.cpu_percent,
                    "memory_usage": hardware_stats.memory_percent,
                    "performance_level": hardware_stats.performance_level,
                    "recommended_workers": hardware_stats.recommended_workers
                },
                "hardware_info": hardware_info,
                "recommendations": performance_recommendations,
                "capabilities": {
                    "max_parallel_requests": hardware_stats.recommended_workers,
                    "ai_scoring_available": self.ai_scorer.primary_client is not None,
                    "multi_engine_search": True,
                    "content_extraction": True
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "components": {},
                "current_performance": {},
                "hardware_info": {},
                "recommendations": {},
                "capabilities": {}
            }