"""
Software Executor - PyAutoGUI-based automation  
Receives commands via MQTT, captures screenshots
"""

import asyncio
import json
import time
import pyautogui
import paho.mqtt.client as mqtt
from device_info import extract_complete_device_info
from PIL import Image
import io
from mss import mss
from constants import (
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_USERNAME,
    MQTT_PASSWORD,
    PYAUTOGUI_FAILSAFE,
    PYAUTOGUI_PAUSE,
    BRIDGE_WAYPOINT_DURATION
)

# Use constants
pyautogui.FAILSAFE = PYAUTOGUI_FAILSAFE
pyautogui.PAUSE = PYAUTOGUI_PAUSE


class MonitorBridgeSystem:
    """Handles safe monitor crossing using bridge points"""
    
    def __init__(self):
        self.monitors = []
        self.virtual_desktop = {}
        self.bridge_points = []
        self.primary_monitor = None
        self.is_dragging = False  # Track drag state
    
    async def initialize(self):
        if self.monitors:
            self.primary_monitor = next((m for m in self.monitors if m.get('primary')), None)
            if not self.primary_monitor:
                self.primary_monitor = max(self.monitors, key=lambda m: m['width'] * m['height'])
            print(f"  ✅ Bridge system ready: {len(self.monitors)} monitors, {len(self.bridge_points)} bridges")
        else:
            print("  ⚠️  No monitor info - loading from device_info...")
            device_info = await extract_complete_device_info(silent=True)
            self.monitors = device_info.get('monitors', {}).get('list', [])
            self.virtual_desktop = device_info.get('virtual_desktop', {})
            self.bridge_points = device_info.get('bridge_points', [])
            self.primary_monitor = next((m for m in self.monitors if m.get('primary')), None)
            if not self.primary_monitor:
                self.primary_monitor = max(self.monitors, key=lambda m: m['width'] * m['height'])
            print(f"  ✅ Loaded {len(self.monitors)} monitors, {len(self.bridge_points)} bridges")
    
    def find_monitor_at_position(self, x, y):
        for monitor in self.monitors:
            if (monitor['x'] <= x < monitor['x'] + monitor['width'] and
                monitor['y'] <= y < monitor['y'] + monitor['height']):
                return monitor
        return self.primary_monitor
    
    def get_bridge_waypoints(self, from_monitor, to_monitor):
        for bridge in self.bridge_points:
            if ((bridge['mon1_name'] == from_monitor['name'] and bridge['mon2_name'] == to_monitor['name']) or
                (bridge['mon2_name'] == from_monitor['name'] and bridge['mon1_name'] == to_monitor['name'])):
                if bridge['mon1_name'] == from_monitor['name']:
                    return [bridge['mon1_waypoint'], bridge['bridge_center'], bridge['mon2_waypoint']]
                else:
                    return [bridge['mon2_waypoint'], bridge['bridge_center'], bridge['mon1_waypoint']]
        return None
    
    async def safe_move_to(self, target_x, target_y, duration=BRIDGE_WAYPOINT_DURATION):
        """
        Move mouse to target position using bridges if crossing monitors
        ✅ FIXED: Uses moveTo during drag (keeps button pressed!)
        """
        current_pos = pyautogui.position()
        current_monitor = self.find_monitor_at_position(current_pos[0], current_pos[1])
        target_monitor = self.find_monitor_at_position(target_x, target_y)
        
        # ✅ FIX: During drag, use moveTo (button is already pressed by MOUSE_PRESS!)
        if self.is_dragging:
            print(f"  🔥 DRAGGING: ({current_pos[0]}, {current_pos[1]}) → ({target_x}, {target_y})")
            # ✅ Use moveTo instead of drag - button is ALREADY pressed!
            pyautogui.moveTo(target_x, target_y, duration=duration)
            return True
        
        # Normal movement (no drag)
        if current_monitor['name'] == target_monitor['name']:
            pyautogui.moveTo(target_x, target_y, duration=duration)
            return True
        
        print(f"  🌉 Crossing from {current_monitor['name']} → {target_monitor['name']}")
        waypoints = self.get_bridge_waypoints(current_monitor, target_monitor)
        
        if waypoints:
            for wp in waypoints:
                pyautogui.moveTo(wp[0], wp[1], duration=duration * 0.3)
                await asyncio.sleep(0.05)
            pyautogui.moveTo(target_x, target_y, duration=duration * 0.4)
        else:
            print(f"  ⚠️  No bridge found, using direct path")
            pyautogui.moveTo(target_x, target_y, duration=duration)
        
        return True


