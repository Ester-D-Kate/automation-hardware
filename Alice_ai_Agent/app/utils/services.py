import logging
import json
from typing import Dict

logger = logging.getLogger(__name__)

def extract_json_from_llm_response(response_content: str) -> Dict:
    """Extract and parse JSON from LLM response, handling control characters properly"""
    logger.info("Extracting JSON from LLM response")
    
    try:
        return json.loads(response_content)
    except json.JSONDecodeError as e:
        logger.warning(f"Direct JSON parsing failed: {e}")
        
        import re
        pattern = r'(\{[\s\S]*\})' 
        match = re.search(pattern, response_content)
        
        if match:
            json_str = match.group(1)
            
            try:
                return json.loads(json_str)
            
            except json.JSONDecodeError:
                try:
                    processed_json = json_str
                    for c in ['\n', '\r', '\t']:
                        if c == '\n':
                            processed_json = processed_json.replace(c, '\\n')
                        elif c == '\r':
                            processed_json = processed_json.replace(c, '\\r')
                        elif c == '\t':
                            processed_json = processed_json.replace(c, '\\t')
                     
                    fixed_json = json.loads(processed_json)
                    logger.info("Successfully parsed JSON after fixing control characters")
                    return fixed_json
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON after control character fixes: {e}")
        
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
    