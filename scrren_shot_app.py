import time
import requests
import os
import platform

# Choose screenshot tool
try:
    import mss
    import mss.tools
except ImportError:
    print("Install mss with: pip install mss")
    exit(1)

API_URL = "http://localhost:8000/upload_screenshot"  # change if needed

def capture_and_send():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        while True:
            img = sct.grab(monitor)
            img_bytes = mss.tools.to_png(img.rgb, img.size)
            filename = "screen.png"
            with open(filename, "wb") as f:
                f.write(img_bytes)
            
            # Send to Alice backend
            with open(filename, "rb") as img_file:
                files = {'screenshot': img_file}
                try:
                    response = requests.post(API_URL, files=files)
                    print(f"Screenshot sent, response: {response.status_code}")
                except Exception as e:
                    print(f"Failed to send screenshot: {e}")
            
            os.remove(filename)
            time.sleep(0.1)  # 100 ms

if __name__ == "__main__":
    capture_and_send()