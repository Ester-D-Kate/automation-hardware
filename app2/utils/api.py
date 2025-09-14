"""
Simple API - All external functions here
Enhanced with unified scraper and improved fallback system
"""

import asyncio
from .search.scraper import search_and_scrape_complete
from .search.hardware_monitor import get_simple_hardware_info, print_hardware_status
from .search.search_config import get_config, print_config_status

async def search_and_scrape(query, required_results=5, url_multiplier=10):
    """
    Main Enhanced API Function - Complete Workflow
    
    This follows your exact requirements:
    1. Gets URLs from local SearXNG (alice_ai_agent/.env) with DuckDuckGo fallback
    2. Applies URL multiplier (5x or 10x more URLs than needed)
    3. Uses Groq Cloud Ollama 70B to rank URLs by relevance to user query
    4. Scrapes URLs in parallel based on hardware availability
    5. Uses BeautifulSoup for simple sites, Playwright for JS sites
    6. Monitors hardware resources during scraping
    7. Has intelligent fallback when URLs fail
    8. Returns exactly the number of results requested
    
    Args:
        query: What to search for (string)
        required_results: How many final results needed (default: 5)
        url_multiplier: URL multiplier - 5 or 10 (default: 10)
    
    Returns:
        List of results with title, url, content, quality scores, and metadata
    """
    print(f"\n🚀 Enhanced Search & Scrape API")
    print(f"📝 Query: '{query}'")
    print(f"🎯 Required Results: {required_results}")
    print(f"📊 URL Multiplier: {url_multiplier}x")
    
    # Show system status
    print_config_status()
    print_hardware_status()
    
    try:
        # Use unified scraper with complete workflow
        results = await search_and_scrape_complete(query, required_results, url_multiplier)
        
        print(f"✅ API completed: {len(results)} results returned")
        return results
        
    except Exception as e:
        print(f"❌ API Error: {e}")
        return []

def search_and_scrape_simple(query, max_results=5):
    """
    Simple API function for basic usage (backward compatibility)
    Uses default settings for simple searches
    
    Args:
        query: What to search for
        max_results: Maximum results to return
    
    Returns:
        List of basic search results
    """
    return asyncio.run(search_and_scrape(query, max_results, 5))

def get_system_info():
    """
    Get comprehensive system information
    Includes hardware status and configuration
    """
    from .search.hardware_monitor import get_simple_hardware_info
    from .search.search_config import get_config
    
    hardware_info = get_simple_hardware_info()
    config_info = get_config()
    
    return {
        'hardware': hardware_info,
        'configuration': config_info,
        'status': 'operational'
    }

async def test_complete_workflow(test_query="Python programming tutorial"):
    """
    Test the complete enhanced workflow
    
    Args:
        test_query: Query to test with
    
    Returns:
        Test results and performance metrics
    """
    print(f"\n🧪 Testing Complete Enhanced Workflow")
    print(f"🔍 Test Query: '{test_query}'")
    
    import time
    start_time = time.time()
    
    # Test with small result set for faster testing
    results = await search_and_scrape(test_query, required_results=3, url_multiplier=5)
    
    end_time = time.time()
    duration = end_time - start_time
    
    test_report = {
        'query': test_query,
        'duration_seconds': round(duration, 2),
        'results_count': len(results),
        'successful_scrapes': sum(1 for r in results if r.get('success', False)),
        'average_quality_score': sum(r.get('quality_score', 0) for r in results) / len(results) if results else 0,
        'methods_used': list(set(r.get('method', 'Unknown') for r in results)),
        'status': 'success' if results else 'no_results'
    }
    
    print(f"\n📊 Test Report:")
    print(f"   Duration: {test_report['duration_seconds']} seconds")
    print(f"   Results: {test_report['results_count']}")
    print(f"   Success Rate: {test_report['successful_scrapes']}/{test_report['results_count']}")
    print(f"   Avg Quality: {test_report['average_quality_score']:.1f}")
    print(f"   Methods: {', '.join(test_report['methods_used'])}")
    
    return test_report

# Main function for testing
if __name__ == "__main__":
    # Run test
    test_result = asyncio.run(test_complete_workflow())
    print("\n✅ API Test Complete")