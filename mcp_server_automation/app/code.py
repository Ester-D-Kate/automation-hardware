# app/main.py

from fastapi import FastAPI

# Initialize the FastAPI application
app = FastAPI(
    title="Hello World FastAPI",
    description="A very simple FastAPI application.",
    version="1.0.0"
)

@app.get("/")
async def read_root():
    """
    Returns a simple "Hello, World!" message.
    """
    return {"message": "Hello, World!"}

@app.get("/health")
async def health_check():
    """
    Endpoint to check the application's health.
    """
    return {"status": "ok"}