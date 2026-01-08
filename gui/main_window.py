"""Main application window for the screen recorder."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QRadioButton, QButtonGroup,
                             QGroupBox, QFileDialog, QMessageBox, QComboBox,
                             QProgressBar, QStatusBar, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QIcon

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
        
        # Set Window Icon
        icon_path = Path.cwd() / "Logo.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
            
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
        """Setup the user interface with modern styling."""
        from gui.styles import STYLESHEET
        self.setStyleSheet(STYLESHEET)
        
        # Central Widget
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)
        
        # Main Layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # --- Header ---
        title = QLabel("Screen Recorder")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        main_layout.addWidget(title)
        
        # --- Recording Mode Card ---
        mode_card = QFrame()
        mode_card.setProperty("class", "Card")
        mode_layout = QVBoxLayout(mode_card)
        mode_layout.setSpacing(12)
        mode_layout.setContentsMargins(16, 16, 16, 16)
        
        mode_header = QLabel("Recording Mode")
        mode_header.setProperty("class", "SectionHeader")
        mode_layout.addWidget(mode_header)
        
        # Mode Options
        self.mode_group = QButtonGroup()
        
        # Layout for radio buttons to align reasonably
        radio_layout = QVBoxLayout()
        radio_layout.setSpacing(8)
        
        self.full_screen_radio = QRadioButton("Full Screen")
        self.window_radio = QRadioButton("Window")
        self.region_radio = QRadioButton("Custom Region")
        
        self.mode_group.addButton(self.full_screen_radio, 0)
        self.mode_group.addButton(self.window_radio, 1)
        self.mode_group.addButton(self.region_radio, 2)
        
        radio_layout.addWidget(self.full_screen_radio)
        radio_layout.addWidget(self.window_radio)
        radio_layout.addWidget(self.region_radio)
        mode_layout.addLayout(radio_layout)
        
        # Dynamic inputs for modes
        input_layout = QHBoxLayout()
        
        self.window_combo = QComboBox()
        self.window_combo.setPlaceholderText("Select a window...")
        self.window_combo.setEnabled(False)
        self.window_combo.currentIndexChanged.connect(self._on_window_selected)
        input_layout.addWidget(self.window_combo, 1) # stretch 1
        
        self.region_button = QPushButton("Select Region")
        self.region_button.setEnabled(False)
        self.region_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.region_button.clicked.connect(self._select_region)
        input_layout.addWidget(self.region_button)
        
        mode_layout.addLayout(input_layout)
        
        # Logic connections
        self.window_radio.toggled.connect(lambda c: self.window_combo.setEnabled(c))
        self.region_radio.toggled.connect(lambda c: self.region_button.setEnabled(c))
        
        main_layout.addWidget(mode_card)
        
        # --- Settings Card (Quality & Audio) ---
        settings_card = QFrame()
        settings_card.setProperty("class", "Card")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setSpacing(12)
        settings_layout.setContentsMargins(16, 16, 16, 16)
        
        settings_header = QLabel("Capture Settings")
        settings_header.setProperty("class", "SectionHeader")
        settings_layout.addWidget(settings_header)
        
        # Grid for info
        info_layout = QHBoxLayout()
        
        self.quality_label = QLabel("1080p | 30 FPS")
        self.quality_label.setStyleSheet("color: #cccccc;")
        info_layout.addWidget(self.quality_label)
        
        info_layout.addStretch()
        
        self.settings_button = QPushButton("Configure...")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.clicked.connect(self._open_settings)
        info_layout.addWidget(self.settings_button)
        
        settings_layout.addLayout(info_layout)
        
        # Audio Indicators (Icons)
        audio_layout = QHBoxLayout()
        audio_layout.setSpacing(16)
        
        # Using Unicode substitutes for Fluent System Icons
        # Mic: 🎤 (\U0001F3A4) or similar. Let's use simpler unicode or text for now to be safe, 
        # or stick to the "Status Dot" idea for devices.
        # User asked for "Modern Fluent Icons". I will try to set font family for these specific labels.
        
        self.audio_system_label = QLabel("System Audio")
        self.audio_mic_label = QLabel("Microphone")
        
        # We will update these in _load_settings with icons/colors
        audio_layout.addWidget(self.audio_system_label)
        audio_layout.addWidget(self.audio_mic_label)
        audio_layout.addStretch()
        
        settings_layout.addLayout(audio_layout)
        
        main_layout.addWidget(settings_card)
        
        # --- Timer Display ---
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("TimerLabel")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.timer_label)
        
        # --- Countdown Label (Overlay/Hidden) ---
        self.countdown_label = QLabel()
        self.countdown_label.setObjectName("TimerLabel") # Use same large font
        self.countdown_label.setStyleSheet("font-size: 72pt; color: #ff3b30;")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.hide()
        # Note: In a real overlay this should probably be a separate window or stacked widget, 
        # but for now we insert it into layout or maintain existing behavior.
        # Existing behavior adds it to layout. Let's keep it but maybe float it if we had a StackedLayout.
        # For simple modernization, adding to layout is fine.
        main_layout.addWidget(self.countdown_label)
        
        main_layout.addStretch()
        
        # --- Control Bar ---
        control_layout = QHBoxLayout()
        control_layout.setSpacing(16)
        control_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Start
        self.start_button = QPushButton("Start Recording")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.setMinimumWidth(140)
        self.start_button.clicked.connect(self._start_recording)
        
        # Pause
        self.pause_button = QPushButton("Pause")
        self.pause_button.setObjectName("GhostButton")
        self.pause_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self._pause_recording)
        
        # Stop
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("DestructiveButton")
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_recording)
        
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.pause_button)
        control_layout.addWidget(self.stop_button)
        
        main_layout.addLayout(control_layout)
        
        # Output Path Label (Subtle)
        self.output_label = QLabel("")
        self.output_label.setStyleSheet("color: #666666; font-size: 11px;")
        self.output_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.output_label)
        
        # --- Status Bar ---
        # Custom status bar styling via styles.py
        self.statusBar().showMessage("Ready")
        
        # Load windows
        self._refresh_windows()
    
    def _load_settings(self):
        """Load settings from configuration."""
        # Mode
        mode = self.config.get("recording_mode", "full_screen")
        if mode == "window":
            self.window_radio.setChecked(True)
        elif mode == "region":
            self.region_radio.setChecked(True)
        else:
            self.full_screen_radio.setChecked(True)
        
        # Quality Label Update
        # Format: 1080p | 30 FPS | 8M (High)
        res = self.config.get("resolution", "1920x1080")
        fps = self.config.get("fps", 30)
        quality_key = self.config.get("video_quality", "High")
        self.quality_label.setText(f"{res} | {fps} FPS | {quality_key} Quality")
        
        # Audio Indicators Update
        # Using Unicode Circles as status dots: ● (U+25CF)
        system_enabled = self.config.get("system_audio_enabled", True)
        mic_enabled = self.config.get("microphone_enabled", True)
        
        sys_color = "#4CAF50" if system_enabled else "#666666"
        mic_color = "#4CAF50" if mic_enabled else "#666666"
        
        self.audio_system_label.setText(f"<span style='color:{sys_color};'>●</span> System Audio")
        self.audio_mic_label.setText(f"<span style='color:{mic_color};'>●</span> Microphone")
        
    def _refresh_windows(self):
        """Refresh the list of available windows."""
        self.window_combo.clear()
        windows = get_all_windows()
        for win in windows:
            # Only show windows with titles
            if win.title:
                self.window_combo.addItem(win.title, win.handle)
    
    def _on_window_selected(self, index):
        """Handle window selection."""
        if index >= 0:
            handle = self.window_combo.currentData()
            # In a real app we might highlight the window border here
            pass

    def _update_ui_state(self, state):
        """Update UI based on recording state."""
        from recording.recorder import RecordingState
        
        is_recording = state == RecordingState.RECORDING
        is_paused = state == RecordingState.PAUSED
        is_idle = state == RecordingState.IDLE
        
        # Inputs
        self.full_screen_radio.setEnabled(is_idle)
        self.window_radio.setEnabled(is_idle)
        self.region_radio.setEnabled(is_idle)
        self.window_combo.setEnabled(is_idle and self.window_radio.isChecked())
        self.region_button.setEnabled(is_idle and self.region_radio.isChecked())
        self.settings_button.setEnabled(is_idle)
        
        # Controls
        self.start_button.setEnabled(is_idle)
        self.pause_button.setEnabled(is_recording or is_paused)
        self.stop_button.setEnabled(is_recording or is_paused)
        
        if is_paused:
            self.pause_button.setText("Resume")
            self.statusBar().showMessage("● Paused")
            self.pause_button.setProperty("class", "PrimaryButton")
        else:
            self.pause_button.setText("Pause")
            self.pause_button.setProperty("class", "GhostButton")
        
        if is_recording:
             self.statusBar().showMessage("● Recording...")
             # Optionally change status bar color or dot color?
             # For now we rely on the dot text.
        elif is_idle:
             self.statusBar().showMessage("Ready")

        # Force style update for dynamic properties
        self.pause_button.style().unpolish(self.pause_button)
        self.pause_button.style().polish(self.pause_button)

    def _select_region(self):
        """Open region selector."""
        self.hide()
        self.region_selector = RegionSelector()
        self.region_selector.region_selected.connect(self._on_region_selected)
        self.region_selector.region_cancelled.connect(self._on_region_cancelled)
        self.region_selector.show()
    
    def _on_region_selected(self, left, top, width, height):
        """Handle region selection from overlay."""
        self.selected_region = (left, top, width, height)
        self.show()
        self.region_button.setText(f"Region: {width}x{height}")
    
    def _on_region_cancelled(self):
        """Handle region cancellation."""
        self.show()
        # If no region was selected before, maybe switch back to full screen?
        if not hasattr(self, 'selected_region') or not self.selected_region:
             self.full_screen_radio.setChecked(True)
    
    def _open_settings(self):
        """Open settings dialog."""
        dialog = SettingsDialog(self)
        
        # Prepare settings dict from config
        current_settings = {
            "video_quality": self.config.get("video_quality", "high"),
            "resolution": self.config.get("resolution", "1080p"),
            "fps": self.config.get("fps", 30),
            "bitrate": self.config.get("bitrate", "8M"),
            "audio_system_enabled": self.config.get("system_audio_enabled", True),
            "audio_microphone_enabled": self.config.get("microphone_enabled", True),
            "countdown_enabled": self.config.get("countdown_enabled", False),
            "countdown_seconds": self.config.get("countdown_seconds", 3),
        }
        
        dialog.set_settings(current_settings)
        
        if dialog.exec():
            settings = dialog.get_settings()
            
            # Save settings to config
            self.config.set("video_quality", settings["quality"])
            self.config.set("resolution", settings["resolution"])
            self.config.set("fps", settings["fps"])
            self.config.set("bitrate", settings["bitrate"])
            self.config.set("system_audio_enabled", settings["system_audio_enabled"])
            self.config.set("microphone_enabled", settings["microphone_enabled"])
            self.config.set("countdown_enabled", settings["countdown_enabled"])
            self.config.set("countdown_seconds", settings["countdown_seconds"])
            self.config.save()
            
            # Refresh UI
            self._load_settings()
    
    def _start_recording(self):
        """Start recording process."""
        # Determine mode
        # ... (Same logic as before, just ensuring variables exist)
        if self.full_screen_radio.isChecked():
            mode = "full_screen"
            self.config.set("recording_mode", "full_screen")
        elif self.window_radio.isChecked():
            if self.window_combo.currentIndex() < 0:
                QMessageBox.warning(self, "No Window Selected", "Please select a window to record.")
                return
            
            # Get handle
            handle = self.window_combo.currentData()
            from utils.window_utils import get_window_by_handle
            self.selected_window = get_window_by_handle(handle)
            if not self.selected_window:
                 QMessageBox.warning(self, "Error", "Window not found.")
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
        self.output_label.setText(f"Saved to: ...{str(output_path)[-40:]}") # Truncate for UI
        
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
            system_audio_enabled=self.config.get("system_audio_enabled", True),
            microphone_enabled=self.config.get("microphone_enabled", True)
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
        self._update_ui_state(state)
    
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
        self._update_ui_state(RecordingState.IDLE)
        self.timer_label.setText("00:00:00")
        self.recorder = None
        self.video_capture = None
        self.audio_capture = None
        # Keep output label logic separate if needed, but IDLE state handles buttons
    
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

