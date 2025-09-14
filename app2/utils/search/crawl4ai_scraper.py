"""
Crawl4AI Scraper - Intelligent Content Extraction
Smart middle tier between BeautifulSoup and Playwright
"""

try:
    from crawl4ai import AsyncWebCrawler
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    print("⚠️ Crawl4AI not installed. Install with: pip install crawl4ai")

import asyncio
import time
import re
from bs4 import BeautifulSoup

# Domains that benefit from Crawl4AI's advanced extraction
CRAWL4AI_DOMAINS = {
    # News sites
    'cnn.com', 'bbc.com', 'reuters.com', 'ap.org', 'npr.org',
    'theguardian.com', 'nytimes.com', 'wsj.com', 'bloomberg.com',
    
    # Academic sites
    'arxiv.org', 'scholar.google.com', 'researchgate.net',
    'ieee.org', 'acm.org', 'springer.com', 'sciencedirect.com',
    
    # E-commerce
    'amazon.com', 'ebay.com', 'etsy.com', 'shopify.com',
    'aliexpress.com', 'walmart.com',
    
    # Tech blogs/complex sites
    'medium.com', 'dev.to', 'stackoverflow.com', 'reddit.com',
    'hackernews.ycombinator.com', 'github.com'
}

def should_use_crawl4ai(url, content_length=0, content_sample=""):
    """
    Smart criteria to determine if Crawl4AI should be used
    Now that we fixed Windows compatibility, we can be more aggressive
    
    Args:
        url: The URL being scraped
        content_length: Length of content from BeautifulSoup
        content_sample: Sample of content to analyze
    
    Returns:
        bool: True if Crawl4AI should be used
    """
    if not CRAWL4AI_AVAILABLE:
        return False
    
    # Criterion 1: BeautifulSoup got < 50 words (back to original threshold)
    if content_length > 0:
        word_count = len(content_sample.split()) if content_sample else 0
        if word_count < 50:
            print(f"🔄 Crawl4AI trigger: Low word count ({word_count} words)")
            return True
    
    # Criterion 2: Content looks messy/mixed
    if content_sample:
        messy_indicators = [
            'javascript', 'advertisement', 'cookie', 'subscribe',
            'login', 'register', 'popup', 'modal', 'sidebar'
        ]
        messy_count = sum(1 for indicator in messy_indicators 
                         if indicator in content_sample.lower())
        if messy_count >= 3:
            print(f"🔄 Crawl4AI trigger: Messy content detected ({messy_count} indicators)")
            return True
    
    # Criterion 3: Beneficial domains (back to full list)
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()
    for crawl4ai_domain in CRAWL4AI_DOMAINS:
        if crawl4ai_domain in domain:
            print(f"🔄 Crawl4AI trigger: Beneficial domain ({crawl4ai_domain})")
            return True
    
    return False

