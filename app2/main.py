"""
Main Application - Enhanced Intelligent Search & Scrape System
FastAPI web server + command line demo
"""

import asyncio
import sys

# Fix Windows asyncio event loop policy for Playwright
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Your existing imports continue below...
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from utils.api import search_and_scrape, test_complete_workflow, get_system_info

# FastAPI app for web API
app = FastAPI(
    title="Enhanced Search & Scrape API",
    description="Intelligent web scraping with dynamic thread management",
    version="2.0"
)

# Enhanced CORS middleware for cross-origin support
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # Allow all origins for development
        "http://localhost:3000",  # React dev server
        "http://localhost:8080",  # Vue dev server  
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://100.89.24.38:8888",  # Local SearXNG instance
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "*", 
        "Content-Type", 
        "Authorization", 
        "Access-Control-Allow-Headers",
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Methods"
    ],
    expose_headers=["*"]
)

# Request models
class SearchRequest(BaseModel):
    query: str
    required_results: int = 5
    url_multiplier: int = 10

class TestRequest(BaseModel):
    test_query: str = "Python programming tutorial"

# API Routes
@app.get("/")
async def root():
    """API status and information"""
    system_info = get_system_info()
    return {
        "status": "Enhanced Search & Scrape API v2.0",
        "message": "Dynamic thread shifting scraper ready!",
        "capabilities": system_info['capabilities'],
        "hardware": system_info['hardware']
    }

@app.post("/search")
async def api_search(request: SearchRequest):
    """
    Main search and scrape endpoint
    
    Uses complete workflow:
    1. Local SearXNG → DuckDuckGo → Public SearXNG fallback
    2. LLM ranking with Groq Ollama 70B
    3. Dynamic parallel scraping with thread shifting
    4. BeautifulSoup → Playwright fallback
    """
    try:
        results = await search_and_scrape(
            query=request.query,
            required_results=request.required_results,
            url_multiplier=request.url_multiplier
        )
        
        return {
            "status": "success",
            "query": request.query,
            "results_count": len(results),
            "results": results
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "query": request.query
        }

@app.post("/test")
async def api_test(request: TestRequest):
    """Test the complete workflow"""
    try:
        test_result = await test_complete_workflow(request.test_query)
        return test_result
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/system")
async def api_system():
    """Get system information and status"""
    return get_system_info()

@app.get("/health")
async def health_check():
    """Simple health check"""
    return {"status": "healthy", "service": "Enhanced Search & Scrape API"}

async def demo_enhanced_system():
    """
    Demonstrate the complete enhanced system following your structure:
    
    1. Local SearXNG URLs (from alice_ai_agent/.env) → DuckDuckGo fallback
    2. URL multiplier (gets 5x or 10x more URLs than requested)
    3. LLM ranking using Groq Cloud Ollama 70B
    4. Parallel scraping with hardware monitoring  
    5. BeautifulSoup → Playwright fallback
    6. Intelligent error recovery and thread management
    """
    
    print("🌟 Enhanced Intelligent Search & Scrape System")
    print("=" * 60)
    
    # Show system capabilities
    print("🔧 System Information:")
    system_info = get_system_info()
    print(f"   CPU Cores: {system_info['hardware']['cpu_cores']}")
    print(f"   Available Memory: {system_info['hardware']['memory_available_gb']} GB")
    print(f"   Local SearXNG: {system_info['configuration']['local_searxng_url']}")
    print(f"   LLM Model: {system_info['configuration']['llm_model']}")
    
    # Demo searches with different parameters
    demo_queries = [
        {
            'query': 'machine learning tutorial for beginners',
            'required_results': 3,
            'url_multiplier': 10,
            'description': 'Educational content search'
        },
        {
            'query': 'latest AI news 2024',
            'required_results': 2,
            'url_multiplier': 5,
            'description': 'News search with lower multiplier'
        }
    ]
    
    for demo in demo_queries:
        print(f"\n{'='*60}")
        print(f"📝 Demo: {demo['description']}")
        print(f"🔍 Query: '{demo['query']}'")
        print(f"🎯 Target: {demo['required_results']} results")
        print(f"📊 Multiplier: {demo['url_multiplier']}x")
        print("-" * 60)
        
        try:
            # Run enhanced search and scrape
            results = await search_and_scrape(
                query=demo['query'],
                required_results=demo['required_results'],
                url_multiplier=demo['url_multiplier']
            )
            
            # Display results
            if results:
                print(f"\n🎉 Successfully retrieved {len(results)} results:")
                for i, result in enumerate(results, 1):
                    print(f"\n   📄 Result {i}:")
                    print(f"      Title: {result.get('title', 'No title')}")
                    print(f"      URL: {result.get('url', '')}")
                    print(f"      Method: {result.get('method', 'Unknown')}")
                    print(f"      Quality Score: {result.get('quality_score', 0)}/100")
                    print(f"      Content Length: {len(result.get('content', '').split())} words")
                    print(f"      LLM Relevance: {result.get('relevance_score', 'N/A')}")
                    
                    # Show content preview
                    content = result.get('content', '')
                    if content:
                        preview = content[:200] + "..." if len(content) > 200 else content
                        print(f"      Preview: {preview}")
            else:
                print("❌ No results retrieved")
                
        except Exception as e:
            print(f"💥 Demo failed: {e}")

