"""
Complete Device Information Extractor (Async Version)
Extracts every detail about monitors, resolution, layout, and system info
All functions are async for integration with automation systems
"""

import pyautogui
import platform
import sys
from typing import List, Dict, Tuple
import json
import asyncio


async def get_primary_monitor_info() -> Dict:
    size = await asyncio.to_thread(pyautogui.size)
    return {"name": "primary", "width": size.width, "height": size.height,
            "x": 0, "y": 0, "is_primary": True}

async def get_all_monitors_info() -> List[Dict]:
    monitors = []
    
    try:
        if platform.system() == "Windows":
            import ctypes
            from ctypes import wintypes
            
            # Windows API structures
            class RECT(ctypes.Structure):
                _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                            ("right", wintypes.LONG), ("bottom", wintypes.LONG)]
            
            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                            ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]
            
            # Monitor enumeration callback
            monitor_list = []
            
            def enum_callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(MONITORINFO)
                if ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(info)):
                    monitor_data = {"handle": hMonitor,
                                    "x": info.rcMonitor.left,
                                    "y": info.rcMonitor.top,
                                    "width": info.rcMonitor.right - info.rcMonitor.left,
                                    "height": info.rcMonitor.bottom - info.rcMonitor.top,
                                    "work_area": {"x": info.rcWork.left,
                                                  "y": info.rcWork.top,
                                                  "width": info.rcWork.right - info.rcWork.left,
                                                  "height": info.rcWork.bottom - info.rcWork.top},
                                    "is_primary": bool(info.dwFlags & 1)}
                    monitor_list.append(monitor_data)
                return True
            
            # Create callback type
            MonitorEnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                                  ctypes.POINTER(RECT), wintypes.LPARAM)
            
            # Enumerate all monitors
            callback = MonitorEnumProc(enum_callback)
            ctypes.windll.user32.EnumDisplayMonitors(None, None, callback, 0)
            
            # Sort monitors: primary first, then by position
            monitor_list.sort(key=lambda m: (not m["is_primary"], m["x"], m["y"]))
            
            # Assign names and indices
            for i, mon in enumerate(monitor_list):
                mon["index"] = i
                if mon["is_primary"]:
                    mon["name"] = "primary"
                else:
                    mon["name"] = f"secondary_{i}" if i == 1 else f"monitor_{i}"
                del mon["handle"]  # Remove handle (not JSON serializable)
            
            monitors = monitor_list
            
    except Exception as e:
        print(f"⚠️  Could not get detailed monitor info: {e}")
        print("📋 Falling back to primary monitor only...")
        monitors = [await get_primary_monitor_info()]
    
    return monitors
async def calculate_monitor_boundaries(monitors: List[Dict]) -> Dict:
    if not monitors:
        return {"min_x": 0, "min_y": 0, "max_x": 0,
                "max_y": 0, "width": 0, "height": 0}
    
    min_x = min(m["x"] for m in monitors)
    min_y = min(m["y"] for m in monitors)
    max_x = max(m["x"] + m["width"] for m in monitors)
    max_y = max(m["y"] + m["height"] for m in monitors)
    
    return {"min_x": min_x, "min_y": min_y, "max_x": max_x,
            "max_y": max_y, "width": max_x - min_x, "height": max_y - min_y}

