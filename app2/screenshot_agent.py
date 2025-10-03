#!/usr/bin/env python3
"""
🖼️ Alice Screenshot Agent
Runs on target computers to provide visual feedback
Communicates with Alice via MQTT
"""

import json
import base64
import logging
import time
import uuid
import io
from datetime import datetime
from typing import Dict, Optional
import threading
import queue

# Core libraries
import paho.mqtt.client as mqtt
from PIL import Image, ImageGrab
import pyautogui
import psutil
import os
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class AliceScreenshotAgent:
    def __init__(self, device_id="LDrago_windows", mqtt_broker="broker.emqx.io", mqtt_port=1883):
        self.device_id = device_id
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        
        # MQTT client setup
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        
        # Command queue for ducky scripts
        self.command_queue = queue.Queue()
        self.command_thread = None
        
        # Status
        self.is_running = False
        self.last_screenshot = None
        
        # Initialize PyAutoGUI
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
        
        logger.info(f"🖼️ Alice Screenshot Agent initialized for device: {device_id}")
    
    def start(self):
        """Start the screenshot agent"""
        
        try:
            # Connect to MQTT
            logger.info(f"🔌 Connecting to MQTT broker: {self.mqtt_broker}")
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            
            # Start command processing thread
            self.command_thread = threading.Thread(target=self._process_commands, daemon=True)
            self.command_thread.start()
            
            self.is_running = True
            logger.info("✅ Alice Screenshot Agent started successfully")
            
            # Send initial status
            self._send_system_status("online")
            
            # Keep running
            while self.is_running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown requested by user")
            self.stop()
        except Exception as e:
            logger.error(f"❌ Agent error: {e}")
            self.stop()
    
    def stop(self):
        """Stop the screenshot agent"""
        
        logger.info("🛑 Stopping Alice Screenshot Agent...")
        
        self.is_running = False
        
        # Stop MQTT
        try:
            self._send_system_status("offline")
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        except Exception as e:
            logger.error(f"MQTT disconnect error: {e}")
        
        logger.info("👋 Alice Screenshot Agent stopped")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        
        if rc == 0:
            logger.info("✅ Connected to MQTT broker")
            
            # Subscribe to commands for this device
            screenshot_topic = f"{self.device_id}/screenshot/request"
            ducky_topic = f"{self.device_id}/ducky_script"
            
            client.subscribe(screenshot_topic)
            client.subscribe(ducky_topic)
            
            logger.info(f"📡 Subscribed to: {screenshot_topic}, {ducky_topic}")
        else:
            logger.error(f"❌ MQTT connection failed with code: {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Handle MQTT messages"""
        
        try:
            topic_parts = msg.topic.split('/')
            if len(topic_parts) < 2:
                return
            
            device_id = topic_parts[0]
            message_type = topic_parts[1]
            
            if device_id != self.device_id:
                return
            
            payload = json.loads(msg.payload.decode())
            
            if message_type == "screenshot":
                self._handle_screenshot_request(payload)
            elif message_type == "ducky_script":
                self._handle_ducky_script(payload)
                
        except Exception as e:
            logger.error(f"❌ Message handling error: {e}")
    
    def _handle_screenshot_request(self, request: Dict):
        """Handle screenshot request from Alice"""
        
        try:
            request_id = request.get("request_id", str(uuid.uuid4()))
            logger.info(f"📷 Screenshot request: {request_id}")
            
            # Capture screenshot
            screenshot_data = self._capture_screenshot()
            
            if screenshot_data:
                # Analyze screenshot (basic analysis)
                analysis = self._analyze_screenshot_basic(screenshot_data["image"])
                
                response = {
                    "request_id": request_id,
                    "device_id": self.device_id,
                    "timestamp": datetime.now().isoformat(),
                    "success": True,
                    "image_data": screenshot_data["base64"],
                    "image_info": screenshot_data["info"],
                    "analysis": analysis
                }
            else:
                response = {
                    "request_id": request_id,
                    "device_id": self.device_id,
                    "timestamp": datetime.now().isoformat(),
                    "success": False,
                    "error": "Screenshot capture failed"
                }
            
            # Send response
            response_topic = f"{self.device_id}/screenshot/response"
            self.mqtt_client.publish(response_topic, json.dumps(response))
            
            logger.info(f"✅ Screenshot response sent: {request_id}")
            
        except Exception as e:
            logger.error(f"❌ Screenshot handling failed: {e}")
    
    def _capture_screenshot(self) -> Optional[Dict]:
        """Capture screenshot and return data"""
        
        try:
            # Capture screenshot
            screenshot = ImageGrab.grab()
            
            # Convert to bytes
            img_buffer = io.BytesIO()
            screenshot.save(img_buffer, format='PNG', optimize=True)
            img_bytes = img_buffer.getvalue()
            
            # Convert to base64
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            
            # Store for later reference
            self.last_screenshot = screenshot
            
            return {
                "base64": img_base64,
                "image": screenshot,
                "info": {
                    "width": screenshot.width,
                    "height": screenshot.height,
                    "size_bytes": len(img_bytes),
                    "format": "PNG"
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Screenshot capture failed: {e}")
            return None
    
    def _analyze_screenshot_basic(self, image: Image.Image) -> Dict:
        """Basic screenshot analysis"""
        
        try:
            analysis = {
                "screen_resolution": f"{image.width}x{image.height}",
                "screen_state": "desktop",  # Default
                "applications": [],
                "interactive_elements": [],
                "errors_visible": False,
                "text_content": "",
                "dominant_colors": []
            }
            
            # Get dominant colors (simplified)
            colors = image.getcolors(maxcolors=10)
            if colors:
                analysis["dominant_colors"] = [{"count": count, "rgb": color} for count, color in colors[:3]]
            
            # Try to detect common UI elements (basic)
            # This could be enhanced with OCR and computer vision
            
            # Check if it looks like desktop (very basic heuristic)
            pixel_data = list(image.getdata())
            if len(set(pixel_data[:100])) > 50:  # Lots of different colors = likely desktop
                analysis["screen_state"] = "desktop"
            else:
                analysis["screen_state"] = "application"
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Screenshot analysis failed: {e}")
            return {"error": str(e)}
    
    def _handle_ducky_script(self, command: Dict):
        """Handle rubber ducky script command"""
        
        try:
            command_id = command.get("command_id", str(uuid.uuid4()))
            script = command.get("script", "")
            
            logger.info(f"🦆 Ducky script command: {command_id}")
            
            # Add to command queue
            self.command_queue.put({
                "command_id": command_id,
                "script": script,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ Ducky script handling failed: {e}")
    
    def _process_commands(self):
        """Process ducky script commands in separate thread"""
        
        while self.is_running:
            try:
                # Get command from queue (with timeout)
                command = self.command_queue.get(timeout=1)
                
                command_id = command["command_id"]
                script = command["script"]
                
                logger.info(f"🦆 Executing ducky script: {command_id}")
                
                # Execute script
                success = self._execute_ducky_script(script)
                
                # Send status response
                status_response = {
                    "command_id": command_id,
                    "device_id": self.device_id,
                    "status": "completed" if success else "failed",
                    "timestamp": datetime.now().isoformat()
                }
                
                status_topic = f"{self.device_id}/ducky_script/status"
                self.mqtt_client.publish(status_topic, json.dumps(status_response))
                
                logger.info(f"✅ Ducky script {'completed' if success else 'failed'}: {command_id}")
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Command processing error: {e}")
    
    def _execute_ducky_script(self, script: str) -> bool:
        """Execute rubber ducky script"""
        
        try:
            lines = script.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split(' ', 1)
                command = parts[0].upper()
                
                if command == "DELAY":
                    delay_ms = int(parts[1]) if len(parts) > 1 else 500
                    time.sleep(delay_ms / 1000.0)
                
                elif command == "STRING":
                    text = parts[1] if len(parts) > 1 else ""
                    pyautogui.typewrite(text)
                
                elif command == "ENTER":
                    pyautogui.press('enter')
                
                elif command == "TAB":
                    pyautogui.press('tab')
                
                elif command == "SPACE":
                    pyautogui.press('space')
                
                elif command == "ESCAPE":
                    pyautogui.press('escape')
                
                elif command == "GUI":
                    key = parts[1].lower() if len(parts) > 1 else ""
                    if key:
                        pyautogui.hotkey('win', key)
                    else:
                        pyautogui.press('win')
                
                elif command == "CTRL":
                    key = parts[1].lower() if len(parts) > 1 else ""
                    if key:
                        pyautogui.hotkey('ctrl', key)
                
                elif command == "ALT":
                    key = parts[1].lower() if len(parts) > 1 else ""
                    if key:
                        pyautogui.hotkey('alt', key)
                
                elif command == "SHIFT":
                    key = parts[1].lower() if len(parts) > 1 else ""
                    if key:
                        pyautogui.hotkey('shift', key)
                
                else:
                    logger.warning(f"⚠️ Unknown ducky command: {command}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ducky script execution failed: {e}")
            return False
    
    def _send_system_status(self, status: str):
        """Send system status update"""
        
        try:
            system_info = {
                "device_id": self.device_id,
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "system_info": {
                    "platform": sys.platform,
                    "python_version": sys.version.split()[0],
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "uptime": time.time()
                }
            }
            
            status_topic = f"{self.device_id}/system/status"
            self.mqtt_client.publish(status_topic, json.dumps(system_info))
            
        except Exception as e:
            logger.error(f"❌ Status update failed: {e}")

def main():
    """Main entry point"""
    
    # Get device ID from command line or use default
    device_id = sys.argv[1] if len(sys.argv) > 1 else "LDrago_windows"
    
    # Create and start agent
    agent = AliceScreenshotAgent(device_id=device_id)
    
    try:
        agent.start()
    except Exception as e:
        logger.error(f"❌ Agent startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
