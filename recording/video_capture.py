"""Video capture module for screen recording using mss."""

import time
import threading
import queue
from typing import Optional, Tuple, Callable
import mss
import numpy as np
from PIL import Image
import win32gui  # type: ignore[import-untyped]  # pywin32 module, IDE may not resolve


class VideoCapture:
    """Handles screen capture for recording."""
    
    def __init__(self, mode: str = "full_screen", region: Optional[Tuple[int, int, int, int]] = None, 
                 window_handle: Optional[int] = None, fps: int = 30):
        """
        Initialize video capture.
        
        Args:
            mode: Recording mode - "full_screen", "window", or "region"
            region: For region mode, tuple of (left, top, width, height)
            window_handle: For window mode, the window handle (HWND)
            fps: Target frames per second
        """
        self.mode = mode
        self.region = region
        self.window_handle = window_handle
        self.fps = fps
        self.frame_time = 1.0 / fps
        
        # MSS instance - will be created when needed
        self.sct: Optional[mss.mss] = None
        self.capture_rect = None
        self.is_capturing = False
        self.capture_thread: Optional[threading.Thread] = None
        self.frame_queue: queue.Queue = queue.Queue(maxsize=30)  # Buffer up to 30 frames
        
        # For direct capture mode (no threading)
        self._last_frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        
        # Setup capture region using a temporary mss instance
        temp_sct = mss.mss()
        self._setup_capture_region(temp_sct)
    
    def _setup_capture_region(self, sct: Optional[mss.mss] = None) -> None:
        """
        Setup the capture region based on mode.
        
        Args:
            sct: Optional mss instance to use (for initialization)
        """
        if sct is None:
            sct = mss.mss()
        
        if self.mode == "full_screen":
            # Capture primary monitor
            monitor = sct.monitors[1]  # monitors[0] is all monitors, [1] is primary
            self.capture_rect = {
                "top": monitor["top"],
                "left": monitor["left"],
                "width": monitor["width"],
                "height": monitor["height"]
            }
        
        elif self.mode == "window" and self.window_handle:
            # Get window rectangle
            try:
                rect = win32gui.GetWindowRect(self.window_handle)
                left, top, right, bottom = rect
                width = right - left
                height = bottom - top
                
                self.capture_rect = {
                    "top": top,
                    "left": left,
                    "width": width,
                    "height": height
                }
            except Exception as e:
                print(f"Error getting window rect: {e}")
                # Fallback to full screen
                monitor = sct.monitors[1]
                self.capture_rect = {
                    "top": monitor["top"],
                    "left": monitor["left"],
                    "width": monitor["width"],
                    "height": monitor["height"]
                }
        
        elif self.mode == "region" and self.region:
            # Region is (left, top, width, height)
            left, top, width, height = self.region
            self.capture_rect = {
                "top": top,
                "left": left,
                "width": width,
                "height": height
            }
        
        else:
            # Default to full screen
            monitor = sct.monitors[1]
            self.capture_rect = {
                "top": monitor["top"],
                "left": monitor["left"],
                "width": monitor["width"],
                "height": monitor["height"]
            }
    
    def start_capture(self) -> None:
        """Start capturing frames in a separate thread."""
        if self.is_capturing:
            return
        
        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
    
    def stop_capture(self) -> None:
        """Stop capturing frames."""
        self.is_capturing = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
    
    def _capture_loop(self) -> None:
        """Main capture loop running in separate thread."""
        # Create mss instance in this thread (required for thread-local storage)
        self.sct = mss.mss()
        
        last_capture_time = time.time()
        
        while self.is_capturing:
            current_time = time.time()
            elapsed = current_time - last_capture_time
            
            # Maintain target FPS
            if elapsed >= self.frame_time:
                try:
                    # Capture screen
                    screenshot = self.sct.grab(self.capture_rect)
                    
                    # Convert to numpy array (BGRA format from mss)
                    frame = np.array(screenshot)
                    
                    # Convert BGRA to RGB for FFmpeg
                    # mss returns BGRA, we need RGB (remove alpha, swap B and R)
                    frame_rgb = frame[:, :, [2, 1, 0]]  # BGRA -> RGB (B->R, G->G, R->B, drop A)
                    
                    # Ensure it's uint8 and contiguous
                    if frame_rgb.dtype != np.uint8:
                        frame_rgb = frame_rgb.astype(np.uint8)
                    if not frame_rgb.flags['C_CONTIGUOUS']:
                        frame_rgb = np.ascontiguousarray(frame_rgb)
                    
                    # Add timestamp
                    timestamp = time.time()
                    
                    # Put frame in queue (non-blocking, drop if full)
                    try:
                        self.frame_queue.put_nowait((timestamp, frame_rgb))
                    except queue.Full:
                        # Drop oldest frame if queue is full
                        try:
                            self.frame_queue.get_nowait()
                            self.frame_queue.put_nowait((timestamp, frame_rgb))
                        except queue.Empty:
                            pass
                    
                    last_capture_time = current_time
                    
                except Exception as e:
                    print(f"Error capturing frame: {e}")
                    time.sleep(0.01)  # Small delay on error
            
            else:
                # Sleep to maintain FPS
                sleep_time = self.frame_time - elapsed
                time.sleep(min(sleep_time, 0.01))
    
    def get_frame(self, timeout: float = 0.1) -> Optional[Tuple[float, np.ndarray]]:
        """
        Get the next captured frame.
        
        Args:
            timeout: Maximum time to wait for a frame
        
        Returns:
            Tuple of (timestamp, frame_array) or None if no frame available
        """
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_resolution(self) -> Tuple[int, int]:
        """
        Get the resolution of the capture area.
        
        Returns:
            Tuple of (width, height)
        """
        if self.capture_rect:
            return (self.capture_rect["width"], self.capture_rect["height"])
        return (1920, 1080)  # Default
    
    def update_region(self, region: Tuple[int, int, int, int]) -> None:
        """
        Update the capture region (for region mode).
        
        Args:
            region: Tuple of (left, top, width, height)
        """
        self.region = region
        # Use existing sct if available, otherwise create temporary one
        sct = self.sct if self.sct else mss.mss()
        self._setup_capture_region(sct)
    
    def update_window(self, window_handle: int) -> None:
        """
        Update the window to capture (for window mode).
        
        Args:
            window_handle: Window handle (HWND)
        """
        self.window_handle = window_handle
        # Use existing sct if available, otherwise create temporary one
        sct = self.sct if self.sct else mss.mss()
        self._setup_capture_region(sct)
    
    def capture_frame_direct(self) -> Optional[np.ndarray]:
        """
        Capture a single frame directly (synchronous).
        
        This method is thread-safe and creates its own mss instance if needed.
        Use this for precise timing control in the recording loop.
        
        Returns:
            RGB frame as numpy array, or None if capture failed
        """
        try:
            # Create mss instance if not exists (thread-local, so create per call for safety)
            with mss.mss() as sct:
                if not self.capture_rect:
                    return None
                
                # Capture screen
                screenshot = sct.grab(self.capture_rect)
                
                # Convert to numpy array (BGRA format from mss)
                frame = np.array(screenshot)
                
                # Convert BGRA to RGB for FFmpeg
                frame_rgb = frame[:, :, [2, 1, 0]]  # BGRA -> RGB
                
                # Ensure it's uint8 and contiguous
                if frame_rgb.dtype != np.uint8:
                    frame_rgb = frame_rgb.astype(np.uint8)
                if not frame_rgb.flags['C_CONTIGUOUS']:
                    frame_rgb = np.ascontiguousarray(frame_rgb)
                
                return frame_rgb
                
        except Exception as e:
            print(f"Error in direct capture: {e}")
            return None

