# Quick Start Guide - Game Controller Bot Control

## Step-by-Step Setup

### 1️⃣ Install Dependencies
```bash
cd automation-hardware/hardware/laptop_control_esp01
pip install pygame paho-mqtt
```

### 2️⃣ Connect Your Controller

**Option A: USB Controller (Easiest)**
- Just plug in your controller via USB cable
- Works with PS4, PS5, Xbox, and most USB controllers
- No pairing required!

**Option B: Bluetooth Controller**
- PS5/PS4: Hold PS + Share buttons until light flashes
- Xbox: Press pairing button on controller
- Pair via Windows Bluetooth settings

### 3️⃣ Test Controller Detection
```bash
python test_controller.py
```

**Expected output:**
```
✅ Pygame initialized
📊 Controllers found: 1

Controller 0:
  Name: Wireless Controller
  Axes: 6
  Buttons: 14
  Hats (D-pads): 1
```

If you see "No controllers detected", check connection!

### 4️⃣ Set Bot Password (Optional)
```powershell
# Windows PowerShell
$env:BOT_PASSWORD = "E1s2t3e4r5"

# Or edit ps5_bot_controller.py line 26:
BOT_PASSWORD = "E1s2t3e4r5"
```

### 5️⃣ Run Bot Controller
```bash
python ps5_bot_controller.py
```

**Expected output:**
```
✅ Connected to MQTT broker
✅ Controller connected: Wireless Controller
   Axes: 6
   Buttons: 14
   Hats: 1

Controller active! Press Button 9 (Options/Start) to exit.
```

### 6️⃣ Control Your Bot!

| Action | How To |
|--------|--------|
| **Move Forward** | Push left stick up |
| **Move Backward** | Push left stick down |
| **Turn Left** | Push right stick left |
| **Turn Right** | Push right stick right |
| **Look Up** | Push right stick up |
| **Look Down** | Push right stick down |
| **Tilt Head Left** | Press L1/LB (Button 4) |
| **Tilt Head Right** | Press R1/RB (Button 5) |
| **Stop Motors** | Press Circle/B (Button 1) |
| **Turbo Mode** | Hold Cross/A (Button 0) |
| **Exit** | Press Options/Start (Button 9) |

## Common Issues

### "No game controller found!"
✅ **Solution**: 
- Check USB cable connection
- Make sure controller is on
- Try `test_controller.py` first

### "MQTT connection failed"
✅ **Solution**:
- Check internet connection
- Verify ESP01 is online
- Check password matches ESP01

### "Bot not responding"
✅ **Solution**:
- Check ESP01 serial monitor (115200 baud)
- Verify password is correct
- Make sure STM32 is connected to ESP01

### Controller buttons not working right
✅ **Solution**:
- Different controllers use different button numbers
- Run `test_controller.py` to see your button numbers
- Edit `ps5_bot_controller.py` button mappings if needed

## Button Mapping by Controller Type

### PS5/PS4 Controller
- Button 0 = Cross (✕)
- Button 1 = Circle (○)
- Button 2 = Square (□)
- Button 3 = Triangle (△)
- Button 4 = L1
- Button 5 = R1
- Button 9 = Options

### Xbox Controller
- Button 0 = A
- Button 1 = B
- Button 2 = X
- Button 3 = Y
- Button 4 = LB
- Button 5 = RB
- Button 9 = Start

### Generic USB Controller
- Run `test_controller.py` to see your button numbers
- Note which buttons do what
- May need to edit script mappings

## Performance Tips

1. **Use USB for lowest latency** (better than Bluetooth)
2. **Close other programs** using controller
3. **Keep ESP01 close to WiFi router** for best MQTT performance
4. **Lower UPDATE_RATE** in script if experiencing lag (default: 20Hz)

## Next Steps

- ✅ Test basic movements
- ✅ Adjust dead zones if sticks drift
- ✅ Customize button mappings
- ✅ Try different speed modes
- ✅ Add custom commands

## Need Help?

1. Run `test_controller.py` - Shows controller detection
2. Run `test_mqtt_bot.py` - Tests MQTT without controller
3. Check ESP01 serial monitor - Shows received commands
4. Read full `PS5_CONTROLLER_README.md` - Complete documentation

Happy bot controlling! 🎮🤖
