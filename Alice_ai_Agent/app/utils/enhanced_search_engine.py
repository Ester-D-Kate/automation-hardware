import asyncio
import logging
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
import time
from .search import perform_search
from .async_parallel_scraper import AsyncParallelScraper
from .hardware_monitor import HardwareMonitor
from .config import SEARXNG_URL

logger = logging.getLogger(__name__)

class EnhancedSearchEngine:
    """Enhanced search engine with multiple search providers and parallel processing."""
    
    def __init__(self):
        self.hardware_monitor = HardwareMonitor()
        self.search_providers = [
            'duckduckgo', 'google', 'bing', 'yahoo', 'startpage'
        ]
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
        )
    
    async def enhanced_search(self, query: str, num_results: int = 10) -> Dict:
        """Perform enhanced search using multiple engines and parallel processing."""
        start_time = time.time()
        
        logger.info(f"Starting enhanced search for: {query} (requesting {num_results} results)")
        
        try:
            # Get 5x more URLs than requested for better filtering
            target_urls = num_results * 5
            
            # Perform multi-engine search
            search_results = await self._multi_engine_search(query, target_urls)
            
            if not search_results:
                logger.warning("No search results found")
                return self._create_error_response("No search results found", query, start_time)
            
            # Extract URLs for scraping
            urls_to_scrape = search_results[:min(target_urls, len(search_results))]
            
            # Parallel scraping with hardware awareness
            async with AsyncParallelScraper(self.hardware_monitor) as scraper:
                scraped_results = await scraper.scrape_urls_parallel(urls_to_scrape)
                scraping_stats = await scraper.get_scraping_stats()
            
            # Filter successful results
            successful_results = [
                result for result in scraped_results 
                if result.get('scrape_status') == 'success' and result.get('content')
            ]
            
            # Take requested number of results
            final_results = successful_results[:num_results]
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Compile response
            response = {
                "status": "success",
                "query": query,
                "results": final_results,
                "metadata": {
                    "total_found": len(search_results),
                    "scraped_count": len(scraped_results),
                    "successful_scrapes": len(successful_results),
                    "returned_count": len(final_results),
                    "search_duration": round(duration, 2),
                    "search_engines_used": self.search_providers,
                    "hardware_stats": scraping_stats.get("hardware_stats", {}),
                    "performance_level": scraping_stats.get("hardware_stats", {}).get("performance_level", "unknown")
                },
                "search_insights": {
                    "expansion_ratio": f"{target_urls}/{num_results}",
                    "success_rate": f"{len(successful_results)}/{len(scraped_results)}" if scraped_results else "0/0",
                    "avg_content_length": sum(len(r.get('content', '')) for r in final_results) // max(1, len(final_results))
                }
            }
            
            logger.info(f"Enhanced search completed: {len(final_results)} results in {duration:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"Enhanced search error: {e}")
            return self._create_error_response(str(e), query, start_time)
    
    async def _multi_engine_search(self, query: str, num_results: int) -> List[Dict[str, str]]:
        """Search using multiple engines for better coverage."""
        all_results = []
        
        # Primary search via SearXNG (which aggregates multiple engines)
        try:
            primary_results = await self._searxng_search(query, num_results)
            all_results.extend(primary_results)
            logger.info(f"SearXNG search returned {len(primary_results)} results")
        except Exception as e:
            logger.error(f"SearXNG search failed: {e}")
        
        # Fallback to direct engine searches if not enough results
        if len(all_results) < num_results // 2:
            logger.info("Insufficient results from primary search, trying fallback methods")
            
            try:
                fallback_results = await self._fallback_search(query, num_results - len(all_results))
                all_results.extend(fallback_results)
                logger.info(f"Fallback search added {len(fallback_results)} more results")
            except Exception as e:
                logger.error(f"Fallback search failed: {e}")
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_results = []
        
        for result in all_results:
            url = result.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
        
        logger.info(f"Multi-engine search completed: {len(unique_results)} unique results")
        return unique_results
    
    async def _searxng_search(self, query: str, num_results: int) -> List[Dict[str, str]]:
        """Search using SearXNG instance."""
        if not SEARXNG_URL:
            logger.warning("SEARXNG_URL not configured")
            return []
        
        try:
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "DNT": "1"
            }
            
            params = {
                "q": query,
                "categories": "general",
                "format": "html"
            }
            
            response = requests.get(
                SEARXNG_URL,
                params=params,
                headers=headers,
                timeout=15
            )
            
            if not response.ok:
                logger.error(f"SearXNG returned status {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Parse SearXNG results
            for result_elem in soup.select('article.result')[:num_results]:
                try:
                    title_elem = result_elem.select_one('h3 a')
                    if title_elem and 'href' in title_elem.attrs:
                        title = title_elem.get_text(strip=True)
                        url = title_elem['href']
                        
                        # Extract description/snippet if available
                        desc_elem = result_elem.select_one('.content, .description, p')
                        description = desc_elem.get_text(strip=True) if desc_elem else ""
                        
                        results.append({
                            'title': title,
                            'url': url,
                            'description': description,
                            'source': 'searxng'
                        })
                except Exception as e:
                    logger.debug(f"Error parsing SearXNG result: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"SearXNG search error: {e}")
            return []
    
    async def _fallback_search(self, query: str, num_results: int) -> List[Dict[str, str]]:
        """Fallback search using the original search module."""
        try:
            # Use the existing search function as fallback
            search_result = perform_search(query)
            
            if search_result.get('status') == 'success':
                # Parse the formatted results to extract URLs
                results_text = search_result.get('results', '')
                
                # This is a simple parser for the formatted text results
                # In a real implementation, you might want to modify the original
                # search function to return structured data
                
                fallback_results = []
                
                # Try to extract URLs from the formatted text
                import re
                url_pattern = r'https?://[^\s]+'
                urls = re.findall(url_pattern, results_text)
                
                for i, url in enumerate(urls[:num_results]):
                    fallback_results.append({
                        'title': f'Fallback Result {i+1}',
                        'url': url,
                        'description': 'Result from fallback search',
                        'source': 'fallback'
                    })
                
                return fallback_results
            
            return []
            
        except Exception as e:
            logger.error(f"Fallback search error: {e}")
            return []
    
    def _create_error_response(self, error_message: str, query: str, start_time: float) -> Dict:
        """Create standardized error response."""
        end_time = time.time()
        return {
            "status": "error",
            "error": error_message,
            "query": query,
            "results": [],
            "metadata": {
                "total_found": 0,
                "scraped_count": 0,
                "successful_scrapes": 0,
                "returned_count": 0,
                "search_duration": round(end_time - start_time, 2),
                "search_engines_used": [],
                "hardware_stats": {},
                "performance_level": "unknown"
            },
            "search_insights": {
                "expansion_ratio": "0/0",
                "success_rate": "0/0",
                "avg_content_length": 0
            }
        }
    
    async def simple_scrape(self, url: str) -> Dict:
        """Simple single URL scraping."""
        try:
            url_info = {'url': url, 'title': 'Direct URL', 'description': ''}
            
            async with AsyncParallelScraper(self.hardware_monitor) as scraper:
                results = await scraper.scrape_urls_parallel([url_info])
            
            if results and results[0].get('scrape_status') == 'success':
                return {
                    "status": "success",
                    "url": url,
                    "content": results[0].get('content', ''),
                    "metadata": {
                        "content_length": results[0].get('content_length', 0),
                        "final_url": results[0].get('final_url', url),
                        "scrape_status": "success"
                    }
                }
            else:
                error_msg = results[0].get('scrape_error', 'Unknown error') if results else 'No results'
                return {
                    "status": "error",
                    "error": f"Scraping failed: {error_msg}",
                    "url": url,
                    "content": "",
                    "metadata": {"scrape_status": "failed"}
                }
                
        except Exception as e:
            logger.error(f"Simple scrape error for {url}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "url": url,
                "content": "",
                "metadata": {"scrape_status": "error"}
            }