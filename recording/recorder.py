"""Main recording engine coordinating video and audio capture."""

import time
import threading
from enum import Enum
from typing import Optional, Callable, Tuple
import numpy as np
from .video_capture import VideoCapture
from .audio_capture import AudioCapture
from .encoder import FFmpegEncoder


class RecordingState(Enum):
    """Recording state enumeration."""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"


class Recorder:
    """Main recording engine coordinating all capture and encoding."""
    
    def __init__(self, output_path: str, width: int = 1920, height: int = 1080, 
                 fps: int = 30, bitrate: str = "8M",
                 video_capture: Optional[VideoCapture] = None,
                 audio_capture: Optional[AudioCapture] = None):
        """
        Initialize recorder.
        
        Args:
            output_path: Path to output video file
            width: Video width
            height: Video height
            fps: Frames per second
            bitrate: Video bitrate
            video_capture: VideoCapture instance (created if None)
            audio_capture: AudioCapture instance (created if None)
        """
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps
        self.bitrate = bitrate
        
        self.video_capture = video_capture
        self.audio_capture = audio_capture
        self.encoder: Optional[FFmpegEncoder] = None
        
        self.state = RecordingState.IDLE
        self.recording_thread: Optional[threading.Thread] = None
        
        # Statistics
        self.frames_recorded = 0
        self.audio_chunks_recorded = 0
        self.start_time: Optional[float] = None
        self.pause_time: Optional[float] = None
        self.total_pause_duration = 0.0
        
        # Callbacks
        self.on_state_changed: Optional[Callable[[RecordingState], None]] = None
        self.on_progress: Optional[Callable[[float], None]] = None  # Duration in seconds
        
        # Audio mixing
        self.audio_buffer: list = []
        self.audio_buffer_lock = threading.Lock()
    
    def set_video_capture(self, video_capture: VideoCapture) -> None:
        """Set the video capture instance."""
        self.video_capture = video_capture
        if video_capture:
            self.width, self.height = video_capture.get_resolution()
    
    def set_audio_capture(self, audio_capture: AudioCapture) -> None:
        """Set the audio capture instance."""
        self.audio_capture = audio_capture
    
    def start_recording(self) -> bool:
        """
        Start recording.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.state != RecordingState.IDLE:
            return False
        
        if not self.video_capture:
            print("Error: Video capture not initialized")
            return False
        
        try:
            # Initialize encoder
            audio_enabled = self.audio_capture is not None and (
                self.audio_capture.system_audio_enabled or 
                self.audio_capture.microphone_enabled
            )
            
            self.encoder = FFmpegEncoder(
                output_path=self.output_path,
                width=self.width,
                height=self.height,
                fps=self.fps,
                bitrate=self.bitrate,
                audio_enabled=audio_enabled,
                sample_rate=AudioCapture.SAMPLE_RATE
            )
            
            if not self.encoder.start_encoding():
                print("Failed to start encoder")
                return False
            
            # Note: We use direct capture in the recording loop for precise timing
            # Don't start the async capture thread
            # self.video_capture.start_capture()
            
            # Start audio capture
            if self.audio_capture:
                if not self.audio_capture.start_capture():
                    print("Warning: Audio capture failed to start, continuing without audio")
            
            # Start recording thread
            self.state = RecordingState.RECORDING
            self.start_time = time.time()
            self.total_pause_duration = 0.0
            self.frames_recorded = 0
            self.audio_chunks_recorded = 0
            
            self.recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
            self.recording_thread.start()
            
            if self.on_state_changed:
                self.on_state_changed(self.state)
            
            return True
            
        except Exception as e:
            print(f"Error starting recording: {e}")
            self.stop_recording()
            return False
    
    def stop_recording(self) -> bool:
        """
        Stop recording and finalize video file.
        
        Returns:
            True if stopped successfully, False otherwise
        """
        if self.state == RecordingState.IDLE:
            return True
        
        # Signal recording thread to stop
        self.state = RecordingState.IDLE
        
        # Wait for recording thread to finish BEFORE closing encoder
        # This prevents race condition where thread tries to write to closed pipe
        if self.recording_thread:
            self.recording_thread.join(timeout=5.0)
            self.recording_thread = None
        
        # Now it's safe to stop the encoder
        if self.encoder:
            self.encoder.stop_encoding()
            self.encoder = None
        
        # Stop audio capture
        if self.audio_capture:
            self.audio_capture.stop_capture()
        
        if self.on_state_changed:
            self.on_state_changed(self.state)
        
        return True
    
    def pause_recording(self) -> bool:
        """
        Pause recording.
        
        Returns:
            True if paused successfully, False otherwise
        """
        if self.state != RecordingState.RECORDING:
            return False
        
        self.state = RecordingState.PAUSED
        self.pause_time = time.time()
        
        if self.on_state_changed:
            self.on_state_changed(self.state)
        
        return True
    
    def resume_recording(self) -> bool:
        """
        Resume recording.
        
        Returns:
            True if resumed successfully, False otherwise
        """
        if self.state != RecordingState.PAUSED:
            return False
        
        if self.pause_time:
            self.total_pause_duration += time.time() - self.pause_time
            self.pause_time = None
        
        self.state = RecordingState.RECORDING
        
        if self.on_state_changed:
            self.on_state_changed(self.state)
        
        return True
    
    def _recording_loop(self) -> None:
        """Main recording loop running in separate thread."""
        frame_interval = 1.0 / self.fps
        next_frame_time = time.time()
        
        # Audio mixing
        audio_samples_per_frame = int(AudioCapture.SAMPLE_RATE / self.fps)
        
        while self.state != RecordingState.IDLE:
            if self.state == RecordingState.PAUSED:
                time.sleep(0.1)
                # Reset timing after pause
                next_frame_time = time.time()
                continue
            
            current_time = time.time()
            
            # Capture and write video frame at precise intervals
            if self.video_capture and self.encoder:
                if current_time >= next_frame_time:
                    # Capture frame directly (synchronous, precise timing)
                    frame = self.video_capture.capture_frame_direct()
                    
                    if frame is not None:
                        # Write frame to encoder
                        if self.encoder.write_video_frame(frame):
                            self.frames_recorded += 1
                    
                    # Schedule next frame at exact interval (prevents drift)
                    next_frame_time += frame_interval
                    
                    # If we're running behind, catch up but don't try to make up lost frames
                    if next_frame_time < current_time:
                        next_frame_time = current_time + frame_interval
                else:
                    # Sleep until next frame time
                    sleep_time = next_frame_time - current_time
                    if sleep_time > 0:
                        time.sleep(min(sleep_time, 0.01))
            
            # Handle audio (simplified - mix system and microphone)
            if self.audio_capture and self.encoder:
                # Collect audio chunks
                audio_chunks = []
                while len(audio_chunks) < 3:  # Get a few chunks
                    chunk = self.audio_capture.get_audio_chunk(timeout=0.01)
                    if chunk:
                        audio_chunks.append(chunk)
                    else:
                        break
                
                # Mix audio if we have chunks
                if audio_chunks:
                    # Simple mixing: combine system and microphone
                    mixed_audio = None
                    for source, timestamp, audio_data in audio_chunks:
                        if mixed_audio is None:
                            mixed_audio = audio_data.copy()
                        else:
                            # Mix by averaging (simple approach)
                            min_len = min(len(mixed_audio), len(audio_data))
                            mixed_audio[:min_len] = (
                                mixed_audio[:min_len].astype(np.int32) + 
                                audio_data[:min_len].astype(np.int32)
                            ) // 2
                            mixed_audio = mixed_audio.astype(np.int16)
                    
                    if mixed_audio is not None:
                        # Note: Actual audio writing to FFmpeg would go here
                        # For now, we'll handle it in a simplified way
                        self.audio_chunks_recorded += 1
            
            # Update progress
            if self.start_time and self.on_progress:
                elapsed = current_time - self.start_time - self.total_pause_duration
                if self.pause_time:
                    elapsed -= (current_time - self.pause_time)
                self.on_progress(elapsed)
            
            # Frame rate pacing is handled in the video frame writing section above
    
    def get_duration(self) -> float:
        """
        Get current recording duration in seconds.
        
        Returns:
            Duration in seconds
        """
        if not self.start_time:
            return 0.0
        
        current_time = time.time()
        elapsed = current_time - self.start_time - self.total_pause_duration
        
        if self.pause_time:
            elapsed -= (current_time - self.pause_time)
        
        return max(0.0, elapsed)
    
    def get_statistics(self) -> dict:
        """
        Get recording statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "state": self.state.value,
            "duration": self.get_duration(),
            "frames_recorded": self.frames_recorded,
            "audio_chunks_recorded": self.audio_chunks_recorded,
            "fps": self.fps,
            "resolution": f"{self.width}x{self.height}",
        }

