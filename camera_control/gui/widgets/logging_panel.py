"""Logging panel widget with custom Qt logging handler"""

import logging
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit
from PyQt5.QtCore import Qt, pyqtSignal, QObject

from ..constants import DEFAULT_PADDING


# TODO: Improve logging panel aesthetics

class QTextEditLogger(logging.Handler, QObject):
    """Custom logging handler that emits log messages as Qt signals"""
    log_signal = pyqtSignal(str)
    
    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        
    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(msg)


class LoggingPanel(QWidget):
    """Panel widget that displays log messages"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logging-panel")
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DEFAULT_PADDING, DEFAULT_PADDING, DEFAULT_PADDING, DEFAULT_PADDING)
        
        # Title
        title_label = QLabel("Log")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setObjectName("logging-panel-title")
        layout.addWidget(title_label)
        
        # Text display for logs
        self.log_display = QTextEdit()
        self.log_display.setObjectName("log-display")
        self.log_display.setReadOnly(True)
        
        # Calculate height for 4 lines (approximate)
        # Line height ~= font size * 1.5 for spacing
        font_metrics = self.log_display.fontMetrics()
        line_height = font_metrics.lineSpacing()
        desired_height = line_height * 4 + 10  # 4 lines + padding
        self.log_display.setMaximumHeight(desired_height)
        self.log_display.setMinimumHeight(desired_height)
        
        layout.addWidget(self.log_display)
        
        # Set up the custom logging handler
        self.log_handler = QTextEditLogger()
        self.log_handler.log_signal.connect(self.append_log)
        
        # Format the log messages
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', 
                                     datefmt='%H:%M:%S')
        self.log_handler.setFormatter(formatter)
        
        # Add handler to root logger
        logging.getLogger().addHandler(self.log_handler)
        logging.getLogger().setLevel(logging.INFO)
    
    def append_log(self, message):
        """Append a log message to the display"""
        self.log_display.append(message)
        # Auto-scroll to bottom
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )
