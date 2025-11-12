"""Main application window"""

import sys
import json
import logging
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QStatusBar, QWidget, 
    QHBoxLayout, QVBoxLayout, QLabel
)
from PyQt5.QtCore import QFile, QTextStream

from .constants import COLORS, DEFAULT_PADDING
from .widgets import (
    LoggingPanel, ConnectionIndicatorButton, AcquisitionPanel, LiveImageViewWidget
)
from .dialogs import CameraConfigDialog, SocketConfigDialog

logger = logging.getLogger(__name__)

# TODO: Change the camera and socket button text colors

# TODO: Live analysis


class MainWindow(QMainWindow):
    """Main application window with camera control interface"""
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.setWindowTitle("Camera Control")
        self.resize(1600, 900)

        # Create central widget with layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(DEFAULT_PADDING, DEFAULT_PADDING, DEFAULT_PADDING, DEFAULT_PADDING)

        # Create horizontal layout for plot widget and acquisition panel side-by-side
        main_content_layout = QHBoxLayout()
        main_content_layout.setSpacing(DEFAULT_PADDING)
        
        # Create plot widget
        self.live_image_view_widget = LiveImageViewWidget(1200, 500)
        main_content_layout.addWidget(self.live_image_view_widget)
        
        # Create acquisition panel
        self.acquisition_panel = AcquisitionPanel(controller)
        self.acquisition_panel.setMinimumWidth(250)
        self.acquisition_panel.setMaximumWidth(250)
        main_content_layout.addWidget(self.acquisition_panel)
        
        central_layout.addLayout(main_content_layout)

        # Add stretch to push logging to bottom
        central_layout.addStretch()

        # Add logging panel at bottom - spans entire width
        self.logging_panel = LoggingPanel()
        central_layout.addWidget(self.logging_panel)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # Container for the right side indicators
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        # Temperature display
        self.temperature_label = QLabel()
        self.temperature_label.setObjectName("temperature-label")
        layout.addWidget(self.temperature_label)

        # Buttons
        self.camera_indicator_button = ConnectionIndicatorButton("Camera", COLORS["green"])
        self.socket_indicator_button = ConnectionIndicatorButton("Socket", COLORS["red"])

        self.camera_indicator_button.clicked.connect(self.open_camera_config)
        self.socket_indicator_button.clicked.connect(self.open_socket_config)

        layout.addWidget(self.camera_indicator_button)
        layout.addWidget(self.socket_indicator_button)

        # Add the container to the right side of the status bar
        status_bar.addPermanentWidget(container)
        
        # Connect signals from controller
        if self.controller:
            self.controller.temperature_signal.connect(self.update_temperature)
            self.controller.camera_connection_signal.connect(self.update_camera_connection_indicator)
            self.controller.camera_connection_signal.connect(self.acquisition_panel.update_camera_connection)
            self.controller.socket_connection_signal.connect(self.update_socket_connection_indicator)
            self.controller.new_data_signal.connect(self.on_new_image_data)
            self.controller.shot_counter_signal.connect(self.acquisition_panel.update_shot_counter)
            
            # Set initial indicator states
            self.update_camera_connection_indicator(self.controller.is_camera_connected)
            self.update_socket_connection_indicator(self.controller.is_socket_connected)
            # Set initial start button state based on camera connection
            self.acquisition_panel.update_camera_connection(self.controller.is_camera_connected)
    
    def on_new_image_data(self, images, parameters):
        """Handle new image data from the camera
        
        Args:
            images: 3D numpy array of shape (n_images, height, width)
            parameters: Dictionary of acquisition parameters
        """
        self.live_image_view_widget.update_image_plots(images)
    
    def update_camera_connection_indicator(self, is_connected):
        """Update the camera connection indicator color based on connection status"""
        if is_connected:
            self.camera_indicator_button.setColor(COLORS["green"])
        else:
            self.camera_indicator_button.setColor(COLORS["red"])
    
    def update_socket_connection_indicator(self, is_connected):
        """Update the socket connection indicator color based on connection status"""
        if is_connected:
            self.socket_indicator_button.setColor(COLORS["green"])
        else:
            self.socket_indicator_button.setColor(COLORS["red"])
    
    def update_temperature(self, temperature, status):
        """Update the temperature display in the status bar with dynamic color coding
        
        Args:
            temperature: Temperature value in Celsius
            status: Temperature status string from Andor SDK2 camera.get_temperature_status()
                   Possible values: 'stabilized', 'not_reached', 'drift', 'not_stabilized', 'off'
        """
        # Update the text
        self.temperature_label.setText(f"Sensor temperature: {temperature:.1f}°C")
        
        # Set color based on Andor SDK2 status strings
        if not self.controller.get_is_camera_connected() or status == "off":
            # Not connected - use text_light (gray)
            color = COLORS["text_light"]
        elif status == "stabilized":
            # Temperature reached and stable - green
            color = COLORS["green"]
        elif status == "not_reached":
            # Temperature not reached or cooling off - red
            color = COLORS["red"]
        elif status == "drift" or status == "not_stabilized":
            # Temperature drifting or not stable - yellow
            color = COLORS["yellow"]
        else:
            # Unknown status - use text_light
            color = COLORS["text_light"]
        
        # Apply the color
        self.temperature_label.setStyleSheet(f"color: {color}; font-size: 12px; padding: 2px 8px; background-color: transparent;")

    def closeEvent(self, event):
        """Clean shutdown when window closes"""
        if self.controller:
            self.controller.stop()
            self.controller.wait()
        event.accept()

    def open_camera_config(self):
        """Open camera configuration dialog"""
        dlg = CameraConfigDialog("Camera", self.controller, self)
        dlg.exec_()

    def open_socket_config(self):
        """Open socket configuration dialog"""
        dlg = SocketConfigDialog(self.controller.get_socket_config(), self.controller, self)
        dlg.exec_()


def load_stylesheet(filename):
    """Load a QSS stylesheet from file"""
    file = QFile(filename)
    if file.open(QFile.ReadOnly | QFile.Text):
        stream = QTextStream(file)
        stylesheet = stream.readAll()
        file.close()
        return stylesheet
    return ""


if __name__ == "__main__":
    from ..Controller import Controller
    
    config = json.load(open("config.json"))
    controller = Controller(config)
    controller.start()
    app = QApplication(sys.argv)
    window = MainWindow(controller)

    # Load global stylesheet
    stylesheet = load_stylesheet("camera_control/styles.qss")
    if stylesheet:
        app.setStyleSheet(stylesheet)

    window.show()
    sys.exit(app.exec_())