async def scrape_with_crawl4ai(url, timeout=30, max_retries=2):
    """
    Scrape website using Crawl4AI HTTP-only mode (no browser, no Playwright)
    Fixes Windows NotImplementedError by using AsyncHTTPCrawlerStrategy
    
    Args:
        url: Website URL to scrape
        timeout: How long to wait for page to load
        max_retries: Number of retry attempts for failed connections
    
    Returns:
        Dictionary with title, content, and success status
    """
    if not CRAWL4AI_AVAILABLE:
        return {
            'success': False,
            'title': '',
            'content': '',
            'method': 'Crawl4AI',
            'error': 'Crawl4AI not available'
        }
    
    print(f"🕷️ Crawl4AI HTTP-only scraping: {url}")
    
    # Import the HTTP-only strategy to avoid Playwright
    from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy
    from crawl4ai import HTTPCrawlerConfig
    
    # Create HTTP-only crawler strategy (no browser involved)
    http_config = HTTPCrawlerConfig(
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br'
        },
        follow_redirects=True,
        verify_ssl=False  # More lenient for testing
    )
    
    http_strategy = AsyncHTTPCrawlerStrategy(browser_config=http_config)
    
    # Retry logic for handling connection timeouts
    for attempt in range(max_retries + 1):
        try:
            # Use AsyncWebCrawler with HTTP-only strategy
            async with AsyncWebCrawler(
                crawler_strategy=http_strategy,
                verbose=False
            ) as crawler:
                
                result = await crawler.arun(
                    url=url,
                    word_count_threshold=10,
                    bypass_cache=True,
                    page_timeout=45000,  # Page timeout in milliseconds (45 seconds)
                    # HTTP-only specific options
                    process_iframes=False,
                    remove_overlay_elements=True
                )
                
                if result.success:
                    # Extract raw content 
                    raw_content = result.extracted_content or result.cleaned_html or result.markdown or ""
                    title = ""
                    
                    # Try to extract title from metadata
                    if hasattr(result, 'metadata') and result.metadata:
                        title = result.metadata.get('title', '')
                    
                    # Clean HTML properly using BeautifulSoup
                    clean_content = extract_clean_text_from_html(raw_content)
                    
                    # Apply additional cleaning
                    clean_content = clean_crawl4ai_content(clean_content)
                    
                    if len(clean_content.split()) > 10:  # Meaningful content threshold
                        print(f"✅ Crawl4AI HTTP success: {len(clean_content)} chars, {len(clean_content.split())} words")
                        return {
                            'success': True,
                            'title': title,
                            'content': clean_content,
                            'method': 'Crawl4AI-HTTP',
                            'word_count': len(clean_content.split()),
                            'quality_score': min(len(clean_content.split()) * 2, 100)
                        }
                    else:
                        print(f"⚠️ Crawl4AI HTTP minimal content: {len(clean_content)} chars")
                else:
                    print(f"⚠️ Crawl4AI HTTP request failed")
        
        except Exception as e:
            if attempt < max_retries:
                print(f"🔄 Crawl4AI attempt {attempt + 1} failed, retrying... ({str(e)})")
                await asyncio.sleep(2 * (attempt + 1))  # Exponential backoff
                continue
            else:
                print(f"❌ Crawl4AI HTTP error after {max_retries + 1} attempts: {str(e)}")
                return {
                    'success': False,
                    'title': '',
                    'content': '',
                    'method': 'Crawl4AI-HTTP',
                    'error': f"HTTP strategy failed after retries: {str(e)}"
                }
    
    # If we get here, all attempts failed
    return {
        'success': False,
        'title': '',
        'content': '',
        'method': 'Crawl4AI-HTTP',
        'error': 'HTTP request failed or insufficient content after all retries'
    }

def extract_clean_text_from_html(html_content):
    """
    Extract clean text from HTML using BeautifulSoup
    Removes all HTML tags and extracts only readable text
    """
    if not html_content:
        return ""
    
    try:
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'button', 'input']):
            element.decompose()
        
        # Extract text
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
        
    except Exception as e:
        print(f"⚠️ HTML parsing error: {e}")
        # Fallback: simple tag removal
        text = re.sub('<[^<]+?>', '', html_content)
        return re.sub(r'\s+', ' ', text).strip()

def clean_crawl4ai_content(content):
    """
    Clean and optimize Crawl4AI extracted content
    """
    if not content:
        return ""
    
    # Remove excessive whitespace and normalize
    content = re.sub(r'\s+', ' ', content)
    content = content.strip()
    
    # Remove common boilerplate phrases
    boilerplate_patterns = [
        r'accept cookies?',
        r'privacy policy',
        r'terms of service',
        r'subscribe to newsletter',
        r'follow us on',
        r'share this article',
        r'sign in',
        r'register',
        r'advertisement',
        r'ad feedback',
        r'close'
    ]
    
    for pattern in boilerplate_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    # Remove short fragments (less than 3 words)
    words = content.split()
    meaningful_words = []
    for word in words:
        if len(word.strip()) > 2:
            meaningful_words.append(word)
    
    return ' '.join(meaningful_words)

# Simple test function
async def test_crawl4ai():
    """Test Crawl4AI functionality"""
    test_url = "https://example.com"
    result = await scrape_with_crawl4ai(test_url)
    print(f"Crawl4AI Test Result: {result}")
    return result

if __name__ == "__main__":
    # Quick test
    asyncio.run(test_crawl4ai())