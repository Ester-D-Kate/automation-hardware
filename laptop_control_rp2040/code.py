import re
import time
import random
import board
import digitalio
import busio
import json
import usb_hid
from digitalio import DigitalInOut, Pull
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.consumer_control_code import ConsumerControlCode
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS as KeyboardLayout
from adafruit_hid.keycode import Keycode

# ---- Ducky Key/Consumer Code Maps ----
duckyKeys = {
    'WINDOWS': Keycode.GUI, 'RWINDOWS': Keycode.RIGHT_GUI, 'GUI': Keycode.GUI, 'RGUI': Keycode.RIGHT_GUI, 'COMMAND': Keycode.GUI, 'RCOMMAND': Keycode.RIGHT_GUI,
    'APP': Keycode.APPLICATION, 'MENU': Keycode.APPLICATION, 'SHIFT': Keycode.SHIFT, 'RSHIFT': Keycode.RIGHT_SHIFT,
    'ALT': Keycode.ALT, 'RALT': Keycode.RIGHT_ALT, 'OPTION': Keycode.ALT, 'ROPTION': Keycode.RIGHT_ALT, 'CONTROL': Keycode.CONTROL, 'CTRL': Keycode.CONTROL, 'RCTRL': Keycode.RIGHT_CONTROL,
    'DOWNARROW': Keycode.DOWN_ARROW, 'DOWN': Keycode.DOWN_ARROW, 'LEFTARROW': Keycode.LEFT_ARROW,
    'LEFT': Keycode.LEFT_ARROW, 'RIGHTARROW': Keycode.RIGHT_ARROW, 'RIGHT': Keycode.RIGHT_ARROW,
    'UPARROW': Keycode.UP_ARROW, 'UP': Keycode.UP_ARROW, 'BREAK': Keycode.PAUSE,
    'PAUSE': Keycode.PAUSE, 'CAPSLOCK': Keycode.CAPS_LOCK, 'DELETE': Keycode.DELETE,
    'END': Keycode.END, 'ESC': Keycode.ESCAPE, 'ESCAPE': Keycode.ESCAPE, 'HOME': Keycode.HOME,
    'INSERT': Keycode.INSERT, 'NUMLOCK': Keycode.KEYPAD_NUMLOCK, 'PAGEUP': Keycode.PAGE_UP,
    'PAGEDOWN': Keycode.PAGE_DOWN, 'PRINTSCREEN': Keycode.PRINT_SCREEN, 'ENTER': Keycode.ENTER,
    'SCROLLLOCK': Keycode.SCROLL_LOCK, 'SPACE': Keycode.SPACE, 'TAB': Keycode.TAB,
    'BACKSPACE': Keycode.BACKSPACE,
    'A': Keycode.A, 'B': Keycode.B, 'C': Keycode.C, 'D': Keycode.D, 'E': Keycode.E,
    'F': Keycode.F, 'G': Keycode.G, 'H': Keycode.H, 'I': Keycode.I, 'J': Keycode.J,
    'K': Keycode.K, 'L': Keycode.L, 'M': Keycode.M, 'N': Keycode.N, 'O': Keycode.O,
    'P': Keycode.P, 'Q': Keycode.Q, 'R': Keycode.R, 'S': Keycode.S, 'T': Keycode.T,
    'U': Keycode.U, 'V': Keycode.V, 'W': Keycode.W, 'X': Keycode.X, 'Y': Keycode.Y,
    'Z': Keycode.Z, 'F1': Keycode.F1, 'F2': Keycode.F2, 'F3': Keycode.F3,
    'F4': Keycode.F4, 'F5': Keycode.F5, 'F6': Keycode.F6, 'F7': Keycode.F7,
    'F8': Keycode.F8, 'F9': Keycode.F9, 'F10': Keycode.F10, 'F11': Keycode.F11,
    'F12': Keycode.F12, 'F13': Keycode.F13, 'F14': Keycode.F14, 'F15': Keycode.F15,
    'F16': Keycode.F16, 'F17': Keycode.F17, 'F18': Keycode.F18, 'F19': Keycode.F19,
    'F20': Keycode.F20, 'F21': Keycode.F21, 'F22': Keycode.F22, 'F23': Keycode.F23,
    'F24': Keycode.F24
}
duckyConsumerKeys = {
    'MK_VOLUP': ConsumerControlCode.VOLUME_INCREMENT, 'MK_VOLDOWN': ConsumerControlCode.VOLUME_DECREMENT, 'MK_MUTE': ConsumerControlCode.MUTE,
    'MK_NEXT': ConsumerControlCode.SCAN_NEXT_TRACK, 'MK_PREV': ConsumerControlCode.SCAN_PREVIOUS_TRACK,
    'MK_PP': ConsumerControlCode.PLAY_PAUSE, 'MK_STOP': ConsumerControlCode.STOP
}

variables = {"$_RANDOM_MIN": 0, "$_RANDOM_MAX": 65535}
internalVariables = {}
defines = {}
functions = {}

