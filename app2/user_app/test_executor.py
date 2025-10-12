"""
Test Client for Software Executor
Demonstrates sending commands via MQTT
"""

import asyncio
import json
import paho.mqtt.client as mqtt
import time


class TestClient:
    def __init__(self, executor_type='software'):
        self.broker = "broker.emqx.io"
        self.port = 1883
        self.username = "LDrago_windows"
        self.password = "E1s2t3e4r5"
        
        # Choose executor type
        if executor_type == 'hardware':
            # Hardware Pico executor (UNCHANGED - original topics)
            self.command_topic = "LDrago_windows/ducky_script"
            self.feedback_topic = "LDrago_windows/pico_feedback"
            self.executor_name = "Hardware (Pico - original topics)"
        else:
            # Software PyAutoGUI executor (NEW topics to avoid conflict)
            self.command_topic = "LDrago_windows/ducky_script_software"
            self.feedback_topic = "LDrago_windows/pico_feedback_software"
            self.executor_name = "Software (PyAutoGUI - separate topics)"
        
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"TestClient-{int(time.time())}")
        self.mqtt_client.username_pw_set(self.username, self.password)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.is_connected = False
    
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.is_connected = True
            print("✅ Connected to MQTT broker")
            client.subscribe(self.feedback_topic)
            print(f"📡 Subscribed to feedback: {self.feedback_topic}")
        else:
            print(f"❌ Connection failed: {reason_code}")
    
    def _on_message(self, client, userdata, msg):
        """Handle feedback from executor"""
        try:
            feedback = json.loads(msg.payload.decode())
            print(f"\n📬 FEEDBACK: {json.dumps(feedback, indent=2)}")
        except:
            print(f"\n📬 FEEDBACK: {msg.payload.decode()}")
    
    async def connect(self):
        """Connect to MQTT broker"""
        print(f"🔌 Connecting to {self.broker}...")
        self.mqtt_client.connect(self.broker, self.port, 60)
        self.mqtt_client.loop_start()
        
        timeout = 10
        while not self.is_connected and timeout > 0:
            await asyncio.sleep(0.1)
            timeout -= 0.1
        
        return self.is_connected
    
    def send_command(self, script):
        """Send command to executor"""
        payload = {
            'script': script,
            'password': self.password,
            'repeat': True
        }
        
        self.mqtt_client.publish(self.command_topic, json.dumps(payload))
        print(f"\n📤 SENT COMMAND:\n{script}\n")
    
    def disconnect(self):
        """Disconnect from MQTT"""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()


async def main():
    """Main test interface"""
    print("\n" + "="*80)
    print("🧪 TEST CLIENT - Select Executor")
    print("="*80)
    print("\n📋 Which executor to test?")
    print("   1. Software Executor (PyAutoGUI)")
    print("   2. Hardware Executor (Pico)")
    print("="*80)
    
    choice = input("\nSelect: ").strip()
    
    if choice == '1':
        executor_type = 'software'
    elif choice == '2':
        executor_type = 'hardware'
    else:
        print("❌ Invalid choice")
        return
    
    client = TestClient(executor_type=executor_type)
    
    if not await client.connect():
        print("❌ Failed to connect")
        return
    
    print("\n" + "="*80)
    print(f"🧪 TEST CLIENT - Sending to {client.executor_name}")
    print("="*80)
    print(f"   Command Topic: {client.command_topic}")
    print(f"   Feedback Topic: {client.feedback_topic}")
    print("="*80)
    
    while True:
        print("\n" + "="*80)
        print("📋 TEST MENU:")
        print("   1. Test mouse movement")
        print("   2. Test keyboard (open notepad + type)")
        print("   3. Test mouse clicks")
        print("   4. Test key combinations")
        print("   5. Send custom script")
        print("   6. Demo script (full automation)")
        print("   0. Exit")
        print("="*80)
        
        choice = input("\nSelect: ").strip()
        
        if choice == '0':
            break
        
        elif choice == '1':
            # Test mouse movement
            script = """REM Test mouse movement
DELAY 1000
MOUSE_MOVE 1920 540
DELAY 500
MOUSE_MOVE 960 540
DELAY 500
MOUSE_MOVE_REL 200 100
DELAY 500
MOUSE_MOVE_REL -200 -100"""
            client.send_command(script)
        
        elif choice == '2':
            # Test keyboard - open notepad and type
            script = """REM Open Notepad and type
GUI r
DELAY 1000
STRING notepad
ENTER
DELAY 2000
STRING Hello from Software Rubber Ducky!
ENTER
STRING This is a test of PyAutoGUI automation.
ENTER
STRING Current time: 2025-10-12"""
            client.send_command(script)
        
        elif choice == '3':
            # Test mouse clicks
            script = """REM Test mouse clicks
DELAY 1000
MOUSE_MOVE 960 540
DELAY 500
CLICK
DELAY 500
RIGHTCLICK
DELAY 500
DOUBLECLICK"""
            client.send_command(script)
        
        elif choice == '4':
            # Test key combinations
            script = """REM Test keyboard shortcuts
DELAY 1000
CTRL ALT DELETE
DELAY 2000
ESC
DELAY 1000
GUI D
DELAY 1000
GUI D"""
            client.send_command(script)
        
        elif choice == '5':
            # Custom script
            print("\n📝 Enter your DuckyScript (end with empty line):")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)
            
            script = '\n'.join(lines)
            client.send_command(script)
        
        elif choice == '6':
            # Full demo automation
            script = """REM Full automation demo
DEFAULT_DELAY 100
GUI r
DELAY 800
STRING notepad
ENTER
DELAY 2000
STRING ===================================
ENTER
STRING SOFTWARE RUBBER DUCKY DEMO
ENTER
STRING ===================================
ENTER
ENTER
STRING This automation demonstrates:
ENTER
STRING - Keyboard control
ENTER
STRING - Mouse movement
ENTER
STRING - Multi-monitor support
ENTER
STRING - Bridge-based crossing
ENTER
ENTER
STRING Position test...
DELAY 1000
MOUSE_MOVE 500 300
DELAY 500
MOUSE_MOVE 1500 800
DELAY 500
STRING Done!
ENTER
ENTER
STRING Press Alt+F4 to close in 3 seconds...
DELAY 3000
ALT F4
DELAY 500
ENTER"""
            client.send_command(script)
        
        else:
            print("❌ Invalid choice")
        
        await asyncio.sleep(0.5)
    
    client.disconnect()
    print("\n👋 Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
