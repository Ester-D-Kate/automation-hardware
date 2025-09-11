import logging
import json
import paho.mqtt.publish as publish
from utils.config import (
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_DUCKY_TOPIC,
    MQTT_DUCKY_USER,
    MQTT_DUCKY_PASS,
    LAPTOP_CONTROL_PASS
)


logger = logging.getLogger(__name__)

# Store last executed command to prevent repeats
_last_command = None

def reset_last_command():
    """Reset the last command to allow re-execution"""
    global _last_command
    _last_command = None
    logger.info("Last command reset - new commands will be allowed")

def fix_ducky_script_format(script: str) -> str:
    """Fix common formatting issues in ducky scripts to match ESP32 expectations"""
    import re
    
    # Fix DELAY commands - ensure space between DELAY and number
    # Convert DELAY300 -> DELAY 300, DELAY500 -> DELAY 500, etc.
    script = re.sub(r'DELAY(\d+)', r'DELAY \1', script)
    
    # Remove any .exe extensions from common applications
    script = script.replace('notepad.exe', 'notepad')
    script = script.replace('cmd.exe', 'cmd')
    script = script.replace('chrome.exe', 'chrome')
    
    # Remove any trailing newlines
    script = script.rstrip('\n')
    
    logger.info(f"Fixed ducky script format: {script}")
    return script

def publish_ducky_script_to_mqtt(ducky_data: dict) -> bool:
    """
    Publish ducky script to MQTT, requiring password and handling repeat logic.
    Expects ducky_data to contain:
        - 'password': str
        - 'script': str
        - 'repeat': bool (optional, default False)
    """
    global _last_command
    try:
        # Password check
        password = ducky_data.get('password')
        if not password or password != LAPTOP_CONTROL_PASS:
            logger.warning("Invalid or missing password for laptop control command.")
            return False

        original_script = ducky_data.get('script')
        repeat = ducky_data.get('repeat', False)
        if not original_script:
            logger.warning("No script provided in ducky_data.")
            return False

        # 🔧 DEBUG: Log original AI-generated script
        logger.warning(f"🤖 ORIGINAL AI SCRIPT: {repr(original_script)}")
        
        # Fix formatting issues
        fixed_script = fix_ducky_script_format(original_script)
        
        # 🔧 DEBUG: Log fixed script
        logger.warning(f"🔧 FIXED SCRIPT: {repr(fixed_script)}")

        # Repeat logic
        if not repeat and fixed_script == _last_command:
            logger.info("Duplicate command ignored due to repeat=False.")
            return False

        # Prepare payload for MQTT (keep password for ESP32 validation, use fixed script)
        mqtt_data = {k: v for k, v in ducky_data.items()}  # Keep all fields including password
        mqtt_data['script'] = fixed_script  # Use the fixed script
        mqtt_payload = json.dumps(mqtt_data)
        
        # 🔧 DEBUG: Log final MQTT payload
        logger.warning(f"📡 MQTT PAYLOAD TO ESP32: {mqtt_payload}")
        
        # Prepare MQTT connection parameters
        mqtt_params = {
            'topic': MQTT_DUCKY_TOPIC,
            'payload': mqtt_payload,
            'hostname': MQTT_BROKER,
            'port': MQTT_PORT
        }
        
        # Add auth only if credentials are provided
        if MQTT_DUCKY_USER and MQTT_DUCKY_PASS:
            mqtt_params['auth'] = {'username': MQTT_DUCKY_USER, 'password': MQTT_DUCKY_PASS}
        
        publish.single(**mqtt_params)
        logger.info(f"Published to MQTT (Windows ducky): {mqtt_payload}")
        _last_command = fixed_script
        return True
    except Exception as e:
        logger.error(f"Failed to publish to MQTT (Windows ducky): {e}")
        return False