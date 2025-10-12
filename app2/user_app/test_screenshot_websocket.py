"""
WebSocket Screenshot Client
Receives screenshots via WebSocket (MUCH faster than MQTT!)
"""

import asyncio
import json
import time
import websockets
from pathlib import Path


class ScreenshotWebSocketClient:
    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port
        self.uri = f"ws://{host}:{port}"
        self.screenshot_dir = Path("screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        self.screenshot_count = 0
        self.last_request_time = None
        self.websocket = None
        
        # Clean up old screenshots (keep only last 10)
        self._cleanup_old_screenshots()
    
    def _cleanup_old_screenshots(self):
        """Keep only the last 10 screenshots"""
        screenshots = sorted(self.screenshot_dir.glob("screenshot_*.*"), 
                           key=lambda p: p.stat().st_mtime, 
                           reverse=True)
        
        if len(screenshots) > 10:
            for old_file in screenshots[10:]:
                try:
                    old_file.unlink()
                    print(f"🗑️  Deleted old: {old_file.name}")
                except Exception as e:
                    print(f"⚠️  Could not delete {old_file.name}: {e}")
    
    async def connect(self):
        """Connect to WebSocket server"""
        print(f"🔌 Connecting to {self.uri}...")
        try:
            self.websocket = await websockets.connect(self.uri)
            print("✅ Connected to WebSocket server")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    async def receive_screenshots(self):
        """Listen for incoming screenshots"""
        try:
            while True:
                # Receive metadata (JSON)
                metadata_msg = await self.websocket.recv()
                
                # Check if it's binary data (JPEG) - if so, it's out of order, skip it
                if isinstance(metadata_msg, bytes):
                    # Try to decode as JSON first
                    try:
                        metadata_str = metadata_msg.decode('utf-8')
                        metadata = json.loads(metadata_str)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        # It's binary image data, not metadata - skip it
                        print("⚠️  Received binary data when expecting metadata, skipping...")
                        continue
                else:
                    # It's a string
                    try:
                        metadata = json.loads(metadata_msg)
                    except json.JSONDecodeError:
                        print("⚠️  Invalid JSON metadata, skipping...")
                        continue
                
                receive_time = time.time()
                
                # Receive binary data (JPEG image)
                img_data = await self.websocket.recv()
                
                # Validate it's actually binary data
                if not isinstance(img_data, bytes):
                    print("⚠️  Expected binary image data but got text, skipping...")
                    continue
                
                # Calculate latencies
                timestamp = metadata.get('timestamp', receive_time)
                transmission_latency_ms = (receive_time - timestamp) * 1000
                
                # Round-trip latency
                if self.last_request_time:
                    round_trip_ms = (receive_time - self.last_request_time) * 1000
                else:
                    round_trip_ms = None
                
                # Generate filename
                timestamp_str = time.strftime("%Y%m%d_%H%M%S")
                monitor = metadata.get('monitor', 'all')
                img_format = metadata.get('format', 'jpeg')
                extension = 'png' if img_format == 'png' else 'jpg'
                filename = f"screenshot_{monitor}_{timestamp_str}.{extension}"
                filepath = self.screenshot_dir / filename
                
                # Save file
                with open(filepath, 'wb') as f:
                    f.write(img_data)
                
                self.screenshot_count += 1
                
                # Display results
                print("\n" + "="*80)
                print("📸 SCREENSHOT RECEIVED (WebSocket)")
                print("="*80)
                print(f"   Monitor: {metadata.get('monitor', 'unknown')}")
                print(f"   Size: {metadata.get('width', 0)}x{metadata.get('height', 0)}")
                print(f"   Format: {metadata.get('format', 'unknown')}")
                print(f"   Quality: {metadata.get('quality', 0)}%")
                print(f"   Data size: {len(img_data):,} bytes (raw binary, no base64!)")
                print(f"   💾 Saved: {filepath}")
                
                # Transmission latency with color-coded status
                if transmission_latency_ms < 500:
                    status = "⚡ EXCELLENT"
                elif transmission_latency_ms < 1000:
                    status = "✅ GOOD"
                elif transmission_latency_ms < 2000:
                    status = "⚠️  ACCEPTABLE"
                else:
                    status = "❌ SLOW"
                
                print(f"   📡 Transmission: {transmission_latency_ms:.0f} ms ({transmission_latency_ms/1000:.2f}s) {status}")
                
                # Round-trip latency
                if round_trip_ms is not None:
                    if round_trip_ms < 1000:
                        rt_status = "⚡ EXCELLENT"
                    elif round_trip_ms < 1500:
                        rt_status = "✅ GOOD"
                    elif round_trip_ms < 2500:
                        rt_status = "⚠️  ACCEPTABLE"
                    else:
                        rt_status = "❌ SLOW"
                    
                    print(f"   🔄 Round-trip: {round_trip_ms:.0f} ms ({round_trip_ms/1000:.2f}s) {rt_status}")
                
                # Cleanup
                self._cleanup_old_screenshots()
                print(f"   ♻️  Kept last 10 screenshots")
                print(f"   📊 Total screenshots: {self.screenshot_count}")
                print("="*80)
                
        except websockets.exceptions.ConnectionClosed:
            print("\n❌ Connection closed")
        except Exception as e:
            print(f"\n❌ Error receiving screenshot: {e}")
    
    async def send_ping(self):
        """Send periodic pings to keep connection alive"""
        try:
            while True:
                await asyncio.sleep(30)
                if self.websocket:
                    await self.websocket.send(json.dumps({
                        'type': 'ping',
                        'timestamp': time.time()
                    }))
        except:
            pass
    
    async def run(self):
        """Main run loop"""
        if not await self.connect():
            return
        
        print("\n" + "="*80)
        print("📸 WEBSOCKET SCREENSHOT CLIENT")
        print("="*80)
        print(f"   Connected to: {self.uri}")
        print(f"   Screenshots saved to: {self.screenshot_dir.absolute()}")
        print("="*80)
        print("\n⏸️  Press Ctrl+C to stop\n")
        print("💡 Use test_screenshot.py or MQTT to request screenshots")
        print("   This client only receives via WebSocket (10-20x faster!)\n")
        
        # Run receiver and ping tasks
        try:
            await asyncio.gather(
                self.receive_screenshots(),
                self.send_ping()
            )
        except KeyboardInterrupt:
            print("\n\n✅ Client stopped")
        finally:
            if self.websocket:
                await self.websocket.close()


if __name__ == "__main__":
    client = ScreenshotWebSocketClient()
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\n\n✅ Client stopped")
