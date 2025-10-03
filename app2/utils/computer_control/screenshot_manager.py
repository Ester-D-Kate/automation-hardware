"""
📷 Alice Screenshot Management System
Coordinates screenshot capture and analysis across multiple devices
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger(__name__)

class AliceScreenshotManager:
    def __init__(self):
        self.active_devices = {}
        self.screenshot_cache = {}
        self.analysis_cache = {}
        self.executor = ThreadPoolExecutor(max_workers=5)
        self._lock = threading.Lock()
        
        logger.info("📷 Alice Screenshot Manager initialized")
    
    def register_device(self, device_id: str, capabilities: Dict = None):
        """Register a device for screenshot coordination"""
        
        with self._lock:
            self.active_devices[device_id] = {
                "registered_at": datetime.now(),
                "last_seen": datetime.now(),
                "capabilities": capabilities or {},
                "status": "active"
            }
        
        logger.info(f"📱 Device registered: {device_id}")
    
    def unregister_device(self, device_id: str):
        """Unregister a device"""
        
        with self._lock:
            if device_id in self.active_devices:
                self.active_devices[device_id]["status"] = "inactive"
        
        logger.info(f"📱 Device unregistered: {device_id}")
    
    async def capture_screenshot_from_device(self, device_id: str, quality: str = "high") -> Optional[Dict]:
        """Capture screenshot from specific device via computer control"""
        
        try:
            # Import here to avoid circular dependency
            from .control_logic import get_computer_control
            
            computer_control = get_computer_control()
            screenshot = await computer_control._request_screenshot(device_id)
            
            if screenshot:
                # Cache the screenshot
                cache_key = f"{device_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.screenshot_cache[cache_key] = {
                    "device_id": device_id,
                    "screenshot": screenshot,
                    "timestamp": datetime.now(),
                    "quality": quality
                }
                
                # Clean old cache entries (keep last 10 per device)
                self._cleanup_cache(device_id)
                
                logger.info(f"📷 Screenshot captured from {device_id}")
                return screenshot
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Screenshot capture failed for {device_id}: {e}")
            return None
    
    async def capture_screenshots_from_multiple_devices(self, device_ids: List[str]) -> Dict[str, Optional[Dict]]:
        """Capture screenshots from multiple devices simultaneously"""
        
        tasks = []
        for device_id in device_ids:
            task = self.capture_screenshot_from_device(device_id)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        screenshot_results = {}
        for i, device_id in enumerate(device_ids):
            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"❌ Multi-screenshot failed for {device_id}: {result}")
                screenshot_results[device_id] = None
            else:
                screenshot_results[device_id] = result
        
        return screenshot_results
    
    async def analyze_screenshot_with_ai(self, screenshot_data: Dict, device_id: str) -> Dict:
        """Analyze screenshot using AI multimodal capabilities"""
        
        try:
            # Import here to avoid circular dependency
            from .control_logic import get_computer_control
            
            computer_control = get_computer_control()
            analysis = await computer_control._analyze_screenshot_with_ai(screenshot_data)
            
            # Cache analysis
            if analysis.get("success"):
                cache_key = f"analysis_{device_id}_{hash(str(screenshot_data.get('timestamp', '')))}"
                self.analysis_cache[cache_key] = {
                    "device_id": device_id,
                    "analysis": analysis["analysis"],
                    "timestamp": datetime.now()
                }
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Screenshot analysis failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_device_status(self, device_id: str = None) -> Dict:
        """Get status of devices"""
        
        with self._lock:
            if device_id:
                return self.active_devices.get(device_id, {"status": "unknown"})
            else:
                return dict(self.active_devices)
    
    def get_recent_screenshots(self, device_id: str, limit: int = 5) -> List[Dict]:
        """Get recent screenshots for a device"""
        
        screenshots = []
        for cache_key, data in self.screenshot_cache.items():
            if data["device_id"] == device_id:
                screenshots.append({
                    "cache_key": cache_key,
                    "timestamp": data["timestamp"],
                    "quality": data["quality"]
                })
        
        # Sort by timestamp, most recent first
        screenshots.sort(key=lambda x: x["timestamp"], reverse=True)
        return screenshots[:limit]
    
    def _cleanup_cache(self, device_id: str, max_keep: int = 10):
        """Clean up old cache entries"""
        
        device_screenshots = []
        for cache_key, data in self.screenshot_cache.items():
            if data["device_id"] == device_id:
                device_screenshots.append((cache_key, data["timestamp"]))
        
        # Sort by timestamp, oldest first
        device_screenshots.sort(key=lambda x: x[1])
        
        # Remove old entries if we have more than max_keep
        if len(device_screenshots) > max_keep:
            to_remove = device_screenshots[:-max_keep]
            for cache_key, _ in to_remove:
                del self.screenshot_cache[cache_key]
    
    def cleanup_old_data(self, max_age_hours: int = 24):
        """Clean up old cached data"""
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        # Clean screenshot cache
        to_remove = []
        for cache_key, data in self.screenshot_cache.items():
            if data["timestamp"] < cutoff_time:
                to_remove.append(cache_key)
        
        for cache_key in to_remove:
            del self.screenshot_cache[cache_key]
        
        # Clean analysis cache
        to_remove = []
        for cache_key, data in self.analysis_cache.items():
            if data["timestamp"] < cutoff_time:
                to_remove.append(cache_key)
        
        for cache_key in to_remove:
            del self.analysis_cache[cache_key]
        
        logger.info(f"🧹 Cleaned up {len(to_remove)} old cache entries")

# Global instance
_screenshot_manager = None

def get_screenshot_manager() -> AliceScreenshotManager:
    """Get global screenshot manager instance"""
    global _screenshot_manager
    if _screenshot_manager is None:
        _screenshot_manager = AliceScreenshotManager()
    return _screenshot_manager