async def run_system_test():
    """
    Run comprehensive system test
    """
    print(f"\n{'='*60}")
    print("🧪 Running System Test")
    print("-" * 60)
    
    # Test the complete workflow
    test_result = await test_complete_workflow("Python web scraping guide")
    
    if test_result['status'] == 'success':
        print("✅ System Test PASSED")
    else:
        print("❌ System Test FAILED")
    
    return test_result

def interactive_mode():
    """
    Interactive mode for manual testing
    """
    print(f"\n{'='*60}")
    print("🎮 Interactive Mode")
    print("Type your search query (or 'quit' to exit)")
    print("-" * 60)
    
    while True:
        try:
            query = input("\n🔍 Enter search query: ").strip()
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if not query:
                print("⚠️ Please enter a valid query")
                continue
            
            # Get user preferences
            try:
                required_results = int(input("📊 How many results do you want? (default 3): ") or "3")
                url_multiplier = int(input("🔢 URL multiplier (5 or 10, default 10): ") or "10")
                
                if url_multiplier not in [5, 10]:
                    print("⚠️ Using default multiplier of 10")
                    url_multiplier = 10
                    
            except ValueError:
                print("⚠️ Using default values: 3 results, 10x multiplier")
                required_results = 3
                url_multiplier = 10
            
            # Run search
            print(f"\n🚀 Searching for: '{query}'...")
            results = asyncio.run(search_and_scrape(query, required_results, url_multiplier))
            
            if results:
                print(f"\n✅ Found {len(results)} results!")
                for i, result in enumerate(results, 1):
                    print(f"\n📄 Result {i}: {result.get('title', 'No title')}")
                    print(f"   URL: {result.get('url', '')}")
                    print(f"   Quality: {result.get('quality_score', 0)}/100")
                    print(f"   Words: {len(result.get('content', '').split())}")
            else:
                print("❌ No results found")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"💥 Error: {e}")

async def main():
    """
    Main function - orchestrates the entire system
    """
    try:
        print("🚀 Starting Enhanced Intelligent Search & Scrape System")
        
        # Run demonstrations
        await demo_enhanced_system()
        
        # Run system test
        test_result = await run_system_test()
        
        # Interactive mode
        interactive_mode()
        
    except KeyboardInterrupt:
        print("\n👋 System shutdown requested")
    except Exception as e:
        print(f"💥 System error: {e}")
        raise

# Command Line Demo (when run directly with python main.py)
if __name__ == "__main__":
    print("🚀 Running Enhanced Search & Scrape Demo")
    print("💡 For API server, use: uvicorn main:app --host 0.0.0.0 --port 8000")
    print("="*60)
    
    # Run the main application
    asyncio.run(main())