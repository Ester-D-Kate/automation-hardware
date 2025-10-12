"""
Main automation script for device monitoring and MQTT integration
"""

import asyncio
import json
from mqtt_handler import MQTTHandler
from device_info import extract_complete_device_info, get_current_mouse_position


def convert_to_json(data):
    """Convert data to JSON string, handling tuples"""
    def convert_tuples(obj):
        if isinstance(obj, dict):
            return {k: convert_tuples(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_tuples(item) for item in obj]
        elif isinstance(obj, tuple):
            return list(obj)
        return obj
    
    converted_data = convert_tuples(data)
    return json.dumps(converted_data)


class DeviceChangeDetector:
    @staticmethod
    def has_changed(new_info: dict, old_info: dict) -> bool:
        """Check if ANY device configuration changed (monitors, layout, bridges, virtual desktop)"""
        if not old_info:
            return True
        
        # Check monitor count
        new_monitors = new_info.get("monitors", {}).get("list", [])
        old_monitors = old_info.get("monitors", {}).get("list", [])
        
        if len(new_monitors) != len(old_monitors):
            return True
        
        # Check each monitor's properties (position, size, work area)
        for new_mon, old_mon in zip(new_monitors, old_monitors):
            if (new_mon.get("x") != old_mon.get("x") or
                new_mon.get("y") != old_mon.get("y") or
                new_mon.get("width") != old_mon.get("width") or
                new_mon.get("height") != old_mon.get("height")):
                return True
            
            # Check work area changes
            new_work = new_mon.get("work_area", {})
            old_work = old_mon.get("work_area", {})
            if (new_work.get("x") != old_work.get("x") or
                new_work.get("y") != old_work.get("y") or
                new_work.get("width") != old_work.get("width") or
                new_work.get("height") != old_work.get("height")):
                return True
        
        # Check virtual desktop boundaries
        new_vd = new_info.get("virtual_desktop", {})
        old_vd = old_info.get("virtual_desktop", {})
        if (new_vd.get("width") != old_vd.get("width") or
            new_vd.get("height") != old_vd.get("height") or
            new_vd.get("min_x") != old_vd.get("min_x") or
            new_vd.get("max_x") != old_vd.get("max_x") or
            new_vd.get("min_y") != old_vd.get("min_y") or
            new_vd.get("max_y") != old_vd.get("max_y")):
            return True
        
        # Check layout type
        new_layout = new_info.get("layout", {})
        old_layout = old_info.get("layout", {})
        if new_layout.get("layout") != old_layout.get("layout"):
            return True
        
        # Check relationships count (different arrangements)
        new_rels = new_layout.get("relationships", [])
        old_rels = old_layout.get("relationships", [])
        if len(new_rels) != len(old_rels):
            return True
        
        # Check bridge points count (different monitor connections)
        new_bridges = new_info.get("bridge_points", [])
        old_bridges = old_info.get("bridge_points", [])
        if len(new_bridges) != len(old_bridges):
            return True
        
        return False


class DeviceMonitor:
    def __init__(self):
        self.mqtt = None
        self.current_device_info = None
        self.check_interval = 5.0
        
    def _handle_mqtt_message(self, topic, payload):
        if topic == "LDrago_windows/get_mouse_position":
            asyncio.create_task(self._send_mouse_position())
        elif topic == "LDrago_windows/get_device_info":
            asyncio.create_task(self._send_device_info())
    
    async def _send_mouse_position(self):
        try:
            mouse_info = await get_current_mouse_position()
            payload = convert_to_json(mouse_info)
            self.mqtt.publish("LDrago_windows/mouse_position", payload)
            
            print("\n" + "─" * 80)
            print("� MOUSE POSITION REQUEST")
            print("─" * 80)
            print(f"   Global Position: ({mouse_info['global_x']}, {mouse_info['global_y']})")
            print(f"   Monitor: {mouse_info.get('monitor_name', 'Unknown')}")
            print(f"   Topic: LDrago_windows/mouse_position")
            print("─" * 80 + "\n")
        except Exception as e:
            print(f"❌ Error sending mouse position: {e}")
    
    async def _send_device_info(self):
        try:
            if self.current_device_info:
                payload = convert_to_json(self.current_device_info)
                self.mqtt.publish("LDrago_windows/device_info", payload)
                
                monitors = self.current_device_info.get("monitors", {})
                count = monitors.get("count", 0)
                
                print("\n" + "─" * 80)
                print("📋 DEVICE INFO REQUEST")
                print("─" * 80)
                print(f"   Monitors: {count}")
                print(f"   Topic: LDrago_windows/device_info")
                print("─" * 80 + "\n")
        except Exception as e:
            print(f"❌ Error sending device info: {e}")
    
    async def monitor_device(self):
        # Initial device capture
        self.current_device_info = await extract_complete_device_info(silent=False)
        
        # Get initial mouse position
        mouse_info = await get_current_mouse_position()
        
        monitors = self.current_device_info.get("monitors", {})
        monitor_list = monitors.get("list", [])
        vd = self.current_device_info.get("virtual_desktop", {})
        layout = self.current_device_info.get("layout", {})
        bridges = self.current_device_info.get("bridge_points", [])
        
        print("\n" + "=" * 80)
        print("📤 INITIAL DEVICE INFO PUBLISHED")
        print("=" * 80)
        print(f"   Topic: LDrago_windows/device_info")
        print(f"\n   📺 Monitors: {len(monitor_list)}")
        for mon in monitor_list:
            work = mon.get("work_area", {})
            print(f"      └─ {mon['name']}: {mon['width']}x{mon['height']} at ({mon['x']}, {mon['y']})")
            print(f"         Work Area: {work.get('width')}x{work.get('height')} at ({work.get('x')}, {work.get('y')})")
        
        print(f"\n   🖼️  Virtual Desktop: {vd.get('width')}x{vd.get('height')}")
        print(f"      Boundaries: X[{vd.get('min_x')} to {vd.get('max_x')}], Y[{vd.get('min_y')} to {vd.get('max_y')}]")
        
        print(f"\n   📐 Layout: {layout.get('layout', 'unknown')}")
        for rel in layout.get("relationships", []):
            print(f"      └─ {rel['from']} → {rel['to']}: {rel.get('position', 'unknown')}, {rel.get('alignment', 'unknown')}")
        
        if bridges:
            print(f"\n   🌉 Bridge Points: {len(bridges)}")
            for bridge in bridges:
                print(f"      └─ {bridge['mon1_name']} ↔ {bridge['mon2_name']}: {bridge['orientation']}")
                print(f"         Center: {bridge.get('bridge_center')}")
                print(f"         Waypoint in {bridge['mon1_name']}: {bridge.get('mon1_waypoint')}")
                print(f"         Waypoint in {bridge['mon2_name']}: {bridge.get('mon2_waypoint')}")
        
        payload = convert_to_json(self.current_device_info)
        self.mqtt.publish("LDrago_windows/device_info", payload)
        print(f"\n   💾 Payload Size: {len(payload)} bytes")
        print("=" * 80)
        
        # Send initial mouse position
        mouse_payload = convert_to_json(mouse_info)
        self.mqtt.publish("LDrago_windows/mouse_position", mouse_payload)
        print("\n" + "─" * 80)
        print("📍 INITIAL MOUSE POSITION")
        print("─" * 80)
        print(f"   Global: ({mouse_info['global_x']}, {mouse_info['global_y']})")
        print(f"   Monitor: {mouse_info.get('monitor_name', 'Unknown')} (index {mouse_info.get('monitor_index')})")
        print(f"   Local: ({mouse_info.get('local_x')}, {mouse_info.get('local_y')})")
        print(f"   Topic: LDrago_windows/mouse_position")
        print("─" * 80)
        
        print(f"\n⏱️  Monitoring for changes (checking every {self.check_interval}s)...")
        print("   Press Ctrl+C to stop\n")
        
        while True:
            await asyncio.sleep(self.check_interval)
            
            try:
                new_info = await extract_complete_device_info(silent=True)
                
                if DeviceChangeDetector.has_changed(new_info, self.current_device_info):
                    self.current_device_info = new_info
                    
                    new_monitors = new_info.get("monitors", {}).get("list", [])
                    new_vd = new_info.get("virtual_desktop", {})
                    new_layout = new_info.get("layout", {})
                    new_bridges = new_info.get("bridge_points", [])
                    
                    print("\n" + "=" * 80)
                    print("🔄 DEVICE CONFIGURATION CHANGED!")
                    print("=" * 80)
                    print(f"   Topic: LDrago_windows/device_info_changed")
                    
                    print(f"\n   📺 Monitors: {len(new_monitors)}")
                    for mon in new_monitors:
                        work = mon.get("work_area", {})
                        print(f"      └─ {mon['name']}: {mon['width']}x{mon['height']} at ({mon['x']}, {mon['y']})")
                        print(f"         Work Area: {work.get('width')}x{work.get('height')} at ({work.get('x')}, {work.get('y')})")
                    
                    print(f"\n   🖼️  Virtual Desktop: {new_vd.get('width')}x{new_vd.get('height')}")
                    print(f"      Boundaries: X[{new_vd.get('min_x')} to {new_vd.get('max_x')}], Y[{new_vd.get('min_y')} to {new_vd.get('max_y')}]")
                    
                    print(f"\n   📐 Layout: {new_layout.get('layout', 'unknown')}")
                    for rel in new_layout.get("relationships", []):
                        print(f"      └─ {rel['from']} → {rel['to']}: {rel.get('position', 'unknown')}, {rel.get('alignment', 'unknown')}")
                    
                    if new_bridges:
                        print(f"\n   🌉 Bridge Points: {len(new_bridges)}")
                        for bridge in new_bridges:
                            print(f"      └─ {bridge['mon1_name']} ↔ {bridge['mon2_name']}: {bridge['orientation']}")
                            print(f"         Center: {bridge.get('bridge_center')}")
                            print(f"         Waypoint in {bridge['mon1_name']}: {bridge.get('mon1_waypoint')}")
                            print(f"         Waypoint in {bridge['mon2_name']}: {bridge.get('mon2_waypoint')}")
                    
                    payload = convert_to_json(new_info)
                    self.mqtt.publish("LDrago_windows/device_info_changed", payload)
                    print(f"\n   💾 Payload Size: {len(payload)} bytes")
                    print("=" * 80 + "\n")
                    
            except Exception as e:
                print(f"⚠️  Monitoring error: {e}")
    
    async def run(self):
        print("\n" + "=" * 80)
        print("🚀 DEVICE MONITOR STARTING")
        print("=" * 80)
        
        self.mqtt = MQTTHandler(self._handle_mqtt_message)
        
        if not await self.mqtt.connect():
            print("❌ MQTT connection failed")
            return
        
        print("✅ MQTT connected successfully")
        print("=" * 80)
        
        try:
            await self.monitor_device()
        except KeyboardInterrupt:
            print("\n\n" + "=" * 80)
            print("⚠️  MONITOR STOPPED BY USER")
            print("=" * 80)
        finally:
            self.mqtt.disconnect()
            print("✅ Disconnected from MQTT")


async def main():
    """
    Main automation system:
    - Device monitoring always runs (detects monitors, bridges, changes)
    - Choose execution backend: Software (PyAutoGUI) or Hardware (Pico)
    """
    print("\n" + "="*80)
    print("🚀 AUTOMATION SYSTEM - UNIFIED LAUNCHER")
    print("="*80)
    print("\n📋 SELECT EXECUTION MODE:")
    print("   1. Software Executor (PyAutoGUI - for development/testing)")
    print("   2. Hardware Executor (Pico HID - for production/BIOS)")
    print("   0. Exit")
    print("\n" + "="*80)
    print("ℹ️  Device monitoring runs automatically in both modes")
    print("="*80)
    
    choice = input("\nSelect mode: ").strip()
    
    if choice == '0':
        print("👋 Goodbye!")
        return
    
    # Start device monitor (always runs)
    print("\n" + "="*80)
    print("📡 STARTING DEVICE MONITOR")
    print("="*80)
    
    monitor = DeviceMonitor()
    
    # Initialize MQTT handler
    monitor.mqtt = MQTTHandler(monitor._handle_mqtt_message)
    
    # Connect to MQTT
    if not await monitor.mqtt.connect():
        print("❌ MQTT connection failed")
        return
    
    print("✅ MQTT connected successfully")
    
    # Load initial device info
    monitor.current_device_info = await extract_complete_device_info(silent=False)
    
    # Publish initial device info
    mouse_info = await get_current_mouse_position()
    
    monitors_info = monitor.current_device_info.get("monitors", {})
    monitor_list = monitors_info.get("list", [])
    vd = monitor.current_device_info.get("virtual_desktop", {})
    
    print("\n" + "="*80)
    print("� DEVICE INFO PUBLISHED")
    print("="*80)
    print(f"   📺 Monitors: {len(monitor_list)}")
    for mon in monitor_list:
        print(f"      └─ {mon['name']}: {mon['width']}x{mon['height']} at ({mon['x']}, {mon['y']})")
    
    print(f"\n   �️  Virtual Desktop: {vd.get('width')}x{vd.get('height')}")
    print(f"   📍 Current Mouse: ({mouse_info['global_x']}, {mouse_info['global_y']})")
    
    payload = convert_to_json(monitor.current_device_info)
    monitor.mqtt.publish("LDrago_windows/device_info", payload)
    
    mouse_payload = convert_to_json(mouse_info)
    monitor.mqtt.publish("LDrago_windows/mouse_position", mouse_payload)
    
    print("="*80)
    
    # Start executor based on choice
    if choice == '1':
        # Software executor
        print("\n" + "="*80)
        print("🖥️  STARTING SOFTWARE EXECUTOR (PyAutoGUI)")
        print("="*80)
        
        from execute_command import MQTTExecutor
        from screenshot_websocket_server import get_server_instance
        
        executor = MQTTExecutor()
        executor.executor.bridge_system.monitors = monitor_list
        executor.executor.bridge_system.virtual_desktop = vd
        executor.executor.bridge_system.bridge_points = monitor.current_device_info.get('bridge_points', [])
        
        # Start WebSocket server for screenshots
        ws_server = get_server_instance(host='0.0.0.0', port=8765)
        print("🌐 Starting WebSocket server for screenshots...")
        print(f"   URL: ws://localhost:8765")
        print(f"   (10-20x faster than MQTT!)")
        
        if await executor.start():
            print("✅ Software executor ready")
            print("="*80)
            
            # Run monitor, executor, and WebSocket server
            try:
                # Create all tasks
                monitor_task = asyncio.create_task(monitor.monitor_device())
                executor_task = asyncio.create_task(executor.run_forever())
                websocket_task = asyncio.create_task(ws_server.start())
                
                # Wait for all to complete (all run forever)
                await asyncio.gather(monitor_task, executor_task, websocket_task)
                
            except KeyboardInterrupt:
                print("\n\n" + "="*80)
                print("⚠️  SYSTEM STOPPED BY USER")
                print("="*80)
            finally:
                monitor.mqtt.disconnect()
                print("✅ Disconnected from MQTT")
        else:
            print("❌ Failed to start software executor")
            monitor.mqtt.disconnect()
    
    elif choice == '2':
        # Hardware executor
        print("\n" + "="*80)
        print("🔧 HARDWARE EXECUTOR MODE")
        print("="*80)
        print("ℹ️  Expecting Pico hardware on UART")
        print("ℹ️  Device monitor will track changes and update hardware")
        print("="*80)
        
        # Just run device monitor - hardware listens to same MQTT topics
        try:
            await monitor.monitor_device()
        except KeyboardInterrupt:
            print("\n\n" + "="*80)
            print("⚠️  MONITOR STOPPED BY USER")
            print("="*80)
        finally:
            monitor.mqtt.disconnect()
            print("✅ Disconnected from MQTT")
    
    else:
        print("❌ Invalid choice")
        monitor.mqtt.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
