"""
Screenshot Test Client
Receives and saves screenshots sent via MQTT
"""

import asyncio
import json
import time
import base64
import gzip
import paho.mqtt.client as mqtt
from pathlib import Path


class ScreenshotClient:
    def __init__(self):
        self.broker = "broker.emqx.io"
        self.port = 1883
        self.username = "LDrago_windows"
        self.password = "E1s2t3e4r5"
        
        # Topics
        self.command_topic = "LDrago_windows/ducky_script_software"
        self.screenshot_topic = "LDrago_windows/screenshot"
        
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, 
                                      client_id=f"ScreenshotClient-{int(time.time())}")
        self.mqtt_client.username_pw_set(self.username, self.password)
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.is_connected = False
        
        # Create screenshots directory
        self.screenshot_dir = Path("screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        self.screenshot_count = 0
        
        # Track request time for round-trip latency
        self.last_request_time = None
    
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.is_connected = True
            print("✅ Connected to MQTT broker")
            client.subscribe(self.screenshot_topic)
            print(f"📡 Subscribed to: {self.screenshot_topic}")
        else:
            print(f"❌ Connection failed: {reason_code}")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming screenshots"""
        try:
            data = json.loads(msg.payload.decode())
            
            print("\n" + "="*80)
            print("📸 SCREENSHOT RECEIVED")
            print("="*80)
            print(f"   Monitor: {data.get('monitor', 'unknown')}")
            print(f"   Size: {data.get('width', 0)}x{data.get('height', 0)}")
            print(f"   Format: {data.get('format', 'unknown')}")
            
            # Show compression info if compressed
            if data.get('compressed', False):
                original = data.get('size_bytes', 0)
                compressed = data.get('compressed_bytes', 0)
                ratio = (compressed / original * 100) if original > 0 else 0
                saved = original - compressed
                print(f"   📦 Compressed: {original:,} → {compressed:,} bytes ({ratio:.1f}%, saved {saved:,} bytes)")
            print(f"   Quality: {data.get('quality', 0)}%")
            print(f"   Data size: {data.get('size_bytes', 0):,} bytes")
            
            # Calculate latencies
            receive_time = time.time()
            capture_time = data.get('timestamp', receive_time)
            
            # Transmission latency (capture to receipt)
            transmission_latency_ms = (receive_time - capture_time) * 1000
            
            # Round-trip latency (request to receipt)
            if self.last_request_time:
                round_trip_ms = (receive_time - self.last_request_time) * 1000
            else:
                round_trip_ms = None
            
            # Decode and decompress screenshot
            img_base64 = base64.b64decode(data.get('data', ''))
            
            # Decompress if compressed
            if data.get('compressed', False):
                img_data = gzip.decompress(img_base64)
            else:
                img_data = img_base64
            
            # Generate filename with correct extension
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            monitor = data.get('monitor', 'all')
            img_format = data.get('format', 'jpeg')
            
            # Use correct extension based on format
            extension = 'webp' if img_format == 'webp' else 'jpg'
            filename = f"screenshot_{monitor}_{timestamp}.{extension}"
            filepath = self.screenshot_dir / filename
            
            # Save file
            with open(filepath, 'wb') as f:
                f.write(img_data)
            
            self.screenshot_count += 1
            
            print(f"   💾 Saved: {filepath}")
            
            # Display transmission latency with color-coded status
            if transmission_latency_ms < 1000:
                status = "⚡ EXCELLENT"
            elif transmission_latency_ms < 2000:
                status = "✅ GOOD"
            elif transmission_latency_ms < 3000:
                status = "⚠️  ACCEPTABLE"
            else:
                status = "❌ SLOW"
            
            print(f"   📡 Transmission: {transmission_latency_ms:.0f} ms ({transmission_latency_ms/1000:.2f}s) {status}")
            
            # Display round-trip latency if available
            if round_trip_ms is not None:
                if round_trip_ms < 1500:
                    rt_status = "⚡ EXCELLENT"
                elif round_trip_ms < 2500:
                    rt_status = "✅ GOOD"
                elif round_trip_ms < 3500:
                    rt_status = "⚠️  ACCEPTABLE"
                else:
                    rt_status = "❌ SLOW"
                
                print(f"   🔄 Round-trip: {round_trip_ms:.0f} ms ({round_trip_ms/1000:.2f}s) {rt_status}")
            
            # Clean up old screenshots (keep only last 10)
            self._cleanup_old_screenshots(max_files=10)
            
            print(f"   📊 Total screenshots: {self.screenshot_count}")
            print("="*80 + "\n")
            
        except Exception as e:
            print(f"❌ Error processing screenshot: {e}")
    
    def _cleanup_old_screenshots(self, max_files=10):
        """Keep only the most recent N screenshots, delete older ones"""
        try:
            # Get all screenshot files (both .jpg and .webp) sorted by modification time (oldest first)
            screenshots = sorted(
                list(self.screenshot_dir.glob("screenshot_*.jpg")) + 
                list(self.screenshot_dir.glob("screenshot_*.webp")),
                key=lambda p: p.stat().st_mtime
            )
            
            # If we have more than max_files, delete the oldest ones
            if len(screenshots) > max_files:
                files_to_delete = screenshots[:-max_files]  # All except last N
                for old_file in files_to_delete:
                    old_file.unlink()  # Delete the file
                    print(f"   🗑️  Deleted old: {old_file.name}")
                
                print(f"   ♻️  Kept last {max_files} screenshots")
        except Exception as e:
            print(f"   ⚠️  Cleanup error: {e}")
    
    async def connect(self):
        """Connect to MQTT broker"""
        print(f"🔌 Connecting to {self.broker}...")
        self.mqtt_client.connect(self.broker, self.port, 60)
        self.mqtt_client.loop_start()
        
        # Wait for connection
        for _ in range(50):
            await asyncio.sleep(0.1)
            if self.is_connected:
                return True
        
        print("❌ Failed to connect")
        return False
    
    def send_screenshot_request(self, monitor=None, quality=85):
        """Send command to take screenshot (JPEG format, fast encoding)"""
        # Record request time for round-trip latency calculation
        self.last_request_time = time.time()
        
        if monitor is None or monitor == 'all':
            command = f"SCREENSHOT ALL {quality}"
        else:
            command = f"SCREENSHOT {monitor} {quality}"
        
        payload = json.dumps({
            'password': self.password,
            'script': command
        })
        
        print(f"\n📤 Requesting screenshot: {command}")
        self.mqtt_client.publish(self.command_topic, payload)
    
    def disconnect(self):
        """Disconnect from MQTT"""
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        print("\n✅ Disconnected from MQTT")


async def main():
    client = ScreenshotClient()
    
    if not await client.connect():
        return
    
    print("\n" + "="*80)
    print("📸 SCREENSHOT TEST CLIENT")
    print("="*80)
    print(f"   Listening on: {client.screenshot_topic}")
    print(f"   Sending commands to: {client.command_topic}")
    print(f"   Screenshots saved to: {client.screenshot_dir.absolute()}")
    print("="*80)
    
    while True:
        print("\n" + "="*80)
        print("📋 SCREENSHOT MENU:")
        print("   1. Capture all monitors")
        print("   2. Capture primary monitor (0)")
        print("   3. Capture secondary monitor (1)")
        print("   ─────────────────────────────────")
        print("   4. Custom quality")
        print("   5. View saved screenshots")
        print("   0. Exit")
        print("")
        print("   ℹ️  Using JPEG format (fast encoding, quality 85)")
        print("   🗜️  Gzip compression enabled (level 6)")
        print("="*80)
        
        try:
            choice = input("\nSelect: ").strip()
            
            if choice == '0':
                break
            
            elif choice == '1':
                client.send_screenshot_request('all', 85)
            
            elif choice == '2':
                client.send_screenshot_request(0, 85)
            
            elif choice == '3':
                client.send_screenshot_request(1, 85)
            
            elif choice == '4':
                monitor = input("Monitor (0, 1, or 'all'): ").strip()
                quality = input("Quality (1-100, default 85): ").strip()
                
                if not quality:
                    quality = 85
                else:
                    quality = int(quality)
                
                if monitor.lower() == 'all':
                    client.send_screenshot_request('all', quality)
                else:
                    client.send_screenshot_request(int(monitor), quality)
            
            elif choice == '5':
                print("\n📂 Saved screenshots:")
                screenshots = list(client.screenshot_dir.glob("*.jpg")) + list(client.screenshot_dir.glob("*.webp"))
                if screenshots:
                    for i, path in enumerate(sorted(screenshots), 1):
                        size = path.stat().st_size
                        print(f"   {i}. {path.name} ({size:,} bytes)")
                else:
                    print("   (none)")
            
            else:
                print("❌ Invalid choice")
            
            # Small delay to receive response
            await asyncio.sleep(0.5)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")
    
    client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
