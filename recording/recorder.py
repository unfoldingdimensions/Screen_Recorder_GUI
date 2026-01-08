import time
import threading
import wave
import os
from enum import Enum
from pathlib import Path
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
        
        # Temporary files for separate streams
        self.temp_video_path: Optional[str] = None
        self.temp_audio_path: Optional[str] = None
        self.wave_file: Optional[wave.Wave_write] = None
        
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
        
        # Frame buffering for duplication
        self._last_frame: Optional[np.ndarray] = None
    
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
            # Check audio availability
            audio_enabled = self.audio_capture is not None and (
                self.audio_capture.system_audio_enabled or 
                self.audio_capture.microphone_enabled
            )
            
            # Setup temporary files
            output_dir = Path(self.output_path).parent
            timestamp = int(time.time())
            self.temp_video_path = str(output_dir / f".temp_video_{timestamp}.mp4")
            
            if audio_enabled:
                self.temp_audio_path = str(output_dir / f".temp_audio_{timestamp}.wav")
                try:
                    self.wave_file = wave.open(self.temp_audio_path, 'wb')
                    self.wave_file.setnchannels(AudioCapture.CHANNELS)
                    self.wave_file.setsampwidth(AudioCapture.SAMPLE_WIDTH)
                    self.wave_file.setframerate(AudioCapture.SAMPLE_RATE)
                except Exception as e:
                    print(f"Failed to open audio file: {e}")
                    audio_enabled = False
                    self.temp_audio_path = None
                    self.wave_file = None
            
            # Initialize encoder with temp video path
            self.encoder = FFmpegEncoder(
                output_path=self.temp_video_path,
                width=self.width,
                height=self.height,
                fps=self.fps,
                bitrate=self.bitrate,
                audio_enabled=False,  # Audio handled separately by Recorder
                sample_rate=AudioCapture.SAMPLE_RATE
            )
            
            if not self.encoder.start_encoding():
                print("Failed to start encoder")
                return False
            
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
            self._last_frame = None
            
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
        if self.recording_thread:
            self.recording_thread.join(timeout=5.0)
            self.recording_thread = None
        
        # Stop video encoder (finalizes temp video file)
        if self.encoder:
            # Optionally fill remaining frames if stops early?
            # For now, just stop.
            self.encoder.stop_encoding()
            self.encoder = None
        
        # Stop audio capture
        if self.audio_capture:
            self.audio_capture.stop_capture()
            
        # Close audio file
        if self.wave_file:
            try:
                self.wave_file.close()
            except Exception as e:
                print(f"Error closing audio file: {e}")
            self.wave_file = None
        
        # Merge files
        success = True
        try:
            if self.temp_video_path and os.path.exists(self.temp_video_path):
                if self.temp_audio_path and os.path.exists(self.temp_audio_path) and os.path.getsize(self.temp_audio_path) > 100:
                    # Merge video and audio
                    print("Merging video and audio...")
                    if not FFmpegEncoder.merge_audio_video(self.temp_video_path, self.temp_audio_path, self.output_path):
                        print("Failed to merge files. Moving video only.")
                        # Fallback: just move video file
                        if os.path.exists(self.output_path):
                            os.remove(self.output_path)
                        os.rename(self.temp_video_path, self.output_path)
                        success = False
                else:
                    # Video only (rename temp to output)
                    print("Saving video only (no audio recorded or file too small)...")
                    if os.path.exists(self.output_path):
                        os.remove(self.output_path)
                    os.rename(self.temp_video_path, self.output_path)
            else:
                print("Error: Temporary video file not found.")
                success = False
                
        except Exception as e:
            print(f"Error finalizing recording: {e}")
            success = False
        finally:
            # Cleanup temp files
            if self.temp_video_path and os.path.exists(self.temp_video_path):
                try:
                    os.remove(self.temp_video_path)
                except Exception:
                    pass
            if self.temp_audio_path and os.path.exists(self.temp_audio_path):
                try:
                    os.remove(self.temp_audio_path)
                except Exception:
                    pass
            
            self.temp_video_path = None
            self.temp_audio_path = None
        
        if self.on_state_changed:
            self.on_state_changed(self.state)
        
        return success
    
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
        """Main recording loop using separate thread."""
        frame_interval = 1.0 / self.fps
        
        while self.state != RecordingState.IDLE:
            if self.state == RecordingState.PAUSED:
                time.sleep(0.1)
                continue
            
            current_time = time.time()
            
            # 1. Video Frame Handling (CFR Logic)
            if self.video_capture and self.encoder:
                elapsed = current_time - self.start_time - self.total_pause_duration
                expected_frames = int(elapsed * self.fps)
                
                # If we are behind schedule
                if self.frames_recorded < expected_frames:
                    frames_needed = expected_frames - self.frames_recorded
                    
                    # Try to get a fresh frame
                    frame = self.video_capture.capture_frame_direct()
                    
                    if frame is not None:
                        self._last_frame = frame
                    
                    # Determine which frame to write
                    # Use fresh frame if available, otherwise reuse last frame
                    write_frame = frame if frame is not None else self._last_frame
                    
                    if write_frame is not None:
                        # Write as many frames as needed to catch up
                        # Limit to a reasonable burst to prevent infinite loops if something goes wrong
                        # e.g. if we are 100 frames behind, it might take too long to write all 100 now.
                        # But we must write them to maintain sync.
                        frames_to_write = min(frames_needed, 5) # Process max 5 at a time to keep UI responsive? 
                        # Actually for CFR we really should catch up, or we lose time. 
                        # Let's try to catch up completely but check for stop signal.
                        
                        for _ in range(frames_needed):
                            if self.state == RecordingState.IDLE:
                                break
                                
                            if self.encoder.write_video_frame(write_frame):
                                self.frames_recorded += 1
                            else:
                                break
            
            # 2. Audio Handling
            if self.audio_capture and self.wave_file:
                # Same audio logic as before...
                audio_chunks = []
                while len(audio_chunks) < 5:
                    chunk = self.audio_capture.get_audio_chunk(timeout=0.001)
                    if chunk:
                        audio_chunks.append(chunk)
                    else:
                        break
                
                if audio_chunks:
                    mixed_audio = None
                    for source, timestamp, audio_data in audio_chunks:
                        if mixed_audio is None:
                            mixed_audio = audio_data.copy()
                        else:
                            min_len = min(len(mixed_audio), len(audio_data))
                            mixed_audio[:min_len] = (
                                mixed_audio[:min_len].astype(np.int32) + 
                                audio_data[:min_len].astype(np.int32)
                            ) // 2
                            mixed_audio = mixed_audio.astype(np.int16)
                    
                    if mixed_audio is not None:
                        try:
                            self.wave_file.writeframes(mixed_audio.tobytes())
                            self.audio_chunks_recorded += 1
                        except Exception as e:
                            print(f"Error writing audio frames: {e}")
            
            # 3. Sleep logic
            # Calculate when the NEXT frame is due
            next_frame_index = self.frames_recorded + 1
            next_frame_time_offset = next_frame_index * frame_interval
            target_time = self.start_time + self.total_pause_duration + next_frame_time_offset
            
            sleep_time = target_time - time.time()
            if sleep_time > 0:
                time.sleep(min(sleep_time, 0.05)) # Sleep in small chunks to stay responsive

    
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

