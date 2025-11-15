"""
PS5 Controller Bot Control via MQTT
Controls bot wheels (L, R) and servos (S1, S2) using PS5/PS4/Xbox controller
Sends commands to ESP01 via MQTT for STM32 bot control

Requirements:
    pip install pygame paho-mqtt pyautogui

Controller Mapping:
    Left Stick Y-axis: Forward/Backward (L & R motors)
    Right Stick X-axis: Turning (differential L & R)
    Right Stick Y-axis: Servo S2 (head up/down, 0-110°)
    Button 4/5 (L1/R1): Servo S1 (head tilt, 20-160°)
    Button 0 (Cross/A): Turbo mode
    Button 1 (Circle/B): Stop all motors
    Button 2 (Square/X): Slow mode
    Button 3 (Triangle/Y): Center servos
    Button 9 (Options/Start): Exit program
"""

import time
import json
import logging
import pygame
import paho.mqtt.client as mqtt
import sys
import os

# ===== CONFIGURATION =====
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "LDrago_windows/ducky_script"
BOT_PASSWORD = os.getenv("BOT_PASSWORD", "E1s2t3e4r5")  # Change to your password

# Servo limits (from main.cpp logic)
S1_MIN = 20   # Head tilt minimum
S1_MAX = 160  # Head tilt maximum
S2_MIN = 0    # Head up/down minimum
S2_MAX = 110  # Head up/down maximum

# Motor speed limits
MOTOR_MIN = 0
MOTOR_MAX = 255

# Control modes
MODE_NORMAL = 1.0
MODE_TURBO = 1.5
MODE_SLOW = 0.5

# Dead zones (ignore small stick movements)
STICK_DEADZONE = 0.15

# Update rate (Hz)
UPDATE_RATE = 20  # 20 updates per second
UPDATE_INTERVAL = 1.0 / UPDATE_RATE

# ===== LOGGING SETUP =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== MQTT CLIENT =====
mqtt_client = None
mqtt_connected = False

def on_mqtt_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        logger.info("✅ Connected to MQTT broker")
        mqtt_connected = True
    else:
        logger.error(f"❌ MQTT connection failed with code: {rc}")
        mqtt_connected = False

def on_mqtt_disconnect(client, userdata, rc):
    global mqtt_connected
    logger.warning(f"⚠️ Disconnected from MQTT broker (code: {rc})")
    mqtt_connected = False

