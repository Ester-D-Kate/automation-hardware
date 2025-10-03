"""
Alice Search Engine - Complete FastAPI Application
Three endpoints: Search, Scraper, and Chat
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from dotenv import load_dotenv
from logs_config import setup_clean_logging
from api.search import router as search_router
from api.chat import router as chat_router

load_dotenv()
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Alice AI Assistant",
    description="AI-powered search, scraping, and chat assistant",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(search_router, tags=["search"])
app.include_router(chat_router, tags=["chat"])

# Root endpoint
@app.get("/")
async def root():
    """Welcome to Alice AI Assistant"""
    return {
        "message": "Welcome to Alice AI Assistant!",
        "version": "2.0.0",
        "endpoints": {
            "chat": "/api/chat - Chat with Alice AI Assistant",
            "search": "/api/search - AI-powered web search with insights",
            "scraper": "/api/scraper - Raw web scraping results",
            "tools": "/api/chat/tools - Get Alice's available tools",
            "docs": "/docs - Interactive API documentation"
        },
        "status": "ready"
    }

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    
    logger.info(f"🤖 Starting Alice AI Assistant on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="critical",
        access_log=False,
        use_colors=False
    )
