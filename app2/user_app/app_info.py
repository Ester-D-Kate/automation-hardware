"""
Application Information Extractor
Gets all USER applications with visible UI windows
FILTERS: Based on window properties (position/coordinates)
GROUPS: Windows apps by actual title (Settings, Task Manager, etc.)
NO HARDCODING - Pure dynamic detection!
"""

import win32gui
import win32process
import win32con
import win32api
import psutil
import os
import re
from collections import defaultdict


def get_friendly_app_name(process_name, exe_path=None, window_title=None):
    """
    Get friendly application name dynamically.
    For Windows system apps with generic metadata, use window title instead!
    NO HARDCODING - works for ANY app!
    """
    
    # Try to get friendly name from executable metadata
    friendly_name = None
    
    if exe_path and os.path.exists(exe_path):
        try:
            # Get string file info (language and codepage)
            lang, codepage = win32api.GetFileVersionInfo(exe_path, '\\VarFileInfo\\Translation')[0]
            
            # Try ProductName first (most apps use this)
            try:
                product_name = win32api.GetFileVersionInfo(
                    exe_path, 
                    f'\\StringFileInfo\\{lang:04x}{codepage:04x}\\ProductName'
                )
                if product_name and len(product_name.strip()) > 0:
                    friendly_name = product_name.strip()
            except:
                pass
            
            # Fallback to FileDescription
            if not friendly_name:
                try:
                    file_desc = win32api.GetFileVersionInfo(
                        exe_path, 
                        f'\\StringFileInfo\\{lang:04x}{codepage:04x}\\FileDescription'
                    )
                    if file_desc and len(file_desc.strip()) > 0:
                        friendly_name = file_desc.strip()
                except:
                    pass
                    
        except Exception:
            pass
    
    # SPECIAL CASE: If metadata is generic "Microsoft Windows Operating System"
    # Use the window title instead (Settings, Task Manager, etc.)
    if friendly_name and "Microsoft" in friendly_name and "Windows" in friendly_name and "Operating System" in friendly_name:
        if window_title and window_title not in ['Program Manager', 'Windows Input Experience']:
            return window_title  # Use window title as app name!
    
    # If we got a good name from metadata, return it
    if friendly_name:
        return friendly_name
    
    # Final fallback: Clean up process name intelligently
    clean_name = process_name.replace('.exe', '').replace('_', ' ')
    
    # Handle camelCase (like ApplicationFrameHost → Application Frame Host)
    clean_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean_name)
    
    # Capitalize each word
    clean_name = clean_name.title()
    
    return clean_name


def has_valid_window_position(window_info):
    """
    Check if window has valid UI position (visible or minimized with restore position).
    Returns True if this is a REAL UI app, False if background process.
    
    Logic:
    - Desktop background (Program Manager) = spans entire virtual desktop = FILTER
    - Window with valid position = REAL APP
    - Minimized with restored position = REAL APP
    - No position at all = BACKGROUND PROCESS = FILTER
    """
    
    # Rule 1: Desktop background check
    if window_info['title'] == 'Program Manager':
        return False  # FILTER OUT
    
    # Rule 2: Open window - must have valid position
    if not window_info['is_minimized']:
        if window_info['position'] and window_info['title_bar']:
            return True  # REAL APP!
        return False  # No position = background process
    
    # Rule 3: Minimized window - must have restored position
    if window_info['is_minimized']:
        if window_info['restored_position']:
            return True  # REAL APP (minimized but can be restored)
        return False  # No restore position = background process
    
    # Default: filter out
    return False


def get_window_rect(hwnd):
    """Get window position and size"""
    try:
        rect = win32gui.GetWindowRect(hwnd)
        return {
            'left': rect[0],
            'top': rect[1],
            'right': rect[2],
            'bottom': rect[3],
            'width': rect[2] - rect[0],
            'height': rect[3] - rect[1]
        }
    except:
        return None


def get_window_title_bar_rect(hwnd):
    """Get title bar rectangle for dragging"""
    try:
        rect = win32gui.GetWindowRect(hwnd)
        
        # Title bar center point for dragging
        center_x = (rect[0] + rect[2]) // 2
        center_y = rect[1] + 17
        
        return {
            'center_x': center_x,
            'center_y': center_y,
            'left': rect[0],
            'right': rect[2],
            'top': rect[1],
            'height': 35
        }
    except:
        return None


def is_window_on_monitor(window_rect, monitor):
    """Check if window is primarily on this monitor"""
    if not window_rect:
        return False
    
    window_center_x = (window_rect['left'] + window_rect['right']) // 2
    window_center_y = (window_rect['top'] + window_rect['bottom']) // 2
    
    return (monitor['x'] <= window_center_x < monitor['x'] + monitor['width'] and
            monitor['y'] <= window_center_y < monitor['y'] + monitor['height'])


