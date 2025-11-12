"""Connection indicator widgets"""

from PyQt5.QtWidgets import QWidget, QPushButton, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QPainter, QBrush

from ..constants import COLORS, DEFAULT_PADDING


class ConnectionIndicator(QWidget):
    """Colored dot indicator widget"""
    def __init__(self, color=COLORS["red"], parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(QSize(12, 12))

    def setColor(self, color):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(self._color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, self.width(), self.height())


class ConnectionIndicatorButton(QPushButton):
    """Button with indicator dot on the left and text label"""
    def __init__(self, label, color=COLORS["red"], parent=None):
        super().__init__(parent)
        self.setFlat(True)
        self.setObjectName("connection-indicator-button")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(DEFAULT_PADDING, DEFAULT_PADDING, 0, 0)
        layout.setSpacing(6)

        self.indicator = ConnectionIndicator(color)
        self.label = QLabel(label)

        layout.addWidget(self.indicator)
        layout.addWidget(self.label)

        self.setLayout(layout)

    def sizeHint(self):
        return QSize(100, 24)

    def setColor(self, color):
        self.indicator.setColor(color)