letters = "abcdefghijklmnopqrstuvwxyz"
numbers = "0123456789"
specialChars = "!@#$%^&*()"

kbd = Keyboard(usb_hid.devices)
consumerControl = ConsumerControl(usb_hid.devices)
layout = KeyboardLayout(kbd)
defaultDelay = 0

def deepcopy(List):
    return List[:]

def convertLine(line):
    commands = []
    for key in filter(None, line.split(" ")):
        key = key.upper()
        command_keycode = duckyKeys.get(key, None)
        command_consumer_keycode = duckyConsumerKeys.get(key, None)
        if command_keycode is not None:
            commands.append(command_keycode)
        elif command_consumer_keycode is not None:
            commands.append(1000 + command_consumer_keycode)
        elif hasattr(Keycode, key):
            commands.append(getattr(Keycode, key))
        else:
            print(f"Unknown key: <{key}>")
    return commands

def runScriptLine(line):
    keys = convertLine(line)
    for k in keys:
        if k > 1000:
            consumerControl.press(int(k - 1000))
        else:
            kbd.press(k)
    for k in reversed(keys):
        if k > 1000:
            consumerControl.release()
        else:
            kbd.release(k)

def sendString(line):
    layout.write(line)

def replaceVariables(line):
    for var in variables:
        line = line.replace(var, str(variables[var]))
    for var in internalVariables:
        line = line.replace(var, str(internalVariables[var]()))
    return line

def replaceDefines(line):
    for define, value in defines.items():
        line = line.replace(define, value)
    return line

def evaluateExpression(expression):
    expression = re.sub(r"\$(\w+)", lambda m: str(variables.get(f"${m.group(1)}", 0)), expression)
    expression = expression.replace("^", "**")
    expression = expression.replace("&&", "and")
    expression = expression.replace("||", "or")
    return eval(expression, {}, variables)

def parseLine(line, script_lines):
    global defaultDelay, variables, functions, defines
    line = line.strip()
    line = line.replace("$_RANDOM_INT", str(random.randint(int(variables.get("$_RANDOM_MIN", 0)), int(variables.get("$_RANDOM_MAX", 65535)))))
    line = replaceDefines(line)
    if line[:10] == "INJECT_MOD":
        line = line[11:]
    elif line.startswith("REM_BLOCK"):
        while line.startswith("END_REM") == False:
            line = next(script_lines).strip()
    elif line[0:3] == "REM":
        pass
    elif line.startswith("HOLD"):
        key = line[5:].strip().upper()
        commandKeycode = duckyKeys.get(key, None)
        if commandKeycode:
            kbd.press(commandKeycode)
        else:
            print(f"Unknown key to HOLD: <{key}>")
    elif line.startswith("RELEASE"):
        key = line[8:].strip().upper()
        commandKeycode = duckyKeys.get(key, None)
        if commandKeycode:
            kbd.release(commandKeycode)
        else:
            print(f"Unknown key to RELEASE: <{key}>")
    elif line[0:5] == "DELAY":
        # Support for DELAY500 (no space) or DELAY 500 (with space)
        match = re.match(r"DELAY\s*(\d+)", line)
        if match:
            ms = int(match.group(1))
            time.sleep(ms / 1000)
    elif line == "STRINGLN":
        line = next(script_lines).strip()
        line = replaceVariables(line)
        while line.startswith("END_STRINGLN") == False:
            sendString(line)
            kbd.press(Keycode.ENTER)
            kbd.release(Keycode.ENTER)
            line = next(script_lines).strip()
            line = replaceVariables(line)
            line = replaceDefines(line)
    elif line[0:8] == "STRINGLN":
        sendString(replaceVariables(line[9:]))
        kbd.press(Keycode.ENTER)
        kbd.release(Keycode.ENTER)
    elif line == "STRING":
        line = next(script_lines).strip()
        line = replaceVariables(line)
        while line.startswith("END_STRING") == False:
            sendString(line)
            line = next(script_lines).strip()
            line = replaceVariables(line)
            line = replaceDefines(line)
    elif line[0:6] == "STRING":
        sendString(replaceVariables(line[7:]))
    elif line[0:5] == "PRINT":
        line = replaceVariables(line[6:])
        print("[SCRIPT]: " + line)
    elif line[0:6] == "IMPORT":
        pass # Not supported in in-memory mode
    elif line[0:13] == "DEFAULT_DELAY":
        defaultDelay = int(line[14:]) * 10
    elif line[0:12] == "DEFAULTDELAY":
        defaultDelay = int(line[13:]) * 10
    elif line[0:3] == "LED":
        pass  # LED not supported here
    elif line[:7] == "LED_OFF":
        pass
    elif line[:5] == "LED_R":
        pass
    elif line[:5] == "LED_G":
        pass
    elif line[0:21] == "WAIT_FOR_BUTTON_PRESS":
        pass  # Not used in this mode
    elif line.startswith("VAR"):
        match = re.match(r"VAR\s+\$(\w+)\s*=\s*(.+)", line)
        if match:
            varName = f"${match.group(1)}"
            value = evaluateExpression(match.group(2))
            variables[varName] = value
        else:
            raise SyntaxError(f"Invalid variable declaration: {line}")
    elif line.startswith("$"):
        match = re.match(r"\$(\w+)\s*=\s*(.+)", line)
        if match:
            varName = f"${match.group(1)}"
            expression = match.group(2)
            value = evaluateExpression(expression)
            variables[varName] = value
        else:
            raise SyntaxError(f"Invalid variable update, declare variable first: {line}")
    elif line.startswith("DEFINE"):
        defineLocation = line.find(" ")
        valueLocation = line.find(" ", defineLocation + 1)
        defineName = line[defineLocation+1:valueLocation]
        defineValue = line[valueLocation+1:]
        defines[defineName] = defineValue
    elif line.startswith("FUNCTION"):
        func_name = line.split()[1]
        functions[func_name] = []
        line = next(script_lines).strip()
        while line != "END_FUNCTION":
            functions[func_name].append(line)
            line = next(script_lines).strip()
    elif line.startswith("WHILE"):
        condition = line[5:].strip()
        loopCode = []
        depth = 1
        for loop_line in script_lines:
            if loop_line.upper().startswith("WHILE"):
                depth += 1
            elif loop_line.upper().startswith("END_WHILE"):
                depth -= 1
                if depth == 0:
                    break
            loopCode.append(loop_line)
        while evaluateExpression(condition) == True:
            currentIterCode = deepcopy(loopCode)
            while currentIterCode:
                loopLine = currentIterCode.pop(0)
                parseLine(loopLine, iter(currentIterCode))
    elif line.upper().startswith("IF"):
        pass  # IF/ELSE/ENDIF not supported in this minimal mode
    elif line.upper().startswith("END_IF"):
        pass
    elif line == "RANDOM_LOWERCASE_LETTER":
        sendString(random.choice(letters))
    elif line == "RANDOM_UPPERCASE_LETTER":
        sendString(random.choice(letters.upper()))
    elif line == "RANDOM_LETTER":
        sendString(random.choice(letters + letters.upper()))
    elif line == "RANDOM_NUMBER":
        sendString(random.choice(numbers))
    elif line == "RANDOM_SPECIAL":
        sendString(random.choice(specialChars))
    elif line == "RANDOM_CHAR":
        sendString(random.choice(letters + letters.upper() + numbers + specialChars))
    elif line == "VID_RANDOM" or line == "PID_RANDOM":
        for _ in range(4):
            sendString(random.choice("0123456789ABCDEF"))
    elif line == "MAN_RANDOM" or line == "PROD_RANDOM":
        for _ in range(12):
            sendString(random.choice(letters + letters.upper() + numbers))
    elif line == "SERIAL_RANDOM":
        for _ in range(12):
            sendString(random.choice(letters + letters.upper() + numbers + specialChars))
    elif line == "RESET":
        kbd.release_all()
    elif line in functions:
        for func_line in functions[line]:
            parseLine(func_line, iter(functions[line]))
    else:
        runScriptLine(line)
    return script_lines