async def analyze_monitor_layout(monitors: List[Dict]) -> Dict:
    if len(monitors) < 2:
        return {"layout": "single_monitor", "relationships": []}
    
    relationships = []
    
    for i, mon1 in enumerate(monitors):
        for j, mon2 in enumerate(monitors):
            if i >= j:
                continue
            
            # Calculate relationship
            mon1_right = mon1["x"] + mon1["width"]
            mon1_bottom = mon1["y"] + mon1["height"]
            mon2_right = mon2["x"] + mon2["width"]
            mon2_bottom = mon2["y"] + mon2["height"]
            
            relationship = {"from": mon1["name"], "to": mon2["name"], "horizontal_gap": 0,
                            "vertical_gap": 0, "alignment": "unknown"}
            
            # Horizontal relationship
            if mon2["x"] >= mon1_right:
                relationship["horizontal_gap"] = mon2["x"] - mon1_right
                relationship["position"] = "right"
            elif mon1["x"] >= mon2_right:
                relationship["horizontal_gap"] = mon1["x"] - mon2_right
                relationship["position"] = "left"
            else:
                relationship["position"] = "overlapping_horizontal"
            
            # Vertical relationship
            if mon2["y"] >= mon1_bottom:
                relationship["vertical_gap"] = mon2["y"] - mon1_bottom
                relationship["vertical_position"] = "below"
            elif mon1["y"] >= mon2_bottom:
                relationship["vertical_gap"] = mon1["y"] - mon2_bottom
                relationship["vertical_position"] = "above"
            else:
                relationship["vertical_position"] = "overlapping_vertical"
            
            # Alignment check
            if abs(mon1["y"] - mon2["y"]) < 10:
                relationship["alignment"] = "top_aligned"
            elif abs(mon1_bottom - mon2_bottom) < 10:
                relationship["alignment"] = "bottom_aligned"
            elif abs((mon1["y"] + mon1["height"]/2) - (mon2["y"] + mon2["height"]/2)) < 10:
                relationship["alignment"] = "center_aligned"
            
            relationships.append(relationship)
    
    return {"layout": f"{len(monitors)}_monitors",
            "relationships": relationships}

