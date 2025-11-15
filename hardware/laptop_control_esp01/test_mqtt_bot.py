"""
Test MQTT Bot Control
Simple test script to verify MQTT connection and send test commands to the bot
Run this BEFORE using PS5 controller to verify your setup
"""

import paho.mqtt.client as mqtt
import json
import time
import sys

# Configuration
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "LDrago_windows/ducky_script"
BOT_PASSWORD = "E1s2t3e4r5"  # Change to your password

# Test commands
TEST_COMMANDS = [
    {
        "name": "Stop (Motors Off)",
        "command": {"password": BOT_PASSWORD, "L": 0, "R": 0, "S1": 90, "S2": 55}
    },
    {
        "name": "Forward Slow",
        "command": {"password": BOT_PASSWORD, "L": 100, "R": 100, "S1": 90, "S2": 55}
    },
    {
        "name": "Turn Right",
        "command": {"password": BOT_PASSWORD, "L": 150, "R": 50, "S1": 90, "S2": 55}
    },
    {
        "name": "Turn Left",
        "command": {"password": BOT_PASSWORD, "L": 50, "R": 150, "S1": 90, "S2": 55}
    },
    {
        "name": "Head Tilt Right",
        "command": {"password": BOT_PASSWORD, "L": 0, "R": 0, "S1": 140, "S2": 55}
    },
    {
        "name": "Head Tilt Left",
        "command": {"password": BOT_PASSWORD, "L": 0, "R": 0, "S1": 40, "S2": 55}
    },
    {
        "name": "Head Look Up",
        "command": {"password": BOT_PASSWORD, "L": 0, "R": 0, "S1": 90, "S2": 100}
    },
    {
        "name": "Head Look Down",
        "command": {"password": BOT_PASSWORD, "L": 0, "R": 0, "S1": 90, "S2": 10}
    },
    {
        "name": "Center All (Default)",
        "command": {"password": BOT_PASSWORD, "L": 0, "R": 0, "S1": 90, "S2": 55}
    }
]

connected = False

def on_connect(client, userdata, flags, rc):
    global connected
    if rc == 0:
        print("✅ Connected to MQTT broker")
        connected = True
    else:
        print(f"❌ Connection failed with code: {rc}")
        connected = False

def on_publish(client, userdata, mid):
    print(f"  📤 Message published (mid: {mid})")

def send_command(client, cmd_name, command):
    """Send a single command to MQTT"""
    print(f"\n🤖 Sending: {cmd_name}")
    print(f"   Command: {json.dumps(command, indent=2)}")
    
    payload = json.dumps(command)
    result = client.publish(MQTT_TOPIC, payload, qos=0)
    
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print("  ✅ Command sent successfully")
        return True
    else:
        print(f"  ❌ Failed to send command: {result.rc}")
        return False

def main():
    print("=" * 60)
    print("MQTT Bot Control Test")
    print("=" * 60)
    print(f"Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Topic: {MQTT_TOPIC}")
    print(f"Password: {BOT_PASSWORD}")
    print("=" * 60)
    
    # Create MQTT client
    client = mqtt.Client(client_id=f"BotTestClient_{int(time.time())}")
    client.on_connect = on_connect
    client.on_publish = on_publish
    
    # Connect to broker
    print("\n⏳ Connecting to MQTT broker...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        
        # Wait for connection
        timeout = 10
        while not connected and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5
        
        if not connected:
            print("❌ Connection timeout")
            return
        
        print("\n" + "=" * 60)
        print("INTERACTIVE TEST MODE")
        print("=" * 60)
        print("\nAvailable commands:")
        for i, test in enumerate(TEST_COMMANDS, 1):
            print(f"  {i}. {test['name']}")
        print("  0. Exit")
        print("  a. Auto sequence (all commands)")
        print("=" * 60)
        
        while True:
            try:
                choice = input("\nEnter command number (0-9, a): ").strip().lower()
                
                if choice == '0':
                    print("\n🛑 Stopping bot before exit...")
                    send_command(client, "Stop", TEST_COMMANDS[0]["command"])
                    time.sleep(0.5)
                    break
                
                elif choice == 'a':
                    print("\n🚀 Running auto sequence...")
                    for test in TEST_COMMANDS:
                        send_command(client, test["name"], test["command"])
                        time.sleep(2)  # 2 seconds between commands
                    print("\n✅ Auto sequence complete")
                
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(TEST_COMMANDS):
                        test = TEST_COMMANDS[idx]
                        send_command(client, test["name"], test["command"])
                    else:
                        print("❌ Invalid command number")
                
                else:
                    print("❌ Invalid input")
            
            except KeyboardInterrupt:
                print("\n\n⚠️ Ctrl+C pressed. Stopping bot...")
                send_command(client, "Stop", TEST_COMMANDS[0]["command"])
                time.sleep(0.5)
                break
            
            except Exception as e:
                print(f"❌ Error: {e}")
    
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return
    
    finally:
        print("\n🧹 Cleaning up...")
        client.loop_stop()
        client.disconnect()
        print("👋 Goodbye!")

if __name__ == "__main__":
    main()
