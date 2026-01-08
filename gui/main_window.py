"""Main application window for the screen recorder."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QRadioButton, QButtonGroup,
                             QGroupBox, QFileDialog, QMessageBox, QComboBox,
                             QProgressBar, QStatusBar)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont

from recording.recorder import Recorder, RecordingState
from recording.video_capture import VideoCapture
from recording.audio_capture import AudioCapture
from gui.region_selector import RegionSelector
from gui.settings_dialog import SettingsDialog
from utils.config import Config
from utils.window_utils import get_all_windows, WindowInfo


class CountdownThread(QThread):
    """Thread for countdown before recording."""
    
    countdown_update = pyqtSignal(int)
    finished = pyqtSignal()
    
    def __init__(self, seconds: int):
        """Initialize countdown thread."""
        super().__init__()
        self.seconds = seconds
    
    def run(self):
        """Run countdown."""
        for i in range(self.seconds, 0, -1):
            self.countdown_update.emit(i)
            self.msleep(1000)
        self.finished.emit()


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        """Initialize main window."""
        super().__init__()
        self.setWindowTitle("Screen Recorder")
        self.setMinimumSize(500, 600)
        
        # Configuration
        self.config = Config()
        
        # Recording components
        self.recorder: Optional[Recorder] = None
        self.video_capture: Optional[VideoCapture] = None
        self.audio_capture: Optional[AudioCapture] = None
        self.selected_window: Optional[WindowInfo] = None
        self.selected_region: Optional[tuple] = None
        
        # UI
        self._setup_ui()
        self._load_settings()
        
        # Timer for updating UI
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_ui)
        self.update_timer.start(100)  # Update every 100ms
        
        # Countdown
        self.countdown_thread: Optional[CountdownThread] = None
        # countdown_label is initialized in _setup_ui()
    
    def _setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Screen Recorder")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Recording Mode Selection
        mode_group = QGroupBox("Recording Mode")
        mode_layout = QVBoxLayout()
        
        self.mode_group = QButtonGroup()
        self.full_screen_radio = QRadioButton("Full Screen")
        self.window_radio = QRadioButton("Window")
        self.region_radio = QRadioButton("Custom Region")
        
        self.mode_group.addButton(self.full_screen_radio, 0)
        self.mode_group.addButton(self.window_radio, 1)
        self.mode_group.addButton(self.region_radio, 2)
        
        mode_layout.addWidget(self.full_screen_radio)
        mode_layout.addWidget(self.window_radio)
        mode_layout.addWidget(self.region_radio)
        
        # Window selection combo
        self.window_combo = QComboBox()
        self.window_combo.setEnabled(False)
        self.window_combo.currentIndexChanged.connect(self._on_window_selected)
        mode_layout.addWidget(self.window_combo)
        
        self.window_radio.toggled.connect(lambda checked: self.window_combo.setEnabled(checked))
        
        # Region selection button
        self.region_button = QPushButton("Select Region")
        self.region_button.setEnabled(False)
        self.region_button.clicked.connect(self._select_region)
        mode_layout.addWidget(self.region_button)
        
        self.region_radio.toggled.connect(lambda checked: self.region_button.setEnabled(checked))
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Quality Settings
        quality_group = QGroupBox("Quality Settings")
        quality_layout = QVBoxLayout()
        
        self.quality_label = QLabel("Quality: High | Resolution: 1080p | FPS: 30")
        quality_layout.addWidget(self.quality_label)
        
        self.settings_button = QPushButton("Settings...")
        self.settings_button.clicked.connect(self._open_settings)
        quality_layout.addWidget(self.settings_button)
        
        quality_group.setLayout(quality_layout)
        layout.addWidget(quality_group)
        
        # Audio Settings
        audio_group = QGroupBox("Audio")
        audio_layout = QVBoxLayout()
        
        self.audio_label = QLabel("System Audio: ✓ | Microphone: ✓")
        audio_layout.addWidget(self.audio_label)
        
        audio_group.setLayout(audio_layout)
        layout.addWidget(audio_group)
        
        # Recording Controls
        control_group = QGroupBox("Controls")
        control_layout = QVBoxLayout()
        
        # Timer display
        self.timer_label = QLabel("00:00:00")
        timer_font = QFont()
        timer_font.setPointSize(24)
        timer_font.setBold(True)
        self.timer_label.setFont(timer_font)
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        control_layout.addWidget(self.timer_label)
        
        # Countdown label (hidden by default)
        self.countdown_label = QLabel()
        countdown_font = QFont()
        countdown_font.setPointSize(48)
        countdown_font.setBold(True)
        self.countdown_label.setFont(countdown_font)
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setStyleSheet("color: red;")
        self.countdown_label.hide()
        control_layout.addWidget(self.countdown_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Recording")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.start_button.clicked.connect(self._start_recording)
        button_layout.addWidget(self.start_button)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self._pause_recording)
        button_layout.addWidget(self.pause_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.stop_button.clicked.connect(self._stop_recording)
        button_layout.addWidget(self.stop_button)
        
        control_layout.addLayout(button_layout)
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Output path
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output:"))
        self.output_label = QLabel()
        self.output_label.setWordWrap(True)
        output_layout.addWidget(self.output_label, 1)
        layout.addLayout(output_layout)
        
        layout.addStretch()
        
        # Status bar
        self.statusBar().showMessage("Ready to record")
        
        # Load windows
        self._refresh_windows()
    
    def _load_settings(self):
        """Load settings from config."""
        mode = self.config.get("recording_mode", "full_screen")
        if mode == "full_screen":
            self.full_screen_radio.setChecked(True)
        elif mode == "window":
            self.window_radio.setChecked(True)
        elif mode == "region":
            self.region_radio.setChecked(True)
        
        # Update quality label
        video_settings = self.config.get_video_settings()
        quality = self.config.get("video_quality", "high").capitalize()
        resolution = self.config.get("resolution", "1080p")
        fps = self.config.get("fps", 30)
        self.quality_label.setText(f"Quality: {quality} | Resolution: {resolution} | FPS: {fps}")
        
        # Update audio label
        system_enabled = self.config.get("audio_system_enabled", True)
        mic_enabled = self.config.get("audio_microphone_enabled", True)
        system_text = "✓" if system_enabled else "✗"
        mic_text = "✓" if mic_enabled else "✗"
        self.audio_label.setText(f"System Audio: {system_text} | Microphone: {mic_text}")
    
    def _refresh_windows(self):
        """Refresh the list of available windows."""
        self.window_combo.clear()
        windows = get_all_windows()
        for window in windows:
            if window.title:  # Only show windows with titles
                self.window_combo.addItem(str(window), window.handle)
    
    def _on_window_selected(self, index: int):
        """Handle window selection."""
        if index >= 0:
            handle = self.window_combo.itemData(index)
            if handle:
                from utils.window_utils import get_window_by_handle
                self.selected_window = get_window_by_handle(handle)
                self.config.set("window_handle", handle)
    
    def _select_region(self):
        """Open region selector."""
        selector = RegionSelector(self)
        selector.region_selected.connect(self._on_region_selected)
        selector.cancelled.connect(lambda: self.statusBar().showMessage("Region selection cancelled", 2000))
        selector.show()
    
    def _on_region_selected(self, left: int, top: int, width: int, height: int):
        """Handle region selection."""
        self.selected_region = (left, top, width, height)
        self.statusBar().showMessage(f"Region selected: {width}x{height} at ({left}, {top})", 3000)
    
    def _open_settings(self):
        """Open settings dialog."""
        dialog = SettingsDialog(self)
        current_settings = {
            "video_quality": self.config.get("video_quality", "high"),
            "resolution": self.config.get("resolution", "1080p"),
            "fps": self.config.get("fps", 30),
            "bitrate": self.config.get("bitrate", "8M"),
            "audio_system_enabled": self.config.get("audio_system_enabled", True),
            "audio_microphone_enabled": self.config.get("audio_microphone_enabled", True),
            "countdown_enabled": self.config.get("countdown_enabled", False),
            "countdown_seconds": self.config.get("countdown_seconds", 3),
        }
        dialog.set_settings(current_settings)
        
        if dialog.exec():
            settings = dialog.get_settings()
            self.config.set("video_quality", settings["quality"])
            self.config.set("resolution", settings["resolution"])
            self.config.set("fps", settings["fps"])
            self.config.set("bitrate", settings["bitrate"])
            self.config.set("audio_system_enabled", settings["system_audio_enabled"])
            self.config.set("audio_microphone_enabled", settings["microphone_enabled"])
            self.config.set("countdown_enabled", settings["countdown_enabled"])
            self.config.set("countdown_seconds", settings["countdown_seconds"])
            self.config.save()
            
            self._load_settings()
    
    def _start_recording(self):
        """Start recording."""
        # Determine recording mode
        if self.full_screen_radio.isChecked():
            mode = "full_screen"
            self.config.set("recording_mode", "full_screen")
        elif self.window_radio.isChecked():
            if not self.selected_window:
                QMessageBox.warning(self, "No Window Selected", "Please select a window to record.")
                return
            mode = "window"
            self.config.set("recording_mode", "window")
        else:  # region
            if not self.selected_region:
                QMessageBox.warning(self, "No Region Selected", "Please select a region to record.")
                return
            mode = "region"
            self.config.set("recording_mode", "region")
        
        self.config.save()
        
        # Get output path
        output_dir = self.config.get_output_directory()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_path = Path(output_dir) / f"ScreenRecording_{timestamp}.mp4"
        self.output_label.setText(str(output_path))
        
        # Get video settings
        video_settings = self.config.get_video_settings()
        
        # Create video capture
        window_handle = self.selected_window.handle if self.selected_window else None
        self.video_capture = VideoCapture(
            mode=mode,
            region=self.selected_region,
            window_handle=window_handle,
            fps=video_settings["fps"]
        )
        
        # Create audio capture
        self.audio_capture = AudioCapture(
            system_audio_enabled=self.config.get("audio_system_enabled", True),
            microphone_enabled=self.config.get("audio_microphone_enabled", True)
        )
        
        # Create recorder
        self.recorder = Recorder(
            output_path=str(output_path),
            width=video_settings["width"],
            height=video_settings["height"],
            fps=video_settings["fps"],
            bitrate=video_settings["bitrate"],
            video_capture=self.video_capture,
            audio_capture=self.audio_capture
        )
        self.recorder.on_state_changed = self._on_recording_state_changed
        self.recorder.on_progress = self._on_recording_progress
        
        # Check for countdown
        if self.config.get("countdown_enabled", False):
            countdown_seconds = self.config.get("countdown_seconds", 3)
            self._start_countdown(countdown_seconds)
        else:
            self._actually_start_recording()
    
    def _start_countdown(self, seconds: int):
        """Start countdown before recording."""
        self.countdown_label.setText(str(seconds))
        self.countdown_label.show()
        self.start_button.setEnabled(False)
        
        self.countdown_thread = CountdownThread(seconds)
        self.countdown_thread.countdown_update.connect(self._on_countdown_update)
        self.countdown_thread.finished.connect(self._on_countdown_finished)
        self.countdown_thread.start()
    
    def _on_countdown_update(self, remaining: int):
        """Update countdown display."""
        self.countdown_label.setText(str(remaining))
    
    def _on_countdown_finished(self):
        """Handle countdown completion."""
        self.countdown_label.hide()
        self._actually_start_recording()
    
    def _actually_start_recording(self):
        """Actually start the recording (after countdown if any)."""
        if self.recorder and self.recorder.start_recording():
            self.statusBar().showMessage("Recording started")
        else:
            QMessageBox.critical(self, "Recording Error", "Failed to start recording. Check console for details.")
            self._reset_ui()
    
    def _pause_recording(self):
        """Pause or resume recording."""
        if not self.recorder:
            return
        
        if self.recorder.state == RecordingState.RECORDING:
            self.recorder.pause_recording()
        elif self.recorder.state == RecordingState.PAUSED:
            self.recorder.resume_recording()
    
    def _stop_recording(self):
        """Stop recording."""
        if self.recorder:
            self.recorder.stop_recording()
            self.statusBar().showMessage("Recording saved", 5000)
        
        self._reset_ui()
    
    def _on_recording_state_changed(self, state: RecordingState):
        """Handle recording state change."""
        if state == RecordingState.RECORDING:
            self.start_button.setEnabled(False)
            self.pause_button.setEnabled(True)
            self.pause_button.setText("Pause")
            self.stop_button.setEnabled(True)
            self.status_label.setText("Recording...")
        elif state == RecordingState.PAUSED:
            self.pause_button.setText("Resume")
            self.status_label.setText("Paused")
        else:  # IDLE
            self._reset_ui()
    
    def _on_recording_progress(self, duration: float):
        """Update recording progress."""
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def _update_ui(self):
        """Update UI elements."""
        if self.recorder:
            duration = self.recorder.get_duration()
            self._on_recording_progress(duration)
    
    def _reset_ui(self):
        """Reset UI to initial state."""
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("Pause")
        self.stop_button.setEnabled(False)
        self.timer_label.setText("00:00:00")
        self.status_label.setText("Ready")
        self.recorder = None
        self.video_capture = None
        self.audio_capture = None
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.recorder and self.recorder.state != RecordingState.IDLE:
            reply = QMessageBox.question(
                self,
                "Recording in Progress",
                "Recording is in progress. Stop and save?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self._stop_recording()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

