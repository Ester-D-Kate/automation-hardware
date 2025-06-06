import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from utils.api import router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Alice AI Assistant",
    description="AI Assistant with speech recognition, computer control, and smart home integration",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to Alice AI Assistant API",
        "version": "0.1.0",
        "endpoints": {
            "/process_audio": "POST - Process audio and get AI response",
            "/reset_conversation": "POST - Reset conversation context"
        }
    }

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Alice AI Assistant")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Alice AI Assistant")