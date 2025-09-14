"""
Enhanced Search Engine with Multiple Fallbacks
1. Local SearXNG (from .env)
2. DuckDuckGo fallback
3. Public SearXNG instances fallback
4. Apply URL multiplier and LLM ranking
"""

from ddgs import DDGS
import time
import re
import requests
from bs4 import BeautifulSoup
from .search_config import get_config, LOCAL_SEARXNG_URL, DEFAULT_URL_MULTIPLIER

# Removed unreliable public SearXNG instances to improve performance
# Now uses only: Local SearXNG → DuckDuckGo (reliable sources)

async def search_web_enhanced(query, required_results=5, url_multiplier=None):
    """
    Enhanced search with multiple fallback layers:
    1. Local SearXNG (from .env)
    2. DuckDuckGo fallback  
    3. Public SearXNG instances fallback
    4. Return multiplied URLs for LLM ranking
    
    Args:
        query: What to search for
        required_results: How many final results user wants
        url_multiplier: Multiplier (5 or 10), uses default if None
    
    Returns:
        List of search results (multiplied count)
    """
    # Step 1: Calculate how many URLs to get (multiplier system)
    if url_multiplier is None:
        url_multiplier = DEFAULT_URL_MULTIPLIER
    
    total_urls_needed = required_results * url_multiplier
    print(f"🔍 Enhanced search for: '{query}'")
    print(f"📊 Required: {required_results}, Multiplier: {url_multiplier}x, Total URLs: {total_urls_needed}")
    
    all_results = []
    
    # Step 2: Try local SearXNG first
    print("🏠 Trying local SearXNG...")
    local_results = await search_local_searxng(query, total_urls_needed)
    all_results.extend(local_results)
    
    # Step 3: If not enough, fallback to DuckDuckGo
    if len(all_results) < total_urls_needed:
        remaining_needed = total_urls_needed - len(all_results)
        print(f"🦆 Need {remaining_needed} more URLs, trying DuckDuckGo...")
        ddg_results = await search_duckduckgo(query, remaining_needed)
        all_results.extend(ddg_results)
    
    # Accept what we have from Local SearXNG + DuckDuckGo (reliable sources only)
    # No public SearXNG fallback to avoid timeouts and failures
    
    # Remove duplicates
    unique_results = remove_duplicate_urls(all_results)
    
    print(f"✅ Total unique URLs found: {len(unique_results)}")
    return unique_results[:total_urls_needed]