def setup_mqtt():
    """Initialize MQTT connection"""
    global mqtt_client
    
    mqtt_client = mqtt.Client(client_id=f"PS5_BotController_{int(time.time())}")
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_disconnect = on_mqtt_disconnect
    
    try:
        logger.info(f"Connecting to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        
        # Wait for connection
        timeout = 10
        while not mqtt_connected and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5
        
        if not mqtt_connected:
            logger.error("MQTT connection timeout")
            return False
        
        return True
    
    except Exception as e:
        logger.error(f"MQTT setup error: {e}")
        return False

# ===== BOT CONTROL CLASS =====
class BotController:
    def __init__(self):
        self.L = 0  # Left motor
        self.R = 0  # Right motor
        self.S1 = 90  # Servo 1 (head tilt) - center
        self.S2 = 55  # Servo 2 (head up/down) - center
        self.speed_mode = MODE_NORMAL
        self.last_command = {}
        self.last_update_time = 0
        
    def clamp(self, value, min_val, max_val):
        """Clamp value between min and max"""
        return max(min_val, min(max_val, value))
    
    def apply_deadzone(self, value, deadzone=STICK_DEADZONE):
        """Apply deadzone to controller input"""
        if abs(value) < deadzone:
            return 0.0
        # Scale the remaining range
        sign = 1 if value > 0 else -1
        return sign * (abs(value) - deadzone) / (1.0 - deadzone)
    
    def map_stick_to_motor(self, stick_value):
        """Map stick value (-1 to 1) to motor speed (0 to 255)"""
        # Apply deadzone
        stick_value = self.apply_deadzone(stick_value)
        
        # Apply speed mode
        stick_value *= self.speed_mode
        
        # Map to motor range
        if stick_value > 0:
            return int(self.clamp(stick_value * MOTOR_MAX, 0, MOTOR_MAX))
        elif stick_value < 0:
            return -int(self.clamp(abs(stick_value) * MOTOR_MAX, 0, MOTOR_MAX))
        return 0
    
    def map_stick_to_servo(self, stick_value, min_val, max_val):
        """Map stick value (-1 to 1) to servo angle"""
        # Apply deadzone
        stick_value = self.apply_deadzone(stick_value, deadzone=0.1)
        
        # Map to servo range
        mid_val = (min_val + max_val) / 2
        range_val = (max_val - min_val) / 2
        
        angle = mid_val + (stick_value * range_val)
        return int(self.clamp(angle, min_val, max_val))
    
    def update_from_controller(self, joystick):
        """Update bot state from game controller using pygame"""
        # ===== MOTOR CONTROL =====
        # Left stick Y-axis: Forward/Backward (axis 1, inverted)
        left_y = -joystick.get_axis(1)  # Invert so up is positive
        
        # Right stick X-axis: Turning (axis 2 or 3 depending on controller)
        try:
            right_x = joystick.get_axis(2)  # Try axis 2 first (PS controllers)
        except:
            right_x = joystick.get_axis(3)  # Xbox controllers
        
        # Calculate differential drive
        forward_speed = self.map_stick_to_motor(left_y)
        turn_speed = self.map_stick_to_motor(right_x)
        
        # Differential steering
        self.L = self.clamp(forward_speed + turn_speed, -MOTOR_MAX, MOTOR_MAX)
        self.R = self.clamp(forward_speed - turn_speed, -MOTOR_MAX, MOTOR_MAX)
        
        # Handle negative values (reverse direction)
        if self.L < 0:
            self.L = 0  # Stop if reverse (or implement reverse logic)
        if self.R < 0:
            self.R = 0
        
        # ===== SERVO CONTROL =====
        # Right stick Y-axis: Servo S2 (head up/down)
        try:
            right_y = -joystick.get_axis(3)  # PS controllers axis 3
        except:
            right_y = -joystick.get_axis(4)  # Xbox controllers axis 4
        
        self.S2 = self.map_stick_to_servo(right_y, S2_MIN, S2_MAX)
        
        # L1/R1 buttons: Servo S1 (head tilt)
        # Button 4 = L1/LB, Button 5 = R1/RB
        if joystick.get_button(4):  # L1/LB - Tilt head left
            self.S1 = max(S1_MIN, self.S1 - 3)
        elif joystick.get_button(5):  # R1/RB - Tilt head right
            self.S1 = min(S1_MAX, self.S1 + 3)
        
        # D-pad for bigger servo movements (hat)
        hat = joystick.get_hat(0)
        if hat[0] == -1:  # D-pad left
            self.S1 = max(S1_MIN, self.S1 - 10)
        elif hat[0] == 1:  # D-pad right
            self.S1 = min(S1_MAX, self.S1 + 10)
        
        # ===== BUTTON ACTIONS =====
        # Button 3 = Triangle/Y: Center servos
        if joystick.get_button(3):
            self.S1 = 90
            self.S2 = 55
            logger.info("🎯 Servos centered")
        
        # Button 1 = Circle/B: Stop all motors
        if joystick.get_button(1):
            self.L = 0
            self.R = 0
            logger.info("🛑 Motors stopped")
        
        # Button 0 = Cross/A: Turbo mode
        if joystick.get_button(0):
            self.speed_mode = MODE_TURBO
        # Button 2 = Square/X: Slow mode
        elif joystick.get_button(2):
            self.speed_mode = MODE_SLOW
        else:
            self.speed_mode = MODE_NORMAL
    
    def send_mqtt_command(self):
        """Send current bot state to MQTT"""
        if not mqtt_connected:
            logger.warning("⚠️ MQTT not connected, skipping command")
            return False
        
        # Check update rate limit
        current_time = time.time()
        if current_time - self.last_update_time < UPDATE_INTERVAL:
            return False
        self.last_update_time = current_time
        
        # Build command
        command = {
            "password": BOT_PASSWORD,
            "L": int(self.L),
            "R": int(self.R),
            "S1": int(self.S1),
            "S2": int(self.S2)
        }
        
        # Only send if changed
        if command == self.last_command:
            return False
        
        self.last_command = command.copy()
        
        # Send to MQTT
        try:
            payload = json.dumps(command)
            result = mqtt_client.publish(MQTT_TOPIC, payload, qos=0)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"📡 Sent: L={self.L} R={self.R} S1={self.S1} S2={self.S2}")
                return True
            else:
                logger.warning(f"⚠️ MQTT publish failed: {result.rc}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Error sending MQTT: {e}")
            return False
    
    def display_status(self):
        """Display current status on console"""
        mode_str = "🚀 TURBO" if self.speed_mode == MODE_TURBO else "🐢 SLOW" if self.speed_mode == MODE_SLOW else "⚙️ NORMAL"
        
        print(f"\r{mode_str} | Motors: L={self.L:3d} R={self.R:3d} | Servos: S1={self.S1:3d}° S2={self.S2:3d}°", end="", flush=True)

