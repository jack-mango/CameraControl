"""Acquisition control panel widget"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QPushButton
)
from PyQt5.QtCore import Qt

from ..constants import DEFAULT_PADDING
from ..dialogs.acquisition_settings import AcquisitionSettingsDialog




class AcquisitionPanel(QWidget):
    """Panel for acquisition control and status display"""
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.shot_count = 0
        self.rep_count = 0
        self.tot_shots = 0

        self.setObjectName("acquisition-panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(DEFAULT_PADDING, DEFAULT_PADDING, DEFAULT_PADDING, DEFAULT_PADDING)
        
        # Title at the top (centered)
        title_label = QLabel("Acquisition Control")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setObjectName("acquisition-panel-title")
        main_layout.addWidget(title_label)
        
        # Status display with borders
        status_layout = QFormLayout()
        status_layout.setContentsMargins(DEFAULT_PADDING, DEFAULT_PADDING, DEFAULT_PADDING, DEFAULT_PADDING)
        
        self.shot_in_rep_label = QLabel("0")
        self.shot_in_rep_label.setObjectName("acquisition-status-value")
        self.shot_in_rep_label.setFrameStyle(QLabel.Box | QLabel.Plain)
        self.shot_in_rep_label.setAlignment(Qt.AlignCenter)
        status_layout.addRow("Current Shot in Rep:", self.shot_in_rep_label)
        
        self.rep_number_label = QLabel("0")
        self.rep_number_label.setObjectName("acquisition-status-value")
        self.rep_number_label.setFrameStyle(QLabel.Box | QLabel.Plain)
        self.rep_number_label.setAlignment(Qt.AlignCenter)
        status_layout.addRow("Current Rep Number:", self.rep_number_label)
        
        # NOT IMPLEMENTED YET
        # self.scan_variable_label = QLabel("N/A")
        # self.scan_variable_label.setObjectName("acquisition-status-value")
        # self.scan_variable_label.setFrameStyle(QLabel.Box | QLabel.Plain)
        # self.scan_variable_label.setAlignment(Qt.AlignCenter)
        # status_layout.addRow("Current Scan Variable:", self.scan_variable_label)
        
        self.total_shots_label = QLabel("0")
        self.total_shots_label.setObjectName("acquisition-status-value")
        self.total_shots_label.setFrameStyle(QLabel.Box | QLabel.Plain)
        self.total_shots_label.setAlignment(Qt.AlignCenter)
        status_layout.addRow("Total Shots:", self.total_shots_label)
        
        main_layout.addLayout(status_layout)
        
        # Control buttons - stacked vertically
        button_layout = QVBoxLayout()
        button_layout.setSpacing(DEFAULT_PADDING)
        
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("acquisition-control-button")
        self.start_btn.clicked.connect(self.on_start_clicked)
        self.start_btn.setEnabled(False)  # Disabled until camera is connected
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("acquisition-control-button")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.on_stop_clicked)
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        
        main_layout.addLayout(button_layout)
        main_layout.addStretch()
        
        # Settings button at bottom right - using absolute positioning
        self.settings_btn = QPushButton("⚙", self)
        self.settings_btn.setObjectName("acquisition-settings-button")
        self.settings_btn.setFixedSize(40, 40)
        self.settings_btn.clicked.connect(self.open_settings)
        self.settings_btn.raise_()
    
    def resizeEvent(self, event):
        """Reposition the settings button when widget is resized"""
        super().resizeEvent(event)
        # Position button at bottom right with padding
        self.settings_btn.move(
            self.width() - self.settings_btn.width() - DEFAULT_PADDING,
            self.height() - self.settings_btn.height() - DEFAULT_PADDING
        )
    
    def open_settings(self):
        """Open the acquisition settings dialog"""
        dialog = AcquisitionSettingsDialog(self.controller, self)
        dialog.exec_()
    
    def on_start_clicked(self):
        """Handle start button click"""
        self.controller.start_acquisition()
        # Update button states
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
    
    def on_stop_clicked(self):
        """Handle stop button click"""
        self.controller.stop_acquisition()
        # Update button states - re-enable start only if camera is connected
        if self.controller.is_camera_connected:
            self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
    
    def update_camera_connection(self, is_connected):
        """
        Update the start button state based on camera connection status.
        
        Args:
            is_connected: True if camera is connected, False otherwise
        """
        # Only enable start button if camera is connected and acquisition is not in progress
        if is_connected:
            # Enable start button (unless stop button is enabled, meaning acquisition is running)
            if not self.stop_btn.isEnabled():
                self.start_btn.setEnabled(True)
        else:
            # Disable start button when camera disconnects
            self.start_btn.setEnabled(False)
    
    def update_shot_counter(self, shot_count):
        """
        Update the total shots counter from Controller's shot_counter_signal.
        
        Args:
            shot_count: Current total shot count
        """
        prev_shot_count = self.shot_count
        self.shot_count = shot_count
        self.total_shots_label.setText(str(shot_count))
        self.tot_shots += 1
        self.total_shots_label.setText(str(self.tot_shots))
        if prev_shot_count < shot_count:
            self.rep_count += 1
            self.rep_number_label.setText(str(self.rep_count))
