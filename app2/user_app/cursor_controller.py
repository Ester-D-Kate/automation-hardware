"""
Cursor Controller - SAFE with Proper Hardware Feedback
CRITICAL: Wait for Pico execution feedback before checking position
"""

import asyncio
import json
import math
import time
from pathlib import Path
from datetime import datetime
import pyautogui

# Disable fail-safe to allow corner coordinates
pyautogui.FAILSAFE = False

from device_info import extract_complete_device_info


class MonitorManager:
    """Manages monitor information and bridge points"""
    
    def __init__(self):
        self.monitors = []
        self.virtual_desktop = {}
        self.bridge_points = []
        self.primary_monitor = None
    
    async def initialize(self):
        """Load device information"""
        device_info = await extract_complete_device_info(silent=True)
        self.monitors = device_info.get('monitors', {}).get('list', [])
        self.virtual_desktop = device_info.get('virtual_desktop', {})
        self.bridge_points = device_info.get('bridge_points', [])
        
        # Find primary monitor
        self.primary_monitor = next((m for m in self.monitors if m.get('primary')), None)
        if not self.primary_monitor:
            self.primary_monitor = max(self.monitors, key=lambda m: m['width'] * m['height'])
    
    def find_monitor_at_position(self, pos):
        """Find which monitor contains the given position"""
        x, y = pos
        for monitor in self.monitors:
            if (monitor['x'] <= x < monitor['x'] + monitor['width'] and
                monitor['y'] <= y < monitor['y'] + monitor['height']):
                return monitor
        return self.primary_monitor
    
    def is_near_edge(self, pos, monitor, threshold=100):
        """Check if position is near monitor edge"""
        x, y = pos
        
        near_left = (x - monitor['x']) < threshold
        near_right = (monitor['x'] + monitor['width'] - x) < threshold
        near_top = (y - monitor['y']) < threshold
        near_bottom = (monitor['y'] + monitor['height'] - y) < threshold
        
        return near_left or near_right or near_top or near_bottom


class HardwareInterface:
    """Handles MQTT communication with Pico hardware"""
    
    def __init__(self):
        import paho.mqtt.client as mqtt
        self.mqtt_client = mqtt.Client(client_id=f"CursorController-{int(time.time())}")
        self.mqtt_client.username_pw_set("LDrago_windows", "E1s2t3e4r5")
        self.mqtt_client.on_message = self._on_message
        self.feedback_received = False
        self.last_feedback = None
        self.is_connected = False
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                self.is_connected = True
                client.subscribe("LDrago_windows/pico_execution_done")
        
        self.mqtt_client.on_connect = on_connect
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.mqtt_client.connect("broker.emqx.io", 1883, 60)
            self.mqtt_client.loop_start()
            time.sleep(2)
            return self.is_connected
        except Exception as e:
            print(f"❌ MQTT connection failed: {e}")
            return False
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        self.feedback_received = True
        try:
            self.last_feedback = json.loads(msg.payload.decode())
        except:
            self.last_feedback = msg.payload.decode()
    
    def send_command_and_wait(self, command, timeout=2):
        """
        Send command and WAIT for Pico feedback
        Returns True if feedback received
        """
        self.feedback_received = False
        self.last_feedback = None
        
        payload = {
            "script": command,
            "password": "E1s2t3e4r5",
            "repeat": True
        }
        self.mqtt_client.publish("LDrago_windows/ducky_script", json.dumps(payload))
        
        # Wait for feedback
        start = time.time()
        while time.time() - start < timeout:
            if self.feedback_received:
                return True
            time.sleep(0.01)
        
        print(f"      ⚠️ No feedback received for: {command}")
        return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()


