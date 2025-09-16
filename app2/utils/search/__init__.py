"""
Search Package - Unified and Simplified
FIXED: Removed SearXNG imports that don't exist anymore
"""

# Main unified scraper (everything in one file)
from .scraper import (
    scrape_single_url,
    search_and_scrape_complete,
    scrape_simple_website
)

# FIXED: Enhanced search engine with DuckDuckGo only
from .search_engine import (
    search_web_enhanced,
    search_duckduckgo,
    search_web
    # REMOVED: search_local_searxng - no longer exists
)

# Advanced scrapers
from .playwright_scraper import scrape_javascript_website, should_use_playwright, PLAYWRIGHT_AVAILABLE
from .crawl4ai_scraper import scrape_with_crawl4ai, should_use_crawl4ai, CRAWL4AI_AVAILABLE

# LLM ranking system
from .llm_ranker import rank_urls_with_llm, simple_rank_urls

# Hardware monitoring
from .hardware_monitor import (
    get_simple_hardware_info,
    can_handle_parallel,
    get_optimal_parallel_count,
    print_hardware_status
)

# Configuration
from .search_config import get_config, print_config_status