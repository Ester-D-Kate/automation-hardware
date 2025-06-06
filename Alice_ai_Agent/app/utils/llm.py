import logging
from typing import Dict
from groq import Groq
from groq.types.chat import ChatCompletionMessageParam

from utils.config import (
    GROQ_API_KEY, 
    LLM_MODEL, 
    LLM_TEMPERATURE, 
    LLM_MAX_TOKENS, 
    AI_SYSTEM_PROMPT
)
from utils.services import extract_json_from_llm_response

logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)

def get_llm_response(prompt: str, previous_context: str = "") -> Dict:
    """Get a response from Groq LLM"""
    try:
        system_prompt = AI_SYSTEM_PROMPT.format(
            transcribed_text=prompt,
            previous_context=previous_context
        )
        
        logger.info(f"Sending request to Groq LLM")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        chat_completion = client.chat.completions.create(
            messages=messages,
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            stop=None,
            stream=False
        )
        
        response_content = chat_completion.choices[0].message.content
        logger.info(f"Received response from LLM")
        
        return extract_json_from_llm_response(response_content)
            
    except Exception as e:
        logger.error(f"LLM error: {e}")
        logger.exception("Detailed exception information:")

        return {
            "output_natural_response": f"I encountered an error: {str(e)}. Please try again.",
            "output_ducky_script": "",
            "output_appliances_response": {},
            "output_search_required": 0,
            "output_search_query": "",
            "previous_relation": 0,
            "new_previous_convo": ""
        }