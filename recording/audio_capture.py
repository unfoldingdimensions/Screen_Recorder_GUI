"""Audio capture module for system audio and microphone recording."""

import time
import threading
import queue
import numpy as np
from typing import Optional, List, Tuple
import sounddevice as sd


class AudioCapture:
    """Handles audio capture from system audio and microphone."""
    
    # Audio settings
    SAMPLE_RATE = 48000
    CHANNELS = 2  # Stereo
    SAMPLE_WIDTH = 2  # 16-bit
    CHUNK_SIZE = 4800  # ~100ms at 48kHz
    
    def __init__(self, system_audio_enabled: bool = True, 
                 microphone_enabled: bool = True,
                 system_device: Optional[int] = None,
                 microphone_device: Optional[int] = None):
        """
        Initialize audio capture.
        
        Args:
            system_audio_enabled: Enable system audio capture
            microphone_enabled: Enable microphone capture
            system_device: System audio device index (None for default)
            microphone_device: Microphone device index (None for default)
        """
        self.system_audio_enabled = system_audio_enabled
        self.microphone_enabled = microphone_enabled
        self.system_device = system_device
        self.microphone_device = microphone_device
        
        self.is_capturing = False
        self.audio_queue: queue.Queue = queue.Queue(maxsize=50)
        
        self.system_stream: Optional[sd.InputStream] = None
        self.microphone_stream: Optional[sd.InputStream] = None
        
        self.system_thread: Optional[threading.Thread] = None
        self.microphone_thread: Optional[threading.Thread] = None
    
    def _get_audio_devices(self) -> List[dict]:
        """Get list of available audio devices."""
        return sd.query_devices()
    
    def _find_loopback_device(self) -> Optional[int]:
        """Find a loopback device for system audio capture."""
        devices = self._get_audio_devices()
        hostapis = sd.query_hostapis()
        
        # On Windows, look for WASAPI loopback devices
        for i, device in enumerate(devices):
            # Get hostapi index and look up its name
            hostapi_idx = device.get('hostapi', -1)
            if hostapi_idx >= 0 and hostapi_idx < len(hostapis):
                hostapi_name = hostapis[hostapi_idx].get('name', '').lower()
                if 'wasapi' in hostapi_name:
                    # Check if it's a loopback device (output device used as input)
                    if device['max_input_channels'] == 0 and device['max_output_channels'] > 0:
                        # Try to use this as loopback
                        try:
                            # Test if we can open it
                            test_stream = sd.InputStream(
                                device=i,
                                channels=min(2, device['max_output_channels']),
                                samplerate=self.SAMPLE_RATE,
                                dtype='float32'
                            )
                            test_stream.close()
                            return i
                        except Exception:
                            continue
        
        return None
    
    def _system_audio_callback(self, indata, frames, time_info, status):
        """Callback for system audio capture."""
        if status:
            print(f"System audio status: {status}")
        
        if self.is_capturing:
            # Convert float32 to int16
            audio_data = (indata * 32767).astype(np.int16)
            timestamp = time.time()
            
            try:
                self.audio_queue.put_nowait(("system", timestamp, audio_data))
            except queue.Full:
                # Drop oldest if queue is full
                try:
                    self.audio_queue.get_nowait()
                    self.audio_queue.put_nowait(("system", timestamp, audio_data))
                except queue.Empty:
                    pass
    
    def _microphone_callback(self, indata, frames, time_info, status):
        """Callback for microphone capture."""
        if status:
            print(f"Microphone status: {status}")
        
        if self.is_capturing:
            # Convert float32 to int16
            audio_data = (indata * 32767).astype(np.int16)
            timestamp = time.time()
            
            try:
                self.audio_queue.put_nowait(("microphone", timestamp, audio_data))
            except queue.Full:
                # Drop oldest if queue is full
                try:
                    self.audio_queue.get_nowait()
                    self.audio_queue.put_nowait(("microphone", timestamp, audio_data))
                except queue.Empty:
                    pass
    
    def start_capture(self) -> bool:
        """
        Start audio capture.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.is_capturing:
            return True
        
        try:
            # Start system audio capture if enabled
            if self.system_audio_enabled:
                loopback_device = self.system_device if self.system_device is not None else self._find_loopback_device()
                
                if loopback_device is not None:
                    try:
                        self.system_stream = sd.InputStream(
                            device=loopback_device,
                            channels=self.CHANNELS,
                            samplerate=self.SAMPLE_RATE,
                            dtype='float32',
                            blocksize=self.CHUNK_SIZE,
                            callback=self._system_audio_callback
                        )
                        self.system_stream.start()
                    except Exception as e:
                        print(f"Failed to start system audio capture: {e}")
                        print("System audio capture may not be available. Continuing without it.")
                        self.system_audio_enabled = False
                else:
                    print("No loopback device found. System audio capture disabled.")
                    self.system_audio_enabled = False
            
            # Start microphone capture if enabled
            if self.microphone_enabled:
                try:
                    self.microphone_stream = sd.InputStream(
                        device=self.microphone_device,
                        channels=self.CHANNELS,
                        samplerate=self.SAMPLE_RATE,
                        dtype='float32',
                        blocksize=self.CHUNK_SIZE,
                        callback=self._microphone_callback
                    )
                    self.microphone_stream.start()
                except Exception as e:
                    print(f"Failed to start microphone capture: {e}")
                    print("Microphone capture may not be available. Continuing without it.")
                    self.microphone_enabled = False
            
            self.is_capturing = True
            return True
            
        except Exception as e:
            print(f"Error starting audio capture: {e}")
            self.stop_capture()
            return False
    
    def stop_capture(self) -> None:
        """Stop audio capture."""
        self.is_capturing = False
        
        if self.system_stream:
            try:
                self.system_stream.stop()
                self.system_stream.close()
            except Exception:
                pass
            self.system_stream = None
        
        if self.microphone_stream:
            try:
                self.microphone_stream.stop()
                self.microphone_stream.close()
            except Exception:
                pass
            self.microphone_stream = None
    
    def get_audio_chunk(self, timeout: float = 0.1) -> Optional[Tuple[str, float, np.ndarray]]:
        """
        Get the next audio chunk.
        
        Args:
            timeout: Maximum time to wait for audio
        
        Returns:
            Tuple of (source, timestamp, audio_data) or None
            source is "system" or "microphone"
        """
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_audio_levels(self) -> Tuple[float, float]:
        """
        Get current audio levels for visualization.
        
        Returns:
            Tuple of (system_level, microphone_level) as RMS values (0-1)
        """
        system_level = 0.0
        microphone_level = 0.0
        
        # Sample recent audio from queue
        chunks_to_check = min(5, self.audio_queue.qsize())
        
        for _ in range(chunks_to_check):
            try:
                source, _, audio_data = self.audio_queue.get_nowait()
                if audio_data is not None and len(audio_data) > 0:
                    # Calculate RMS
                    rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2)) / 32767.0
                    
                    if source == "system":
                        system_level = max(system_level, rms)
                    elif source == "microphone":
                        microphone_level = max(microphone_level, rms)
            except (queue.Empty, ValueError):
                break
        
        return (system_level, microphone_level)
    
    @staticmethod
    def list_audio_devices() -> List[dict]:
        """List all available audio devices."""
        return sd.query_devices()

