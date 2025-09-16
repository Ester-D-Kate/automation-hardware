"""
LLM URL Ranker + METHOD SELECTOR using Groq Cloud
SMART: Ranks URLs AND suggests best scraping method for each!
"""

import json
from .search_config import GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURE, MAX_RANKING_URLS

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️ Groq not installed. Install with: pip install groq")

async def rank_urls_with_method_selection(search_results, user_query, required_count=5):
    """
    🧠 SMART: LLM ranks URLs AND suggests best scraping method for each!
    
    Returns URLs with:
    - Relevance ranking
    - Suggested scraping method (beautifulsoup/crawl4ai/playwright)
    - Reasoning for method choice
    """
    if not GROQ_AVAILABLE or not GROQ_API_KEY:
        print("⚠️ LLM ranking not available, using simple ranking")
        return simple_rank_urls_with_methods(search_results, user_query, len(search_results))

    print(f"🧠 SMART LLM: Ranking {len(search_results)} URLs + Method Selection")
    print(f"🎯 Query: '{user_query}'")

    urls_to_rank = search_results[:MAX_RANKING_URLS]

    try:
        client = Groq(api_key=GROQ_API_KEY)

        # Prepare URLs for LLM with method selection
        url_data = []
        for i, result in enumerate(urls_to_rank):
            url_data.append({
                'id': i,
                'title': result.get('title', ''),
                'url': result.get('url', ''),
                'snippet': result.get('snippet', '')
            })

        # Create SMART ranking prompt with method selection
        ranking_prompt = create_smart_ranking_prompt(user_query, url_data, len(url_data))

        print("🤖 Asking LLM to rank URLs + suggest scraping methods...")
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at ranking web search results AND determining the best web scraping method for each URL. You understand when sites need JavaScript rendering (Playwright), advanced extraction (Crawl4AI), or simple parsing (BeautifulSoup)."
                },
                {
                    "role": "user",
                    "content": ranking_prompt
                }
            ],
            temperature=LLM_TEMPERATURE,
            max_tokens=3000  # Increased for method selection
        )

        llm_output = response.choices[0].message.content.strip()
        ranked_results = parse_smart_llm_ranking(llm_output, search_results)

        print(f"✅ SMART LLM completed: {len(ranked_results)} URLs ranked with methods")
        return ranked_results

    except Exception as e:
        print(f"❌ LLM ranking failed: {e}")
        print("🔄 Falling back to simple ranking")
        return simple_rank_urls_with_methods(search_results, user_query, len(search_results))

def create_smart_ranking_prompt(user_query, url_data, total_count):
    """
    Create SMART prompt for URL ranking + method selection
    """
    prompt = f"""
Rank ALL these web search results by relevance to: "{user_query}"

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
"""

    for item in url_data:
        prompt += f"""
ID: {item['id']}
Title: {item['title']}
URL: {item['url']}
Snippet: {item['snippet']}
---
"""

    prompt += f"\nReturn JSON array with ALL {total_count} URLs ranked by relevance with scraping method suggestions."
    return prompt

def parse_smart_llm_ranking(llm_output, original_results):
    """
    Parse LLM ranking response with method selection
    """
    try:
        print(f"🔍 Parsing SMART LLM output...")
        
        # Extract JSON
        json_str = None
        start_idx = llm_output.find('[')
        end_idx = llm_output.rfind(']') + 1
        
        if start_idx >= 0 and end_idx > start_idx:
            json_str = llm_output[start_idx:end_idx]
        
        if json_str:
            ranking_data = json.loads(json_str)
            
            # Build ranked results with method selection
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
            
            # Add missing URLs with default method
            for i, original_result in enumerate(original_results):
                if i not in used_ids:
                    result = original_result.copy()
                    result['relevance_score'] = 10
                    result['suggested_method'] = 'beautifulsoup'  # Default fallback
                    result['method_reason'] = "Fallback - LLM didn't suggest method"
                    ranked_results.append(result)
            
            # Sort by relevance score
            ranked_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            # Log method distribution
            method_count = {}
            for result in ranked_results:
                method = result.get('suggested_method', 'unknown')
                method_count[method] = method_count.get(method, 0) + 1
            
            print(f"🎯 SMART Method Distribution: {method_count}")
            
            return ranked_results
        
        else:
            raise ValueError("No valid JSON found in LLM response")
            
    except Exception as e:
        print(f"❌ Error parsing SMART LLM ranking: {e}")
        return simple_rank_urls_with_methods(original_results, "", len(original_results))

def simple_rank_urls_with_methods(search_results, user_query, total_count):
    """
    Simple fallback ranking with basic method selection
    """
    print(f"📊 Simple ranking with method selection for {len(search_results)} URLs")
    
    query_words = user_query.lower().split() if user_query else []
    
    for result in search_results:
        # Simple relevance scoring
        score = 0
        title = result.get('title', '').lower()
        snippet = result.get('snippet', '').lower()
        url = result.get('url', '').lower()
        
        for word in query_words:
            if word in title:
                score += 10
            if word in snippet:
                score += 5
        
        # Simple method selection based on URL patterns
        suggested_method = determine_simple_method(result.get('url', ''))
        
        result['relevance_score'] = score
        result['suggested_method'] = suggested_method
        result['method_reason'] = f"Simple pattern matching for {suggested_method}"
    
    # Sort by score
    ranked = sorted(search_results, key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    # Log method distribution
    method_count = {}
    for result in ranked:
        method = result.get('suggested_method', 'unknown')
        method_count[method] = method_count.get(method, 0) + 1
    
    print(f"📊 Simple Method Distribution: {method_count}")
    
    return ranked

def determine_simple_method(url):
    """
    Simple method determination based on URL patterns
    """
    url_lower = url.lower()
    
    # Playwright sites (JavaScript-heavy)
    js_sites = [
        'twitter.com', 'x.com', 'facebook.com', 'instagram.com',
        'youtube.com', 'tiktok.com', 'linkedin.com'
    ]
    
    if any(site in url_lower for site in js_sites):
        return 'playwright'
    
    # Crawl4AI sites (complex but not JS-heavy)
    complex_sites = [
        'amazon.com', 'ebay.com', 'cnn.com', 'bbc.com',
        'medium.com', 'reddit.com', 'github.com'
    ]
    
    if any(site in url_lower for site in complex_sites):
        return 'crawl4ai'
    
    # Default to BeautifulSoup
    return 'beautifulsoup'

# Backward compatibility
async def rank_urls_with_llm(search_results, user_query, required_count=5):
    """Backward compatibility wrapper"""
    return await rank_urls_with_method_selection(search_results, user_query, required_count)

def simple_rank_urls(search_results, user_query, total_count):
    """Backward compatibility wrapper"""
    return simple_rank_urls_with_methods(search_results, user_query, total_count)

def print_ranking_results(ranked_results):
    """Print ranking results with method suggestions"""
    print(f"\n🏆 Top {len(ranked_results)} Ranked URLs with Methods:")
    for i, result in enumerate(ranked_results, 1):
        method = result.get('suggested_method', 'unknown')
        score = result.get('relevance_score', 0)
        print(f" {i}. [{score}] {method.upper()}: {result.get('title', 'No title')}")
        print(f"    URL: {result.get('url', '')}")
        print(f"    Reason: {result.get('method_reason', 'No reason')}")
    print()
