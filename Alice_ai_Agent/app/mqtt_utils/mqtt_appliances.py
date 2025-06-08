import logging
import json
import paho.mqtt.publish as publish
from utils.config import (
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_APPLIANCE_TOPIC,
    MQTT_APPLIANCE_USER,
    MQTT_APPLIANCE_PASS
)

logger = logging.getLogger(__name__)

def publish_appliance_command_to_mqtt(appliance_data: dict) -> bool:
    """Publish only appliance control payload to the dedicated appliances topic."""
    try:
        mqtt_payload = json.dumps(appliance_data)
        publish.single(
            MQTT_APPLIANCE_TOPIC,
            payload=mqtt_payload,
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
            auth={'username': MQTT_APPLIANCE_USER, 'password': MQTT_APPLIANCE_PASS}
        )
        logger.info(f"Published to MQTT (appliance): {mqtt_payload}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish to MQTT (appliance): {e}")
        return False