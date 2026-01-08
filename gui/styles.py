"""
Modern Dark Theme Stylesheet for Screen Recorder.
"""

STYLESHEET = """
/* Global Window Settings */
QMainWindow, QWidget#CentralWidget {
    background-color: #202020;
    color: #ffffff;
    font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
    font-size: 14px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #202020;
    width: 10px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:vertical {
    background: #3b3b3b;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}

/* Cards (Sections) */
QFrame.Card {
    background-color: #2b2b2b;
    border-radius: 8px;
    border: 1px solid #333333;
}

/* Typography */
QLabel#Title {
    font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif;
    font-size: 28pt;
    font-weight: 600;
    color: #ffffff;
    margin-bottom: 10px;
}

QLabel.SectionHeader {
    font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif;
    font-size: 12px;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.8);
    text-transform: uppercase;
    margin-bottom: 4px;
}

QLabel#TimerLabel {
    font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
    font-size: 32pt;
    font-weight: 700;
    color: #ffffff;
}

/* Inputs & Controls */
QComboBox {
    background-color: #333333;
    border: 1px solid #3b3b3b;
    border-radius: 4px;
    padding: 5px 10px;
    color: white;
    min-height: 24px;
}
QComboBox:hover {
    background-color: #3a3a3a;
    border: 1px solid #4a4a4a;
}
QComboBox:focus {
    border-bottom: 2px solid #60cdff; /* Accent color highlight */
    background-color: #3a3a3a;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 0px;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}

QPushButton {
    background-color: #333333;
    border: 1px solid #3b3b3b;
    border-radius: 4px;
    color: white;
    padding: 6px 12px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #3a3a3a;
    border-color: #4a4a4a;
}
QPushButton:pressed {
    background-color: #2a2a2a;
}
QPushButton:disabled {
    background-color: #252525;
    color: #666666;
    border-color: #2a2a2a;
}

/* Primary Action Button (Start) */
QPushButton#PrimaryButton {
    background-color: #0078d4; /* Windows Accent Blue */
    border: 1px solid #0078d4;
    color: white;
    font-size: 14px;
    padding: 8px 16px;
    border-radius: 6px;
}
QPushButton#PrimaryButton:hover {
    background-color: #1084d9; /* Lighten 10% approx */
    border-color: #1084d9;
}
QPushButton#PrimaryButton:pressed {
    background-color: #006cc1;
}
QPushButton#PrimaryButton:disabled {
    background-color: #333333;
    border: 1px solid #3b3b3b;
    color: #888888;
}

/* Secondary/Ghost Button (Pause) */
QPushButton#GhostButton {
    background-color: transparent;
    border: 1px solid #4a4a4a;
    color: #ffffff;
}
QPushButton#GhostButton:hover {
    background-color: rgba(255, 255, 255, 0.05);
    border-color: #666666;
}

/* Destructive Button (Stop) */
QPushButton#DestructiveButton {
    background-color: #333333;
    border: 1px solid #3b3b3b;
}
QPushButton#DestructiveButton:hover {
    background-color: rgba(255, 59, 48, 0.1); /* Red tint */
    border-color: #ff3b30;
    color: #ff3b30;
}

/* Radio Buttons */
QRadioButton {
    spacing: 8px;
    color: #dddddd;
}
QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border-radius: 10px;
    border: 2px solid #888888;
    background-color: transparent;
}
QRadioButton::indicator:checked {
    border-color: #60cdff;
    background-color: #60cdff;
}
QRadioButton::indicator:unchecked:hover {
    border-color: #aaaaaa;
}

/* Groups */
QGroupBox {
    border: none;
    margin-top: 24px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: rgba(255, 255, 255, 0.8);
    font-weight: bold;
    font-size: 12px;
    text-transform: uppercase;
}

/* Status Bar */
QStatusBar {
    background-color: #202020;
    color: #aaaaaa;
    border-top: 1px solid #333333;
}
QStatusBar::item {
    border: none;
}
"""
