"""
Alice LLM URL Ranker & Method Selector - Intelligent URL Ranking System
Smart URL ranking with scraping method selection using Groq Cloud 70B model.
Provides relevance scoring and optimal scraping method determination for web content extraction.
"""

import json
import os
import time
import logging
import asyncio
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# ==================== GLOBAL CONFIGURATION (CACHED) ====================

# Load API keys once at module level (More Efficient)
API_KEYS = [
    os.getenv('GROQ_API_KEY'),
    os.getenv('GROQ_API_KEY_ALT_1'), 
    os.getenv('GROQ_API_KEY_ALT_2'),
    os.getenv('GROQ_API_KEY_ALT_3'),
    os.getenv('GROQ_API_KEY_ALT_4')
]

# Filter out None/empty keys once
AVAILABLE_API_KEYS = [key for key in API_KEYS if key and key.strip()]

# LLM Configuration - Ranker priority order
LLM_RANKER_API_ORDER = [
    'GROQ_API_KEY_ALT_2',
    'GROQ_API_KEY_ALT_3',
    'GROQ_API_KEY_ALT_4',
    'GROQ_API_KEY',         
    'GROQ_API_KEY_ALT_1'
]  
LLM_MODEL = "llama-3.3-70b-versatile"          # 70B model for intelligent ranking
LLM_TEMPERATURE = 0.3                          # Balanced temperature for consistent ranking
MAX_RANKING_URLS = 100                         # Maximum URLs to process in single batch
MAX_TOKENS = 3000                              # Token limit for ranking response

# Scraping Method Categories
JAVASCRIPT_HEAVY_SITES = [
    'twitter.com', 'x.com', 'facebook.com', 'instagram.com',
    'youtube.com', 'tiktok.com', 'linkedin.com', 'discord.com'
]

COMPLEX_DYNAMIC_SITES = [
    'amazon.com', 'ebay.com', 'cnn.com', 'bbc.com',
    'medium.com', 'reddit.com', 'github.com', 'stackoverflow.com'
]

# LLM Ranking Prompt Template - Cached for optimization
SMART_RANKING_PROMPT_TEMPLATE = """Rank ALL these web search results by relevance to: "{user_query}"
                                
                                For EACH URL, determine the BEST scraping method:
                                **beautifulsoup**: Simple static HTML sites, blogs, news articles, documentation
                                **crawl4ai**: Complex sites with dynamic content but no heavy JavaScript (e-commerce, modern news sites, academic papers)
                                **playwright**: JavaScript-heavy sites, SPAs, social media, interactive applications
                                
                                Return ALL {total_count} results as JSON array:
                                [
                                {{"id": 0, "relevance_score": 95, "method": "beautifulsoup", "reason": "Static blog site, simple HTML structure"}},
                                {{"id": 2, "relevance_score": 85, "method": "crawl4ai", "reason": "E-commerce site with dynamic content but no heavy JS"}},
                                {{"id": 1, "relevance_score": 75, "method": "playwright", "reason": "JavaScript-heavy application requiring browser rendering"}},
                                ... (continue for ALL {total_count} URLs)
                                ]
                                
                                **Analysis Guidelines:**
                                - **beautifulsoup**: Wikipedia, simple blogs, static documentation, basic news sites
                                - **crawl4ai**: Amazon, complex news sites, academic journals, modern content sites
                                - **playwright**: Twitter, Facebook, Instagram, SPAs, sites requiring JavaScript
                                
                                Consider:
                                1. URL domain patterns (github.com, stackoverflow.com, etc.)
                                2. Site complexity indicators in title/snippet
                                3. Known site types requiring specific methods
                                
                                Search Results:
                                {url_data}
                                
                                Return JSON array with ALL {total_count} URLs ranked by relevance with scraping method suggestions."""

# System Prompt for LLM - Cached
LLM_SYSTEM_PROMPT = """You are an expert at ranking web search results AND determining the best web scraping method for each URL. You understand when sites need JavaScript rendering (Playwright), advanced extraction (Crawl4AI), or simple parsing (BeautifulSoup)."""