def get_window_info(hwnd, monitors):
    """Get complete window information including position and friendly app name"""
    try:
        if not win32gui.IsWindowVisible(hwnd):
            return None
        
        title = win32gui.GetWindowText(hwnd)
        if not title or len(title) < 1:
            return None
        
        # Get window state
        placement = win32gui.GetWindowPlacement(hwnd)
        show_cmd = placement[1]
        
        is_minimized = (show_cmd == win32con.SW_SHOWMINIMIZED)
        is_maximized = (show_cmd == win32con.SW_SHOWMAXIMIZED)
        
        # Get restored position for minimized windows
        restored_position = None
        if is_minimized:
            restored_rect = placement[4]
            restored_position = {
                'left': restored_rect[0],
                'top': restored_rect[1],
                'right': restored_rect[2],
                'bottom': restored_rect[3],
                'width': restored_rect[2] - restored_rect[0],
                'height': restored_rect[3] - restored_rect[1]
            }
        
        # Get window position
        window_rect = get_window_rect(hwnd)
        title_bar_rect = get_window_title_bar_rect(hwnd)
        
        if not window_rect:
            return None
        
        # Find which monitor this window is on
        monitor_index = -1
        monitor_name = "unknown"
        
        if not is_minimized:
            for idx, monitor in enumerate(monitors):
                if is_window_on_monitor(window_rect, monitor):
                    monitor_index = idx
                    monitor_name = monitor.get('name', f'monitor_{idx}')
                    break
        else:
            # For minimized windows, use restored position
            if restored_position:
                for idx, monitor in enumerate(monitors):
                    if is_window_on_monitor(restored_position, monitor):
                        monitor_index = idx
                        monitor_name = monitor.get('name', f'monitor_{idx}')
                        break
        
        # Get process info and friendly app name
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            process_name = process.name()
            exe_path = process.exe()
            
            # Get friendly app name DYNAMICALLY (pass window title for Windows apps)
            friendly_name = get_friendly_app_name(process_name, exe_path, title)
            
        except:
            process_name = "unknown"
            friendly_name = "Unknown Application"
        
        return {
            'hwnd': hwnd,
            'title': title,
            'process_name': process_name,
            'app_name': friendly_name,
            'is_minimized': is_minimized,
            'is_maximized': is_maximized,
            'monitor_index': monitor_index,
            'monitor_name': monitor_name,
            'position': window_rect if not is_minimized else None,
            'title_bar': title_bar_rect if not is_minimized else None,
            'restored_position': restored_position if is_minimized else None
        }
    except Exception:
        return None


def get_all_windows(monitors):
    """Get all visible windows with their information"""
    windows = []
    
    def enum_callback(hwnd, _):
        window_info = get_window_info(hwnd, monitors)
        if window_info:
            # FILTER: Only keep windows with valid UI positions
            if has_valid_window_position(window_info):
                windows.append(window_info)
        return True
    
    win32gui.EnumWindows(enum_callback, None)
    return windows


def get_applications_info(monitors):
    """
    Get all USER applications with visible UI windows.
    
    FILTERING: Based on window coordinates
    - Keeps apps with valid positions (visible or minimized with restore)
    - Filters background processes without UI
    
    GROUPING: By app name (not process name)
    - Windows apps with same title (Settings, Task Manager) group together
    - Chrome windows group together
    - NO HARDCODING!
    
    Args:
        monitors: List of monitor dictionaries from device_info
    
    Returns:
        Dictionary with user applications grouped by app name
    """
    
    # Get all windows (already filtered by position)
    all_windows = get_all_windows(monitors)
    
    # Group windows by APP NAME (not process name)
    # This groups Settings windows together, Task Manager together, etc.
    apps_dict = defaultdict(list)
    for window in all_windows:
        apps_dict[window['app_name']].append(window)
    
    # Build applications list
    applications = []
    active_app = None
    
    for app_name, windows in apps_dict.items():
        if not windows:
            continue
        
        # Get process name from first window (for reference)
        process_name = windows[0]['process_name']
        
        # Count window states
        open_windows = sum(1 for w in windows if not w['is_minimized'])
        minimized_windows = sum(1 for w in windows if w['is_minimized'])
        
        # Check if this app has the active window
        is_active = False
        try:
            foreground_hwnd = win32gui.GetForegroundWindow()
            is_active = any(w['hwnd'] == foreground_hwnd for w in windows)
        except:
            pass
        
        # Format window info
        windows_info = []
        for window in windows:
            win_info = {
                'title': window['title'],
                'is_minimized': window['is_minimized'],
                'is_maximized': window['is_maximized'],
                'monitor_index': window['monitor_index']
            }
            
            if window['is_minimized']:
                if window['restored_position']:
                    win_info['restored_position'] = window['restored_position']
            else:
                if window['position']:
                    win_info['position'] = window['position']
                if window['title_bar']:
                    win_info['title_bar'] = window['title_bar']
            
            windows_info.append(win_info)
        
        app_info = {
            'app_name': app_name,
            'process_name': process_name,
            'total_windows': len(windows),
            'open_windows': open_windows,
            'minimized_windows': minimized_windows,
            'is_active': is_active,
            'all_windows': windows_info
        }
        
        applications.append(app_info)
        
        if is_active:
            active_app = app_name
    
    # Sort: active first, then by number of windows
    applications.sort(key=lambda x: (not x['is_active'], -x['total_windows']))
    
    return {
        'total_apps': len(applications),
        'total_windows': sum(app['total_windows'] for app in applications),
        'active_app': active_app,
        'applications': applications
    }
