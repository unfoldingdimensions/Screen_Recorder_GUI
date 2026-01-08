"""Configuration management for saving and loading user preferences."""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any


class Config:
    """Manages application configuration and user preferences."""
    
    DEFAULT_CONFIG = {
        "recording_mode": "full_screen",  # full_screen, window, region
        "output_directory": str(Path.home() / "Videos" / "ScreenRecordings"),
        "video_quality": "high",  # low, medium, high, custom
        "resolution": "1080p",  # 720p, 1080p, 1440p, 4k, custom
        "fps": 30,  # 30 or 60
        "bitrate": "8M",  # Video bitrate
        "audio_system_enabled": True,
        "audio_microphone_enabled": True,
        "audio_system_device": None,  # Auto-detect if None
        "audio_microphone_device": None,  # Auto-detect if None
        "countdown_enabled": False,
        "countdown_seconds": 3,
        "window_handle": None,  # Last selected window handle
    }
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to config file. Defaults to user config directory.
        """
        if config_file is None:
            config_dir = Path.home() / ".screen_recorder"
            config_dir.mkdir(exist_ok=True)
            config_file = str(config_dir / "config.json")
        
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> None:
        """Load configuration from file, using defaults if file doesn't exist."""
        self.config = self.DEFAULT_CONFIG.copy()
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config: {e}. Using defaults.")
    
    def save(self) -> None:
        """Save current configuration to file."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            print(f"Error saving config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self.config[key] = value
    
    def get_output_directory(self) -> str:
        """Get output directory, creating it if it doesn't exist."""
        output_dir = Path(self.get("output_directory", self.DEFAULT_CONFIG["output_directory"]))
        output_dir.mkdir(parents=True, exist_ok=True)
        return str(output_dir)
    
    def get_video_settings(self) -> Dict[str, Any]:
        """Get video quality settings as a dictionary."""
        quality = self.get("video_quality", "high")
        fps = self.get("fps", 30)
        resolution = self.get("resolution", "1080p")
        bitrate = self.get("bitrate", "8M")
        
        # Resolution mapping
        resolution_map = {
            "720p": (1280, 720),
            "1080p": (1920, 1080),
            "1440p": (2560, 1440),
            "4k": (3840, 2160),
        }
        
        width, height = resolution_map.get(resolution, (1920, 1080))
        
        # Quality presets for bitrate
        quality_bitrates = {
            "low": "2M",
            "medium": "5M",
            "high": "8M",
            "custom": bitrate,
        }
        
        actual_bitrate = quality_bitrates.get(quality, bitrate)
        
        return {
            "width": width,
            "height": height,
            "fps": fps,
            "bitrate": actual_bitrate,
            "quality": quality,
        }