# ==================== DEPENDENCY MANAGEMENT ====================

# Check Groq availability
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️ Groq not installed. Install with: pip install groq")

# ==================== UTILITY FUNCTIONS ====================

def check_groq_availability() -> bool:
    """Check if Groq is available and at least one API key is configured"""
    if not GROQ_AVAILABLE:
        return False
    return len(AVAILABLE_API_KEYS) > 0

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
    """Make Groq request with automatic fallback between API keys"""
    
    # Use default order if not specified
    if api_key_priority_order is None:
        api_key_priority_order = LLM_RANKER_API_ORDER
    
    last_error = None
    
    for key_name in api_key_priority_order:
        api_key = get_api_key_by_name(key_name)
        
        if not api_key or not api_key.strip():
            logger.warning(f"API key {key_name} not found or empty")
            continue
            
        try:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            logger.info(f"✅ Successfully used API key: {key_name}")
            return response
            
        except Exception as e:
            error_str = str(e).lower()
            logger.warning(f"❌ API key {key_name} failed: {e}")
            last_error = e
            
            # Check for rate limit errors
            rate_limit_indicators = [
                'rate limit', 'too many requests', 'quota exceeded', 
                'tokens exhausted', '429', 'rate_limit_exceeded',
                'insufficient_quota', 'billing'
            ]
            
            if any(indicator in error_str for indicator in rate_limit_indicators):
                logger.warning(f"⏳ Rate limit hit on {key_name}, trying next key...")
                continue
            else:
                logger.error(f"🔥 Non-rate-limit error on {key_name}: {e}")
                continue
    
    # All keys failed
    raise Exception(f"All API keys failed. Last error: {last_error}")

def prepare_url_data_for_ranking(search_results: List[Dict]) -> List[Dict]:
    """Prepare search results for LLM ranking analysis"""
    url_data = []
    for i, result in enumerate(search_results):
        url_data.append({
            'id': i,
            'title': result.get('title', ''),
            'url': result.get('url', ''),
            'snippet': result.get('snippet', '')
        })
    return url_data

def determine_simple_method(url: str) -> str:
    """Determine scraping method based on simple URL pattern matching"""
    url_lower = url.lower()
    
    # Check for JavaScript-heavy sites
    if any(site in url_lower for site in JAVASCRIPT_HEAVY_SITES):
        return 'playwright'
    
    # Check for complex dynamic sites
    if any(site in url_lower for site in COMPLEX_DYNAMIC_SITES):
        return 'crawl4ai'
    
    # Default to BeautifulSoup for simple sites
    return 'beautifulsoup'

def calculate_simple_relevance_score(result: Dict, query_words: List[str]) -> int:
    """Calculate relevance score using simple keyword matching"""
    score = 0
    title = result.get('title', '').lower()
    snippet = result.get('snippet', '').lower()
    
    for word in query_words:
        if word in title:
            score += 10  # Higher weight for title matches
        if word in snippet:
            score += 5   # Lower weight for snippet matches
    
    return score

def log_method_distribution(results: List[Dict]) -> None:
    """Log distribution of scraping methods for monitoring"""
    method_count = {}
    for result in results:
        method = result.get('suggested_method', 'unknown')
        method_count[method] = method_count.get(method, 0) + 1
    
    print(f"🎯 Method Distribution: {method_count}")

# ==================== MAIN RANKING FUNCTION ====================

