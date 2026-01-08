"""Settings dialog for quality and audio configuration."""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QPushButton, QGroupBox, QCheckBox,
                             QSpinBox, QLineEdit, QFormLayout)
from PyQt6.QtCore import Qt
from typing import Optional


class SettingsDialog(QDialog):
    """Dialog for configuring recording settings."""
    
    def __init__(self, parent=None):
        """Initialize settings dialog."""
        super().__init__(parent)
        self.setWindowTitle("Recording Settings")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Video Quality Settings
        video_group = QGroupBox("Video Quality")
        video_layout = QFormLayout()
        
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Low", "Medium", "High", "Custom"])
        video_layout.addRow("Quality Preset:", self.quality_combo)
        
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["720p", "1080p", "1440p", "4k", "Custom"])
        video_layout.addRow("Resolution:", self.resolution_combo)
        
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["24 FPS", "30 FPS", "60 FPS"])
        video_layout.addRow("Frame Rate:", self.fps_combo)
        
        self.bitrate_edit = QLineEdit()
        self.bitrate_edit.setPlaceholderText("e.g., 8M")
        video_layout.addRow("Bitrate:", self.bitrate_edit)
        
        video_group.setLayout(video_layout)
        layout.addWidget(video_group)
        
        # Audio Settings
        audio_group = QGroupBox("Audio Sources")
        audio_layout = QVBoxLayout()
        
        self.system_audio_check = QCheckBox("Record System Audio")
        self.system_audio_check.setChecked(True)
        audio_layout.addWidget(self.system_audio_check)
        
        self.microphone_check = QCheckBox("Record Microphone")
        self.microphone_check.setChecked(True)
        audio_layout.addWidget(self.microphone_check)
        
        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)
        
        # Countdown Settings
        countdown_group = QGroupBox("Countdown")
        countdown_layout = QHBoxLayout()
        
        self.countdown_check = QCheckBox("Enable countdown before recording")
        countdown_layout.addWidget(self.countdown_check)
        
        self.countdown_spin = QSpinBox()
        self.countdown_spin.setMinimum(1)
        self.countdown_spin.setMaximum(10)
        self.countdown_spin.setValue(3)
        self.countdown_spin.setSuffix(" seconds")
        countdown_layout.addWidget(self.countdown_spin)
        
        countdown_group.setLayout(countdown_layout)
        layout.addWidget(countdown_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # Connect quality preset change
        self.quality_combo.currentTextChanged.connect(self._on_quality_changed)
    
    def _on_quality_changed(self, quality: str):
        """Update bitrate based on quality preset."""
        if quality == "Low":
            self.bitrate_edit.setText("2M")
        elif quality == "Medium":
            self.bitrate_edit.setText("5M")
        elif quality == "High":
            self.bitrate_edit.setText("8M")
        # Custom: leave bitrate as is
    
    def get_settings(self) -> dict:
        """
        Get current settings as dictionary.
        
        Returns:
            Dictionary with settings
        """
        quality = self.quality_combo.currentText().lower()
        resolution = self.resolution_combo.currentText().lower()
        fps_text = self.fps_combo.currentText()
        # Parse FPS from text (e.g., "24 FPS" -> 24)
        if "24" in fps_text:
            fps = 24
        elif "30" in fps_text:
            fps = 30
        else:
            fps = 60
        bitrate = self.bitrate_edit.text() or "8M"
        
        return {
            "quality": quality,
            "resolution": resolution,
            "fps": fps,
            "bitrate": bitrate,
            "system_audio_enabled": self.system_audio_check.isChecked(),
            "microphone_enabled": self.microphone_check.isChecked(),
            "countdown_enabled": self.countdown_check.isChecked(),
            "countdown_seconds": self.countdown_spin.value(),
        }
    
    def set_settings(self, settings: dict) -> None:
        """
        Set dialog settings from dictionary.
        
        Args:
            settings: Dictionary with settings
        """
        quality = settings.get("video_quality", "high")
        self.quality_combo.setCurrentText(quality.capitalize())
        
        resolution = settings.get("resolution", "1080p")
        self.resolution_combo.setCurrentText(resolution)
        
        fps = settings.get("fps", 30)
        self.fps_combo.setCurrentText(f"{fps} FPS")
        
        bitrate = settings.get("bitrate", "8M")
        self.bitrate_edit.setText(bitrate)
        
        self.system_audio_check.setChecked(settings.get("audio_system_enabled", True))
        self.microphone_check.setChecked(settings.get("audio_microphone_enabled", True))
        
        self.countdown_check.setChecked(settings.get("countdown_enabled", False))
        self.countdown_spin.setValue(settings.get("countdown_seconds", 3))

