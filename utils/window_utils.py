"""Window enumeration and selection utilities for Windows."""

import ctypes
from ctypes import wintypes
from typing import List, Dict, Optional, Tuple
import win32gui
import win32con


class WindowInfo:
    """Information about a window."""
    
    def __init__(self, handle: int, title: str, class_name: str, rect: Tuple[int, int, int, int]):
        self.handle = handle
        self.title = title
        self.class_name = class_name
        self.rect = rect  # (left, top, right, bottom)
    
    @property
    def width(self) -> int:
        """Get window width."""
        return self.rect[2] - self.rect[0]
    
    @property
    def height(self) -> int:
        """Get window height."""
        return self.rect[3] - self.rect[1]
    
    @property
    def is_visible(self) -> bool:
        """Check if window is visible."""
        return win32gui.IsWindowVisible(self.handle)
    
    def __str__(self) -> str:
        title = self.title if self.title else f"Window {self.handle}"
        return f"{title} ({self.width}x{self.height})"


def enum_windows_callback(hwnd: int, windows: List[WindowInfo]) -> bool:
    """Callback function for enumerating windows."""
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        
        # Skip certain system windows
        if title or class_name:
            try:
                rect = win32gui.GetWindowRect(hwnd)
                window_info = WindowInfo(hwnd, title, class_name, rect)
                windows.append(window_info)
            except Exception:
                pass
    
    return True


def get_all_windows() -> List[WindowInfo]:
    """
    Get all visible windows.
    
    Returns:
        List of WindowInfo objects for visible windows.
    """
    windows: List[WindowInfo] = []
    win32gui.EnumWindows(enum_windows_callback, windows)
    return windows


def get_window_by_handle(handle: int) -> Optional[WindowInfo]:
    """
    Get window information by handle.
    
    Args:
        handle: Window handle (HWND)
    
    Returns:
        WindowInfo object or None if window not found.
    """
    try:
        if win32gui.IsWindow(handle):
            title = win32gui.GetWindowText(handle)
            class_name = win32gui.GetClassName(handle)
            rect = win32gui.GetWindowRect(handle)
            return WindowInfo(handle, title, class_name, rect)
    except Exception:
        pass
    return None


def get_window_rect(handle: int) -> Optional[Tuple[int, int, int, int]]:
    """
    Get window rectangle coordinates.
    
    Args:
        handle: Window handle (HWND)
    
    Returns:
        Tuple of (left, top, right, bottom) or None if failed.
    """
    try:
        if win32gui.IsWindow(handle):
            return win32gui.GetWindowRect(handle)
    except Exception:
        pass
    return None


def is_window_valid(handle: int) -> bool:
    """
    Check if a window handle is valid.
    
    Args:
        handle: Window handle (HWND)
    
    Returns:
        True if window is valid and visible, False otherwise.
    """
    try:
        return win32gui.IsWindow(handle) and win32gui.IsWindowVisible(handle)
    except Exception:
        return False


def get_foreground_window() -> Optional[WindowInfo]:
    """
    Get the currently active/foreground window.
    
    Returns:
        WindowInfo for foreground window or None.
    """
    try:
        handle = win32gui.GetForegroundWindow()
        if handle:
            return get_window_by_handle(handle)
    except Exception:
        pass
    return None


def bring_window_to_front(handle: int) -> bool:
    """
    Bring a window to the front.
    
    Args:
        handle: Window handle (HWND)
    
    Returns:
        True if successful, False otherwise.
    """
    try:
        if win32gui.IsWindow(handle):
            win32gui.ShowWindow(handle, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(handle)
            return True
    except Exception:
        pass
    return False

