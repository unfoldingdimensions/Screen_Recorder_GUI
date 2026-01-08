"""Region selector overlay for custom area selection."""

from typing import Optional
from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
import mss


class RegionSelector(QWidget):
    """Full-screen overlay for selecting recording region."""
    
    region_selected = pyqtSignal(int, int, int, int)  # left, top, width, height
    cancelled = pyqtSignal()
    
    def __init__(self, parent=None):
        """Initialize region selector."""
        super().__init__(parent)
        
        # Get screen dimensions
        sct = mss.mss()
        monitor = sct.monitors[1]  # Primary monitor
        screen_width = monitor["width"]
        screen_height = monitor["height"]
        screen_left = monitor["left"]
        screen_top = monitor["top"]
        
        # Set window to cover entire screen
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(screen_left, screen_top, screen_width, screen_height)
        
        # Selection state
        self.start_point: Optional[QPoint] = None
        self.end_point: Optional[QPoint] = None
        self.is_selecting = False
        
        # UI elements
        self.info_label = QLabel(self)
        self.info_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 180);
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.hide()
        
        self.setCursor(Qt.CursorShape.CrossCursor)
    
    def mousePressEvent(self, event):
        """Handle mouse press to start selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.position().toPoint()
            self.end_point = self.start_point
            self.is_selecting = True
            self.update()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move to update selection."""
        if self.is_selecting:
            self.end_point = event.position().toPoint()
            self.update()
            
            # Update info label
            if self.start_point and self.end_point:
                rect = self._get_selection_rect()
                self._update_info_label(rect)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to finalize selection."""
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            
            if self.start_point and self.end_point:
                rect = self._get_selection_rect()
                left, top, width, height = rect.left(), rect.top(), rect.width(), rect.height()
                
                # Only emit if selection is valid (at least 100x100 pixels)
                if width >= 100 and height >= 100:
                    # Convert to screen coordinates
                    screen_pos = self.mapToGlobal(self.start_point)
                    self.region_selected.emit(
                        screen_pos.x(),
                        screen_pos.y(),
                        width,
                        height
                    )
                    self.close()
                else:
                    # Reset for new selection
                    self.start_point = None
                    self.end_point = None
                    self.info_label.hide()
                    self.update()
    
    def keyPressEvent(self, event):
        """Handle key press (ESC to cancel)."""
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()
    
    def _get_selection_rect(self) -> QRect:
        """Get the selection rectangle."""
        if not self.start_point or not self.end_point:
            return QRect()
        
        left = min(self.start_point.x(), self.end_point.x())
        top = min(self.start_point.y(), self.end_point.y())
        right = max(self.start_point.x(), self.end_point.x())
        bottom = max(self.start_point.y(), self.end_point.y())
        
        return QRect(left, top, right - left, bottom - top)
    
    def _update_info_label(self, rect: QRect):
        """Update info label with selection dimensions."""
        width = rect.width()
        height = rect.height()
        
        # Position label near selection
        label_x = rect.right() + 10
        label_y = rect.top()
        
        # Adjust if label would go off screen
        if label_x + 200 > self.width():
            label_x = rect.left() - 210
        
        if label_y + 50 > self.height():
            label_y = rect.bottom() - 50
        
        self.info_label.setText(f"{width} × {height} px")
        self.info_label.setGeometry(label_x, label_y, 200, 40)
        self.info_label.show()
    
    def paintEvent(self, event):
        """Paint the overlay and selection."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw semi-transparent overlay
        overlay_color = QColor(0, 0, 0, 100)
        painter.fillRect(self.rect(), overlay_color)
        
        # Draw selection rectangle if selecting
        if self.is_selecting and self.start_point and self.end_point:
            rect = self._get_selection_rect()
            
            # Clear selection area (make it brighter)
            clear_rect = QRect(rect)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(clear_rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            
            # Draw selection border
            pen = QPen(QColor(0, 150, 255), 2)
            painter.setPen(pen)
            painter.drawRect(rect)
            
            # Draw corner handles
            handle_size = 8
            handle_color = QColor(0, 150, 255)
            brush = QBrush(handle_color)
            painter.setBrush(brush)
            painter.setPen(Qt.PenStyle.NoPen)
            
            corners = [
                (rect.left(), rect.top()),
                (rect.right(), rect.top()),
                (rect.left(), rect.bottom()),
                (rect.right(), rect.bottom()),
            ]
            
            for x, y in corners:
                painter.drawEllipse(x - handle_size // 2, y - handle_size // 2, 
                                  handle_size, handle_size)

