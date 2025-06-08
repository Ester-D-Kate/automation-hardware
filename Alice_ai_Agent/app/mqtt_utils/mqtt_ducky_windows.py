import logging
import json
import paho.mqtt.publish as publish
from utils.config import (
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_DUCKY_TOPIC,
    MQTT_DUCKY_USER,
    MQTT_DUCKY_PASS
)

logger = logging.getLogger(__name__)

def publish_ducky_script_to_mqtt(ducky_data: dict) -> bool:
    """Publish only ducky script payload to the dedicated Windows topic."""
    try:
        mqtt_payload = json.dumps(ducky_data)
        publish.single(
            MQTT_DUCKY_TOPIC,
            payload=mqtt_payload,
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
            auth={'username': MQTT_DUCKY_USER, 'password': MQTT_DUCKY_PASS}
        )
        logger.info(f"Published to MQTT (Windows ducky): {mqtt_payload}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish to MQTT (Windows ducky): {e}")
        return False