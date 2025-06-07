import logging
import json
import re
from typing import Dict

logger = logging.getLogger(__name__)

def extract_json_from_llm_response(response_content: str) -> Dict:
    """Extract and parse JSON from LLM response, handling control characters properly"""
    logger.info("Extracting JSON from LLM response")
    
    try:
        return json.loads(response_content)
    except json.JSONDecodeError as e:
        logger.warning(f"Direct JSON parsing failed: {e}")
        
        try:
            cleaned_content = response_content
            control_chars = ''.join([chr(x) for x in range(32) if x not in [9, 10, 13]])
            for char in control_chars:
                cleaned_content = cleaned_content.replace(char, '')
            
            return json.loads(cleaned_content)
        except json.JSONDecodeError:
            logger.error("Failed to parse JSON after control character fixes")
            
            pattern = r'(\{[\s\S]*\})' 
            match = re.search(pattern, response_content)
            
            if match:
                json_str = match.group(1)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    try:
                        fixed_str = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', json_str)
                        fixed_str = fixed_str.replace("'", '"')
                        return json.loads(fixed_str)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to fix and parse JSON: {json_str[:100]}...")
        
        logger.error(f"Failed to extract valid JSON from LLM response: {response_content[:300]}...")
        return {
            "output_natural_response": "I apologize, but I encountered an error processing your request. Could you try again?",
            "output_ducky_script": "",
            "output_appliances_response": {},
            "output_search_required": 0,
            "output_search_query": "",
            "previous_relation": 0,
            "new_previous_convo": ""
        }