async def rank_urls_with_method_selection(search_results: List[Dict], 
                                          user_query: str, 
                                          required_count: int = 5) -> List[Dict]:
    """
    MAIN INTELLIGENT URL RANKING FUNCTION with robust error handling
    
    Smart LLM-powered URL ranking with scraping method selection.
    Ranks URLs by relevance and suggests optimal scraping method for each.
    
    Args:
        search_results: List of search result dictionaries
        user_query: User's search query for relevance analysis
        required_count: Number of top results needed (not used, ranks all)
        
    Returns:
        List of ranked URLs with suggested scraping methods and reasoning
    """
    
    if not search_results:
        logger.warning("No search results provided")
        return []
    
    # Check system availability
    if not check_groq_availability():
        print("⚠️ LLM ranking not available, using simple ranking")
        return simple_rank_urls_with_methods(search_results, user_query, len(search_results))
    
    print(f"🧠 SMART LLM: Ranking {len(search_results)} URLs + Method Selection")
    print(f"🎯 Query: '{user_query}'")
    print(f"🔑 Available API keys: {len(AVAILABLE_API_KEYS)}")
    
    # Limit URLs to process
    urls_to_rank = search_results[:MAX_RANKING_URLS]
    
    try:
        # Generate intelligent ranking
        ranked_results = await _generate_intelligent_ranking(urls_to_rank, user_query)
        
        print(f"✅ SMART LLM completed: {len(ranked_results)} URLs ranked with methods")
        log_method_distribution(ranked_results)
        
        return ranked_results
        
    except Exception as e:
        print(f"❌ LLM ranking failed: {e}")
        print("🔄 Falling back to simple ranking")
        return simple_rank_urls_with_methods(search_results, user_query, len(search_results))

# ==================== INTELLIGENT RANKING ENGINE ====================

async def _generate_intelligent_ranking(search_results: List[Dict], user_query: str) -> List[Dict]:
    """Generate intelligent ranking using LLM analysis with better error handling"""
    
    try:
        # Prepare data for LLM analysis
        url_data = prepare_url_data_for_ranking(search_results)
        ranking_prompt = _build_ranking_prompt(user_query, url_data)
        
        print("🤖 Asking LLM to rank URLs + suggest scraping methods...")
        
        # Call LLM for intelligent analysis
        response = make_groq_request_with_fallback(
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": ranking_prompt}
            ],
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=MAX_TOKENS,
            api_key_priority_order=LLM_RANKER_API_ORDER
        )
        
        # Parse and process LLM response
        llm_output = response.choices[0].message.content.strip()
        ranked_results = _parse_intelligent_ranking(llm_output, search_results)
        
        return ranked_results
        
    except Exception as e:
        logger.error(f"Intelligent ranking failed: {e}")
        raise e  # Re-raise to trigger fallback in main function

def _build_ranking_prompt(user_query: str, url_data: List[Dict]) -> str:
    """Build comprehensive ranking prompt for LLM"""
    
    # Format URL data for prompt
    url_data_formatted = ""
    for item in url_data:
        url_data_formatted += f"""
                               ID: {item['id']}
                               Title: {item['title']}
                               URL: {item['url']}
                               Snippet: {item['snippet']}
                               ---
                               """
    
    # Build complete prompt
    return SMART_RANKING_PROMPT_TEMPLATE.format(
        user_query=user_query,
        total_count=len(url_data),
        url_data=url_data_formatted
    )

def _parse_intelligent_ranking(llm_output: str, original_results: List[Dict]) -> List[Dict]:
    """Parse LLM ranking response and create structured results"""
    
    try:
        print(f"🔍 Parsing SMART LLM output...")
        
        # Extract JSON from LLM response
        json_str = _extract_json_from_response(llm_output)
        if not json_str:
            raise ValueError("No valid JSON found in LLM response")
        
        ranking_data = json.loads(json_str)
        
        # Build ranked results with method selection
        ranked_results = _build_ranked_results(ranking_data, original_results)
        
        # Ensure all URLs are included and properly sorted
        ranked_results = _finalize_ranking(ranked_results, original_results)
        
        return ranked_results
        
    except Exception as e:
        print(f"❌ Error parsing SMART LLM ranking: {e}")
        return simple_rank_urls_with_methods(original_results, "", len(original_results))

def _extract_json_from_response(llm_output: str) -> str:
    """Extract JSON array from LLM response text"""
    start_idx = llm_output.find('[')
    end_idx = llm_output.rfind(']') + 1
    
    if start_idx >= 0 and end_idx > start_idx:
        return llm_output[start_idx:end_idx]
    
    return None

