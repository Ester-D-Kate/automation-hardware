#Imports and Setup
import logging
from pymongo import MongoClient, ASCENDING, DESCENDING
import datetime
from typing import List, Dict, Optional, Any

from utils.config import MONGO_URI

logger = logging.getLogger(__name__)

# Connect to MongoDB
try:
    client = MongoClient(MONGO_URI)
    db = client.alice_assistant  # Database name
    
    # Collections
    conversations = db.conversations
    messages = db.messages
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise

def init_indexes():
    """Initialize database indexes for better query performance"""
    logger.info("Initializing database indexes...")
    try:
        # Create indexes for conversations collection
        conversations.create_index([("conversation_id", ASCENDING)], unique=True)
        conversations.create_index([("user_id", ASCENDING)])
        conversations.create_index([("created_at", DESCENDING)])
        
        # Create indexes for messages collection
        messages.create_index([("message_id", ASCENDING)], unique=True)
        messages.create_index([("conversation_id", ASCENDING)])
        messages.create_index([("created_at", DESCENDING)])
        
        logger.info("Database indexes initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database indexes: {e}")
        raise

def create_conversation(user_id: str) -> str:
    """Create a new conversation and return its ID"""
    conversation_id = f"{user_id}-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    conversations.insert_one({
        "conversation_id": conversation_id,
        "user_id": user_id,
        "created_at": datetime.datetime.utcnow(),
        "updated_at": datetime.datetime.utcnow()
    })
    
    return conversation_id

def get_conversation(conversation_id: str) -> Dict:
    """Get a conversation by ID"""
    return conversations.find_one({"conversation_id": conversation_id})

def store_message(conversation_id: str, role: str, content: str) -> str:
    """Store a message in the database and return its ID"""
    message_id = f"{conversation_id}-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    
    messages.insert_one({
        "message_id": message_id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "created_at": datetime.datetime.utcnow()
    })
    
    # Update conversation's updated_at timestamp
    conversations.update_one(
        {"conversation_id": conversation_id},
        {"$set": {"updated_at": datetime.datetime.utcnow()}}
    )
    
    return message_id

def get_message(message_id: str) -> Dict:
    """Get a message by ID"""
    return messages.find_one({"message_id": message_id})

def get_conversation_messages(conversation_id: str, limit: int = 10) -> List[Dict]:
    """Get messages for a conversation, limited to the most recent ones"""
    return list(
        messages.find({"conversation_id": conversation_id})
        .sort("created_at", 1)
        .limit(limit)
    )

def format_messages_for_llm(conversation_messages: List[Dict]) -> List[Dict]:
    """Format messages for sending to LLM"""
    formatted_messages = []
    
    for msg in conversation_messages:
        formatted_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    return formatted_messages

def store_conversation_summary(conversation_id: str, summary: str) -> None:
    """Store a summary of the conversation for future context"""
    conversations.update_one(
        {"conversation_id": conversation_id},
        {"$set": {
            "context_summary": summary,
            "summary_updated_at": datetime.datetime.utcnow()
        }}
    )

def get_conversation_context(conversation_id: str) -> str:
    """Get the conversation context (either summary or recent messages)"""
    conversation = conversations.find_one({"conversation_id": conversation_id})
    
    if not conversation:
        return ""
    
    # If we have a summary, use that
    if "context_summary" in conversation:
        return conversation["context_summary"]
    
    # Otherwise, get recent messages and format them
    recent_messages = list(messages.find(
        {"conversation_id": conversation_id},
        sort=[("created_at", -1)],
        limit=5
    ).sort("created_at", 1))
    
    if not recent_messages:
        return ""
    
    context = ""
    for msg in recent_messages:
        if msg["role"] == "system":
            continue  # Skip system messages
        if msg["role"] == "user":
            context += f"User: {msg['content']}\n"
        else:
            context += f"Alice: {msg['content']}\n"
    
    return context.strip()

def reset_conversation_context(conversation_id: str) -> None:
    """Reset the conversation context when starting a new topic"""
    conversations.update_one(
        {"conversation_id": conversation_id},
        {"$unset": {"context_summary": ""}}
    )

def check_connection() -> bool:
    """Check if database connection is working"""
    try:
        # Try to ping the database
        client.admin.command('ping')
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False