"""Acquisition control panel widget"""

import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QPushButton
)
from PyQt5.QtCore import Qt

from ..constants import DEFAULT_PADDING
from ..dialogs.acquisition_settings import AcquisitionSettingsDialog

logger = logging.getLogger(__name__)

# TODO: Make the acquisition panel functional

# TODO: Change acquisition panel text color to all be text_light

# TODO: Disable settings button (or at least the apply button in the settings) when acquisition is in progress

# TODO: Disable the start button unless 1. socket is connected and 2. camera is connected.




class AcquisitionPanel(QWidget):
    """Panel for acquisition control and status display"""
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

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
        
        self.scan_variable_label = QLabel("N/A")
        self.scan_variable_label.setObjectName("acquisition-status-value")
        self.scan_variable_label.setFrameStyle(QLabel.Box | QLabel.Plain)
        self.scan_variable_label.setAlignment(Qt.AlignCenter)
        status_layout.addRow("Current Scan Variable:", self.scan_variable_label)
        
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
        # Update button states
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
    
    def update_status(self, shot_in_rep=None, rep_number=None, scan_variable=None, total_shots=None):
        """Update the status display"""
        if shot_in_rep is not None:
            self.shot_in_rep_label.setText(str(shot_in_rep))
        if rep_number is not None:
            self.rep_number_label.setText(str(rep_number))
        if scan_variable is not None:
            self.scan_variable_label.setText(str(scan_variable))
        if total_shots is not None:
            self.total_shots_label.setText(str(total_shots))