class SoftwareExecutor:
    """Software-based command executor using PyAutoGUI"""
    
    def __init__(self, ws_client=None):
        self.bridge_system = MonitorBridgeSystem()
        self.variables = {}
        self.default_delay = 0
        self.mqtt_handler = None
        self.ws_client = ws_client
        
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
        
        for i in range(1, 25):
            self.key_map[f'F{i}'] = f'f{i}'
        
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            self.key_map[letter] = letter.lower()
    
    async def initialize(self):
        await self.bridge_system.initialize()
        print("✅ Software executor ready")
    
    def capture_screenshot(self, monitor_index=None, quality=85):
        """Capture screenshot as raw JPEG bytes"""
        try:
            t_start = time.time()
            
            with mss() as sct:
                if monitor_index is None:
                    t_capture_start = time.time()
                    monitor = sct.monitors[0]
                    screenshot = sct.grab(monitor)
                    img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
                    t_capture = (time.time() - t_capture_start) * 1000
                    
                    t_encode_start = time.time()
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=quality)
                    img_bytes = buffer.getvalue()
                    t_encode = (time.time() - t_encode_start) * 1000
                    
                    t_total = (time.time() - t_start) * 1000
                    print(f"  ⏱️  Capture: {t_capture:.0f}ms | Encode: {t_encode:.0f}ms | Total: {t_total:.0f}ms")
                    print(f"  📦 JPEG: {len(img_bytes):,} bytes")
                    
                    return {
                        'success': True,
                        'monitor': 'all',
                        'width': screenshot.width,
                        'height': screenshot.height,
                        'format': 'jpeg',
                        'quality': quality,
                        'timestamp': time.time(),
                        'data': img_bytes
                    }
                else:
                    if monitor_index + 1 >= len(sct.monitors):
                        return {
                            'success': False,
                            'error': f'Monitor {monitor_index} not found'
                        }
                    
                    t_capture_start = time.time()
                    monitor = sct.monitors[monitor_index + 1]
                    screenshot = sct.grab(monitor)
                    img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
                    t_capture = (time.time() - t_capture_start) * 1000
                    
                    t_encode_start = time.time()
                    buffer = io.BytesIO()
                    img.save(buffer, format='JPEG', quality=quality)
                    img_bytes = buffer.getvalue()
                    t_encode = (time.time() - t_encode_start) * 1000
                    
                    t_total = (time.time() - t_start) * 1000
                    print(f"  ⏱️  Capture: {t_capture:.0f}ms | Encode: {t_encode:.0f}ms | Total: {t_total:.0f}ms")
                    print(f"  📦 JPEG: {len(img_bytes):,} bytes")
                    
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
        try:
            command_line = command_line.strip()
            if not command_line or command_line.startswith('REM'):
                return ('success', 'comment')
            
            parts = command_line.split(None, 1)
            cmd = parts[0].upper()
            args = parts[1] if len(parts) > 1 else ''
            
            # Delays
            if cmd in ['DELAY', 'SLEEP']:
                delay_ms = int(args)
                await asyncio.sleep(delay_ms / 1000.0)
                return ('success', f'delayed {delay_ms}ms')
            
            elif cmd in ['DEFAULT_DELAY', 'DEFAULTDELAY']:
                self.default_delay = int(args)
                return ('success', f'default_delay={self.default_delay}')
            
            # Text input
            elif cmd == 'STRING':
                pyautogui.write(args, interval=0.05)
                return ('success', f'typed: {args[:50]}')
            
            elif cmd == 'STRINGLN':
                pyautogui.write(args, interval=0.05)
                pyautogui.press('enter')
                return ('success', f'typed line: {args[:50]}')
            
            # Mouse movement
            elif cmd == 'MOUSE_MOVE':
                coords = args.split()
                x, y = int(coords[0]), int(coords[1])
                await self.bridge_system.safe_move_to(x, y, duration=BRIDGE_WAYPOINT_DURATION)
                return ('success', f'moved to ({x}, {y})')
            
            elif cmd == 'MOUSE_MOVE_REL':
                coords = args.split()
                dx, dy = int(coords[0]), int(coords[1])
                current = pyautogui.position()
                target_x = current[0] + dx
                target_y = current[1] + dy
                await self.bridge_system.safe_move_to(target_x, target_y, duration=0.2)
                return ('success', f'moved by ({dx}, {dy})')
            
            # ✅ MOUSE HOLD/RELEASE/CLICK COMMANDS (FIXED FOR DRAGGING)
            elif cmd == 'MOUSE_HOLD':
                button = args.upper() if args else 'LEFT'
                self.bridge_system.is_dragging = True  # ✅ Enable drag mode
                if button == 'LEFT':
                    pyautogui.mouseDown()
                    return ('success', 'left hold [DRAG MODE ON]')
                elif button == 'RIGHT':
                    pyautogui.mouseDown(button='right')
                    return ('success', 'right hold [DRAG MODE ON]')
                elif button == 'MIDDLE':
                    pyautogui.mouseDown(button='middle')
                    return ('success', 'middle hold [DRAG MODE ON]')
                else:
                    return ('error', f'Unknown button: {button}')
            
            elif cmd == 'MOUSE_RELEASE':
                button = args.upper() if args else 'LEFT'
                self.bridge_system.is_dragging = False  # ✅ Disable drag mode
                if button == 'LEFT':
                    pyautogui.mouseUp()
                    return ('success', 'left release [DRAG MODE OFF]')
                elif button == 'RIGHT':
                    pyautogui.mouseUp(button='right')
                    return ('success', 'right release [DRAG MODE OFF]')
                elif button == 'MIDDLE':
                    pyautogui.mouseUp(button='middle')
                    return ('success', 'middle release [DRAG MODE OFF]')
                else:
                    return ('error', f'Unknown button: {button}')
            
            elif cmd == 'MOUSE_CLICK':
                button = args.upper() if args else 'LEFT'
                if button == 'LEFT':
                    pyautogui.click()
                    return ('success', 'left click')
                elif button == 'RIGHT':
                    pyautogui.rightClick()
                    return ('success', 'right click')
                elif button == 'MIDDLE':
                    pyautogui.middleClick()
                    return ('success', 'middle click')
                else:
                    return ('error', f'Unknown button: {button}')
            
            # Legacy click commands (for compatibility)
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
            
            # Scrolling
            elif cmd == 'SCROLL_UP':
                amount = int(args) if args else 3
                pyautogui.scroll(amount)
                return ('success', f'scroll up {amount}')
            
            elif cmd == 'SCROLL_DOWN':
                amount = int(args) if args else 3
                pyautogui.scroll(-amount)
                return ('success', f'scroll down {amount}')
            
            # Screenshot
            elif cmd == 'SCREENSHOT':
                parts = args.split() if args else []
                monitor_index = None
                quality = 85
                
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
                
                print(f"  📸 Capturing: monitor={monitor_index if monitor_index is not None else 'all'}, quality={quality}%")
                result = self.capture_screenshot(monitor_index, quality)
                
                if result['success']:
                    print(f"  ✅ Screenshot captured: {result['width']}x{result['height']}")
                    
                    # Send to WebSocket if connected
                    if self.ws_client and self.ws_client.connected:
                        try:
                            asyncio.create_task(self.ws_client.send_screenshot(result))
                            print(f"  📤 Sent to AI Backend via WebSocket")
                        except Exception as e:
                            print(f"  ⚠️  Failed to send: {e}")
                    
                    return ('success', f"screenshot: {result['width']}x{result['height']}")
                else:
                    return ('error', result.get('error', 'Screenshot failed'))
            
            # Key hold/release
            elif cmd == 'HOLD':
                key = self.key_map.get(args.upper(), args.lower())
                pyautogui.keyDown(key)
                return ('success', f'holding {key}')
            
            elif cmd == 'RELEASE':
                key = self.key_map.get(args.upper(), args.lower())
                pyautogui.keyUp(key)
                return ('success', f'released {key}')
            
            # Keyboard commands (shortcuts, single keys)
            else:
                keys = command_line.split()
                mapped_keys = []
                
                for key in keys:
                    key_upper = key.upper()
                    if key_upper in self.key_map:
                        mapped_keys.append(self.key_map[key_upper])
                    else:
                        mapped_keys.append(key.lower())
                
                if len(mapped_keys) == 1:
                    pyautogui.press(mapped_keys[0])
                    return ('success', f'pressed {mapped_keys[0]}')
                else:
                    # Multi-key combination
                    for key in mapped_keys[:-1]:
                        pyautogui.keyDown(key)
                        await asyncio.sleep(0.05)
                    
                    pyautogui.press(mapped_keys[-1])
                    await asyncio.sleep(0.05)
                    
                    for key in reversed(mapped_keys[:-1]):
                        pyautogui.keyUp(key)
                        await asyncio.sleep(0.05)
                    
                    return ('success', f'hotkey: {"+".join(mapped_keys)}')
        
        except Exception as e:
            return ('error', str(e))
    
    async def execute_script(self, script_text):
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
                print(f"  ❌ Line {i}: {line} → {message}")
            else:
                if executed % 10 == 0:
                    print(f"  ⏳ Progress: {executed}/{total_lines}")
            
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
    """MQTT interface for software executor"""
    
    def __init__(self, ws_client=None):
        self.executor = SoftwareExecutor(ws_client)
        self.mqtt_client = None
        self.is_connected = False
        self.event_loop = None
        self.executor.mqtt_handler = self
        
        self.broker = MQTT_BROKER
        self.port = MQTT_PORT
        self.username = MQTT_USERNAME
        self.password = MQTT_PASSWORD
        
        self.command_topic = "LDrago_windows/ducky_script_software"
        self.feedback_topic = "LDrago_windows/pico_feedback_software"
    
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.is_connected = True
            print(f"✅ Connected to MQTT broker: {self.broker}")
            client.subscribe(self.command_topic)
            print(f"📡 Subscribed to: {self.command_topic}")
            
            self.send_feedback({
                'status': 'ready',
                'executor': 'software',
                'backend': 'pyautogui'
            })
        else:
            print(f"❌ MQTT connection failed: {reason_code}")
    
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            
            if payload.get('password') != self.password:
                return
            
            script = payload.get('script', '')
            if not script:
                return
            
            if self.event_loop and self.event_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._execute_and_respond(script),
                    self.event_loop
                )
        
        except Exception as e:
            print(f"❌ Error processing message: {e}")
    
    async def _execute_and_respond(self, script):
        try:
            self.send_feedback({
                'status': 'executing',
                'script_preview': script[:100]
            })
            
            result = await self.executor.execute_script(script)
            
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
        try:
            payload = json.dumps(data)
            self.mqtt_client.publish(self.feedback_topic, payload)
        except Exception as e:
            print(f"⚠️  Failed to send feedback: {e}")
    
    async def start(self):
        self.event_loop = asyncio.get_event_loop()
        
        await self.executor.initialize()
        
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"SoftwareExecutor-{int(time.time())}")
        self.mqtt_client.username_pw_set(self.username, self.password)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        
        print(f"🔌 Connecting executor to MQTT broker...")
        self.mqtt_client.connect(self.broker, self.port, 60)
        self.mqtt_client.loop_start()
        
        timeout = 10
        while not self.is_connected and timeout > 0:
            await asyncio.sleep(0.1)
            timeout -= 0.1
        
        if not self.is_connected:
            print("❌ Failed to connect to MQTT broker")
            return False
        
        print("\n" + "="*80)
        print("✅ EXECUTOR READY")
        print("="*80)
        print(f"  Topic: {self.command_topic}")
        print(f"  Feedback: {self.feedback_topic}")
        print("="*80)
        
        return True
    
    async def run_forever(self):
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\n⚠️  STOPPED")
        finally:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()


async def main():
    executor = MQTTExecutor()
    if await executor.start():
        await executor.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
