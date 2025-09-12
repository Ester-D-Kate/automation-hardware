import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import re
import time
from .hardware_monitor import HardwareMonitor

logger = logging.getLogger(__name__)

class AsyncParallelScraper:
    """High-performance async web scraper with hardware-aware parallelism."""
    
    def __init__(self, hardware_monitor: Optional[HardwareMonitor] = None):
        self.hardware_monitor = hardware_monitor or HardwareMonitor()
        self.session = None
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        connector = aiohttp.TCPConnector(
            limit=50,  # Total connection limit
            limit_per_host=10,  # Limit per host
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(
            total=30,
            connect=10,
            sock_read=10
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": self.user_agent}
        )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def scrape_urls_parallel(self, urls: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Scrape multiple URLs in parallel with hardware-aware optimization."""
        if not urls:
            return []
        
        start_time = time.time()
        
        # Get optimal worker count based on system resources
        stats = await self.hardware_monitor.get_system_stats()
        max_workers = stats.recommended_workers
        
        logger.info(f"Starting parallel scraping of {len(urls)} URLs with {max_workers} workers")
        
        # Process URLs in batches to manage memory and connections
        batch_size = max(1, min(max_workers, len(urls)))
        results = []
        
        # Process URLs in chunks
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            logger.debug(f"Processing batch {i//batch_size + 1}: {len(batch)} URLs")
            
            # Wait for resources if system is under load
            if stats.performance_level in ["high", "critical"]:
                await self.hardware_monitor.wait_for_resources()
            
            # Process batch concurrently
            semaphore = asyncio.Semaphore(max_workers)
            tasks = [
                self._scrape_single_url_with_semaphore(semaphore, url_info)
                for url_info in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and add successful results
            for result in batch_results:
                if isinstance(result, dict):
                    results.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Scraping error in batch: {result}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info(f"Parallel scraping completed: {len(results)} successful, "
                   f"{len(urls) - len(results)} failed, {duration:.2f}s total")
        
        return results
    
    async def _scrape_single_url_with_semaphore(
        self, semaphore: asyncio.Semaphore, url_info: Dict[str, str]
    ) -> Dict[str, str]:
        """Scrape single URL with semaphore control."""
        async with semaphore:
            return await self._scrape_single_url(url_info)
    
    async def _scrape_single_url(self, url_info: Dict[str, str]) -> Dict[str, str]:
        """Scrape content from a single URL."""
        url = url_info.get('url', '')
        title = url_info.get('title', '')
        
        if not url:
            return {**url_info, 'content': 'No URL provided', 'scrape_error': 'Invalid URL'}
        
        try:
            logger.debug(f"Scraping: {url}")
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"HTTP {response.status} for {url}")
                    return {
                        **url_info,
                        'content': f'HTTP {response.status} error',
                        'scrape_error': f'HTTP status {response.status}'
                    }
                
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                if not any(ct in content_type for ct in ['text/html', 'application/xhtml', 'text/plain']):
                    return {
                        **url_info,
                        'content': 'Non-HTML content',
                        'scrape_error': f'Unsupported content type: {content_type}'
                    }
                
                # Read content with size limit
                content = await response.read()
                if len(content) > 5 * 1024 * 1024:  # 5MB limit
                    logger.warning(f"Content too large for {url}: {len(content)} bytes")
                    content = content[:5 * 1024 * 1024]
                
                text_content = content.decode('utf-8', errors='ignore')
                
                # Extract clean text content
                clean_content = self._extract_clean_content(text_content, url)
                
                # Add metadata
                result = {
                    **url_info,
                    'content': clean_content,
                    'scrape_status': 'success',
                    'content_length': len(clean_content),
                    'response_headers': dict(response.headers),
                    'final_url': str(response.url)  # Handle redirects
                }
                
                logger.debug(f"Successfully scraped {url}: {len(clean_content)} chars")
                return result
                
        except asyncio.TimeoutError:
            logger.warning(f"Timeout scraping {url}")
            return {
                **url_info,
                'content': 'Request timeout',
                'scrape_error': 'Timeout'
            }
        except aiohttp.ClientError as e:
            logger.error(f"Client error scraping {url}: {e}")
            return {
                **url_info,
                'content': 'Connection error',
                'scrape_error': f'Client error: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error scraping {url}: {e}")
            return {
                **url_info,
                'content': 'Scraping failed',
                'scrape_error': f'Error: {str(e)}'
            }
    
    def _extract_clean_content(self, html_content: str, url: str) -> str:
        """Extract clean, readable content from HTML."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup.select(
                'script, style, nav, footer, header, aside, .ads, .advertisement, '
                '.comments, .sidebar, .navigation, .menu, .social, .share, '
                '[class*="ad-"], [class*="advertisement"], [id*="ad-"], '
                '.cookie, .popup, .modal, .overlay'
            ):
                element.decompose()
            
            # Try to find main content area
            main_content = ""
            content_selectors = [
                'main', 'article', '.content', '.post-content', '.entry-content',
                '#content', '.main-content', '.article-body', '.post-body',
                '[role="main"]', '.container .content', '.page-content'
            ]
            
            for selector in content_selectors:
                content_area = soup.select_one(selector)
                if content_area:
                    main_content = content_area.get_text(separator=' ', strip=True)
                    break
            
            # Fallback to body content if no main area found
            if not main_content and soup.body:
                main_content = soup.body.get_text(separator=' ', strip=True)
            
            # Fallback to all text if still no content
            if not main_content:
                main_content = soup.get_text(separator=' ', strip=True)
            
            # Clean up whitespace and formatting
            if main_content:
                # Remove excessive whitespace
                main_content = re.sub(r'\s+', ' ', main_content)
                
                # Remove common noise patterns
                noise_patterns = [
                    r'click here\s*',
                    r'read more\s*',
                    r'subscribe\s*',
                    r'newsletter\s*',
                    r'cookie\s*policy\s*',
                    r'privacy\s*policy\s*',
                    r'terms\s*of\s*service\s*'
                ]
                
                for pattern in noise_patterns:
                    main_content = re.sub(pattern, '', main_content, flags=re.IGNORECASE)
                
                # Trim to reasonable length (keep first 2000 chars)
                if len(main_content) > 2000:
                    main_content = main_content[:1997] + "..."
                
                return main_content.strip()
            
            return "No readable content found"
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return "Content extraction failed"
    
    async def get_scraping_stats(self) -> Dict[str, any]:
        """Get current scraping performance statistics."""
        stats = await self.hardware_monitor.get_system_stats()
        
        return {
            "hardware_stats": {
                "cpu_percent": stats.cpu_percent,
                "memory_percent": stats.memory_percent,
                "available_memory_gb": stats.memory_available_gb,
                "performance_level": stats.performance_level
            },
            "scraping_config": {
                "recommended_workers": stats.recommended_workers,
                "max_connections": 50,
                "timeout_seconds": 30,
                "user_agent": self.user_agent[:50] + "..."
            },
            "session_status": {
                "session_active": self.session is not None and not self.session.closed,
                "connector_info": "TCP connector with connection pooling"
            }
        }