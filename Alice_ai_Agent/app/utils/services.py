import logging
import json
import re
from typing import Dict

logger = logging.getLogger(__name__)

def extract_json_from_llm_response(response_content: str) -> Dict:
    """Extract and parse JSON from LLM response, handling control characters properly"""
    logger.info("Extracting JSON from LLM response")
    
    # DEBUG: Log the actual LLM response
    logger.error(f"🔍 RAW LLM RESPONSE: '{response_content}'")
    
    try:
        return json.loads(response_content)
    except json.JSONDecodeError as e:
        logger.warning(f"Direct JSON parsing failed: {e}")
        
        # Try to find JSON between code blocks or other patterns
        patterns = [
            r'```json\n(.*?)\n```',  # JSON in code blocks
            r'```\n(.*?)\n```',      # Any code block
            r'(\{[\s\S]*\})',        # Any JSON-like structure
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response_content, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
                logger.info(f"🔍 Found JSON pattern: {json_str[:100]}...")
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
        
        # If no JSON found, create a fallback response
        logger.error(f"❌ NO VALID JSON FOUND. Creating fallback response.")
        
        # Try to extract ducky script from the response
        ducky_script = ""
        if "GUI" in response_content or "STRING" in response_content or "DELAY" in response_content:
            lines = response_content.split('\n')
            script_lines = []
            for line in lines:
                line = line.strip()
                if any(keyword in line for keyword in ["GUI", "STRING", "DELAY", "ENTER", "TAB", "ALT"]):
                    script_lines.append(line)
            ducky_script = '\n'.join(script_lines)
        
        return {
            "output_natural_response": response_content if len(response_content) < 500 else "I understand your request and will execute it.",
            "output_ducky_script": ducky_script,
            "output_appliances_response": {},
            "output_search_required": 0,
            "output_search_query": "",
            "previous_relation": 1 if "previous" in response_content.lower() else 0,
            "new_previous_convo": ""
        }