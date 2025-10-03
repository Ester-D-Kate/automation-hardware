"""
📡 Alice MQTT Client
Handles MQTT communication for computer control
"""

import logging
import json
import threading
from typing import Dict, Callable, Optional
from datetime import datetime
import paho.mqtt.client as mqtt
from config import MQTT_BROKER, MQTT_PORT

logger = logging.getLogger(__name__)

class AliceMQTTClient:
    def __init__(self, client_id: str = "alice_ai_server"):
        self.client_id = client_id
        self.mqtt_client = mqtt.Client(client_id)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.on_disconnect = self._on_disconnect
        
        # Message handlers
        self.message_handlers = {}
        self.is_connected = False
        self._lock = threading.Lock()
        
        logger.info(f"📡 Alice MQTT Client initialized: {client_id}")
    
    def connect(self, broker: str = MQTT_BROKER, port: int = MQTT_PORT):
        """Connect to MQTT broker"""
        
        try:
            logger.info(f"📡 Connecting to MQTT broker: {broker}:{port}")
            self.mqtt_client.connect(broker, port, 60)
            self.mqtt_client.loop_start()
            return True
            
        except Exception as e:
            logger.error(f"❌ MQTT connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        
        try:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            self.is_connected = False
            logger.info("📡 MQTT client disconnected")
            
        except Exception as e:
            logger.error(f"❌ MQTT disconnect error: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        
        if rc == 0:
            self.is_connected = True
            logger.info("✅ Connected to MQTT broker")
            
            # Subscribe to all device communications
            self.subscribe("+/+/+")  # device_id/service/action
            
        else:
            logger.error(f"❌ MQTT connection failed with code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        
        self.is_connected = False
        if rc != 0:
            logger.warning("⚠️ Unexpected MQTT disconnection")
        else:
            logger.info("📡 MQTT client disconnected normally")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            logger.debug(f"📡 MQTT message received: {topic}")
            
            # Parse topic
            topic_parts = topic.split('/')
            if len(topic_parts) >= 3:
                device_id = topic_parts[0]
                service = topic_parts[1]
                action = topic_parts[2]
                
                # Call registered handlers
                handler_key = f"{service}/{action}"
                if handler_key in self.message_handlers:
                    self.message_handlers[handler_key](device_id, payload)
                
                # Call wildcard handlers
                if "*" in self.message_handlers:
                    self.message_handlers["*"](device_id, service, action, payload)
            
        except Exception as e:
            logger.error(f"❌ MQTT message handling error: {e}")
    
    def subscribe(self, topic: str, qos: int = 0):
        """Subscribe to MQTT topic"""
        
        try:
            self.mqtt_client.subscribe(topic, qos)
            logger.info(f"📡 Subscribed to: {topic}")
            
        except Exception as e:
            logger.error(f"❌ MQTT subscription failed: {e}")
    
    def publish(self, topic: str, payload: Dict, qos: int = 0, retain: bool = False):
        """Publish message to MQTT topic"""
        
        try:
            message = json.dumps(payload)
            result = self.mqtt_client.publish(topic, message, qos, retain)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"📡 MQTT message published: {topic}")
                return True
            else:
                logger.error(f"❌ MQTT publish failed: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"❌ MQTT publish error: {e}")
            return False
    
    def register_handler(self, service_action: str, handler: Callable):
        """
        Register message handler for specific service/action
        
        Args:
            service_action: Format "service/action" or "*" for all messages
            handler: Function to handle messages
        """
        
        with self._lock:
            self.message_handlers[service_action] = handler
        
        logger.info(f"📡 MQTT handler registered: {service_action}")
    
    def unregister_handler(self, service_action: str):
        """Unregister message handler"""
        
        with self._lock:
            if service_action in self.message_handlers:
                del self.message_handlers[service_action]
        
        logger.info(f"📡 MQTT handler unregistered: {service_action}")
    
    def send_screenshot_request(self, device_id: str, request_data: Dict) -> bool:
        """Send screenshot request to device"""
        
        topic = f"{device_id}/screenshot/request"
        return self.publish(topic, request_data)
    
    def send_ducky_script(self, device_id: str, script_data: Dict) -> bool:
        """Send rubber ducky script to device"""
        
        topic = f"{device_id}/ducky_script"
        return self.publish(topic, script_data)
    
    def send_system_command(self, device_id: str, command_data: Dict) -> bool:
        """Send system command to device"""
        
        topic = f"{device_id}/system/command"
        return self.publish(topic, command_data)
    
    def get_connection_status(self) -> Dict:
        """Get MQTT connection status"""
        
        return {
            "connected": self.is_connected,
            "client_id": self.client_id,
            "broker": MQTT_BROKER,
            "port": MQTT_PORT,
            "handlers_registered": len(self.message_handlers)
        }

# Global instance
_mqtt_client = None

def get_mqtt_client() -> AliceMQTTClient:
    """Get global MQTT client instance"""
    global _mqtt_client
    if _mqtt_client is None:
        _mqtt_client = AliceMQTTClient()
    return _mqtt_client
