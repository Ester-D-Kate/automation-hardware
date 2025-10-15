"""
Constants for MQTT and automation system
"""

# MQTT Broker Configuration
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_USERNAME = "LDrago_windows"
MQTT_PASSWORD = "E1s2t3e4r5"

# MQTT Topics - Hardware Executor
MQTT_TOPIC_COMMAND = "LDrago_windows/ducky_script"
MQTT_TOPIC_FEEDBACK = "LDrago_windows/pico_feedback"

# MQTT Topics - Software Executor
MQTT_TOPIC_COMMAND_SOFTWARE = "LDrago_windows/ducky_script_software"
MQTT_TOPIC_FEEDBACK_SOFTWARE = "LDrago_windows/pico_feedback_software"

# MQTT Topics - Device Info
MQTT_TOPIC_DEVICE_INFO = "LDrago_windows/device_info"
MQTT_TOPIC_DEVICE_INFO_CHANGED = "LDrago_windows/device_info_changed"
MQTT_TOPIC_MOUSE_POSITION = "LDrago_windows/mouse_position"
MQTT_TOPIC_APPLICATIONS_INFO = "LDrago_windows/applications_info"
MQTT_TOPIC_SCREENSHOT = "LDrago_windows/screenshot"

# MQTT Topics - Request Topics
MQTT_TOPIC_GET_MOUSE_POSITION = "LDrago_windows/get_mouse_position"
MQTT_TOPIC_GET_DEVICE_INFO = "LDrago_windows/get_device_info"
MQTT_TOPIC_GET_APPLICATIONS = "LDrago_windows/get_applications"

# Device Monitor Settings
MONITOR_CHECK_INTERVAL = 5.0  # seconds

# PyAutoGUI Settings
PYAUTOGUI_FAILSAFE = False
PYAUTOGUI_PAUSE = 0.01  # seconds between commands

# Bridge System Settings
BRIDGE_WAYPOINT_DURATION = 0.3  # seconds per waypoint movement
BRIDGE_MAJOR_OFFSET_PERCENT = 0.10  # 10% of smallest dimension
BRIDGE_MINOR_OFFSET_PERCENT = 0.05  # 5% of smallest dimension

# Cloud AI Settings
CLOUD_AI_ENABLED = True  # Set to True to enable cloud AI backend
CLOUD_AI_URL = "ws://localhost:8765"  # WebSocket URL for AI backend
CLOUD_RECONNECT_INTERVAL = 5.0  # seconds

# AI Backend Server Settings
AI_BACKEND_HOST = '127.0.0.1'
AI_BACKEND_PORT = 8765
