"""
MQTT client handler
"""

import asyncio
import sys
sys.path.insert(0, '../app')
from constants import MQTT_BROKER, MQTT_PORT
import paho.mqtt.client as mqtt


class MQTTHandler:
    def __init__(self, on_message_callback=None):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.is_connected = False
        self.on_message_callback = on_message_callback
        
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True
            print("✅ Connected to MQTT broker")
            client.subscribe("LDrago_windows/get_mouse_position")
            client.subscribe("LDrago_windows/get_device_info")
            print("📡 Subscribed to request topics")
        else:
            print(f"❌ MQTT connection failed: {rc}")
    
    def _on_message(self, client, userdata, msg):
        if self.on_message_callback:
            self.on_message_callback(msg.topic, msg.payload)
    
    async def connect(self):
        try:
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            
            timeout = 10
            while not self.is_connected and timeout > 0:
                await asyncio.sleep(0.1)
                timeout -= 0.1
            
            return self.is_connected
        except Exception as e:
            print(f"❌ MQTT connection error: {e}")
            return False
    
    def publish(self, topic, payload):
        self.mqtt_client.publish(topic, payload)
    
    def disconnect(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
