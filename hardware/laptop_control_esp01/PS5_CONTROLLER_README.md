# Game Controller Bot Control via MQTT

Control your STM32 bot using any game controller (PS5, PS4, Xbox, etc.) through MQTT commands sent to ESP01.

## Features

- **Universal Controller Support**: Works with PS5, PS4, Xbox, and most USB/Bluetooth game controllers
- **Differential Drive Control**: Left stick for forward/backward, right stick X-axis for turning
- **Dual Servo Control**: 
  - S1 (Head Tilt): 20-160° controlled by L1/R1 or D-pad
  - S2 (Head Up/Down): 0-110° controlled by right stick Y-axis
- **Multiple Speed Modes**: Normal, Turbo, and Slow modes for precise control
- **Real-time MQTT Updates**: 20Hz update rate for smooth control
- **Dead Zone Handling**: Prevents drift from stick input noise
- **Auto-stop on Exit**: Safely stops motors when exiting

## Hardware Setup

```
Game Controller (USB/Bluetooth)
        ↓
    Laptop (Python + pygame)
        ↓
    MQTT (broker.emqx.io)
        ↓
    ESP01 (WiFi → MQTT)
        ↓
    STM32 (UART)
        ↓
    Bot Motors & Servos
```

## Installation

### 1. Install Python Dependencies

```bash
cd automation-hardware/hardware/laptop_control_esp01
pip install -r requirements.txt
```

Or manually:
```bash
pip install pygame paho-mqtt
```

### 2. Connect Your Controller

**PS5/PS4 Controller via Bluetooth (Windows):**
1. Put controller in pairing mode: Hold PS button + Share button for 3 seconds (light bar will flash)
2. Go to Settings → Bluetooth & devices → Add device
3. Select "Wireless Controller"

**PS5/PS4 Controller via Bluetooth (Linux):**
1. Put controller in pairing mode
2. Use Bluetooth manager or:
   ```bash
   bluetoothctl
   scan on
   pair <MAC_ADDRESS>
   connect <MAC_ADDRESS>
   ```

**Xbox Controller:**
- Connect via USB cable (plug and play)
- Or use Xbox Wireless Adapter
- Or Bluetooth (Xbox One S/X controllers and newer)

**Any USB Controller:**
- Just plug in via USB - pygame will detect it automatically!

### 3. Set Control Password (Optional)

Set the `BOT_PASSWORD` environment variable:

**Windows PowerShell:**
```powershell
$env:BOT_PASSWORD = "E1s2t3e4r5"
```

**Linux/Mac:**
```bash
export BOT_PASSWORD="E1s2t3e4r5"
```

Or edit the script directly (line 26):
```python
BOT_PASSWORD = "E1s2t3e4r5"  # Your password here
```

## Usage

### Run the Controller

```bash
python ps5_bot_controller.py
```

### Controller Mapping

| Input | PS5 | Xbox | Bot Response |
|-------|-----|------|--------------|
| **Left Stick ↑/↓** | Left Stick | Left Stick | Both motors move (L & R) |
| **Right Stick ←/→** | Right Stick X | Right Stick X | Differential motor speed |
| **Right Stick ↑/↓** | Right Stick Y | Right Stick Y | Servo S2 (0-110°) |
| **Button 4 (L1/LB)** | L1 | LB | Tilt Head Left (S1--) |
| **Button 5 (R1/RB)** | R1 | RB | Tilt Head Right (S1++) |
| **D-pad ←/→** | D-pad | D-pad | Tilt Head (fast) |
| **Button 3** | △ Triangle | Y | Center Servos (S1=90°, S2=55°) |
| **Button 1** | ○ Circle | B | Emergency Stop (L=0, R=0) |
| **Button 0** | ✕ Cross | A | Turbo Mode (1.5x speed) |
| **Button 2** | □ Square | X | Slow Mode (0.5x speed) |
| **Button 9** | Options | Start | Exit Program |

## MQTT Command Format

The script sends commands to `LDrago_windows/ducky_script`:

```json
{
  "password": "E1s2t3e4r5",
  "L": 150,
  "R": 150,
  "S1": 90,
  "S2": 55
}
```

**Fields:**
- `password`: Authentication password (from ESP01 config)
- `L`: Left motor speed (0-255)
- `R`: Right motor speed (0-255)
- `S1`: Servo 1 angle (20-160°, head tilt)
- `S2`: Servo 2 angle (0-110°, head up/down)

## Configuration

Edit these values in `ps5_bot_controller.py`:

