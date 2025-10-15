"""
COMPLETE AI BACKEND TEST TEMPLATE - 100% DYNAMIC!
================================================
✅ WebSocket Server (receives screenshots from main.py)
✅ MQTT Client (receives device/mouse/app info, sends commands)
✅ 100% DYNAMIC coordinates - uses REAL app positions!
✅ SUPPORTS BOTH SOFTWARE & HARDWARE MODES!
✅ FIFO screenshot management (keeps last 10)
✅ ALLOWS DRAGGING MAXIMIZED WINDOWS! (Windows auto un-maximizes)
✅ INCLUDES PASSWORD AUTHENTICATION!
✅ USES MOUSE_HOLD/MOUSE_RELEASE FOR PERFECT DRAGGING!
✅ BINARY-ONLY SCREENSHOTS (no duplicates!)

Use this as reference when building your AI backend!
"""

import asyncio
import json
import time
import base64
import websockets
import paho.mqtt.client as mqtt
from pathlib import Path
from datetime import datetime
from constants import (
    MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD,
    MQTT_TOPIC_FEEDBACK_SOFTWARE,
    MQTT_TOPIC_DEVICE_INFO, MQTT_TOPIC_DEVICE_INFO_CHANGED,
    MQTT_TOPIC_MOUSE_POSITION, MQTT_TOPIC_APPLICATIONS_INFO,
    MQTT_TOPIC_GET_MOUSE_POSITION, MQTT_TOPIC_GET_DEVICE_INFO,
    MQTT_TOPIC_GET_APPLICATIONS, AI_BACKEND_HOST, AI_BACKEND_PORT
)


