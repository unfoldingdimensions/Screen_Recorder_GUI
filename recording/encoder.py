"""FFmpeg encoder for real-time video encoding."""

import subprocess
import threading
import time
import os
from pathlib import Path
from typing import Optional, Tuple
import numpy as np


class FFmpegEncoder:
    """Handles FFmpeg encoding pipeline for video recording."""
    
    def __init__(self, output_path: str, width: int, height: int, fps: int = 30,
                 bitrate: str = "8M", audio_enabled: bool = True, sample_rate: int = 48000):
        """
        Initialize FFmpeg encoder.
        
        Args:
            output_path: Path to output video file
            width: Video width in pixels
            height: Video height in pixels
            fps: Frames per second
            bitrate: Video bitrate (e.g., "8M" for 8 Mbps)
            audio_enabled: Whether to include audio
            sample_rate: Audio sample rate
        """
        self.output_path = output_path
        self.width = width
        self.height = height
        self.fps = fps
        self.bitrate = bitrate
        self.audio_enabled = audio_enabled
        self.sample_rate = sample_rate
        
        self.process: Optional[subprocess.Popen] = None
        self.video_pipe: Optional[subprocess.Popen] = None
        self.audio_pipe: Optional[subprocess.Popen] = None
        
        self.is_encoding = False
        self.start_time: Optional[float] = None
        
        # Find FFmpeg executable
        self.ffmpeg_path = self._find_ffmpeg()
        if not self.ffmpeg_path:
            raise RuntimeError("FFmpeg not found. Please install FFmpeg and add it to PATH.")
    
    def _find_ffmpeg(self) -> Optional[str]:
        """Find FFmpeg executable."""
        # Check common locations
        possible_paths = [
            "ffmpeg",
            "ffmpeg.exe",
            str(Path(__file__).parent.parent / "ffmpeg" / "ffmpeg.exe"),
            str(Path(__file__).parent.parent / "ffmpeg.exe"),
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run(
                    [path, "-version"],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    return path
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        return None
    
    def _build_ffmpeg_command(self) -> list:
        """Build FFmpeg command for encoding."""
        cmd = [
            self.ffmpeg_path,
            "-y",  # Overwrite output file
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{self.width}x{self.height}",
            "-pix_fmt", "rgb24",
            "-r", str(self.fps),
            "-i", "pipe:0",  # Read video from stdin
        ]
        
        if self.audio_enabled:
            # Note: Audio input is currently disabled - audio mixing needs to be implemented
            # For now, we'll record video-only and add audio support later
            # cmd.extend([
            #     "-f", "s16le",
            #     "-ac", "2",  # Stereo
            #     "-ar", str(self.sample_rate),
            #     "-i", "pipe:3",  # Read audio from file descriptor 3
            # ])
            pass
        
        # Video encoding settings
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "ultrafast",  # Fast encoding for real-time
            "-tune", "zerolatency",
            "-b:v", self.bitrate,
            "-pix_fmt", "yuv420p",
        ])
        
        # Audio encoding settings
        # Temporarily disable audio until proper audio pipe is implemented
        cmd.append("-an")  # No audio for now
        
        # Output format
        # Note: +faststart requires a second pass which can cause issues if interrupted
        # We'll write the file normally and it should still be playable
        cmd.extend([
            self.output_path
        ])
        
        return cmd
    
    def start_encoding(self) -> bool:
        """
        Start FFmpeg encoding process.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.is_encoding:
            return True
        
        try:
            cmd = self._build_ffmpeg_command()
            
            # For simplicity, we'll use a single stdin for video
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            self.is_encoding = True
            self.start_time = time.time()
            return True
            
        except Exception as e:
            print(f"Error starting FFmpeg encoder: {e}")
            self.stop_encoding()
            return False
    
    def write_video_frame(self, frame: np.ndarray) -> bool:
        """
        Write a video frame to encoder.
        
        Args:
            frame: RGB frame as numpy array (height, width, 3)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_encoding or not self.process or not self.process.stdin:
            return False
        
        try:
            # Ensure frame is correct size and format
            if frame.shape[:2] != (self.height, self.width):
                # Resize if needed
                from PIL import Image
                img = Image.fromarray(frame)
                img = img.resize((self.width, self.height))
                frame = np.array(img)
            
            # Ensure frame is uint8 and contiguous
            if frame.dtype != np.uint8:
                frame = frame.astype(np.uint8)
            if not frame.flags['C_CONTIGUOUS']:
                frame = np.ascontiguousarray(frame)
            
            # Write raw RGB24 frame (height x width x 3 bytes)
            frame_bytes = frame.tobytes()
            if len(frame_bytes) != self.width * self.height * 3:
                print(f"Warning: Frame size mismatch. Expected {self.width * self.height * 3}, got {len(frame_bytes)}")
                return False
            
            self.process.stdin.write(frame_bytes)
            self.process.stdin.flush()
            return True
            
        except (BrokenPipeError, OSError, ValueError) as e:
            # ValueError occurs if stdin is closed during write
            if "closed file" not in str(e).lower():
                print(f"Error writing video frame: {e}")
            return False
    
    def write_audio_chunk(self, audio_data: np.ndarray) -> bool:
        """
        Write an audio chunk to encoder.
        
        Args:
            audio_data: Audio samples as int16 numpy array
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_encoding or not self.audio_enabled:
            return False
        
        if not self.process or not self.process.stdin:
            return False
        
        try:
            # For simplicity, we'll mix audio in the recorder and write combined
            # This is a simplified version - actual implementation may need separate audio pipe
            # For now, audio will be handled by mixing in recorder.py
            return True
            
        except Exception as e:
            print(f"Error writing audio chunk: {e}")
            return False
    
    def stop_encoding(self) -> bool:
        """
        Stop encoding and finalize video file.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_encoding:
            return True
        
        self.is_encoding = False
        
        try:
            if self.process:
                # Close stdin to signal end of input
                if self.process.stdin:
                    self.process.stdin.close()
                
                # Wait for encoding to finish (with longer timeout for finalization)
                # FFmpeg needs time to finalize the MP4 file (write moov atom)
                try:
                    # Read stderr to prevent buffer overflow
                    import threading
                    def read_stderr():
                        if self.process.stderr:
                            try:
                                while True:
                                    line = self.process.stderr.readline()
                                    if not line:
                                        break
                            except Exception:
                                pass
                    
                    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
                    stderr_thread.start()
                    
                    # Wait with longer timeout (30 seconds should be enough for most recordings)
                    self.process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    print("FFmpeg encoding timeout, trying graceful shutdown...")
                    # Try to close stdin gracefully first
                    if self.process.stdin:
                        try:
                            self.process.stdin.close()
                        except Exception:
                            pass
                    # Give it a bit more time
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        print("Force terminating FFmpeg...")
                        self.process.terminate()
                        self.process.wait(timeout=5)
                
                # Check for errors
                if self.process.returncode != 0:
                    stderr = self.process.stderr.read().decode() if self.process.stderr else ""
                    print(f"FFmpeg encoding error (return code {self.process.returncode}): {stderr}")
                    return False
                
                self.process = None
            
            return True
            
        except Exception as e:
            print(f"Error stopping encoder: {e}")
            return False
    
    def get_encoding_time(self) -> float:
        """Get elapsed encoding time in seconds."""
        if self.start_time:
            return time.time() - self.start_time
        return 0.0

    @staticmethod
    def merge_audio_video(video_path: str, audio_path: str, output_path: str) -> bool:
        """
        Merge video and audio files using FFmpeg.
        
        Args:
            video_path: Path to video file
            audio_path: Path to audio file
            output_path: Path to output file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find FFmpeg (can reuse the class method if we make it static or instantiate locally)
            # For simplicity, we'll implement a simple finder here or assume it's valid if instance worked
            ffmpeg_path = "ffmpeg"
            possible_paths = [
                "ffmpeg.exe",
                str(Path(__file__).parent.parent / "ffmpeg" / "ffmpeg.exe"),
                str(Path(__file__).parent.parent / "ffmpeg.exe"),
            ]
            
            for path in possible_paths:
                if Path(path).exists() or os.path.exists(path):
                    ffmpeg_path = path
                    break
            
            cmd = [
                ffmpeg_path,
                "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",  # Copy video stream (already encoded)
                "-c:a", "aac",   # Encode audio to AAC
                "-shortest",     # Match duration of shortest stream
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True
            )
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg merge error: {e.stderr.decode()}")
            return False
        except Exception as e:
            print(f"Error merging files: {e}")
            return False
