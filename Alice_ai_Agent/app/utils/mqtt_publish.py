import logging
import json
import paho.mqtt.publish as publish

from utils.config import (
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_TOPIC,
    MQTT_USER,
    MQTT_PASS
)

logger = logging.getLogger(__name__)

def publish_command_to_mqtt(data: dict) -> bool:
    """Publish a command payload to the MQTT topic for ESP8266."""
    try:
        mqtt_payload = json.dumps(data)
        publish.single(
            MQTT_TOPIC,
            payload=mqtt_payload,
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
            auth={'username': MQTT_USER, 'password': MQTT_PASS}
        )
        logger.info(f"Published to MQTT: {mqtt_payload}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish to MQTT: {e}")
        return False