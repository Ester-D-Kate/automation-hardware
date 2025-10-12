"""
Software Executor - PyAutoGUI-based automation
Receives commands via MQTT, captures screenshots via WebSocket
"""

import asyncio
import json
import time
import pyautogui
import paho.mqtt.client as mqtt
from device_info import extract_complete_device_info
import re
from PIL import Image
import io
from mss import mss
from screenshot_websocket_server import get_server_instance, send_screenshot_via_websocket

# Disable PyAutoGUI fail-safe
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.01  # Minimal delay between commands


class MonitorBridgeSystem:
    """Handles safe monitor crossing using bridge points"""
    
    def __init__(self):
        self.monitors = []
        self.virtual_desktop = {}
        self.bridge_points = []
        self.primary_monitor = None
    
    async def initialize(self):
        """
        Initialize bridge system (device info loaded by main)
        Note: monitors, virtual_desktop, and bridge_points should be set by caller
        """
        if self.monitors:
            self.primary_monitor = next((m for m in self.monitors if m.get('primary')), None)
            if not self.primary_monitor:
                self.primary_monitor = max(self.monitors, key=lambda m: m['width'] * m['height'])
            print(f"   ✅ Bridge system ready: {len(self.monitors)} monitors, {len(self.bridge_points)} bridges")
        else:
            print("   ⚠️ No monitor info - loading from device_info...")
            device_info = await extract_complete_device_info(silent=True)
            self.monitors = device_info.get('monitors', {}).get('list', [])
            self.virtual_desktop = device_info.get('virtual_desktop', {})
            self.bridge_points = device_info.get('bridge_points', [])
            
            self.primary_monitor = next((m for m in self.monitors if m.get('primary')), None)
            if not self.primary_monitor:
                self.primary_monitor = max(self.monitors, key=lambda m: m['width'] * m['height'])
            
            print(f"   ✅ Loaded {len(self.monitors)} monitors, {len(self.bridge_points)} bridges")
    
    def find_monitor_at_position(self, x, y):
        """Find which monitor contains the given position"""
        for monitor in self.monitors:
            if (monitor['x'] <= x < monitor['x'] + monitor['width'] and
                monitor['y'] <= y < monitor['y'] + monitor['height']):
                return monitor
        return self.primary_monitor
    
    def get_bridge_waypoints(self, from_monitor, to_monitor):
        """Get waypoints to safely cross from one monitor to another"""
        for bridge in self.bridge_points:
            if ((bridge['mon1_name'] == from_monitor['name'] and bridge['mon2_name'] == to_monitor['name']) or
                (bridge['mon2_name'] == from_monitor['name'] and bridge['mon1_name'] == to_monitor['name'])):
                
                # Return waypoints in correct order
                if bridge['mon1_name'] == from_monitor['name']:
                    return [bridge['mon1_waypoint'], bridge['bridge_center'], bridge['mon2_waypoint']]
                else:
                    return [bridge['mon2_waypoint'], bridge['bridge_center'], bridge['mon1_waypoint']]
        
        # No bridge found, return direct path
        return None
    
    async def safe_move_to(self, target_x, target_y, duration=0.3):
        """
        Move cursor to target using bridge system if crossing monitors
        """
        current_pos = pyautogui.position()
        current_monitor = self.find_monitor_at_position(current_pos[0], current_pos[1])
        target_monitor = self.find_monitor_at_position(target_x, target_y)
        
        # Same monitor? Direct move
        if current_monitor['name'] == target_monitor['name']:
            pyautogui.moveTo(target_x, target_y, duration=duration)
            return True
        
        # Different monitors - use bridge
        print(f"   🌉 Crossing from {current_monitor['name']} → {target_monitor['name']}")
        waypoints = self.get_bridge_waypoints(current_monitor, target_monitor)
        
        if waypoints:
            # Move through waypoints
            for wp in waypoints:
                pyautogui.moveTo(wp[0], wp[1], duration=duration * 0.3)
                await asyncio.sleep(0.05)
            
            # Final move to target
            pyautogui.moveTo(target_x, target_y, duration=duration * 0.4)
        else:
            # No bridge, direct move (risky but fallback)
            print(f"   ⚠️ No bridge found, using direct path")
            pyautogui.moveTo(target_x, target_y, duration=duration)
        
        return True


