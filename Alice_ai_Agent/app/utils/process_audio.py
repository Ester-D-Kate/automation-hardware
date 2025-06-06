import logging
from io import BytesIO
from typing import Dict, Optional
from fastapi import UploadFile
from groq import Groq

from utils.config import GROQ_API_KEY
from utils.llm import get_llm_response
from utils.search import perform_search

logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)

async def transcribe_audio(audio_file: UploadFile) -> str:
    """Transcribe audio using Groq Whisper API"""
    try:
        # Read audio file data
        audio_buffer = BytesIO(await audio_file.read())
        audio_buffer.name = audio_file.filename

        logger.info(f"Transcribing audio with Groq Whisper: {audio_file.filename}")
        
        # Call Groq's transcription API
        transcription = client.audio.transcriptions.create(
            file=(audio_buffer.name, audio_buffer.getvalue()),
            model="distil-whisper-large-v3-en",
            response_format="json"
        )
        
        transcribed_text = transcription.text
        logger.info(f"Transcription: {transcribed_text}")
        
        return transcribed_text
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise

async def process_audio_input(audio_file: UploadFile, previous_context: str = "") -> Dict:
    """Process audio: transcribe and get AI response"""

    transcribed_text = await transcribe_audio(audio_file)
    
    if not transcribed_text:
        return {
            "output_natural_response": "I didn't hear anything. Please try again.",
            "output_ducky_script": "",
            "output_appliances_response": {},
            "output_search_required": 0,
            "output_search_query": "",
            "previous_relation": 0,
            "new_previous_convo": ""
        }

    llm_response = get_llm_response(transcribed_text, previous_context)
    
    if llm_response.get("output_search_required") == 1 and llm_response.get("output_search_query"):
        search_result = perform_search(llm_response["output_search_query"])
        
        search_prompt = (
            f"Original user query: {transcribed_text}\n\n"
            f"Based on search for '{llm_response['output_search_query']}', here are the results:\n\n"
            f"{search_result['results']}\n\n"
            f"Please provide a concise, helpful response addressing the user's query using this information. "
            f"Focus on the most relevant facts and don't mention that this came from a search unless necessary."
        )

        logger.info(f"Search results: {search_result['status']}")
        logger.debug(f"Search results content: {search_result['results'][:200]}...")
        
        try:
            final_response = get_llm_response(search_prompt, previous_context)
            llm_response = final_response
        except Exception as e:
            logger.error(f"Error getting final response with search results: {e}")
            llm_response["output_natural_response"] = f"Based on my search, {search_result['results'][:500]}..."
    return llm_response