import websocket
import cv2
import numpy as np
import time
from threading import Thread
import queue

ESP32_IP = "192.168.1.40"
WEBSOCKET_URL = f"ws://{ESP32_IP}:81"

# Frame size
WIDTH = 320
HEIGHT = 240
RGB565_SIZE = WIDTH * HEIGHT * 2

# Fast frame queue
frame_queue = queue.Queue(maxsize=2)
running = True

frame_count = 0
start_time = time.time()

def rgb565_to_bgr_fast(data):
    """Ultra-fast RGB565 to BGR conversion using numpy"""
    # Convert to uint16 array
    rgb565 = np.frombuffer(data, dtype=np.uint16).reshape((HEIGHT, WIDTH))
    
    # Extract channels (vectorized - FAST!)
    r = ((rgb565 & 0xF800) >> 8).astype(np.uint8)
    g = ((rgb565 & 0x07E0) >> 3).astype(np.uint8)
    b = ((rgb565 & 0x001F) << 3).astype(np.uint8)
    
    # Stack as BGR for OpenCV
    return np.dstack((b, g, r))

def on_message(ws, message):
    """Receive and decode frames"""
    global frame_count
    
    if len(message) == RGB565_SIZE:
        try:
            # Drop old frame if queue full
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except:
                    pass
            
            # Fast conversion
            img = rgb565_to_bgr_fast(message)
            frame_queue.put(img)
            frame_count += 1
            
        except Exception as e:
            print(f"Error: {e}")

def on_error(ws, error):
    if error:
        print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    global running
    print("Connection closed")
    running = False

def on_open(ws):
    print("Connected! Receiving RGB565 stream...")

def display_loop():
    """Display thread - runs independently"""
    global running
    
    cv2.namedWindow('ESP32-CAM Stream', cv2.WINDOW_NORMAL)
    
    fps_count = 0
    fps_time = time.time()
    
    while running:
        try:
            img = frame_queue.get(timeout=1)
            
            # Calculate FPS
            fps_count += 1
            if time.time() - fps_time >= 1.0:
                fps = fps_count / (time.time() - fps_time)
                fps_count = 0
                fps_time = time.time()
                print(f"FPS: {fps:.1f}")
            
            # Display
            cv2.imshow('ESP32-CAM Stream', img)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                running = False
                break
                
        except queue.Empty:
            continue
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    print(f"Connecting to {WEBSOCKET_URL}")
    print("PC will do RGB565 conversion (fast!)")
    
    # Start display thread
    display_thread = Thread(target=display_loop, daemon=True)
    display_thread.start()
    
    # WebSocket client
    ws = websocket.WebSocketApp(
        WEBSOCKET_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    ws.run_forever(ping_interval=60, ping_timeout=30)
    
    running = False
    display_thread.join(timeout=2)
    print("Stopped")