async def search_local_searxng(query, max_results):
    """
    Search using local SearXNG instance (based on alice_ai_agent implementation)
    """
    try:
        if not LOCAL_SEARXNG_URL:
            print("⚠️ No local SearXNG URL configured")
            return []
        
        # Headers matching alice_ai_agent implementation exactly  
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9", 
            "Referer": LOCAL_SEARXNG_URL.replace('/search', '/'),  # Use env variable only
            "DNT": "1"
        }
        
        # SearXNG search parameters (HTML format, not JSON)
        params = {
            'q': query,
            'categories': 'general'
        }
        
        print(f"🏠 Requesting local SearXNG: {LOCAL_SEARXNG_URL}")
        print(f"🏠 Params: {params}")
        print(f"🏠 Headers: {headers}")
        
        # Make request to local SearXNG
        response = requests.get(LOCAL_SEARXNG_URL, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Parse HTML response like alice_ai_agent does
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Extract results from HTML (matching alice_ai_agent approach exactly)
            result_elements = soup.select('article.result')
            for element in result_elements[:max_results]:
                title_elem = element.select_one('h3 a')
                
                # Use alice_ai_agent approach: get URL from h3 a element directly
                if title_elem and 'href' in title_elem.attrs:
                    title = clean_text(title_elem.get_text(strip=True))
                    url = title_elem['href']  # Direct attribute access like alice_ai_agent
                    
                    # Try to get snippet from content area
                    snippet_elem = element.select_one('.content')
                    snippet = clean_text(snippet_elem.get_text(strip=True)) if snippet_elem else ''
                    
                    clean_result = {
                        'title': title,
                        'url': url,
                        'snippet': snippet,
                        'source': 'local_searxng'
                    }
                    
                    if clean_result['url'] and is_valid_url(clean_result['url']):
                        results.append(clean_result)
            
            print(f"🏠 Local SearXNG found {len(results)} results")
            if len(results) == 0:
                print(f"🔍 Debug - Response length: {len(response.text)}")
                print(f"🔍 Debug - Found {len(result_elements)} result elements")
                print(f"🔍 Debug - First 300 chars: {response.text[:300]}")
                # Check page title
                title_elem = soup.select_one('title')
                print(f"🔍 Debug - Page title: {title_elem.get_text() if title_elem else 'None'}")
            return results
        else:
            print(f"⚠️ Local SearXNG returned status {response.status_code}")
            print(f"⚠️ Response: {response.text[:200]}")
            return []
            
    except Exception as e:
        print(f"❌ Local SearXNG failed: {e}")
        return []

async def search_duckduckgo(query, max_results):
    """
    Fallback search using DuckDuckGo
    """
    print(f"🦆 Searching DuckDuckGo for: '{query}'")
    
    try:
        results = []
        
        # Use DuckDuckGo search
        with DDGS() as ddgs:
            search_results = ddgs.text(
                query, 
                max_results=max_results,
                region='us-en',
                safesearch='moderate'
            )
            
            for result in search_results:
                clean_result = {
                    'title': clean_text(result.get('title', '')),
                    'url': result.get('href', ''),
                    'snippet': clean_text(result.get('body', '')),
                    'source': 'duckduckgo'
                }
                
                if clean_result['url'] and is_valid_url(clean_result['url']):
                    results.append(clean_result)
        
        print(f"🦆 DuckDuckGo found {len(results)} results")
        return results
        
    except Exception as e:
        print(f"❌ DuckDuckGo search failed: {e}")
        return []

# Removed unreliable search_public_searxng function
# System now uses only reliable sources: Local SearXNG + DuckDuckGo

# Keep the original simple function for backward compatibility
async def search_web(query, max_results=5):
    """
    Simple search (backward compatibility)
    """
    return await search_duckduckgo(query, max_results)

def search_web_sync(query, max_results=5):
    """
    Synchronous version of search_web
    For when you don't need async
    
    Args:
        query: What to search for
        max_results: How many results to return
    
    Returns:
        List of search results
    """
    import asyncio
    return asyncio.run(search_web(query, max_results))

def clean_text(text):
    """
    Clean up text from search results
    Remove weird characters and extra spaces
    
    Args:
        text: Text to clean
    
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove weird characters but keep basic punctuation
    text = re.sub(r'[^\w\s\.\,\!\?\-\(\)\[\]\/\:]', '', text)
    
    return text.strip()

def is_valid_url(url):
    """
    Simple check - is this a valid URL we can scrape?
    
    Args:
        url: URL to check
    
    Returns:
        True if URL looks valid, False otherwise
    """
    if not url:
        return False
    
    # Must start with http or https
    if not (url.startswith('http://') or url.startswith('https://')):
        return False
    
    # Skip certain file types we can't scrape
    skip_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                       '.zip', '.rar', '.exe', '.dmg', '.mp4', '.avi', '.mov']
    
    url_lower = url.lower()
    if any(url_lower.endswith(ext) for ext in skip_extensions):
        return False
    
    # Skip certain sites that are hard to scrape
    skip_sites = ['youtube.com/watch', 'twitter.com/status', 'instagram.com/p/',
                  'facebook.com/photo', 'pinterest.com/pin']
    
    if any(site in url_lower for site in skip_sites):
        return False
    
    return True

def improve_search_query(query):
    """
    Simple query improvement
    Add helpful search terms
    
    Args:
        query: Original search query
    
    Returns:
        Improved search query
    """
    # Add quotes around exact phrases
    if ' ' in query and '"' not in query:
        if len(query.split()) <= 3:  # Short phrases get quotes
            query = f'"{query}"'
    
    # Add helpful terms for better results
    if 'how to' not in query.lower() and 'what is' not in query.lower():
        # For informational queries, add context terms
        info_terms = ['guide', 'tutorial', 'explanation', 'information']
        if any(term in query.lower() for term in ['learn', 'understand', 'know']):
            query += ' guide'
    
    return query

def remove_duplicate_urls(results):
    """
    Remove duplicate URLs from search results
    Keep the first occurrence of each URL
    """
    seen_urls = set()
    unique_results = []
    
    for result in results:
        url = result.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(result)
    
    return unique_results

async def search_multiple_queries(queries, max_results_per_query=3):
    """
    Search multiple queries and combine results
    
    Args:
        queries: List of search queries
        max_results_per_query: Results per query
    
    Returns:
        Combined list of unique results
    """
    print(f"🔍 Searching {len(queries)} different queries")
    
    all_results = []
    
    for query in queries:
        print(f"   Searching: '{query}'")
        
        results = await search_web(query, max_results_per_query)
        all_results.extend(results)
        
        # Small delay to be nice to the search service
        time.sleep(0.5)
    
    # Remove duplicates
    unique_results = remove_duplicate_urls(all_results)
    print(f"✅ Combined {len(unique_results)} unique results from all queries")
    return unique_results