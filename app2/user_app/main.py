"""
Main automation script for device monitoring and MQTT integration
"""

import asyncio
import json
from mqtt_handler import MQTTHandler
from device_info import extract_complete_device_info, get_current_mouse_position
from screenshot_websocket_client import CloudWebSocketClient
from constants import (
    CLOUD_AI_ENABLED,
    CLOUD_AI_URL,
    MONITOR_CHECK_INTERVAL
)


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
        """Check if ANY device configuration changed"""
        if not old_info:
            return True
        
        new_monitors = new_info.get("monitors", {}).get("list", [])
        old_monitors = old_info.get("monitors", {}).get("list", [])
        
        if len(new_monitors) != len(old_monitors):
            return True
        
        for new_mon, old_mon in zip(new_monitors, old_monitors):
            if (new_mon.get("x") != old_mon.get("x") or
                new_mon.get("y") != old_mon.get("y") or
                new_mon.get("width") != old_mon.get("width") or
                new_mon.get("height") != old_mon.get("height")):
                return True
        
        return False


class DeviceMonitor:
    """Monitors device changes and publishes via MQTT"""
    
    def __init__(self):
        self.mqtt = MQTTHandler()
        self.current_device_info = {}
        self.last_published_info = {}
        self.publish_interval = MONITOR_CHECK_INTERVAL
        self.loop = None
        self.mqtt.on_message_callback = self._handle_mqtt_message
    
    async def start(self):
        """Initialize MQTT connection"""
        if self.loop is None:
            self.loop = asyncio.get_running_loop()
        
        print("\n" + "="*80)
        print("📡 STARTING DEVICE MONITOR")
        print("="*80)
        
        if not await self.mqtt.connect():
            print("❌ Failed to connect to MQTT")
            return False
        
        print("✅ MQTT connected successfully")
        return True
    
    def _handle_mqtt_message(self, topic, payload):
        """Handle incoming MQTT messages"""
        if topic == "LDrago_windows/get_mouse_position":
            asyncio.run_coroutine_threadsafe(self._send_mouse_position(), self.loop)
        elif topic == "LDrago_windows/get_device_info":
            asyncio.run_coroutine_threadsafe(self._send_device_info(), self.loop)
        elif topic == "LDrago_windows/get_applications":
            asyncio.run_coroutine_threadsafe(self._send_applications_info(), self.loop)
    
    async def _send_mouse_position(self):
        """Send current mouse position"""
        try:
            mouse_info = await get_current_mouse_position()
            payload = convert_to_json(mouse_info)
            self.mqtt.publish("LDrago_windows/mouse_position", payload)
            print(f"\n🖱️  Mouse position sent")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    async def _send_device_info(self):
        """Send device info"""
        try:
            payload = convert_to_json(self.current_device_info)
            self.mqtt.publish("LDrago_windows/device_info", payload)
            print(f"\n🖥️  Device info sent")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    async def _send_applications_info(self):
        """Send applications info"""
        try:
            from device_info import get_applications_info
            monitors_info = self.current_device_info.get("monitors", {})
            apps_info = await get_applications_info(monitors_info)
            
            payload = convert_to_json(apps_info)
            self.mqtt.publish("LDrago_windows/applications_info", payload)
            print(f"\n🪟 Applications info sent")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    async def _publish_device_info(self, info):
        """Publish device info via MQTT"""
        payload = convert_to_json(info)
        self.mqtt.publish("LDrago_windows/device_info", payload)
        self.last_published_info = info.copy()
        
        print("\n" + "="*80)
        print("📤 DEVICE INFO PUBLISHED")
        print("="*80)
        
        monitors = info.get("monitors", {}).get("list", [])
        print(f"   📺 Monitors: {len(monitors)}")
        for mon in monitors:
            print(f"      └─ {mon['name']}: {mon['width']}x{mon['height']} at ({mon['x']}, {mon['y']})")
        
        vd = info.get("virtual_desktop", {})
        print(f"\n   🖼️  Virtual Desktop: {vd.get('width', 0)}x{vd.get('height', 0)}")
        
        bridges = info.get("bridge_points", [])
        if bridges:
            print(f"\n   🌉 Bridge Points: {len(bridges)}")
        
        print("="*80)
    
    async def monitor_device(self):
        """Main monitoring loop"""
        self.current_device_info = await extract_complete_device_info(silent=True)
        await self._publish_device_info(self.current_device_info)
        
        print(f"\n⏱️  Monitoring every {self.publish_interval}s...\n")
        
        while True:
            await asyncio.sleep(self.publish_interval)
            new_info = await extract_complete_device_info(silent=True)
            
            if DeviceChangeDetector.has_changed(new_info, self.last_published_info):
                print("📢 Device configuration changed!")
                self.current_device_info = new_info
                await self._publish_device_info(new_info)