# ---- In-memory Ducky runner ----
def run_ducky_script_from_string(script_str):
    global defaultDelay
    restart = True
    lines = script_str.splitlines()
    while restart:
        restart = False
        script_lines = iter(lines)
        previousLine = ""
        for line in script_lines:
            clean_line = line.split('#', 1)[0].strip()
            if clean_line == "":
                continue
            if clean_line[0:6] == "REPEAT":
                for i in range(int(clean_line[7:])):
                    parseLine(previousLine, script_lines)
                    time.sleep(float(defaultDelay) / 1000)
            elif clean_line.startswith("RESTART_PAYLOAD"):
                restart = True
                break
            elif clean_line.startswith("STOP_PAYLOAD"):
                restart = False
                break
            else:
                parseLine(clean_line, script_lines)
                previousLine = clean_line
            time.sleep(float(defaultDelay) / 1000)

# ---- UART receiver and executor ----
uart = busio.UART(board.GP0, board.GP1, baudrate=115200, timeout=0.5)  # RX, TX

def receive_and_execute():
    buffer = b""
    print("Ready to receive and execute ducky scripts over UART.")
    print("Deduplication logic is handled by ESP device.")
    while True:
        b = uart.read(1)
        if b:
            if b == b"\n":
                try:
                    decoded = buffer.decode("utf-8").strip()
                    print("Received:", decoded)
                    if decoded.startswith("{") and "ducky_script" in decoded:
                        data = json.loads(decoded)
                        ducky_script = data.get("ducky_script", "")
                        if ducky_script:
                            print("Executing script...")
                            run_ducky_script_from_string(ducky_script.replace("\\n", "\n"))
                            print("Script execution completed.")
                        else:
                            print("Empty script received.")
                except Exception as e:
                    print("Error parsing/executing:", e)
                finally:
                    buffer = b""
            else:
                buffer += b
        else:
            time.sleep(0.01)

# ---- MAIN LOOP ----
receive_and_execute()