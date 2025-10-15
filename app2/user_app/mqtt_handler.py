"""
MQTT client handler
"""

import asyncio
import paho.mqtt.client as mqtt
from constants import MQTT_BROKER, MQTT_PORT


class MQTTHandler:
    def __init__(self, on_message_callback=None):
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.is_connected = False
        self.on_message_callback = on_message_callback
    
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.is_connected = True
            print("✅ Connected to MQTT broker")
            # Subscribe to ALL request topics
            client.subscribe("LDrago_windows/get_mouse_position")
            client.subscribe("LDrago_windows/get_device_info")
            client.subscribe("LDrago_windows/get_applications")  # ← ADD THIS
            print("📡 Subscribed to request topics")
        else:
            print(f"❌ MQTT connection failed: {reason_code}")
    
    def _on_message(self, client, userdata, msg):
        if self.on_message_callback:
            self.on_message_callback(msg.topic, msg.payload)
    
    async def connect(self):
        try:
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            
            # Wait for connection
            for _ in range(50):
                await asyncio.sleep(0.1)
                if self.is_connected:
                    return True
            
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def publish(self, topic, payload):
        """Publish message to MQTT topic"""
        try:
            self.mqtt_client.publish(topic, payload)
        except Exception as e:
            print(f"❌ Publish error: {e}")
    
    def disconnect(self):
        """Disconnect from MQTT"""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.is_connected = False
