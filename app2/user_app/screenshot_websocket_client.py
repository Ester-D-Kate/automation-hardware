"""
WebSocket Client - User's computer connects TO AI backend
Sends screenshots to test.py (AI backend server)
"""

import asyncio
import json
import time
import io
import websockets
from PIL import ImageGrab
from constants import CLOUD_RECONNECT_INTERVAL


class CloudWebSocketClient:
    """WebSocket CLIENT - connects to AI backend (test.py)"""
    
    def __init__(self, cloud_url, device_monitor=None):
        self.cloud_url = cloud_url
        self.websocket = None
        self.connected = False
        self.device_monitor = device_monitor
        self.reconnect_interval = CLOUD_RECONNECT_INTERVAL  # ← USE CONSTANT
        
    async def connect(self):
        """Connect to AI backend"""
        while True:
            try:
                print(f"\n🔌 Connecting to AI Backend: {self.cloud_url}")
                self.websocket = await websockets.connect(self.cloud_url)
                self.connected = True
                print("✅ Connected to AI Backend\n")
                
                # Send device info
                if self.device_monitor:
                    await self.send_device_info(self.device_monitor.current_device_info)
                
                return True
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                print(f"⏳ Retrying in {self.reconnect_interval}s...")
                await asyncio.sleep(self.reconnect_interval)
    
    async def send_screenshot(self, screenshot_data):
        """Send screenshot to AI backend"""
        if not self.websocket or not self.connected:
            return False
        
        try:
            # Send metadata
            metadata = {
                'type': 'screenshot',
                'monitor': screenshot_data['monitor'],
                'width': screenshot_data['width'],
                'height': screenshot_data['height'],
                'timestamp': screenshot_data['timestamp']
            }
            await self.websocket.send(json.dumps(metadata))
            
            # Send image data
            await self.websocket.send(screenshot_data['data'])
            
            print(f"📤 Screenshot sent: {len(screenshot_data['data']):,} bytes")
            return True
        except Exception as e:
            print(f"❌ Send failed: {e}")
            self.connected = False
            return False
    
    async def send_device_info(self, device_info):
        """Send device info to AI"""
        if not self.websocket or not self.connected:
            return False
        
        try:
            message = {'type': 'device_info', 'data': device_info}
            await self.websocket.send(json.dumps(message))
            print("📤 Device info sent to AI")
            return True
        except:
            return False
    
    async def send_mouse_position(self, mouse_info):
        """Send mouse position to AI"""
        if not self.websocket or not self.connected:
            return False
        
        try:
            message = {'type': 'mouse_position', 'data': mouse_info}
            await self.websocket.send(json.dumps(message))
            return True
        except:
            return False
    
    async def send_applications_info(self, apps_info):
        """Send applications to AI"""
        if not self.websocket or not self.connected:
            return False
        
        try:
            message = {'type': 'applications_info', 'data': apps_info}
            await self.websocket.send(json.dumps(message))
            print("📤 Applications sent to AI")
            return True
        except:
            return False
    
    async def receive_commands(self, executor):
        """Listen for AI commands"""
        while True:
            try:
                if not self.connected:
                    await self.connect()
                    continue
                
                message = await self.websocket.recv()
                command_data = json.loads(message)
                
                if command_data['type'] == 'execute':
                    print(f"\n🤖 AI Command: {command_data['script'][:100]}...")
                    await executor.execute_script(command_data['script'])
                    
                elif command_data['type'] == 'request_screenshot':
                    print(f"📸 AI requested screenshot")
                    monitor = command_data.get('monitor', 'all')
                    quality = command_data.get('quality', 85)
                    screenshot = await self._capture_screenshot(monitor, quality)
                    await self.send_screenshot(screenshot)
                
            except websockets.exceptions.ConnectionClosed:
                print("⚠️  Connection closed")
                self.connected = False
                await asyncio.sleep(self.reconnect_interval)
            except Exception as e:
                print(f"❌ Error: {e}")
                await asyncio.sleep(1)
    
    async def _capture_screenshot(self, monitor, quality):
        """Capture screenshot"""
        screenshot_pil = ImageGrab.grab(all_screens=True if monitor == 'all' else False)
        
        img_byte_arr = io.BytesIO()
        screenshot_pil.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
        img_data = img_byte_arr.getvalue()
        
        return {
            'monitor': monitor,
            'width': screenshot_pil.width,
            'height': screenshot_pil.height,
            'timestamp': time.time(),
            'data': img_data
        }


# ============================================================================
# LEGACY COMPATIBILITY FOR execute_command.py
# ============================================================================
# These functions are needed by execute_command.py but do nothing now
# The cloud client handles everything

_client_instance = None


def get_server_instance(host='0.0.0.0', port=8765):
    """Legacy function - returns stub"""
    return LegacyServerStub()


class LegacyServerStub:
    """Stub for legacy code"""
    async def start(self):
        """Does nothing"""
        pass
    
    def has_clients(self):
        """Always returns False (cloud client sends directly)"""
        return False


async def send_screenshot_via_websocket(screenshot_data):
    """Legacy function - does nothing (cloud client handles it)"""
    pass


# ============================================================================
# MAIN CLIENT INSTANCE
# ============================================================================

def get_client_instance(cloud_url, device_monitor=None):
    """Get or create cloud client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = CloudWebSocketClient(cloud_url, device_monitor)
    return _client_instance
