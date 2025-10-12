import paho.mqtt.client as mqtt
import json
import time
import threading
import os
import sys


class UltimateMultiMonitorController:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)  
        self.monitor_info = None
        self.simplified_monitors = None
        self.virtual_desktop = None
        self.connected = False
        self.last_result = None
        self.waiting_for_result = False
        self.support_mode = "dual"  # dual, simplified, universal
        
    def setup_mqtt(self):
        """Setup MQTT connection with dual-mode support"""
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                self.connected = True
                print("✅ Connected to MQTT broker")
                # Subscribe to all relevant topics
                client.subscribe("LDrago_windows/system_info")
                client.subscribe("LDrago_windows/simplified_monitor_info")
                client.subscribe("LDrago_windows/mouse_result")
                client.subscribe("LDrago_windows/monitor_change")
                client.subscribe("LDrago_windows/alice_voice_alert")
            else:
                print(f"❌ Failed to connect to MQTT broker: {rc}")
        
        def on_message(client, userdata, msg):
            try:
                topic = msg.topic
                payload = json.loads(msg.payload.decode())
                
                if topic == "LDrago_windows/system_info":
                    self.monitor_info = payload
                    self.virtual_desktop = payload.get("virtual_desktop", {})
                    self.display_monitor_info_received()
                    
                elif topic == "LDrago_windows/simplified_monitor_info":
                    self.simplified_monitors = payload
                    self.display_simplified_info_received()
                    
                elif topic == "LDrago_windows/mouse_result":
                    self.last_result = payload
                    self.waiting_for_result = False
                    self.display_movement_result(payload)
                    
                elif topic == "LDrago_windows/monitor_change":
                    print(f"\n🖥️ DISPLAY CONFIGURATION CHANGED!")
                    self.monitor_info = payload.get("new_setup")
                    if self.monitor_info:
                        self.virtual_desktop = self.monitor_info.get("virtual_desktop", {})
                    print("📡 Updated monitor information received")
                    
                elif topic == "LDrago_windows/alice_voice_alert":
                    alert_type = payload.get("alert_type", "unknown")
                    message = payload.get("message", "")
                    print(f"\n🤖 ALICE: {message}")
                    
            except Exception as e:
                print(f"❌ Error processing message: {e}")
        
        self.client.on_connect = on_connect
        self.client.on_message = on_message
        
        try:
            self.client.connect("broker.emqx.io", 1883, 60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            while not self.connected and timeout > 0:
                time.sleep(0.1)
                timeout -= 0.1
                
            return self.connected
            
        except Exception as e:
            print(f"❌ MQTT connection error: {e}")
            return False
    
    def display_monitor_info_received(self):
        """Display received universal monitor information"""
        if not self.monitor_info:
            return
            
        print(f"\n📡 UNIVERSAL MONITOR INFO RECEIVED:")
        
        # Fixed: monitor_count and arrangement are now at top level
        print(f"   Monitor Count: {self.monitor_info.get('monitor_count', 'Unknown')}")
        print(f"   Arrangement: {self.monitor_info.get('arrangement_type', 'Unknown')}")
        print(f"   Description: {self.monitor_info.get('arrangement_description', 'Unknown')}")
        
        # Virtual desktop info is in virtual_desktop
        vd = self.monitor_info.get("virtual_desktop", {})
        if vd:
            bounds = vd.get("bounds", {})
            print(f"   Virtual Desktop: {bounds.get('width', 0)}x{bounds.get('height', 0)}")
            print(f"   Global Coordinates: ({bounds.get('left', 0)},{bounds.get('top', 0)}) to ({bounds.get('right', 0)},{bounds.get('bottom', 0)})")
    
    def display_simplified_info_received(self):
        """Display received simplified monitor information"""
        if not self.simplified_monitors:
            return
            
        print(f"\n🎯 SIMPLIFIED MONITOR INFO RECEIVED:")
        print(f"   Monitor Count: {self.simplified_monitors.get('monitor_count', 'Unknown')}")
        print(f"   Arrangement: {self.simplified_monitors.get('arrangement', 'Unknown')}")
        
        for monitor in self.simplified_monitors.get("monitors", []):
            print(f"   {monitor['name']}: {monitor['resolution']} | Local coords: 0-{monitor['width']-1} x 0-{monitor['height']-1}")
    
    def display_movement_result(self, result):
        """Display detailed movement result"""
        status = result.get("status", "unknown")
        error = result.get("error", 0)
        corrections = result.get("corrections", 0)
        total_time = result.get("total_time", 0)
        phase = result.get("phase", "unknown")
        
        if status == "success":
            print(f"\n✅ MOVEMENT SUCCESS!")
            print(f"   Final Error: {error:.1f}px")
            print(f"   Corrections Used: {corrections}")
            print(f"   Total Time: {total_time:.2f}s")
            print(f"   Completion Phase: {phase}")
            
            if result.get("multi_screen", False):
                print(f"   🖥️ Multi-screen movement completed")
            
            if result.get("universal_mode", False):
                print(f"   🌍 Universal pathfinding used")
                
        else:
            print(f"\n⚠️ MOVEMENT {status.upper()}")
            print(f"   Final Error: {error:.1f}px")
            print(f"   Corrections Attempted: {corrections}")
            print(f"   Time Elapsed: {total_time:.2f}s")
            
            failure_reason = result.get("failure_reason", "Unknown reason")
            print(f"   Reason: {failure_reason}")
    
    def send_simplified_mouse_command(self, monitor_id, local_x, local_y, timeout=35.0):
        """Send simplified monitor-based mouse command"""
        if not self.connected:
            print("❌ Not connected to MQTT broker")
            return False
        
        # Validate simplified command
        if not self.simplified_monitors:
            print("❌ No simplified monitor information available")
            return False
        
        monitors = self.simplified_monitors.get("monitors", [])
        if monitor_id >= len(monitors):
            print(f"❌ Monitor {monitor_id} does not exist")
            return False
        
        target_monitor = monitors[monitor_id]
        
        # Validate local coordinates
        if not (0 <= local_x < target_monitor["width"] and 
                0 <= local_y < target_monitor["height"]):
            print(f"❌ Coordinates ({local_x}, {local_y}) outside {target_monitor['name']} bounds")
            print(f"   Valid range: X: 0-{target_monitor['width']-1}, Y: 0-{target_monitor['height']-1}")
            return False
        
        command = {
            "monitor_id": monitor_id,
            "x": int(local_x),
            "y": int(local_y),
            "timeout": timeout,
            "timestamp": time.time()
        }
        
        try:
            self.client.publish("LDrago_windows/simple_monitor_target", json.dumps(command))
            print(f"🎯 Sent simplified command: {target_monitor['name']} at ({local_x}, {local_y})")
            self.waiting_for_result = True
            return True
        except Exception as e:
            print(f"❌ Error sending command: {e}")
            return False
    
    def send_universal_mouse_command(self, target_x, target_y, timeout=35.0):
        """Send universal coordinate mouse command"""
        if not self.connected:
            print("❌ Not connected to MQTT broker")
            return False
        
        # Validate coordinates if monitor info is available
        if self.monitor_info and self.virtual_desktop:
            is_valid, message = self.validate_coordinates(target_x, target_y)
            if not is_valid:
                print(f"❌ COORDINATE VALIDATION FAILED: {message}")
                return False
            print(f"✅ Coordinates validated: {message}")
        
        command = {
            "x": int(target_x),
            "y": int(target_y),
            "timeout": timeout,
            "timestamp": time.time()
        }
        
        try:
            self.client.publish("LDrago_windows/mouse_target", json.dumps(command))
            print(f"🎯 Sent universal command: ({target_x}, {target_y})")
            self.waiting_for_result = True
            return True
        except Exception as e:
            print(f"❌ Error sending command: {e}")
            return False
    
    def validate_coordinates(self, x, y):
        """Validate target coordinates against virtual desktop bounds"""
        if not self.virtual_desktop or not self.virtual_desktop.get("bounds"):
            return True, "No bounds information available"
        
        bounds = self.virtual_desktop["bounds"]
        
        if (bounds["left"] <= x <= bounds["right"] and 
            bounds["top"] <= y <= bounds["bottom"]):
            
            # Find which monitor will contain these coordinates
            target_monitor = None
            for monitor in self.monitor_info.get("monitors", []):
                if (monitor["x"] <= x < monitor["bounds"]["right"] and 
                    monitor["y"] <= y < monitor["bounds"]["bottom"]):
                    target_monitor = monitor
                    break
            
            if target_monitor:
                return True, f"Target on {target_monitor['name']} ({target_monitor['resolution']})"
            else:
                return True, "Coordinates within virtual desktop bounds"
        else:
            return False, f"Coordinates outside valid range ({bounds['left']},{bounds['top']}) to ({bounds['right']},{bounds['bottom']})"
    
    def request_system_info(self):
        """Request both universal and simplified system information"""
        if not self.connected:
            print("❌ Not connected to MQTT broker")
            return False
            
        try:
            # Request universal info
            self.client.publish("LDrago_windows/system_info_request", "{}")
            # Request simplified info
            self.client.publish("LDrago_windows/get_simplified_info", "{}")
            print("📡 Requesting system info...")
            
            # Wait for responses
            timeout = 10
            start_time = time.time()
            while ((self.monitor_info is None or self.simplified_monitors is None) and 
                   (time.time() - start_time) < timeout):
                time.sleep(0.1)
                
            return self.monitor_info is not None or self.simplified_monitors is not None
            
        except Exception as e:
            print(f"❌ Error requesting system info: {e}")
            return False
    
    def wait_for_movement_complete(self, timeout=35):
        """Wait for movement to complete with enhanced feedback"""
        start_time = time.time()
        
        print("⏳ Moving mouse", end="")
        dots = 0
        
        while self.waiting_for_result and (time.time() - start_time) < timeout:
            elapsed = time.time() - start_time
            
            # Show progress dots
            dots = (dots + 1) % 4
            progress_str = "." * dots + " " * (3 - dots)
            print(f"\r⏳ Moving mouse{progress_str} ({elapsed:.1f}s)", end="")
            
            time.sleep(0.5)
        
        print()  # New line
        
        if self.waiting_for_result:
            print("⚠️ Movement timed out after 35 seconds")
            self.waiting_for_result = False
            return False
        
        return True


def clear_screen():
    """Clear terminal screen (Cross-platform)"""
    os.system('cls' if os.name == 'nt' else 'clear')


def display_header():
    """Display enhanced program header"""
    clear_screen()
    print("=" * 80)
    print("🖱️  ULTIMATE DUAL-MODE MULTI-MONITOR CONTROLLER v3.0")
    print("=" * 80)
    print("🎯 Simplified Mode: Select monitor + local coordinates")
    print("🌍 Universal Mode: Global coordinate system")
    print("=" * 80)


def show_enhanced_menu(title, options):
    """Display enhanced numbered menu"""
    print(f"\n{title}")
    print("-" * len(title))
    
    for i, option in enumerate(options, 1):
        print(f"{i}. {option}")
    
    while True:
        try:
            choice = input(f"\nSelect option (1-{len(options)}) or 'q' to quit: ").strip().lower()
            
            if choice == 'q':
                return None
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(options):
                return choice_num - 1
            else:
                print(f"❌ Please enter a number between 1 and {len(options)}")
                
        except ValueError:
            print("❌ Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            return None


def simplified_monitor_selection(controller):
    """Simplified monitor-based coordinate input"""
    if not controller.simplified_monitors:
        print("❌ No simplified monitor information available. Request system info first.")
        return None, None, None
    
    monitors = controller.simplified_monitors.get("monitors", [])
    if not monitors:
        print("❌ No monitors available")
        return None, None, None
    
    # Monitor selection
    monitor_options = [f"{monitor['name']} - {monitor['resolution']} ({monitor['orientation']})" 
                      for monitor in monitors]
    
    print(f"\n🖥️ SELECT TARGET MONITOR:")
    monitor_choice = show_enhanced_menu("Available Monitors:", monitor_options)
    
    if monitor_choice is None:
        return None, None, None
    
    selected_monitor = monitors[monitor_choice]
    monitor_id = selected_monitor["id"]
    
    print(f"\n📐 Selected: {selected_monitor['name']} ({selected_monitor['resolution']})")
    print(f"Valid coordinates: X: 0 to {selected_monitor['width']-1}, Y: 0 to {selected_monitor['height']-1}")
    
    # Coordinate input
    try:
        print(f"\n🎯 Enter coordinates for {selected_monitor['name']}:")
        x = input(f"X coordinate (0 to {selected_monitor['width']-1}): ")
        y = input(f"Y coordinate (0 to {selected_monitor['height']-1}): ")
        
        x = int(x)
        y = int(y)
        
        # Validate coordinates
        if (0 <= x < selected_monitor["width"] and 
            0 <= y < selected_monitor["height"]):
            return monitor_id, x, y
        else:
            print(f"❌ Coordinates out of bounds!")
            return None, None, None
            
    except ValueError:
        print("❌ Invalid input! Please enter numbers only.")
        return None, None, None


def simplified_preset_coordinates(controller):
    """Simplified preset coordinates for each monitor"""
    if not controller.simplified_monitors:
        print("❌ No simplified monitor information available")
        return None, None, None
    
    presets = []
    
    # Generate presets for each monitor
    for monitor in controller.simplified_monitors.get("monitors", []):
        monitor_id = monitor["id"]
        name = monitor["name"]
        width = monitor["width"]
        height = monitor["height"]
        
        # Center
        presets.append((f"🎯 {name} - Center", monitor_id, width//2, height//2))
        
        # Corners (with safe margins)
        margin = 50
        presets.extend([
            (f"↖️ {name} - Top Left", monitor_id, margin, margin),
            (f"↗️ {name} - Top Right", monitor_id, width-margin, margin),
            (f"↙️ {name} - Bottom Left", monitor_id, margin, height-margin),
            (f"↘️ {name} - Bottom Right", monitor_id, width-margin, height-margin),
        ])
    
    options = [f"{name} ({x}, {y})" for name, mid, x, y in presets]
    choice = show_enhanced_menu("🎯 Simplified Preset Locations:", options)
    
    if choice is not None and choice < len(presets):
        name, monitor_id, x, y = presets[choice]
        print(f"Selected: {name}")
        return monitor_id, x, y
    
    return None, None, None


def universal_coordinate_input(controller):
    """Universal coordinate input system"""
    if not controller.monitor_info or not controller.virtual_desktop:
        print("⚠️ No universal monitor information available. Using default bounds.")
        max_x, max_y = 1920, 1080
        min_x, min_y = 0, 0
        print(f"📐 Assuming screen size: {max_x}x{max_y}")
    else:
        # Fixed: virtual_desktop structure
        vd = controller.monitor_info.get("virtual_desktop", {})
        bounds = vd.get("bounds", {})
        min_x = bounds.get("left", 0)
        max_x = bounds.get("right", 1920)
        min_y = bounds.get("top", 0)
        max_y = bounds.get("bottom", 1080)
        print(f"📐 Virtual Desktop: {bounds.get('width', 0)}x{bounds.get('height', 0)}")
        print(f"📏 Global Range: ({min_x},{min_y}) to ({max_x},{max_y})")
    
    try:
        print("\n🌍 Enter global coordinates:")
        x = input(f"X coordinate ({min_x} to {max_x}): ")
        y = input(f"Y coordinate ({min_y} to {max_y}): ")
        
        x = int(x)
        y = int(y)
        
        # Validate coordinates
        if min_x <= x <= max_x and min_y <= y <= max_y:
            # Additional validation using controller's validation method
            if controller.monitor_info:
                is_valid, message = controller.validate_coordinates(x, y)
                if is_valid:
                    print(f"✅ {message}")
                    return x, y
                else:
                    print(f"❌ {message}")
                    return None, None
            else:
                return x, y
        else:
            print(f"❌ Coordinates out of bounds! Use {min_x}-{max_x} for X, {min_y}-{max_y} for Y")
            return None, None
            
    except ValueError:
        print("❌ Invalid input! Please enter numbers only.")
        return None, None


def universal_preset_coordinates(controller):
    """Universal preset coordinates menu"""
    if not controller.monitor_info:
        print("❌ No universal monitor information available")
        return None, None
    
    presets = []
    
    # Add presets for each monitor with global coordinates
    for monitor in controller.monitor_info.get("monitors", []):
        monitor_name = monitor.get("name", f"Monitor {monitor.get('id', 0)}")
        width = monitor.get("width", 1920)
        height = monitor.get("height", 1080)
        offset_x = monitor.get("x", 0)
        offset_y = monitor.get("y", 0)
        
        # Add center point for each monitor
        center_x = offset_x + width // 2
        center_y = offset_y + height // 2
        presets.append((f"🎯 {monitor_name} Center (Global)", center_x, center_y))
        
        # Add corners for primary monitor only
        if monitor.get("is_primary", False):
            presets.extend([
                (f"↖️ {monitor_name} Top Left (Global)", offset_x + 50, offset_y + 50),
                (f"↗️ {monitor_name} Top Right (Global)", offset_x + width - 50, offset_y + 50),
                (f"↙️ {monitor_name} Bottom Left (Global)", offset_x + 50, offset_y + height - 50),
                (f"↘️ {monitor_name} Bottom Right (Global)", offset_x + width - 50, offset_y + height - 50),
            ])
    
    # Add virtual desktop center if multiple monitors
    if len(controller.monitor_info.get("monitors", [])) > 1:
        vd = controller.monitor_info.get("virtual_desktop", {})
        bounds = vd.get("bounds", {})
        if bounds:
            virtual_center_x = bounds.get("left", 0) + bounds.get("width", 0) // 2
            virtual_center_y = bounds.get("top", 0) + bounds.get("height", 0) // 2
            presets.insert(0, ("🌐 Virtual Desktop Center", virtual_center_x, virtual_center_y))
    
    options = [f"{name} ({x}, {y})" for name, x, y in presets]
    choice = show_enhanced_menu("🌍 Universal Preset Locations:", options)
    
    if choice is not None and choice < len(presets):
        name, x, y = presets[choice]
        print(f"Selected: {name}")
        return x, y
    
    return None, None


def display_comprehensive_system_info(controller):
    """Display both simplified and universal system information"""
    print("\n" + "="*70)
    print("🖥️  COMPREHENSIVE SYSTEM INFORMATION")
    print("="*70)
    
    # Simplified monitor info
    if controller.simplified_monitors:
        print("🎯 SIMPLIFIED MONITOR INFO:")
        print(f"   Monitor Count: {controller.simplified_monitors.get('monitor_count', 'Unknown')}")
        print(f"   Arrangement: {controller.simplified_monitors.get('arrangement', 'Unknown')}")
        
        for monitor in controller.simplified_monitors.get("monitors", []):
            print(f"   {monitor['name']}: {monitor['resolution']} | Local: 0-{monitor['width']-1} x 0-{monitor['height']-1}")
        print()
    
    # Universal monitor info
    if controller.monitor_info:
        print("🌍 UNIVERSAL MONITOR INFO:")
        # Fixed: data structure changed in test.py v12.0
        print(f"   Controller Type: {controller.monitor_info.get('controller_type', 'Unknown')}")
        print(f"   Version: {controller.monitor_info.get('version', 'Unknown')}")
        print(f"   Monitor Count: {controller.monitor_info.get('monitor_count', 'Unknown')}")
        print(f"   Arrangement: {controller.monitor_info.get('arrangement_type', 'Unknown')}")
        print(f"   Description: {controller.monitor_info.get('arrangement_description', 'Unknown')}")
        
        # Virtual desktop info
        vd = controller.monitor_info.get("virtual_desktop", {})
        if vd:
            bounds = vd.get("bounds", {})
            print(f"   Virtual Desktop: {bounds.get('width', 0)}x{bounds.get('height', 0)}")
            print(f"   Global Range: ({bounds.get('left', 0)},{bounds.get('top', 0)}) to ({bounds.get('right', 0)},{bounds.get('bottom', 0)})")
        
        # Individual monitor details with global coordinates
        monitors = controller.monitor_info.get("monitors", [])
        if monitors:
            print(f"   Individual Monitors (Global Coordinates):")
            for monitor in monitors:
                primary_str = "🏆 PRIMARY" if monitor.get("is_primary", False) else ""
                resolution = f"{monitor.get('width', 0)}x{monitor.get('height', 0)}"
                print(f"     {monitor.get('name', 'Unknown')}: {resolution} at ({monitor.get('x', 0)},{monitor.get('y', 0)}) {primary_str}")
        
        # Features
        features = controller.monitor_info.get("features", {})
        if features:
            print(f"   Features:")
            print(f"     • Phase System: {'✅' if features.get('master_phase_system') else '❌'}")
            print(f"     • Hardware Verification: {'✅' if features.get('hardware_verification') else '❌'}")
            print(f"     • Cross-Monitor: {'✅' if features.get('cross_monitor_automatic') else '❌'}")
            print(f"     • Timeout: {features.get('phase_1_duration', 0) + features.get('phase_2_duration', 0) + features.get('phase_3_duration', 0)}s")
    
    print("="*70 + "\n")


def main():
    """Ultimate dual-mode main program"""
    display_header()
    
    controller = UltimateMultiMonitorController()
    
    # Try to connect to MQTT
    print("🔌 Connecting to MQTT broker...")
    if not controller.setup_mqtt():
        print("❌ Failed to connect to MQTT. Exiting...")
        input("Press Enter to exit...")
        return
    
    print("✅ Connected! Requesting system information...")
    controller.request_system_info()
    time.sleep(2)  # Give time for system info to arrive
    
    main_options = [
        "🎯 Simplified Mode - Select Monitor + Local Coordinates", 
        "🖥️ Simplified Mode - Monitor Presets",
        "🌍 Universal Mode - Enter Global Coordinates",
        "🌐 Universal Mode - Global Presets", 
        "📡 Request System Info",
        "📺 Display Comprehensive System Info",
        "🔄 Test Connection & Refresh Info"
    ]
    
    while True:
        display_header()
        
        connection_status = "🟢 Connected" if controller.connected else "🔴 Disconnected"
        simplified_status = f"🎯 {controller.simplified_monitors['monitor_count'] if controller.simplified_monitors else 0} monitors (Simplified)" 
        # Fixed: monitor_count is now at top level, not in system_info
        universal_status = f"🌍 {controller.monitor_info.get('monitor_count', 0) if controller.monitor_info else 0} monitors (Universal)"
        
        print(f"Status: {connection_status} | {simplified_status} | {universal_status}")
        print(f"Broker: broker.emqx.io\n")
        
        choice = show_enhanced_menu("🎮 Ultimate Dual-Mode Controller - Main Menu:", main_options)
        
        if choice is None:  # User chose to quit
            break
            
        elif choice == 0:  # Simplified Mode - Custom Coordinates
            monitor_id, x, y = simplified_monitor_selection(controller)
            if monitor_id is not None and x is not None and y is not None:
                if controller.send_simplified_mouse_command(monitor_id, x, y):
                    controller.wait_for_movement_complete()
                    
        elif choice == 1:  # Simplified Mode - Presets
            monitor_id, x, y = simplified_preset_coordinates(controller)
            if monitor_id is not None and x is not None and y is not None:
                if controller.send_simplified_mouse_command(monitor_id, x, y):
                    controller.wait_for_movement_complete()
                    
        elif choice == 2:  # Universal Mode - Custom Coordinates
            x, y = universal_coordinate_input(controller)
            if x is not None and y is not None:
                if controller.send_universal_mouse_command(x, y):
                    controller.wait_for_movement_complete()
                    
        elif choice == 3:  # Universal Mode - Presets
            x, y = universal_preset_coordinates(controller)
            if x is not None and y is not None:
                if controller.send_universal_mouse_command(x, y):
                    controller.wait_for_movement_complete()
                    
        elif choice == 4:  # Request System Info
            print("📡 Requesting fresh system information...")
            controller.request_system_info()
            
        elif choice == 5:  # Display Comprehensive System Info
            display_comprehensive_system_info(controller)
            
        elif choice == 6:  # Test Connection
            print("🔍 Testing connection and refreshing info...")
            if controller.connected:
                print("✅ MQTT connection is active")
                controller.request_system_info()
                time.sleep(1)
                if controller.monitor_info or controller.simplified_monitors:
                    print("✅ System information refreshed")
                else:
                    print("⚠️ No response from controller")
            else:
                print("❌ MQTT connection lost - attempting reconnection...")
                controller.setup_mqtt()
        
        # Pause before showing menu again
        if choice is not None:
            input("\nPress Enter to continue...")
    
    print("👋 Goodbye!")
    controller.client.loop_stop()
    controller.client.disconnect()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        input("Press Enter to exit...")