class SafeAdaptiveController:
    """
    SAFE controller with proper hardware feedback waiting
    """
    
    def __init__(self, hardware, monitor_manager):
        self.hardware = hardware
        self.monitor_manager = monitor_manager
        self.calibration_file = Path("safe_calibration.json")
        
        # Conservative defaults
        self.distance_to_max_hid = {
            50: 15,
            100: 25,
            200: 40,
            300: 55,
            500: 70,
        }
        
        # Performance tracking
        self.total_movements = 0
        self.successful_movements = 0
        self.overshoot_count = 0
        self.no_movement_count = 0
    
    def reset_cursor_position(self):
        """Reset cursor to safe starting position"""
        safe_x = self.monitor_manager.primary_monitor['x'] + 300
        safe_y = self.monitor_manager.primary_monitor['y'] + 300
        
        pyautogui.moveTo(safe_x, safe_y, duration=0.1)
        time.sleep(0.3)  # Extra time for pyautogui
        
        actual = pyautogui.position()
        return actual
    
    def test_hid_with_feedback(self, hid_value, expected_distance):
        """
        Test HID value with PROPER feedback waiting
        Returns (actual_distance, overshot, jumped)
        """
        before_pos = pyautogui.position()
        before_monitor = self.monitor_manager.find_monitor_at_position(before_pos)
        
        # Send command and WAIT for feedback
        feedback_received = self.hardware.send_command_and_wait(f"MOUSE_MOVE_REL {hid_value} 0", timeout=2)
        
        if not feedback_received:
            print(f"      ⚠️ No feedback for HID {hid_value}, assuming it failed")
            return 0, False, False
        
        # Small extra delay to ensure OS processed the HID input
        time.sleep(0.05)
        
        after_pos = pyautogui.position()
        after_monitor = self.monitor_manager.find_monitor_at_position(after_pos)
        
        actual_movement = abs(after_pos[0] - before_pos[0])
        monitor_jumped = (before_monitor['name'] != after_monitor['name'])
        overshot = (actual_movement > expected_distance + 15) or monitor_jumped
        
        return actual_movement, overshot, monitor_jumped
    
    def binary_search_safe_hid(self, target_distance):
        """
        Binary search with proper feedback waiting
        """
        print(f"\n   🔍 Finding safe HID for {target_distance}px...")
        
        low = 5  # Start higher since very small values unreliable
        high = 80  # Conservative max
        best_safe_hid = 5
        
        iteration = 0
        while low <= high and iteration < 10:
            iteration += 1
            mid = (low + high) // 2
            
            # Reset
            self.reset_cursor_position()
            time.sleep(0.2)
            
            # Test with feedback
            actual_movement, overshot, jumped = self.test_hid_with_feedback(mid, target_distance)
            
            print(f"      Iter {iteration}: HID={mid} → {actual_movement}px (target ≤{target_distance}px) | Jump: {jumped}")
            
            if actual_movement == 0:
                # No movement detected - command might have failed
                print(f"      ⚠️ No movement detected for HID {mid}")
                # Try a bit higher
                low = mid + 1
                continue
            
            if jumped:
                print(f"      ⚠️ MONITOR JUMP!")
                high = mid - 1
                continue
            
            if overshot or actual_movement > target_distance:
                high = mid - 1
            else:
                best_safe_hid = mid
                low = mid + 1
        
        print(f"      ✅ Safe HID for {target_distance}px = {best_safe_hid}")
        return best_safe_hid
    
    def comprehensive_calibration(self):
        """Full calibration"""
        print("\n" + "="*80)
        print("🎯 SAFE CALIBRATION with Feedback Waiting")
        print("="*80)
        
        test_distances = [50, 100, 200, 300, 500]
        
        print(f"\n📊 Testing {len(test_distances)} distances")
        input("\n⏸️  Press Enter to start...")
        
        for distance in test_distances:
            safe_hid = self.binary_search_safe_hid(distance)
            self.distance_to_max_hid[distance] = safe_hid
            time.sleep(0.5)
        
        print(f"\n📊 RESULTS:")
        for d in sorted(self.distance_to_max_hid.keys()):
            print(f"   {d}px → HID {self.distance_to_max_hid[d]}")
        
        self.save_calibration()
        print(f"\n✅ CALIBRATION COMPLETE!")
        print("="*80)
    
    def get_safe_hid_for_distance(self, distance):
        """Get safe HID with interpolation"""
        if not self.distance_to_max_hid:
            return max(5, int(distance * 0.08))
        
        distances = sorted(self.distance_to_max_hid.keys())
        
        if distance <= distances[0]:
            ratio = distance / distances[0]
            return max(5, int(self.distance_to_max_hid[distances[0]] * ratio * 0.6))
        
        if distance >= distances[-1]:
            return int(self.distance_to_max_hid[distances[-1]] * 0.6)
        
        # Interpolate
        for i in range(len(distances) - 1):
            if distances[i] <= distance <= distances[i+1]:
                d1, d2 = distances[i], distances[i+1]
                h1, h2 = self.distance_to_max_hid[d1], self.distance_to_max_hid[d2]
                
                ratio = (distance - d1) / (d2 - d1)
                interpolated = h1 + ratio * (h2 - h1)
                
                # 60% safety margin
                return max(5, int(interpolated * 0.6))
        
        return max(5, int(distance * 0.08))
    
    def safe_move_to(self, target_x, target_y, tolerance=15, max_iterations=300):
        """
        Safe movement with feedback waiting
        """
        start_time = time.time()
        start_pos = pyautogui.position()
        
        print(f"\n🎯 Safe move to ({target_x}, {target_y})")
        print(f"   Starting from ({start_pos[0]}, {start_pos[1]})")
        
        start_monitor = self.monitor_manager.find_monitor_at_position(start_pos)
        target_monitor = self.monitor_manager.find_monitor_at_position((target_x, target_y))
        
        if start_monitor['name'] != target_monitor['name']:
            print(f"   ⚠️ TARGET ON DIFFERENT MONITOR - BLOCKED")
            return False
        
        last_good_pos = start_pos
        no_move_counter = 0
        
        for iteration in range(1, max_iterations + 1):
            current_pos = pyautogui.position()
            current_monitor = self.monitor_manager.find_monitor_at_position(current_pos)
            
            # Check monitor
            if current_monitor['name'] != target_monitor['name']:
                print(f"   ⚠️ JUMPED TO DIFFERENT MONITOR! Recovering...")
                pyautogui.moveTo(last_good_pos[0], last_good_pos[1], duration=0.1)
                time.sleep(0.3)
                self.overshoot_count += 1
                continue
            
            # Distance
            dx = target_x - current_pos[0]
            dy = target_y - current_pos[1]
            distance = math.sqrt(dx**2 + dy**2)
            
            # Arrived?
            if distance <= tolerance:
                elapsed = time.time() - start_time
                total_dist = math.sqrt((current_pos[0]-start_pos[0])**2 + (current_pos[1]-start_pos[1])**2)
                speed = total_dist / elapsed if elapsed > 0 else 0
                print(f"   ✅ ARRIVED in {iteration} steps, {elapsed:.2f}s, {speed:.0f}px/s")
                self.successful_movements += 1
                self.total_movements += 1
                return True
            
            # Near edge?
            if self.monitor_manager.is_near_edge(current_pos, current_monitor, 120):
                safe_hid = min(5, self.get_safe_hid_for_distance(distance))
            else:
                safe_hid = self.get_safe_hid_for_distance(distance)
            
            # Direction
            direction_x = dx / distance
            direction_y = dy / distance
            
            hid_x = int(direction_x * safe_hid)
            hid_y = int(direction_y * safe_hid)
            
            # Minimum move
            if hid_x == 0 and hid_y == 0 and distance > tolerance:
                hid_x = 1 if dx > 0 else -1 if dx < 0 else 0
                hid_y = 1 if dy > 0 else -1 if dy < 0 else 0
            
            # Log
            if iteration % 20 == 1 or distance < 100:
                print(f"   Step {iteration}: ({current_pos[0]}, {current_pos[1]}) | {distance:.1f}px | HID: ({hid_x}, {hid_y})")
            
            # Remember position
            last_good_pos = current_pos
            
            # Execute with feedback
            before = pyautogui.position()
            feedback = self.hardware.send_command_and_wait(f"MOUSE_MOVE_REL {hid_x} {hid_y}", timeout=1.5)
            
            if not feedback:
                print(f"   ⚠️ No feedback at step {iteration}")
                no_move_counter += 1
                if no_move_counter > 10:
                    print(f"   ❌ Too many failed commands")
                    return False
                time.sleep(0.1)
                continue
            
            time.sleep(0.01)  # Small delay after feedback
            
            # Check if actually moved
            after = pyautogui.position()
            if before == after and distance > tolerance:
                no_move_counter += 1
                if no_move_counter > 10:
                    print(f"   ❌ Cursor not moving")
                    return False
            else:
                no_move_counter = 0
        
        print(f"   ⚠️ Max iterations reached")
        self.total_movements += 1
        return False
    
    def save_calibration(self):
        """Save"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'distance_to_max_hid': self.distance_to_max_hid,
            'performance': {
                'total': self.total_movements,
                'successful': self.successful_movements,
                'overshoots': self.overshoot_count
            }
        }
        with open(self.calibration_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n💾 Saved")
    
    def load_calibration(self):
        """Load"""
        if not self.calibration_file.exists():
            return False
        
        try:
            with open(self.calibration_file, 'r') as f:
                data = json.load(f)
            
            self.distance_to_max_hid = {int(k): v for k, v in data.get('distance_to_max_hid', {}).items()}
            perf = data.get('performance', {})
            self.total_movements = perf.get('total', 0)
            self.successful_movements = perf.get('successful', 0)
            self.overshoot_count = perf.get('overshoots', 0)
            
            print(f"✅ Loaded calibration: {sorted(self.distance_to_max_hid.keys())}")
            return True
        except:
            return False


class CursorController:
    """Main"""
    
    def __init__(self):
        self.monitor_manager = MonitorManager()
        self.hardware = HardwareInterface()
        self.controller = None
    
    async def initialize(self):
        print("\n" + "="*80)
        print("🚀 SAFE CURSOR CONTROLLER v2")
        print("="*80)
        
        if not self.hardware.connect():
            return False
        
        time.sleep(1)
        await self.monitor_manager.initialize()
        
        self.controller = SafeAdaptiveController(self.hardware, self.monitor_manager)
        
        if not self.controller.load_calibration():
            return False
        
        print("✅ READY")
        return True
    
    def calibrate(self):
        self.controller.comprehensive_calibration()
    
    def move_to(self, x, y):
        success = self.controller.safe_move_to(x, y)
        self.controller.save_calibration()
        return success
    
    def shutdown(self):
        self.hardware.disconnect()


async def main():
    controller = CursorController()
    
    if not await controller.initialize():
        print("\n⚠️ Running calibration...")
        input("Press Enter...")
        
        await controller.monitor_manager.initialize()
        controller.controller = SafeAdaptiveController(controller.hardware, controller.monitor_manager)
        controller.calibrate()
        
        controller.shutdown()
        return
    
    while True:
        print("\n" + "="*80)
        print("MENU")
        print("1. Re-calibrate")
        print("2. Test (1500, 800)")
        print("3. Custom")
        print("4. Stats")
        print("0. Exit")
        print("="*80)
        
        choice = input("\nSelect: ").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            controller.calibrate()
        elif choice == '2':
            controller.move_to(1500, 800)
        elif choice == '3':
            try:
                coords = input("(x,y): ").strip()
                x, y = map(int, coords.split(','))
                controller.move_to(x, y)
            except:
                print("❌ Invalid")
        elif choice == '4':
            c = controller.controller
            print(f"\nTotal: {c.total_movements} | Success: {c.successful_movements} | Overshoots: {c.overshoot_count}")
        
        input("\nPress Enter...")
    
    controller.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