class SoftwareExecutor:
    """
    Software-based command executor using PyAutoGUI
    Mimics hardware Pico interface for easy swapping
    """
    
    def __init__(self):
        self.bridge_system = MonitorBridgeSystem()
        self.variables = {}
        self.default_delay = 0
        self.mqtt_handler = None  # Will be set by MQTTExecutor
        
        # Key mappings (DuckyScript to PyAutoGUI)
        self.key_map = {
            'WINDOWS': 'win', 'GUI': 'win', 'COMMAND': 'command',
            'SHIFT': 'shift', 'ALT': 'alt', 'CTRL': 'ctrl', 'CONTROL': 'ctrl',
            'ENTER': 'enter', 'RETURN': 'enter',
            'ESC': 'esc', 'ESCAPE': 'esc',
            'BACKSPACE': 'backspace',
            'TAB': 'tab',
            'SPACE': 'space',
            'UP': 'up', 'DOWN': 'down', 'LEFT': 'left', 'RIGHT': 'right',
            'UPARROW': 'up', 'DOWNARROW': 'down', 'LEFTARROW': 'left', 'RIGHTARROW': 'right',
            'PAGEUP': 'pageup', 'PAGEDOWN': 'pagedown',
            'HOME': 'home', 'END': 'end',
            'INSERT': 'insert', 'DELETE': 'delete',
            'CAPSLOCK': 'capslock', 'NUMLOCK': 'numlock', 'SCROLLLOCK': 'scrolllock',
            'PRINTSCREEN': 'printscreen',
            'PAUSE': 'pause', 'BREAK': 'pause',
        }
        
        # Add F1-F24
        for i in range(1, 25):
            self.key_map[f'F{i}'] = f'f{i}'
        
        # Add A-Z
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            self.key_map[letter] = letter.lower()
    
    async def initialize(self):
        """Initialize the executor"""
        await self.bridge_system.initialize()
        print("✅ Software executor ready")
    
    def capture_screenshot_websocket(self, monitor_index=None, quality=85):
        """Capture screenshot as raw JPEG bytes for WebSocket transmission"""
        try:
            t_start = time.time()
            with mss() as sct:
                if monitor_index is None:
                    # Capture all monitors
                    t_capture_start = time.time()
                    monitor = sct.monitors[0]
                    screenshot = sct.grab(monitor)
                    img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
                    t_capture = (time.time() - t_capture_start) * 1000
                    
                    # Encode to JPEG (NO gzip, NO base64 - send raw bytes!)
                    t_encode_start = time.time()
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=quality)
                    img_bytes = buffer.getvalue()
                    t_encode = (time.time() - t_encode_start) * 1000
                    
                    t_total = (time.time() - t_start) * 1000
                    print(f"⏱️  Timing - Capture: {t_capture:.0f}ms | Encode: {t_encode:.0f}ms | Total: {t_total:.0f}ms")
                    print(f"📦 Raw JPEG: {len(img_bytes):,} bytes (no base64, no gzip!)")
                    
                    return {
                        'success': True,
                        'monitor': 'all',
                        'width': screenshot.width,
                        'height': screenshot.height,
                        'format': 'jpeg',
                        'quality': quality,
                        'timestamp': time.time(),
                        'data': img_bytes  # Raw bytes, not base64!
                    }
                else:
                    # Capture specific monitor
                    if monitor_index + 1 >= len(sct.monitors):
                        return {
                            'success': False,
                            'error': f'Monitor {monitor_index} not found. Available: 0-{len(sct.monitors)-2}'
                        }
                    
                    t_capture_start = time.time()
                    monitor = sct.monitors[monitor_index + 1]
                    screenshot = sct.grab(monitor)
                    img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
                    t_capture = (time.time() - t_capture_start) * 1000
                    
                    # Encode to JPEG (NO gzip, NO base64!)
                    t_encode_start = time.time()
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=quality)
                    img_bytes = buffer.getvalue()
                    t_encode = (time.time() - t_encode_start) * 1000
                    
                    t_total = (time.time() - t_start) * 1000
                    print(f"⏱️  Timing - Capture: {t_capture:.0f}ms | Encode: {t_encode:.0f}ms | Total: {t_total:.0f}ms")
                    print(f"📦 Raw JPEG: {len(img_bytes):,} bytes (no base64, no gzip!)")
                    
                    return {
                        'success': True,
                        'monitor': monitor_index,
                        'width': screenshot.width,
                        'height': screenshot.height,
                        'format': 'jpeg',
                        'quality': quality,
                        'timestamp': time.time(),
                        'data': img_bytes
                    }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def execute_command(self, command_line):
        """
        Execute a single command line (DuckyScript compatible)
        Returns (status, message)
        """
        try:
            command_line = command_line.strip()
            
            if not command_line or command_line.startswith('REM'):
                return ('success', 'comment')
            
            # Parse command
            parts = command_line.split(None, 1)
            cmd = parts[0].upper()
            args = parts[1] if len(parts) > 1 else ''
            
            # ===== DELAY =====
            if cmd in ['DELAY', 'SLEEP']:
                delay_ms = int(args)
                await asyncio.sleep(delay_ms / 1000.0)
                return ('success', f'delayed {delay_ms}ms')
            
            # ===== DEFAULT_DELAY =====
            elif cmd in ['DEFAULT_DELAY', 'DEFAULTDELAY']:
                self.default_delay = int(args)
                return ('success', f'default_delay={self.default_delay}')
            
            # ===== STRING =====
            elif cmd == 'STRING':
                pyautogui.write(args, interval=0.05)  # 50ms between keys for reliability
                return ('success', f'typed: {args[:50]}')
            
            # ===== STRINGLN =====
            elif cmd == 'STRINGLN':
                pyautogui.write(args, interval=0.05)  # 50ms between keys for reliability
                pyautogui.press('enter')
                return ('success', f'typed line: {args[:50]}')
            
            # ===== MOUSE COMMANDS =====
            elif cmd == 'MOUSE_MOVE':
                # Absolute move: MOUSE_MOVE x y
                coords = args.split()
                x, y = int(coords[0]), int(coords[1])
                await self.bridge_system.safe_move_to(x, y, duration=0.3)
                return ('success', f'moved to ({x}, {y})')
            
            elif cmd == 'MOUSE_MOVE_REL':
                # Relative move: MOUSE_MOVE_REL dx dy
                coords = args.split()
                dx, dy = int(coords[0]), int(coords[1])
                current = pyautogui.position()
                target_x = current[0] + dx
                target_y = current[1] + dy
                await self.bridge_system.safe_move_to(target_x, target_y, duration=0.2)
                return ('success', f'moved by ({dx}, {dy})')
            
            elif cmd == 'CLICK' or cmd == 'LEFTCLICK':
                pyautogui.click()
                return ('success', 'left click')
            
            elif cmd == 'RIGHTCLICK':
                pyautogui.rightClick()
                return ('success', 'right click')
            
            elif cmd == 'MIDDLECLICK':
                pyautogui.middleClick()
                return ('success', 'middle click')
            
            elif cmd == 'DOUBLECLICK':
                pyautogui.doubleClick()
                return ('success', 'double click')
            
            elif cmd == 'SCROLL_UP':
                amount = int(args) if args else 3
                pyautogui.scroll(amount)
                return ('success', f'scroll up {amount}')
            
            elif cmd == 'SCROLL_DOWN':
                amount = int(args) if args else 3
                pyautogui.scroll(-amount)
                return ('success', f'scroll down {amount}')
            
            # ===== SCREENSHOT COMMAND =====
            elif cmd == 'SCREENSHOT':
                # SCREENSHOT [monitor_index] [quality]
                # Uses WebP format for optimal quality and file size
                # 
                # Examples:
                #   SCREENSHOT           - capture all monitors (quality 85)
                #   SCREENSHOT 0         - capture primary monitor
                #   SCREENSHOT 1         - capture secondary monitor
                #   SCREENSHOT 0 90      - primary monitor, 90% quality (larger file)
                #   SCREENSHOT ALL 80    - all monitors, 80% quality (smaller/faster)
                parts = args.split() if args else []
                
                monitor_index = None
                quality = 85  # High quality by default
                
                if len(parts) >= 1:
                    if parts[0].upper() == 'ALL':
                        monitor_index = None
                    else:
                        try:
                            monitor_index = int(parts[0])
                        except ValueError:
                            return ('error', f'Invalid monitor index: {parts[0]}')
                
                if len(parts) >= 2:
                    try:
                        quality = int(parts[1])
                        if quality < 1 or quality > 100:
                            quality = 85
                    except ValueError:
                        pass
                
                print(f"   📸 Capturing: monitor={monitor_index if monitor_index is not None else 'all'}, quality={quality}%, JPEG format")
                print(f"   🚀 Using WebSocket (10-20x faster than MQTT!)")
                
                # Capture for WebSocket (raw bytes, no base64!)
                result = self.capture_screenshot_websocket(monitor_index, quality)
                
                if result['success']:
                    # Send via WebSocket (async)
                    t_ws_start = time.time()
                    asyncio.create_task(send_screenshot_via_websocket(result))
                    t_ws = (time.time() - t_ws_start) * 1000
                    
                    print(f"   ✅ Screenshot queued for WebSocket: {result['width']}x{result['height']}, {len(result['data']):,} bytes")
                    print(f"   📡 WebSocket Queue: {t_ws:.0f}ms (async, no blocking!)")
                    return ('success', f"screenshot: {result['width']}x{result['height']}")
                else:
                    return ('error', result.get('error', 'Screenshot failed'))
            
            # ===== KEYBOARD COMMANDS =====
            elif cmd == 'HOLD':
                # HOLD key - press and don't release
                key = self.key_map.get(args.upper(), args.lower())
                pyautogui.keyDown(key)
                return ('success', f'holding {key}')
            
            elif cmd == 'RELEASE':
                # RELEASE key
                key = self.key_map.get(args.upper(), args.lower())
                pyautogui.keyUp(key)
                return ('success', f'released {key}')
            
            # ===== KEY COMBINATIONS =====
            else:
                # Parse as key combination (e.g., "CTRL ALT DELETE", "ALT F4")
                keys = command_line.split()
                mapped_keys = []
                
                for key in keys:
                    key_upper = key.upper()
                    if key_upper in self.key_map:
                        mapped_keys.append(self.key_map[key_upper])
                    else:
                        mapped_keys.append(key.lower())
                
                if len(mapped_keys) == 1:
                    # Single key press
                    pyautogui.press(mapped_keys[0])
                    return ('success', f'pressed {mapped_keys[0]}')
                else:
                    # Key combination - use manual key down/up for reliability
                    print(f"   🎹 Hotkey: {' + '.join(mapped_keys)}")
                    
                    # Press all modifier keys down
                    for key in mapped_keys[:-1]:
                        pyautogui.keyDown(key)
                        await asyncio.sleep(0.05)
                    
                    # Press and release the final key
                    pyautogui.press(mapped_keys[-1])
                    await asyncio.sleep(0.05)
                    
                    # Release all modifier keys in reverse order
                    for key in reversed(mapped_keys[:-1]):
                        pyautogui.keyUp(key)
                        await asyncio.sleep(0.05)
                    
                    return ('success', f'hotkey: {"+".join(mapped_keys)}')
            
        except Exception as e:
            return ('error', str(e))
    
    async def execute_script(self, script_text):
        """
        Execute a full DuckyScript
        Returns execution summary
        """
        lines = script_text.strip().split('\n')
        total_lines = len(lines)
        executed = 0
        errors = 0
        
        print(f"\n🚀 Executing script: {total_lines} lines")
        start_time = time.time()
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            
            if not line or line.startswith('REM'):
                continue
            
            status, message = await self.execute_command(line)
            executed += 1
            
            if status == 'error':
                errors += 1
                print(f"   ❌ Line {i}: {line} → {message}")
            else:
                if executed % 10 == 0:
                    print(f"   ⏳ Progress: {executed}/{total_lines}")
            
            # Apply default delay
            if self.default_delay > 0:
                await asyncio.sleep(self.default_delay / 1000.0)
        
        elapsed = time.time() - start_time
        
        print(f"\n✅ Script complete: {executed} commands in {elapsed:.2f}s ({errors} errors)")
        
        return {
            'total_lines': total_lines,
            'executed': executed,
            'errors': errors,
            'elapsed_seconds': elapsed
        }