# ===== MAIN PROGRAM =====
def main():
    logger.info("=" * 60)
    logger.info("Game Controller Bot Control via MQTT")
    logger.info("=" * 60)
    
    # Setup MQTT
    if not setup_mqtt():
        logger.error("Failed to connect to MQTT broker. Exiting.")
        return
    
    # Initialize pygame and controller
    try:
        logger.info("Initializing pygame...")
        pygame.init()
        pygame.joystick.init()
        
        # Check for connected controllers
        joystick_count = pygame.joystick.get_count()
        if joystick_count == 0:
            logger.error("❌ No game controller found!")
            logger.info("Make sure:")
            logger.info("  1. Controller is connected (USB or Bluetooth)")
            logger.info("  2. Controller is turned on")
            logger.info("  3. Drivers are installed")
            return
        
        # Use first controller
        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        
        logger.info(f"✅ Controller connected: {joystick.get_name()}")
        logger.info(f"   Axes: {joystick.get_numaxes()}")
        logger.info(f"   Buttons: {joystick.get_numbuttons()}")
        logger.info(f"   Hats: {joystick.get_numhats()}")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize controller: {e}")
        logger.info("Make sure pygame is installed: pip install pygame")
        return
    
    # Initialize bot controller
    bot = BotController()
    
    logger.info("\n" + "=" * 60)
    logger.info("CONTROLS:")
    logger.info("  Left Stick Y-axis: Forward/Backward")
    logger.info("  Right Stick X-axis: Turn Left/Right")
    logger.info("  Right Stick Y-axis: Head Up/Down (S2)")
    logger.info("  L1/R1 (Buttons 4/5): Head Tilt Left/Right (S1)")
    logger.info("  D-pad: Head Tilt (fast)")
    logger.info("  Button 3 (Triangle/Y): Center servos")
    logger.info("  Button 1 (Circle/B): Stop motors")
    logger.info("  Button 0 (Cross/A): Turbo mode")
    logger.info("  Button 2 (Square/X): Slow mode")
    logger.info("  Button 9 (Options/Start): Exit")
    logger.info("=" * 60)
    logger.info("\nController active! Press Button 9 (Options/Start) to exit.\n")
    
    try:
        running = True
        while running:
            # Process pygame events (required for controller input)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 9:  # Options/Start button
                        logger.info("\n\n🛑 Exit button pressed. Exiting...")
                        running = False
            
            # Read controller state
            bot.update_from_controller(joystick)
            
            # Send to MQTT
            bot.send_mqtt_command()
            
            # Display status
            bot.display_status()
            
            # Small delay to prevent CPU overload
            time.sleep(0.01)
    
    except KeyboardInterrupt:
        logger.info("\n\n⚠️ Ctrl+C pressed. Stopping bot...")
    
    except Exception as e:
        logger.error(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        logger.info("\n\nCleaning up...")
        
        # Stop motors before exit
        bot.L = 0
        bot.R = 0
        bot.send_mqtt_command()
        time.sleep(0.2)
        
        # Close controller
        try:
            joystick.quit()
            pygame.joystick.quit()
            pygame.quit()
            logger.info("✅ Controller closed")
        except:
            pass
        
        # Close MQTT
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
            logger.info("✅ MQTT disconnected")
        
        logger.info("👋 Goodbye!")

if __name__ == "__main__":
    main()