def _build_ranked_results(ranking_data: List[Dict], original_results: List[Dict]) -> List[Dict]:
    """Build ranked results from LLM analysis data"""
    
    ranked_results = []
    used_ids = set()
    
    for item in ranking_data:
        result_id = item.get('id')
        relevance_score = item.get('relevance_score', 0)
        suggested_method = item.get('method', 'beautifulsoup')
        reason = item.get('reason', '')
        
        if 0 <= result_id < len(original_results) and result_id not in used_ids:
            result = original_results[result_id].copy()
            result['relevance_score'] = relevance_score
            result['suggested_method'] = suggested_method
            result['method_reason'] = reason
            ranked_results.append(result)
            used_ids.add(result_id)
    
    return ranked_results, used_ids

def _finalize_ranking(ranked_results: List[Dict], original_results: List[Dict]) -> List[Dict]:
    """Finalize ranking by adding missing URLs and sorting"""
    
    # Get used IDs from previous processing
    if isinstance(ranked_results, tuple):
        ranked_results, used_ids = ranked_results
    else:
        used_ids = set()
    
    # Add missing URLs with default method
    for i, original_result in enumerate(original_results):
        if i not in used_ids:
            result = original_result.copy()
            result['relevance_score'] = 10  # Low default score
            result['suggested_method'] = 'beautifulsoup'
            result['method_reason'] = "Fallback - LLM didn't suggest method"
            ranked_results.append(result)
    
    # Sort by relevance score (highest first)
    ranked_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    return ranked_results

# ==================== SIMPLE FALLBACK RANKING ====================

def simple_rank_urls_with_methods(search_results: List[Dict], 
                                  user_query: str, 
                                  total_count: int) -> List[Dict]:
    """
    Simple fallback ranking system with basic method selection
    
    Used when LLM ranking is unavailable or fails.
    Provides basic relevance scoring and pattern-based method selection.
    
    Args:
        search_results: List of search result dictionaries
        user_query: User's search query for relevance scoring
        total_count: Total number of results to process
        
    Returns:
        List of ranked URLs with basic method suggestions
    """
    
    print(f"📊 Simple ranking with method selection for {len(search_results)} URLs")
    
    # Prepare query words for scoring
    query_words = user_query.lower().split() if user_query else []
    
    # Process each result
    for result in search_results:
        # Calculate simple relevance score
        score = calculate_simple_relevance_score(result, query_words)
        
        # Determine scraping method using simple patterns
        suggested_method = determine_simple_method(result.get('url', ''))
        
        # Add ranking metadata
        result['relevance_score'] = score
        result['suggested_method'] = suggested_method
        result['method_reason'] = f"Simple pattern matching for {suggested_method}"
    
    # Sort by relevance score
    ranked_results = sorted(
        search_results, 
        key=lambda x: x.get('relevance_score', 0), 
        reverse=True
    )
    
    # Log results
    print(f"📊 Simple ranking completed for {len(ranked_results)} URLs")
    log_method_distribution(ranked_results)
    
    return ranked_results

# ==================== CONVENIENCE FUNCTIONS ====================

async def rank_urls(search_results: List[Dict], 
                    user_query: str, 
                    count: int = 5) -> List[Dict]:
    """
    Convenience function for URL ranking (backward compatibility)
    
    Args:
        search_results: Search results to rank
        user_query: Query for relevance analysis
        count: Number of results needed
        
    Returns:
        Ranked list of URLs with method suggestions
    """
    return await rank_urls_with_method_selection(search_results, user_query, count)

def get_method_statistics(ranked_results: List[Dict]) -> Dict[str, int]:
    """
    Get statistics about method distribution in ranked results
    
    Args:
        ranked_results: List of ranked URLs with method suggestions
        
    Returns:
        Dictionary with method counts
    """
    method_count = {}
    for result in ranked_results:
        method = result.get('suggested_method', 'unknown')
        method_count[method] = method_count.get(method, 0) + 1
    
    return method_count