async def get_monitor_corners(monitor: Dict) -> Dict:
    return {"top_left": (monitor["x"], monitor["y"]),
            "top_right": (monitor["x"] + monitor["width"], monitor["y"]),
            "bottom_left": (monitor["x"], monitor["y"] + monitor["height"]),
            "bottom_right": (monitor["x"] + monitor["width"], monitor["y"] + monitor["height"]),
            "center": (monitor["x"] + monitor["width"] // 2, monitor["y"] + monitor["height"] // 2)}

async def get_system_info() -> Dict:
    return {"os": platform.system(), "os_version": platform.version(), "os_release": platform.release(),
            "machine": platform.machine(), "processor": platform.processor(),
            "python_version": sys.version,
            "pyautogui_version": pyautogui.__version__ if hasattr(pyautogui, "__version__") else "unknown"}

async def get_current_mouse_position() -> Dict:
    pos = await asyncio.to_thread(pyautogui.position)
    monitors = await get_all_monitors_info()
    location = await find_monitor_at_position(pos[0], pos[1], monitors)
    
    return {"global_x": pos[0], "global_y": pos[1], "monitor_index": location.get("index"),
            "monitor_name": location.get("monitor"), "local_x": location.get("local_x"),
            "local_y": location.get("local_y"), "found": location.get("found", False)}

async def find_monitor_at_position(x: int, y: int, monitors: List[Dict]) -> Dict:
    for mon in monitors:
        if (mon["x"] <= x < mon["x"] + mon["width"] and
            mon["y"] <= y < mon["y"] + mon["height"]):
            return {"found": True, "monitor": mon["name"], "index": mon["index"],
                    "local_x": x - mon["x"], "local_y": y - mon["y"]}
    
    return {"found": False, "monitor": None, "index": None,
            "local_x": None, "local_y": None}


async def calculate_bridge_points(mon1: Dict, mon2: Dict) -> Dict:
    """
    Calculate bridge points between two monitors for safe cursor crossing.
    
    This finds:
    1. The common edge where monitors meet
    2. The center point of that edge
    3. Two waypoint positions (one in each monitor) near the edge
    
    Offsets are calculated as percentage of smallest resolution side:
    - Major offset (perpendicular to edge): 10% of smallest side
    - Minor offset (parallel to edge): 5% of smallest side
    
    Args:
        mon1: First monitor dictionary
        mon2: Second monitor dictionary
    
    Returns:
        Dictionary with bridge information including waypoints
    """
    
    # Calculate boundaries
    mon1_right = mon1["x"] + mon1["width"]
    mon1_bottom = mon1["y"] + mon1["height"]
    mon2_right = mon2["x"] + mon2["width"]
    mon2_bottom = mon2["y"] + mon2["height"]
    
    # Calculate offsets based on smallest resolution dimension
    min_dimension = min(
        mon1["width"], mon1["height"],
        mon2["width"], mon2["height"]
    )
    major_offset = int(min_dimension * 0.10)  # 10% for perpendicular
    minor_offset = int(min_dimension * 0.05)   # 5% for parallel to edge
    
    result = {"mon1_name": mon1["name"], "mon2_name": mon2["name"], "edge_type": None,
              "bridge_center": None, "mon1_waypoint": None, "mon2_waypoint": None,
              "orientation": None, "offsets": {"major": major_offset, "minor": minor_offset}}
    
    # Determine edge relationship and calculate bridge points
    
    # Case 1: Horizontal arrangement (left-right)
    # Constant axis: X coordinate at the joining edge
    # Variable axis: Y coordinate along the edge
    if mon1_right == mon2["x"]:  # mon2 is RIGHT of mon1
        result["orientation"] = "horizontal"
        result["edge_type"] = "mon1_right_to_mon2_left"
        
        # Find overlapping Y range
        overlap_top = max(mon1["y"], mon2["y"])
        overlap_bottom = min(mon1_bottom, mon2_bottom)
        
        if overlap_bottom > overlap_top:  # Valid overlap
            # Center Y of the overlap
            center_y = (overlap_top + overlap_bottom) // 2
            bridge_x = mon1_right  # X is constant at the edge
            
            result["bridge_center"] = (bridge_x, center_y)
            
            # Calculate Y offsets AWAY from overlap zone
            # mon1 waypoint: move toward mon1's safe interior (away from overlap zone)
            mon1_center_y = mon1["y"] + mon1["height"] // 2
            mon1_y_direction = -1 if mon1_center_y < center_y else 1
            mon1_waypoint_y = center_y + (mon1_y_direction * minor_offset)
            
            # mon2 waypoint: move toward mon2's safe interior (away from overlap zone)
            mon2_center_y = mon2["y"] + mon2["height"] // 2
            mon2_y_direction = -1 if mon2_center_y < center_y else 1
            mon2_waypoint_y = center_y + (mon2_y_direction * minor_offset)
            
            result["mon1_waypoint"] = (bridge_x - major_offset, mon1_waypoint_y)
            result["mon2_waypoint"] = (bridge_x + major_offset, mon2_waypoint_y)
    
    elif mon2_right == mon1["x"]:  # mon2 is LEFT of mon1
        result["orientation"] = "horizontal"
        result["edge_type"] = "mon2_right_to_mon1_left"
        
        overlap_top = max(mon1["y"], mon2["y"])
        overlap_bottom = min(mon1_bottom, mon2_bottom)
        
        if overlap_bottom > overlap_top:
            center_y = (overlap_top + overlap_bottom) // 2
            bridge_x = mon1["x"]
            
            result["bridge_center"] = (bridge_x, center_y)
            
            # Calculate Y offsets AWAY from overlap zone
            mon1_center_y = mon1["y"] + mon1["height"] // 2
            mon1_y_direction = -1 if mon1_center_y < center_y else 1
            mon1_waypoint_y = center_y + (mon1_y_direction * minor_offset)
            
            mon2_center_y = mon2["y"] + mon2["height"] // 2
            mon2_y_direction = -1 if mon2_center_y < center_y else 1
            mon2_waypoint_y = center_y + (mon2_y_direction * minor_offset)
            
            result["mon1_waypoint"] = (bridge_x + major_offset, mon1_waypoint_y)
            result["mon2_waypoint"] = (bridge_x - major_offset, mon2_waypoint_y)
    
    # Case 2: Vertical arrangement (top-bottom)
    # Constant axis: Y coordinate at the joining edge
    # Variable axis: X coordinate along the edge
    elif mon1_bottom == mon2["y"]:  # mon2 is BELOW mon1
        result["orientation"] = "vertical"
        result["edge_type"] = "mon1_bottom_to_mon2_top"
        
        # Find overlapping X range
        overlap_left = max(mon1["x"], mon2["x"])
        overlap_right = min(mon1_right, mon2_right)
        
        if overlap_right > overlap_left:
            center_x = (overlap_left + overlap_right) // 2
            bridge_y = mon1_bottom  # Y is constant at the edge
            
            result["bridge_center"] = (center_x, bridge_y)
            
            # Calculate X offsets AWAY from overlap zone
            mon1_center_x = mon1["x"] + mon1["width"] // 2
            mon1_x_direction = -1 if mon1_center_x < center_x else 1
            mon1_waypoint_x = center_x + (mon1_x_direction * minor_offset)
            
            mon2_center_x = mon2["x"] + mon2["width"] // 2
            mon2_x_direction = -1 if mon2_center_x < center_x else 1
            mon2_waypoint_x = center_x + (mon2_x_direction * minor_offset)
            
            result["mon1_waypoint"] = (mon1_waypoint_x, bridge_y - major_offset)
            result["mon2_waypoint"] = (mon2_waypoint_x, bridge_y + major_offset)
    
    elif mon2_bottom == mon1["y"]:  # mon2 is ABOVE mon1
        result["orientation"] = "vertical"
        result["edge_type"] = "mon2_bottom_to_mon1_top"
        
        overlap_left = max(mon1["x"], mon2["x"])
        overlap_right = min(mon1_right, mon2_right)
        
        if overlap_right > overlap_left:
            center_x = (overlap_left + overlap_right) // 2
            bridge_y = mon1["y"]
            
            result["bridge_center"] = (center_x, bridge_y)
            
            # Calculate X offsets AWAY from overlap zone
            mon1_center_x = mon1["x"] + mon1["width"] // 2
            mon1_x_direction = -1 if mon1_center_x < center_x else 1
            mon1_waypoint_x = center_x + (mon1_x_direction * minor_offset)
            
            mon2_center_x = mon2["x"] + mon2["width"] // 2
            mon2_x_direction = -1 if mon2_center_x < center_x else 1
            mon2_waypoint_x = center_x + (mon2_x_direction * minor_offset)
            
            result["mon1_waypoint"] = (mon1_waypoint_x, bridge_y + major_offset)
            result["mon2_waypoint"] = (mon2_waypoint_x, bridge_y - major_offset)
    
    # Case 3: Diagonal or complex arrangement
    else:
        result["orientation"] = "diagonal_or_separated"
        result["edge_type"] = "no_direct_edge"
        
        # For diagonal/separated monitors, use center-to-center approach
        mon1_center_x = mon1["x"] + mon1["width"] // 2
        mon1_center_y = mon1["y"] + mon1["height"] // 2
        mon2_center_x = mon2["x"] + mon2["width"] // 2
        mon2_center_y = mon2["y"] + mon2["height"] // 2
        
        # Midpoint between centers
        bridge_x = (mon1_center_x + mon2_center_x) // 2
        bridge_y = (mon1_center_y + mon2_center_y) // 2
        
        result["bridge_center"] = (bridge_x, bridge_y)
        
        # Waypoints: offset towards the bridge from each monitor center
        result["mon1_waypoint"] = (mon1_center_x + (bridge_x - mon1_center_x) // 3,
                                    mon1_center_y + (bridge_y - mon1_center_y) // 3)
        result["mon2_waypoint"] = (mon2_center_x + (bridge_x - mon2_center_x) // 3,
                                    mon2_center_y + (bridge_y - mon2_center_y) // 3)
    
    return result


async def calculate_all_bridge_points(monitors: List[Dict]) -> List[Dict]:
    """
    Calculate bridge points between all pairs of monitors.
    
    Returns list of bridge point dictionaries for each monitor pair.
    """
    if len(monitors) < 2:
        return []
    
    bridge_points = []
    
    for i, mon1 in enumerate(monitors):
        for j, mon2 in enumerate(monitors):
            if i >= j:  # Only calculate once per pair
                continue
            
            bridge = await calculate_bridge_points(mon1, mon2)
            bridge_points.append(bridge)
    
    return bridge_points

async def extract_complete_device_info(silent: bool = False) -> Dict:
    """Extract ALL device information"""
    
    if not silent:
        print("🔍 Extracting complete device information...")
        print()
    
    # Get monitors
    monitors = await get_all_monitors_info()
    if not silent:
        print(f"✅ Found {len(monitors)} monitor(s)")
    
    # Get boundaries
    boundaries = await calculate_monitor_boundaries(monitors)
    
    # Get layout analysis
    layout = await analyze_monitor_layout(monitors)
    
    # Get corners for each monitor
    monitor_corners = {}
    for mon in monitors:
        monitor_corners[mon["name"]] = await get_monitor_corners(mon)
    
    # Calculate bridge points between monitors
    bridge_points = await calculate_all_bridge_points(monitors)
    
    # Get system info
    system_info = await get_system_info()
    
    complete_info = {"timestamp": platform.node(), "system": system_info,
                     "monitors": {"count": len(monitors), "list": monitors, "corners": monitor_corners},
                     "virtual_desktop": boundaries, "layout": layout,
                     "bridge_points": bridge_points}
    
    return complete_info

async def print_device_info(info: Dict):
    """Pretty print device information"""
    
    print("=" * 80)
    print("📊 COMPLETE DEVICE INFORMATION")
    print("=" * 80)
    print()
    
    # System Info
    print("🖥️  SYSTEM INFORMATION")
    print("-" * 80)
    sys_info = info["system"]
    print(f"  OS: {sys_info['os']} {sys_info['os_release']}")
    print(f"  Machine: {sys_info['machine']}")
    print(f"  Processor: {sys_info['processor']}")
    print(f"  Python: {sys_info['python_version'].split()[0]}")
    print()
    
    # Virtual Desktop
    print("🖼️  VIRTUAL DESKTOP")
    print("-" * 80)
    vd = info["virtual_desktop"]
    print(f"  Total Size: {vd['width']}x{vd['height']}")
    print(f"  Boundaries: X[{vd['min_x']} to {vd['max_x']}], Y[{vd['min_y']} to {vd['max_y']}]")
    print()
    
    # Monitors
    print(f"🖥️  MONITORS ({info['monitors']['count']} detected)")
    print("-" * 80)
    
    for mon in info["monitors"]["list"]:
        print(f"\n  📺 Monitor {mon['index']}: {mon['name'].upper()}")
        print(f"     Resolution: {mon['width']}x{mon['height']}")
        print(f"     Position: ({mon['x']}, {mon['y']})")
        print(f"     Primary: {'Yes' if mon['is_primary'] else 'No'}")
        
        # Corners
        corners = info["monitors"]["corners"][mon["name"]]
        print(f"     Corners:")
        print(f"       Top-Left:     {corners['top_left']}")
        print(f"       Top-Right:    {corners['top_right']}")
        print(f"       Bottom-Left:  {corners['bottom_left']}")
        print(f"       Bottom-Right: {corners['bottom_right']}")
        print(f"       Center:       {corners['center']}")
        
        # Work area
        if "work_area" in mon:
            wa = mon["work_area"]
            print(f"     Work Area: {wa['width']}x{wa['height']} at ({wa['x']}, {wa['y']})")
    
    print()
    
    # Layout Analysis
    if len(info["monitors"]["list"]) > 1:
        print("📐 MONITOR LAYOUT ANALYSIS")
        print("-" * 80)
        for rel in info["layout"]["relationships"]:
            print(f"\n  {rel['from']} → {rel['to']}:")
            print(f"    Position: {rel.get('position', 'unknown')}")
            print(f"    Vertical: {rel.get('vertical_position', 'unknown')}")
            print(f"    Alignment: {rel.get('alignment', 'unknown')}")
            if rel.get('horizontal_gap', 0) > 0:
                print(f"    Horizontal Gap: {rel['horizontal_gap']}px")
            if rel.get('vertical_gap', 0) > 0:
                print(f"    Vertical Gap: {rel['vertical_gap']}px")
        print()
    
    # Bridge Points (for safe monitor crossing)
    if len(info["monitors"]["list"]) > 1 and info.get("bridge_points"):
        print("🌉 BRIDGE POINTS (for Safe Monitor Crossing)")
        print("-" * 80)
        for bridge in info["bridge_points"]:
            print(f"\n  🔗 {bridge['mon1_name'].upper()} ↔ {bridge['mon2_name'].upper()}")
            print(f"     Orientation: {bridge['orientation']}")
            print(f"     Edge Type: {bridge['edge_type']}")
            
            if bridge['bridge_center']:
                print(f"     Bridge Center: {bridge['bridge_center']}")
            
            if bridge['mon1_waypoint']:
                print(f"     Waypoint in {bridge['mon1_name']}: {bridge['mon1_waypoint']}")
            
            if bridge['mon2_waypoint']:
                print(f"     Waypoint in {bridge['mon2_name']}: {bridge['mon2_waypoint']}")
            
            offsets = bridge.get('offsets', {})
            if offsets:
                print(f"     Offsets: Major={offsets.get('major', 0)}px, Minor={offsets.get('minor', 0)}px")
        print()
    
    # Current Mouse Position
    print("🖱️  CURRENT MOUSE POSITION")
    print("-" * 80)
    mouse = info["current_mouse"]
    print(f"  Global Position: ({mouse['global_x']}, {mouse['global_y']})")
    if mouse.get("found"):
        print(f"  Monitor: {mouse['monitor_name']} (index {mouse['monitor_index']})")
        print(f"  Local Position: ({mouse['local_x']}, {mouse['local_y']})")
    else:
        print(f"  ⚠️  Mouse is outside all detected monitors!")
    print()
    
    print("=" * 80)

async def save_device_info(info: Dict, filename: str = "device_info.json"):
    """Save device info to JSON file"""
    # Convert tuple positions to lists for JSON serialization
    def convert_tuples(obj):
        if isinstance(obj, dict):
            return {k: convert_tuples(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_tuples(item) for item in obj]
        elif isinstance(obj, tuple):
            return list(obj)
        else:
            return obj
    
    info_serializable = convert_tuples(info)
    
    def write_file():
        with open(filename, 'w') as f:
            json.dump(info_serializable, f, indent=2)
    
    await asyncio.to_thread(write_file)
    print(f"💾 Device info saved to: {filename}")

async def main():
    """Main function"""
    try:
        # Extract all info
        info = await extract_complete_device_info()
        
        # Print formatted info
        await print_device_info(info)
        
        # Save to JSON
        await save_device_info(info)
        
        print("\n✅ Complete device information extracted successfully!")
        print("\nℹ️  This data can be used to configure your mouse control system")
        
    except Exception as e:
        print(f"\n❌ Error extracting device info: {e}")
        import traceback
        traceback.print_exc()


async def get_mouse_position_simple() -> Tuple[int, int]:
    """
    Simple function to get current mouse position (x, y)
    Returns just the coordinates as a tuple
    """
    pos = await asyncio.to_thread(pyautogui.position)
    return (pos.x, pos.y)


if __name__ == "__main__":
    asyncio.run(main())