```python
# MQTT Settings
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "LDrago_windows/ducky_script"
BOT_PASSWORD = "E1s2t3e4r5"

# Servo Limits
S1_MIN = 20   # Head tilt min
S1_MAX = 160  # Head tilt max
S2_MIN = 0    # Head up/down min
S2_MAX = 110  # Head up/down max

# Motor Limits
MOTOR_MIN = 0
MOTOR_MAX = 255

# Control Sensitivity
STICK_DEADZONE = 0.15  # Ignore small movements
UPDATE_RATE = 20       # Commands per second (Hz)

# Speed Modes
MODE_TURBO = 1.5   # Turbo multiplier
MODE_SLOW = 0.5    # Slow multiplier
```

## Troubleshooting

### Controller Not Detected

**Error: `No game controller found!`**

**Solutions:**
1. **Check connection**:
   - USB: Make sure cable is plugged in properly
   - Bluetooth: Verify controller is paired and connected
2. **Test controller detection**:
   ```bash
   python -c "import pygame; pygame.init(); pygame.joystick.init(); print(f'Controllers: {pygame.joystick.get_count()}')"
   ```
3. **Windows**: Install Xbox controller drivers if needed
4. **Linux**: May need additional permissions:
   ```bash
   sudo usermod -a -G input $USER
   # Log out and back in
   ```
5. **Linux alternative**: Run with sudo:
   ```bash
   sudo python ps5_bot_controller.py
   ```

### MQTT Connection Failed

**Error: `MQTT connection failed`**

**Solutions:**
1. Check internet connection
2. Verify MQTT broker is accessible:
   ```bash
   ping broker.emqx.io
   ```
3. Check firewall isn't blocking port 1883
4. Try alternative broker:
   ```python
   MQTT_BROKER = "test.mosquitto.org"
   ```

### Bot Not Responding

**Error: Commands sent but bot doesn't move**

**Solutions:**
1. Check ESP01 serial monitor (115200 baud):
   - Should show: `Message received on topic: LDrago_windows/ducky_script`
   - If shows `AUTHENTICATION FAILED`, password is wrong
2. Verify ESP01 is connected to WiFi and MQTT
3. Check STM32 is receiving UART commands from ESP01
4. Verify bot power supply

### Invalid Password

**Error: `AUTHENTICATION FAILED: Invalid control password`**

**Solutions:**
1. Set correct password in script or environment:
   ```python
   BOT_PASSWORD = "your_password_here"
   ```
2. Or use ESP01 web config to set password:
   - Connect to `LaptopControl_Config` WiFi
   - Go to http://192.168.4.1
   - Set control password
3. Default password is `1234` (not `E1s2t3e4r5`)

## Advanced Usage

### Custom Control Mapping

Edit the `update_from_controller()` method:

```python
def update_from_controller(self, ds):
    state = ds.state
    
    # Example: Use triggers for speed control
    if state.R2 > 0:  # R2 trigger for forward
        forward_speed = int(state.R2 * MOTOR_MAX)
        self.L = forward_speed
        self.R = forward_speed
```

### Add Haptic Feedback

```python
# In update_from_controller() method
if state.circle:  # Stop pressed
    ds.setTriggerEffect(pydualsense.TriggerModes.Rigid)
    ds.light.setColorI(255, 0, 0)  # Red light
```

### Multiple Bot Control

Change topic per bot:
```python
MQTT_TOPIC = "Bot1/control"  # Bot 1
MQTT_TOPIC = "Bot2/control"  # Bot 2
```

## Performance

- **Update Rate**: 20Hz (50ms interval)
- **MQTT QoS**: 0 (fire and forget for low latency)
- **Latency**: ~50-100ms (controller → MQTT → ESP01 → STM32)
- **Dead Zone**: 15% (prevents stick drift)

## Safety Features

1. **Auto-stop on Exit**: Motors stop when program exits
2. **Emergency Stop**: Circle button immediately stops motors
3. **Dead Zone**: Prevents accidental movement from stick drift
4. **Connection Check**: Won't send commands if MQTT disconnected
5. **Rate Limiting**: Max 20 commands/second prevents command flooding

## Dependencies

- **pygame**: Universal game controller interface (PS5, PS4, Xbox, etc.)
- **paho-mqtt**: MQTT client library
- **Python 3.7+**: Required for script execution

## License

MIT License - Use freely for personal and commercial projects

## Credits

- ESP01 MQTT bridge by Ester-D-Kate
- STM32 bot control logic
- PyDualSense library for PS5 controller support
