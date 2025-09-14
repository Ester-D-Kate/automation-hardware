import requests
import time
import random
import asyncio
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from .search_engine import search_web_enhanced
from .llm_ranker import rank_urls_with_llm
from .hardware_monitor import get_simple_hardware_info, get_optimal_parallel_count
from .playwright_scraper import should_use_playwright, PLAYWRIGHT_AVAILABLE
import sys
import subprocess
import json
import tempfile
import os

def run_playwright_subprocess(url):
    """Run Playwright in subprocess to avoid threading issues"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script = f'''
import asyncio
import json
import sys
import os
# Add the directory containing playwright_scraper to the path
sys.path.insert(0, r"{script_dir}")
from playwright_scraper import scrape_javascript_website

async def main():
    try:
        result = await scrape_javascript_website("{url}")
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({{"success": False, "content": "", "error": str(e)}}))

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8'
        )
        
        if result.stdout:
            try:
                return json.loads(result.stdout.strip())
            except json.JSONDecodeError as e:
                return {"success": False, "content": "", "error": f"JSON decode error: {e}. stdout: {result.stdout[:200]}"}
        else:
            return {"success": False, "content": "", "error": f"No output. stderr: {result.stderr}"}
            
    except Exception as e:
        return {"success": False, "content": "", "error": str(e)}

def scrape_single_url_enhanced(url):
    """
    Enhanced three-tier scraping system:
    BeautifulSoup -> Crawl4AI -> Playwright
    """
    try:
        # Step 1: Try BeautifulSoup first (fastest)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        
        time.sleep(random.uniform(0.1, 0.5))  # Rate limiting
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        
        text = soup.get_text(separator=' ', strip=True)
        word_count = len(text.split())
        
        # Check content quality
        blocked_indicators = ['please enable javascript', 'javascript required', 'js required']
        is_blocked = any(indicator in text.lower() for indicator in blocked_indicators)
        is_insufficient = word_count < 50  # Updated threshold for Crawl4AI
        
        result = {
            'url': url,
            'success': True,
            'content': text,
            'word_count': word_count,
            'method': 'BeautifulSoup',
            'quality_score': min(word_count * 2, 100)
        }
        
        # Step 2: Try Crawl4AI if BeautifulSoup quality is poor
        # NOTE: This will be handled in async version, here we return BeautifulSoup result
        # and let the async wrapper handle Crawl4AI upgrade
        result['needs_crawl4ai_upgrade'] = False
        from .crawl4ai_scraper import should_use_crawl4ai, CRAWL4AI_AVAILABLE
        
        if CRAWL4AI_AVAILABLE and should_use_crawl4ai(url, word_count, text):
            result['needs_crawl4ai_upgrade'] = True
            result['crawl4ai_reason'] = f"BeautifulSoup got {word_count} words, upgrading to Crawl4AI"
        
        # Step 3: Fallback to Playwright for JavaScript sites
        if (is_blocked or is_insufficient) and PLAYWRIGHT_AVAILABLE and should_use_playwright(url):
            print(f"🎭 Final fallback to Playwright for JS site: {url}")
            pw_result = run_playwright_subprocess(url)
            if pw_result and pw_result.get('success'):
                pw_result['method'] = 'Playwright'
                pw_result['url'] = url
                pw_result['quality_score'] = min(len(pw_result.get('content', '').split()) * 2, 100)
                return pw_result
        
        return result
        
    except Exception as e:
        print(f"❌ Scraping failed for {url}: {str(e)}")
        return {
            'url': url,
            'success': False,
            'content': '',
            'error': str(e),
            'method': 'Failed'
        }

async def search_and_scrape_complete(query, required_results=5, url_multiplier=10):
    """
    Complete implementation following your exact architecture:
    1. Local SearXNG -> DuckDuckGo fallback -> Public SearXNG
    2. URL multiplier system (5x or 10x)
    3. LLM ranking with Ollama 3.3 70B via Groq
    4. Parallel scraping with dynamic thread management
    5. BeautifulSoup -> Playwright fallback
    6. Hardware resource monitoring
    """
    print(f"🚀 Complete Search & Scrape Pipeline")
    print(f"📝 Query: '{query}'")
    print(f"🎯 Required Results: {required_results}")
    print(f"📊 URL Multiplier: {url_multiplier}x")
    
    # Step 1: Enhanced Search (Local SearXNG -> DuckDuckGo -> Public SearXNG)
    search_results = await search_web_enhanced(query, required_results, url_multiplier)
    if not search_results:
        print("❌ No search results found")
        return []
    
    print(f"✅ Search completed: {len(search_results)} URLs found")
    
    # Step 2: LLM Ranking with Ollama 3.3 70B
    ranked_results = await rank_urls_with_llm(search_results, query, required_results)
    if not ranked_results:
        print("❌ LLM ranking failed")
        return []
    
    print(f"✅ LLM ranking completed: {len(ranked_results)} URLs ranked")
    
    # Step 3: Parallel Scraping with Dynamic Thread Management
    hardware_info = get_simple_hardware_info()
    optimal_threads = get_optimal_parallel_count(hardware_info)
    optimal_threads = min(len(ranked_results), optimal_threads)
    
    print(f"🔧 Hardware Analysis:")
    print(f"   CPU Usage: {hardware_info['cpu_usage_percent']:.1f}%")
    print(f"   Memory Usage: {hardware_info['memory_used_percent']:.1f}%") 
    print(f"   Optimal Threads: {optimal_threads}")
    
    successful_results = []
    failed_urls = []
    
    # Async parallel scraping for proper Crawl4AI handling
    async def scrape_url_with_async_upgrade(url_data):
        """Async wrapper to handle Crawl4AI upgrades properly"""
        url = url_data['url']
        
        # Get initial BeautifulSoup result
        bs_result = scrape_single_url_enhanced(url)
        
        # Check if Crawl4AI upgrade is needed
        if bs_result.get('needs_crawl4ai_upgrade'):
            print(f"🕷️ Upgrading to Crawl4AI for better extraction: {url}")
            from .crawl4ai_scraper import scrape_with_crawl4ai
            
            try:
                crawl4ai_result = await scrape_with_crawl4ai(url)
                if crawl4ai_result.get('success'):
                    crawl4ai_result['url'] = url
                    return crawl4ai_result
                else:
                    print(f"⚠️ Crawl4AI failed for {url}, keeping BeautifulSoup result")
            except Exception as e:
                print(f"❌ Crawl4AI error for {url}: {e}")
        
        return bs_result
    
    # Create async tasks for all URLs
    tasks = [scrape_url_with_async_upgrade(result) for result in ranked_results]
    
    # Run all tasks concurrently
    scraping_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    for i, scraped_result in enumerate(scraping_results):
        if isinstance(scraped_result, Exception):
            print(f"❌ Task {i+1} failed with exception: {scraped_result}")
            failed_urls.append(ranked_results[i]['url'])
        else:
            try:
                if scraped_result['success'] and len(scraped_result['content'].split()) > 20:
                    # Merge original search data with scraped content
                    original_result = ranked_results[i]
                    final_result = {**original_result, **scraped_result}
                    successful_results.append(final_result)
                    print(f"✅ Thread SUCCESS ({len(successful_results)}/{required_results}): {scraped_result['url']}")
                    
                    # Stop when we have enough results
                    if len(successful_results) >= required_results:
                        break
                        
                else:
                    failed_urls.append(scraped_result['url'])
                    print(f"❌ Thread FAILED: {scraped_result['url']} - {scraped_result.get('error', 'Poor content')}")
                    
            except Exception as e:
                failed_url = ranked_results[i]['url']
                failed_urls.append(failed_url)
                print(f"💥 Thread EXCEPTION: {failed_url} - {str(e)}")
    
    # Sort by quality score
    successful_results.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
    
    print(f"\n📊 Final Results:")
    print(f"   ✅ Successful: {len(successful_results)}")
    print(f"   ❌ Failed: {len(failed_urls)}")
    print(f"   🎯 Success Rate: {(len(successful_results)/len(ranked_results)*100):.1f}%")
    
    return successful_results[:required_results]

# Aliases for backward compatibility
scrape_single_url = scrape_single_url_enhanced
scrape_simple_website = scrape_single_url_enhanced
scrape_urls = search_and_scrape_complete