class MQTTExecutor:
    """
    MQTT interface for software executor
    Same interface as hardware Pico
    """
    
    def __init__(self):
        self.executor = SoftwareExecutor()
        self.mqtt_client = None
        self.is_connected = False
        self.event_loop = None  # Store event loop reference
        
        # Link executor to MQTT handler (for screenshot publishing)
        self.executor.mqtt_handler = self
        
        # MQTT config (separate from hardware to avoid conflicts)
        self.broker = "broker.emqx.io"
        self.port = 1883
        self.username = "LDrago_windows"
        self.password = "E1s2t3e4r5"
        
        # SOFTWARE uses different topic to avoid conflict with hardware
        self.command_topic = "LDrago_windows/ducky_script_software"
        self.feedback_topic = "LDrago_windows/pico_feedback_software"
    
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.is_connected = True
            print(f"✅ Connected to MQTT broker: {self.broker}")
            client.subscribe(self.command_topic)
            print(f"📡 Subscribed to: {self.command_topic}")
            
            # Send ready message
            self.send_feedback({
                'status': 'ready',
                'executor': 'software',
                'backend': 'pyautogui'
            })
        else:
            print(f"❌ MQTT connection failed: {reason_code}")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming commands"""
        try:
            payload = json.loads(msg.payload.decode())
            
            # Verify password
            if payload.get('password') != self.password:
                print(f"⚠️ Invalid password in command")
                return
            
            script = payload.get('script', '')
            
            if not script:
                print(f"⚠️ Empty script received")
                return
            
            # Execute script asynchronously using stored event loop
            if self.event_loop and self.event_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._execute_and_respond(script),
                    self.event_loop
                )
            else:
                print(f"⚠️ No event loop available to execute command")
            
        except Exception as e:
            print(f"❌ Error processing message: {e}")
    
    async def _execute_and_respond(self, script):
        """Execute script and send feedback"""
        try:
            # Send start feedback
            self.send_feedback({
                'status': 'executing',
                'script_preview': script[:100]
            })
            
            # Execute
            result = await self.executor.execute_script(script)
            
            # Send completion feedback
            self.send_feedback({
                'status': 'completed',
                'result': result
            })
            
        except Exception as e:
            self.send_feedback({
                'status': 'error',
                'error': str(e)
            })
    
    def send_feedback(self, data):
        """Send feedback to MQTT"""
        try:
            payload = json.dumps(data)
            self.mqtt_client.publish(self.feedback_topic, payload)
        except Exception as e:
            print(f"⚠️ Failed to send feedback: {e}")
    
    def publish(self, topic, payload):
        """Publish to MQTT topic (for screenshots, etc.)"""
        try:
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            self.mqtt_client.publish(topic, payload)
        except Exception as e:
            print(f"⚠️ Failed to publish to {topic}: {e}")
    
    async def start(self):
        """Start MQTT executor (device info should be pre-loaded by main)"""
        
        # Store the current event loop for async execution
        self.event_loop = asyncio.get_event_loop()
        
        # Initialize executor (uses pre-loaded device info from main)
        await self.executor.initialize()
        
        # Setup MQTT (reuse existing connection if possible)
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"SoftwareExecutor-{int(time.time())}")
        self.mqtt_client.username_pw_set(self.username, self.password)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        
        # Connect
        print(f"🔌 Connecting executor to MQTT broker...")
        self.mqtt_client.connect(self.broker, self.port, 60)
        self.mqtt_client.loop_start()
        
        # Wait for connection
        timeout = 10
        while not self.is_connected and timeout > 0:
            await asyncio.sleep(0.1)
            timeout -= 0.1
        
        if not self.is_connected:
            print("❌ Failed to connect to MQTT broker")
            return False
        
        print("\n" + "="*80)
        print("✅ EXECUTOR READY - Listening for commands...")
        print("="*80)
        print(f"   Topic: {self.command_topic}")
        print(f"   Feedback: {self.feedback_topic}")
        print(f"   Backend: PyAutoGUI + Monitor Bridge System")
        print("="*80)
        print("\n⏸️  Press Ctrl+C to stop\n")
        
        return True
    
    async def run_forever(self):
        """Keep running until stopped"""
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\n" + "="*80)
            print("⚠️  EXECUTOR STOPPED BY USER")
            print("="*80)
        finally:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            print("✅ Disconnected from MQTT")


async def main():
    """Main entry point"""
    executor = MQTTExecutor()
    
    if await executor.start():
        await executor.run_forever()
    else:
        print("❌ Failed to start executor")


if __name__ == "__main__":
    asyncio.run(main())