async def main():
    """Main entry point"""
    print("\n" + "="*80)
    print("🚀 RUBBER DUCKY AUTOMATION SYSTEM")
    print("="*80)
    print("\n📋 SELECT EXECUTION MODE:")
    print("   1. Software Executor (PyAutoGUI - for development/testing)")
    print("   2. Hardware Executor (Pico HID - for production/BIOS)")
    print("   0. Exit")
    print("\n" + "="*80)
    print("ℹ️  Device monitoring runs automatically in both modes")
    if CLOUD_AI_ENABLED:
        print("🌐 Cloud AI Backend: ENABLED")
        print(f"   URL: {CLOUD_AI_URL}")
    print("="*80)
    print()
    
    choice = input("Select mode: ").strip()
    
    if choice == '0':
        print("\n👋 Goodbye!")
        return
    
    if choice not in ['1', '2']:
        print("\n❌ Invalid choice")
        return
    
    # Create monitor
    monitor = DeviceMonitor()
    monitor.loop = asyncio.get_running_loop()
    
    if not await monitor.start():
        return
    
    # Get device info
    device_info = await extract_complete_device_info(silent=True)
    monitor.current_device_info = device_info
    monitor_list = device_info.get("monitors", {}).get("list", [])
    vd = device_info.get("virtual_desktop", {})
    
    # Initialize Cloud AI Client
    cloud_client = None
    if CLOUD_AI_ENABLED:
        cloud_client = CloudWebSocketClient(CLOUD_AI_URL, monitor)
        asyncio.create_task(cloud_client.connect())
    
    if choice == '1':
        # SOFTWARE EXECUTOR
        print("\n" + "="*80)
        print("🖥️  STARTING SOFTWARE EXECUTOR (PyAutoGUI)")
        print("="*80)
        
        from execute_command import MQTTExecutor
        
        executor = MQTTExecutor(cloud_client)
        executor.executor.bridge_system.monitors = monitor_list
        executor.executor.bridge_system.virtual_desktop = vd
        executor.executor.bridge_system.bridge_points = device_info.get('bridge_points', [])
        
        if await executor.start():
            print("✅ Software executor ready")
            print("="*80)
            
            try:
                tasks = [
                    asyncio.create_task(monitor.monitor_device()),
                    asyncio.create_task(executor.run_forever())
                ]
                
                if cloud_client:
                    tasks.append(asyncio.create_task(cloud_client.receive_commands(executor.executor)))
                
                await asyncio.gather(*tasks)
                
            except KeyboardInterrupt:
                print("\n\n⚠️  STOPPED")
            finally:
                monitor.mqtt.disconnect()
        else:
            print("❌ Failed to start software executor")
            monitor.mqtt.disconnect()
    
    elif choice == '2':
        # HARDWARE EXECUTOR
        print("\n" + "="*80)
        print("⚙️  STARTING HARDWARE EXECUTOR (Rubber Ducky / Pico HID)")
        print("="*80)
        print("\n📌 HARDWARE MODE FEATURES:")
        print("   ✅ True HID emulation (works in BIOS)")
        print("   ✅ No software detection")
        print("   ✅ OS-independent")
        print("   ✅ Maximum compatibility")
        print("\n⚠️  REQUIREMENTS:")
        print("   • Raspberry Pi Pico or compatible board")
        print("   • CircuitPython firmware installed")
        print("   • USB connection to target computer")
        print("="*80)
        
        try:
            from cursor_controller import CursorController
            
            controller = CursorController()
            controller.bridge_system.monitors = monitor_list
            controller.bridge_system.virtual_desktop = vd
            controller.bridge_system.bridge_points = device_info.get('bridge_points', [])
            
            if await controller.start():
                print("✅ Hardware executor ready")
                print("="*80)
                
                try:
                    tasks = [asyncio.create_task(monitor.monitor_device())]
                    
                    if cloud_client:
                        tasks.append(asyncio.create_task(cloud_client.receive_commands(controller)))
                    
                    await asyncio.gather(*tasks)
                    
                except KeyboardInterrupt:
                    print("\n\n⚠️  STOPPED")
                finally:
                    monitor.mqtt.disconnect()
            else:
                print("❌ Failed to start hardware executor")
                monitor.mqtt.disconnect()
                
        except ImportError as e:
            print(f"\n❌ Hardware executor not available: {e}")
            print("\n💡 To use hardware mode:")
            print("   1. Ensure cursor_controller.py is present")
            print("   2. Connect Raspberry Pi Pico")
            print("   3. Install required dependencies")
            monitor.mqtt.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Shutdown")