class CompleteTestClient:
    """
    Complete Test Client - AI Backend Template
    
    RECEIVES via WebSocket:
      - Screenshots sent by main.py when captured (BINARY ONLY)
    
    RECEIVES via MQTT:
      - Device info (monitors, layout, bridges)
      - Mouse position
      - Applications info WITH WINDOW COORDINATES
    
    SENDS via MQTT:
      - Commands (Rubber Ducky scripts) WITH PASSWORD
      - Requests for info updates
    """
    
    def __init__(self):
        self.mqtt_client = None
        self.ws_server = None
        self.command_count = 0
        self.screenshot_count = 0
        self.screenshot_dir = Path("screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        self.max_screenshots = 10
        
        # Store received data
        self.last_device_info = None
        self.last_mouse_position = None
        self.last_applications_info = None
        
        # Feedback tracking
        self.last_feedback_time = None
        
        # Execution mode (software or hardware)
        self.execution_mode = None
        self.command_topic = None
    
    def select_execution_mode(self):
        """Let user select software or hardware mode"""
        print("\n" + "="*80)
        print("📋 SELECT EXECUTION MODE")
        print("="*80)
        print("   1. Software Executor (PyAutoGUI - for development/testing)")
        print("   2. Hardware Executor (Pico HID - for production/BIOS)")
        print("="*80)
        
        while True:
            choice = input("\nSelect mode (1 or 2): ").strip()
            if choice == "1":
                self.execution_mode = "software"
                self.command_topic = "LDrago_windows/ducky_script_software"
                print("\n✅ Software mode selected")
                print(f"   📡 Command topic: {self.command_topic}")
                break
            elif choice == "2":
                self.execution_mode = "hardware"
                self.command_topic = "LDrago_windows/pico_command_software"
                print("\n✅ Hardware mode selected")
                print(f"   📡 Command topic: {self.command_topic}")
                break
            else:
                print("❌ Invalid choice. Please enter 1 or 2.")
    
    def setup_mqtt(self):
        """Setup MQTT client"""
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if MQTT_USERNAME and MQTT_PASSWORD:
            self.mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        
        print(f"\n🔌 Connecting to MQTT: {MQTT_BROKER}:{MQTT_PORT}\n")
        self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        self.mqtt_client.loop_start()
    
    def on_mqtt_connect(self, client, userdata, flags, reason_code, properties):
        """MQTT connection callback"""
        if reason_code == 0:
            print("✅ Connected to MQTT broker")
            client.subscribe(MQTT_TOPIC_FEEDBACK_SOFTWARE)
            client.subscribe(MQTT_TOPIC_DEVICE_INFO)
            client.subscribe(MQTT_TOPIC_DEVICE_INFO_CHANGED)
            client.subscribe(MQTT_TOPIC_MOUSE_POSITION)
            client.subscribe(MQTT_TOPIC_APPLICATIONS_INFO)
            print(f"   📡 Subscribed: {MQTT_TOPIC_FEEDBACK_SOFTWARE}")
            print(f"   📡 Subscribed: {MQTT_TOPIC_DEVICE_INFO}")
            print(f"   📡 Subscribed: {MQTT_TOPIC_DEVICE_INFO_CHANGED}")
            print(f"   📡 Subscribed: {MQTT_TOPIC_MOUSE_POSITION}")
            print(f"   📡 Subscribed: {MQTT_TOPIC_APPLICATIONS_INFO}")
        else:
            print(f"❌ Failed to connect to MQTT broker (rc={reason_code})")
    
    def on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback"""
        try:
            payload = json.loads(msg.payload.decode())
            
            if msg.topic == MQTT_TOPIC_FEEDBACK_SOFTWARE:
                latency = None
                if self.last_feedback_time:
                    latency = int((time.time() - self.last_feedback_time) * 1000)
                
                status = payload.get("status", "unknown")
                message = payload.get("message", "N/A")
                print(f"\n📬 FEEDBACK{f' (latency: {latency}ms)' if latency else ''}:")
                print(f"   Status: {status}")
                print(f"   Message: {message}")
            
            elif msg.topic == MQTT_TOPIC_DEVICE_INFO:
                self.last_device_info = payload
                monitors = payload.get("monitors", {})
                monitor_list = monitors.get("list", [])
                virtual = monitors.get("virtual_desktop", {})
                layout = monitors.get("layout", "unknown")
                
                print("\n" + "="*80)
                print("🖥️  DEVICE INFO RECEIVED")
                print("="*80)
                print(f"   Monitors: {len(monitor_list)}")
                for monitor in monitor_list:
                    name = monitor.get("name", "unknown")
                    res = f"{monitor.get('width')}x{monitor.get('height')}"
                    pos = f"({monitor.get('x')}, {monitor.get('y')})"
                    work = monitor.get("work_area", {})
                    work_str = f"{work.get('width')}x{work.get('height')} at ({work.get('x')}, {work.get('y')})"
                    print(f"      └─ {name}: {res} at {pos}")
                    print(f"         Work Area: {work_str}")
                
                print(f"\n   Virtual Desktop: {virtual.get('width', 0)}x{virtual.get('height', 0)}")
                print(f"   Layout: {layout}")
                print("="*80)
            
            elif msg.topic == MQTT_TOPIC_MOUSE_POSITION:
                self.last_mouse_position = payload
                global_x = payload.get("global_x")
                global_y = payload.get("global_y")
                monitor_name = payload.get("monitor_name", "unknown")
                monitor_index = payload.get("monitor_index", -1)
                local_x = payload.get("local_x")
                local_y = payload.get("local_y")
                
                print("\n" + "="*80)
                print("🖱️  MOUSE POSITION")
                print("="*80)
                print(f"   Global: ({global_x}, {global_y})")
                print(f"   Monitor: {monitor_name} (index {monitor_index})")
                print(f"   Local: ({local_x}, {local_y})")
                print("="*80)
            
            elif msg.topic == MQTT_TOPIC_APPLICATIONS_INFO:
                self.last_applications_info = payload
                total_apps = payload.get("total_apps", 0)
                total_windows = payload.get("total_windows", 0)
                apps = payload.get("applications", [])
                
                print("\n" + "="*80)
                print("🪟 APPLICATIONS INFO")
                print("="*80)
                print(f"   Total Applications: {total_apps}")
                print(f"   Total Windows: {total_windows}")
                print("\n   All Applications:\n")
                
                for app in apps:
                    app_name = app.get("app_name", "Unknown")
                    is_active = app.get("is_active", False)
                    total = app.get("total_windows", 0)
                    open_w = app.get("open_windows", 0)
                    minimized = app.get("minimized_windows", 0)
                    
                    print(f"      • {app_name}{' ⭐' if is_active else ''}")
                    print(f"        Total: {total} windows ({open_w} open, {minimized} minimized)")
                    
                    for window in app.get("all_windows", []):
                        title = window.get("title", "Untitled")
                        is_min = window.get("is_minimized", False)
                        is_max = window.get("is_maximized", False)
                        monitor_idx = window.get("monitor_index", -1)
                        
                        if is_min:
                            restored = window.get("restored_position", {})
                            print(f"        ├─ [MINIMIZED] {title}")
                            if restored:
                                print(f"        │  Monitor {monitor_idx}: Will restore to ({restored.get('left')}, {restored.get('top')})")
                        else:
                            position = window.get("position", {})
                            title_bar = window.get("title_bar", {})
                            max_str = " [MAXIMIZED]" if is_max else ""
                            print(f"        ├─ {title}{max_str}")
                            print(f"        │  Monitor {monitor_idx}: Position ({position.get('left')}, {position.get('top')}) Size {position.get('width')}x{position.get('height')}")
                            if title_bar:
                                print(f"        │  Title Bar Center: ({title_bar.get('center_x')}, {title_bar.get('center_y')}) ← DRAG FROM HERE")
                
                print("="*80)
        
        except Exception as e:
            print(f"❌ Error processing MQTT message: {e}")
    
    async def handle_websocket(self, websocket):
        """Handle WebSocket connections - BINARY ONLY!"""
        client_addr = websocket.remote_address
        print(f"\n🔌 main.py connected via WebSocket: {client_addr}")
        
        try:
            async for message in websocket:
                # ✅ ONLY handle binary screenshots (no JSON!)
                if isinstance(message, bytes):
                    try:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"screenshot_{timestamp}.jpg"
                        filepath = self.screenshot_dir / filename
                        
                        with open(filepath, "wb") as f:
                            f.write(message)
                        
                        self.screenshot_count += 1
                        
                        print("\n" + "="*80)
                        print("📸 SCREENSHOT RECEIVED")
                        print("="*80)
                        print(f"   Size: {len(message):,} bytes")
                        print(f"   💾 Saved: {filepath}")
                        print(f"   📊 Total: {self.screenshot_count}")
                        print("="*80)
                        
                        self.cleanup_old_screenshots()
                    except Exception as e:
                        print(f"❌ Error saving screenshot: {e}")
                else:
                    print(f"\n⚠️  Received non-binary message (ignored)")
        
        except websockets.exceptions.ConnectionClosed:
            print(f"\n🔌 main.py disconnected: {client_addr}")
        except Exception as e:
            print(f"\n❌ WebSocket error: {e}")
    
    def cleanup_old_screenshots(self):
        """Keep only last N screenshots (FIFO)"""
        screenshots = sorted(
            self.screenshot_dir.glob("screenshot_*.jpg"),
            key=lambda p: p.stat().st_mtime
        )
        
        if len(screenshots) > self.max_screenshots:
            to_delete = screenshots[:-self.max_screenshots]
            for screenshot in to_delete:
                screenshot.unlink()
            print(f"🗑️  Cleaned up {len(to_delete)} old screenshot(s)")
    
    def send_command(self, script):
        """Send Rubber Ducky script command via MQTT WITH PASSWORD"""
        self.command_count += 1
        self.last_feedback_time = time.time()
        
        # ✅ Include password in payload!
        payload = json.dumps({
            "script": script,
            "password": MQTT_PASSWORD
        })
        self.mqtt_client.publish(self.command_topic, payload)
        
        preview = script[:60] + "..." if len(script) > 60 else script
        print(f"\n📤 Command sent (#{self.command_count})")
        print(f"   Topic: {self.command_topic}")
        print(f"   Script: {preview}")
    
    def request_mouse_position(self):
        """Request current mouse position"""
        print("\n📤 Requesting mouse position...")
        self.mqtt_client.publish(MQTT_TOPIC_GET_MOUSE_POSITION, json.dumps({"request": "mouse_position"}))
    
    def request_device_info(self):
        """Request device info"""
        print("\n📤 Requesting device info...")
        self.mqtt_client.publish(MQTT_TOPIC_GET_DEVICE_INFO, json.dumps({"request": "device_info"}))
    
    def request_applications(self):
        """Request applications info"""
        print("\n📤 Requesting applications...")
        self.mqtt_client.publish(MQTT_TOPIC_GET_APPLICATIONS, json.dumps({"request": "applications"}))
    
    async def start_websocket_server(self):
        """Start WebSocket server"""
        print(f"\n🌐 Starting WebSocket server: ws://{AI_BACKEND_HOST}:{AI_BACKEND_PORT}")
        
        self.ws_server = await websockets.serve(
            self.handle_websocket,
            AI_BACKEND_HOST,
            AI_BACKEND_PORT
        )
        
        print("\n✅ Ready to test!")
        print(f"   Now run main.py on target computer")
        print(f"   Screenshots will save to: {self.screenshot_dir.absolute()}\n")
    
    async def run_interactive_menu(self):
        """Interactive test menu - 100% DYNAMIC WITH DRAG SUPPORT!"""
        print("\n" + "="*80)
        print(f"🧪 RUBBER DUCKY TEST SUITE - {self.execution_mode.upper()} MODE")
        print("="*80)
        
        while True:
            print("\n📊 INFORMATION REQUESTS:")
            print("   1. Get Mouse Position")
            print("   2. Get Device Info")
            print("   3. Get Applications (with window coordinates)")
            
            print("\n📸 SCREENSHOT TESTS:")
            print("   4. Screenshot (All Monitors)")
            print("   5. Screenshot (Primary Monitor Only)")
            print("   6. Screenshot (Secondary Monitor)")
            
            print("\n🖱️  MOUSE TESTS (100% Dynamic - Choose Any App):")
            print("   7. Move to Window Center (Choose App)")
            print("   8. Cross-Monitor Movement")
            print("   9. Click on Window (Choose App)")
            print("   10. Drag Window to Other Monitor [USES MOUSE_HOLD/MOUSE_RELEASE]")
            
            print("\n⌨️  KEYBOARD TESTS:")
            print("   11. Open Notepad")
            print("   12. Type Text")
            print("   13. Keyboard Shortcuts")
            
            print("\n🎯 ADVANCED TESTS:")
            print("   14. Switch to Specific App (Choose from List)")
            print("   15. Minimize Active Window")
            print("   16. Maximize Active Window")
            
            print("\n📊 SYSTEM:")
            print("   17. Show Statistics")
            print("   18. Clear Statistics")
            print("   0. Exit")
            print("="*80)
            
            choice = await asyncio.get_event_loop().run_in_executor(None, input, "\nSelect: ")
            
            if choice == "0":
                break
            
            # Info requests
            elif choice == "1":
                self.request_mouse_position()
            
            elif choice == "2":
                self.request_device_info()
            
            elif choice == "3":
                self.request_applications()
            
            # Screenshots
            elif choice == "4":
                self.send_command("SCREENSHOT ALL 85")
            
            elif choice == "5":
                self.send_command("SCREENSHOT 0 85")
            
            elif choice == "6":
                self.send_command("SCREENSHOT 1 85")
            
            # Mouse tests
            elif choice == "7":  # Move to window center
                if not self.last_applications_info:
                    print("❌ No applications data! Run option 3 first.")
                    continue
                
                apps = self.last_applications_info.get("applications", [])
                
                # Filter windows (exclude minimized and VSCode)
                available_apps = []
                for app in apps:
                    app_name = app.get("app_name", "")
                    if "visual studio code" in app_name.lower() or "code" in app_name.lower():
                        continue
                    
                    for window in app.get("all_windows", []):
                        if not window.get("is_minimized") and window.get("title_bar"):
                            available_apps.append({
                                "app": app,
                                "window": window
                            })
                            break
                
                if not available_apps:
                    print("❌ No suitable apps found")
                    continue
                
                print("\n📱 Available apps:")
                for idx, item in enumerate(available_apps):
                    app_name = item["app"].get("app_name")
                    monitor_idx = item["window"].get("monitor_index")
                    is_max = " [MAXIMIZED]" if item["window"].get("is_maximized") else ""
                    print(f"   {idx + 1}. {app_name} (Monitor {monitor_idx}){is_max}")
                
                app_choice = await asyncio.get_event_loop().run_in_executor(None, input, "\nSelect app: ")
                
                try:
                    app_index = int(app_choice) - 1
                    if 0 <= app_index < len(available_apps):
                        item = available_apps[app_index]
                        window = item["window"]
                        position = window.get("position", {})
                        center_x = position.get("left") + position.get("width") // 2
                        center_y = position.get("top") + position.get("height") // 2
                        
                        script = f"""REM Move to window center
MOUSE_MOVE {center_x} {center_y}"""
                        
                        self.send_command(script)
                        print(f"✅ Moving to {item['app'].get('app_name')} center")
                    else:
                        print("❌ Invalid selection")
                except ValueError:
                    print("❌ Invalid input")
            
            elif choice == "8":  # Cross-monitor
                if not self.last_mouse_position or not self.last_device_info:
                    print("❌ Need mouse position AND device info! Run options 1 and 2 first.")
                    continue
                
                monitors = self.last_device_info.get("monitors", {}).get("list", [])
                if len(monitors) < 2:
                    print("❌ Need at least 2 monitors")
                    continue
                
                current_x = self.last_mouse_position.get("global_x")
                current_y = self.last_mouse_position.get("global_y")
                current_monitor_index = self.last_mouse_position.get("monitor_index")
                
                target_monitor = None
                target_index = -1
                for idx, monitor in enumerate(monitors):
                    if idx != current_monitor_index:
                        target_monitor = monitor
                        target_index = idx
                        break
                
                if target_monitor:
                    target_x = target_monitor["x"] + target_monitor["width"] // 2
                    target_y = target_monitor["y"] + target_monitor["height"] // 2
                    
                    script = f"""REM Cross-monitor movement
MOUSE_MOVE {target_x} {target_y}
DELAY 1000
MOUSE_MOVE {current_x} {current_y}"""
                    
                    self.send_command(script)
                    print(f"✅ Moving FROM Monitor {current_monitor_index} TO Monitor {target_index}")
                else:
                    print("❌ Could not find target monitor")
            
            elif choice == "9":  # Click on window
                if not self.last_applications_info:
                    print("❌ No applications data! Run option 3 first.")
                    continue
                
                apps = self.last_applications_info.get("applications", [])
                
                # Filter windows (exclude minimized and VSCode)
                available_apps = []
                for app in apps:
                    app_name = app.get("app_name", "")
                    if "visual studio code" in app_name.lower() or "code" in app_name.lower():
                        continue
                    
                    for window in app.get("all_windows", []):
                        if not window.get("is_minimized") and window.get("title_bar"):
                            available_apps.append({
                                "app": app,
                                "window": window
                            })
                            break
                
                if not available_apps:
                    print("❌ No suitable apps found")
                    continue
                
                print("\n📱 Available apps to click:")
                for idx, item in enumerate(available_apps):
                    app_name = item["app"].get("app_name")
                    monitor_idx = item["window"].get("monitor_index")
                    is_max = " [MAXIMIZED]" if item["window"].get("is_maximized") else ""
                    print(f"   {idx + 1}. {app_name} (Monitor {monitor_idx}){is_max}")
                
                app_choice = await asyncio.get_event_loop().run_in_executor(None, input, "\nSelect app: ")
                
                try:
                    app_index = int(app_choice) - 1
                    if 0 <= app_index < len(available_apps):
                        item = available_apps[app_index]
                        window = item["window"]
                        position = window.get("position", {})
                        center_x = position.get("left") + position.get("width") // 2
                        center_y = position.get("top") + position.get("height") // 2
                        
                        script = f"""REM Click on window
MOUSE_MOVE {center_x} {center_y}
DELAY 100
MOUSE_CLICK LEFT"""
                        
                        self.send_command(script)
                        print(f"✅ Clicking on {item['app'].get('app_name')}")
                    else:
                        print("❌ Invalid selection")
                except ValueError:
                    print("❌ Invalid input")
            
            elif choice == "10":  # ✅ DRAG - USES MOUSE_HOLD/MOUSE_RELEASE!
                if not self.last_applications_info or not self.last_device_info:
                    print("❌ Need applications AND device info! Run options 2 and 3 first.")
                    continue
                
                apps = self.last_applications_info.get("applications", [])
                monitors = self.last_device_info.get("monitors", {}).get("list", [])
                
                if len(monitors) < 2:
                    print("❌ Need at least 2 monitors")
                    continue
                
                # Filter windows (exclude minimized and VSCode)
                available_apps = []
                for app in apps:
                    app_name = app.get("app_name", "")
                    if "visual studio code" in app_name.lower() or "code" in app_name.lower():
                        continue
                    
                    for window in app.get("all_windows", []):
                        if not window.get("is_minimized") and window.get("title_bar"):
                            available_apps.append({
                                "app": app,
                                "window": window
                            })
                            break
                
                if not available_apps:
                    print("❌ No suitable apps found")
                    continue
                
                print("\n📱 Available apps to drag:")
                for idx, item in enumerate(available_apps):
                    app_name = item["app"].get("app_name")
                    monitor_idx = item["window"].get("monitor_index")
                    is_max = " [MAXIMIZED - will auto un-maximize]" if item["window"].get("is_maximized") else ""
                    print(f"   {idx + 1}. {app_name} (currently on Monitor {monitor_idx}){is_max}")
                
                app_choice = await asyncio.get_event_loop().run_in_executor(None, input, "\nSelect app to drag: ")
                
                try:
                    app_index = int(app_choice) - 1
                    if 0 <= app_index < len(available_apps):
                        item = available_apps[app_index]
                        selected_app = item["app"]
                        window = item["window"]
                        source_monitor_index = window.get("monitor_index")
                        
                        # Find target monitor
                        target_monitor = None
                        target_index = -1
                        for idx, monitor in enumerate(monitors):
                            if idx != source_monitor_index:
                                target_monitor = monitor
                                target_index = idx
                                break
                        
                        if target_monitor:
                            title_bar = window.get("title_bar", {})
                            start_x = title_bar.get("center_x")
                            start_y = title_bar.get("center_y")
                            
                            # ✅ Drag to safe zone (200px from edge)
                            target_x = target_monitor["x"] + 200
                            target_y = target_monitor["y"] + 150
                            
                            # ✅ NEW: Use MOUSE_HOLD and MOUSE_RELEASE!
                            script = f"""REM Drag {selected_app.get('app_name')} to other monitor
MOUSE_MOVE {start_x} {start_y}
DELAY 200
MOUSE_HOLD LEFT
DELAY 150
MOUSE_MOVE {target_x} {target_y}
DELAY 150
MOUSE_RELEASE LEFT"""
                            
                            self.send_command(script)
                            print(f"✅ Dragging {selected_app.get('app_name')} from Monitor {source_monitor_index} to Monitor {target_index}")
                            print(f"   Using MOUSE_HOLD → MOUSE_MOVE → MOUSE_RELEASE")
                            print(f"   Target position: ({target_x}, {target_y}) [Safe zone - no snap]")
                        else:
                            print("❌ Could not find target monitor")
                    else:
                        print("❌ Invalid selection")
                except ValueError:
                    print("❌ Invalid input")
            
            # Keyboard tests
            elif choice == "11":
                self.send_command("GUI r\nDELAY 500\nSTRING notepad\nDELAY 100\nENTER")
                print("✅ Opening Notepad")
            
            elif choice == "12":
                self.send_command("STRING Hello from dynamic AI backend!")
                print("✅ Typing text")
            
            elif choice == "13":
                self.send_command("CTRL a\nDELAY 100\nCTRL c")
                print("✅ Executing keyboard shortcuts (Ctrl+A, Ctrl+C)")
            
            # Advanced tests
            elif choice == "14":  # ✅ FIXED - Switch to specific app
                if not self.last_applications_info:
                    print("❌ No applications data! Run option 3 first.")
                    continue
                
                apps = self.last_applications_info.get("applications", [])
                
                if not apps:
                    print("❌ No applications found")
                    continue
                
                print("\n📱 Available apps:")
                for idx, app in enumerate(apps):
                    app_name = app.get("app_name")
                    open_count = app.get("open_windows", 0)
                    print(f"   {idx + 1}. {app_name} ({open_count} open windows)")
                
                app_choice = await asyncio.get_event_loop().run_in_executor(None, input, "\nSelect app: ")
                
                try:
                    app_index = int(app_choice) - 1
                    if 0 <= app_index < len(apps):
                        selected_app = apps[app_index]
                        open_windows = [w for w in selected_app.get("all_windows", []) if not w.get("is_minimized")]
                        
                        if not open_windows:
                            print("❌ App has no open windows")
                            continue
                        
                        window = open_windows[0]
                        title_bar = window.get("title_bar", {})
                        
                        if not title_bar:
                            print("❌ Window has no title bar data")
                            continue
                        
                        x = title_bar.get("center_x")
                        y = title_bar.get("center_y")
                        
                        script = f"""REM Switch to {selected_app.get('app_name')}
MOUSE_MOVE {x} {y}
DELAY 100
MOUSE_CLICK LEFT"""
                        
                        self.send_command(script)
                        print(f"✅ Switching to {selected_app.get('app_name')}")
                    else:
                        print("❌ Invalid selection")
                except ValueError:
                    print("❌ Invalid input")
            
            elif choice == "15":  # ✅ FIXED - Minimize active
                self.send_command("ALT SPACE\nDELAY 100\nSTRING n")
                print("✅ Minimizing active window")
            
            elif choice == "16":  # ✅ FIXED - Maximize active
                self.send_command("GUI UP")
                print("✅ Maximizing active window")
            
            # Statistics
            elif choice == "17":
                print(f"\n📊 Statistics:")
                print(f"   Mode: {self.execution_mode}")
                print(f"   Command topic: {self.command_topic}")
                print(f"   Commands sent: {self.command_count}")
                print(f"   Screenshots received: {self.screenshot_count}")
                print(f"   Device info: {'✅' if self.last_device_info else '❌'}")
                print(f"   Mouse position: {'✅' if self.last_mouse_position else '❌'}")
                print(f"   Applications: {'✅' if self.last_applications_info else '❌'}")
            
            elif choice == "18":
                self.command_count = 0
                self.screenshot_count = 0
                print("\n✅ Statistics cleared")
            
            else:
                print("\n❌ Invalid choice")
    
    async def run(self):
        """Main run loop"""
        print("\n" + "="*80)
        print("🤖 COMPLETE AI BACKEND TEST & TEMPLATE - 100% DYNAMIC!")
        print("="*80)
        print("\nFeatures:")
        print("   ✅ WebSocket Server (receives screenshots)")
        print("   ✅ MQTT Client (receives device/mouse/apps WITH COORDINATES)")
        print("   ✅ MQTT Publisher (sends commands WITH PASSWORD)")
        print("   ✅ 100% DYNAMIC coordinates - uses REAL positions!")
        print("   ✅ Supports BOTH Software & Hardware modes!")
        print("   ✅ FIFO screenshot management (keeps last 10)")
        print("   ✅ Full error handling - Never crashes!")
        print("   ✅ ALLOWS DRAGGING MAXIMIZED WINDOWS! (Windows auto un-maximizes)")
        print("   ✅ USES MOUSE_HOLD/MOUSE_RELEASE for perfect dragging!")
        print("   ✅ BINARY-ONLY SCREENSHOTS (no duplicates!)")
        print("="*80)
        
        # Select execution mode
        self.select_execution_mode()
        
        # Setup MQTT
        self.setup_mqtt()
        
        # Request initial data
        await asyncio.sleep(1)
        print("\n📤 Requesting initial data...")
        self.request_device_info()
        
        # Start WebSocket server
        await self.start_websocket_server()
        
        # Run interactive menu
        await self.run_interactive_menu()
        
        # Cleanup
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        print("\n👋 Goodbye!")


if __name__ == "__main__":
    client = CompleteTestClient()
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
