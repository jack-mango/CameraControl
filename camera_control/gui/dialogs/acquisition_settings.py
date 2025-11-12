"""Acquisition settings dialog"""

import logging
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLineEdit, QCheckBox, QComboBox, QPushButton
)
from PyQt5.QtGui import QIntValidator

logger = logging.getLogger(__name__)


class AcquisitionSettingsDialog(QDialog):
    """Dialog for configuring acquisition settings"""
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Acquisition Settings")
        self.resize(400, 250)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Form layout for settings
        form_layout = QFormLayout()
        
        # Frames per shot
        frames_layout = QHBoxLayout()
        self.frames_per_shot_edit = QLineEdit("10")
        self.frames_per_shot_edit.setValidator(QIntValidator(1, 10))
        self.auto_frames_per_shot_checkbox = QCheckBox("Auto")
        frames_layout.addWidget(self.frames_per_shot_edit)
        frames_layout.addWidget(self.auto_frames_per_shot_checkbox)
        form_layout.addRow("Frames per Shot:", frames_layout)

        shots_per_parameter_layout = QHBoxLayout()
        self.shots_per_parameter_edit = QLineEdit("1")
        self.shots_per_parameter_auto = QCheckBox("Auto")
        shots_per_parameter_layout.addWidget(self.shots_per_parameter_edit)
        shots_per_parameter_layout.addWidget(self.shots_per_parameter_auto)
        form_layout.addRow("Shots per Parameter:", shots_per_parameter_layout)

        # Maximum shots
        max_shots_layout = QHBoxLayout()
        self.max_shots_edit = QLineEdit("100")
        self.max_shots_edit.setValidator(QIntValidator(1, 100000))
        self.max_shots_enabled_checkbox = QCheckBox("Enable Limit")
        self.max_shots_enabled_checkbox.setChecked(True)
        max_shots_layout.addWidget(self.max_shots_edit)
        max_shots_layout.addWidget(self.max_shots_enabled_checkbox)
        form_layout.addRow("Maximum Shots:", max_shots_layout)

        # File save type dropdown
        self.file_type_combo = QComboBox()
        self.file_type_combo.setMinimumWidth(150)
        self.file_type_combo.addItems(['.hdf5', '.npz', '.mat'])
        
        # Set current format from controller
        if self.controller:
            current_format = self.controller.get_file_format()
            self.file_type_combo.setCurrentText(current_format)
        else:
            self.file_type_combo.setCurrentText('.hdf5')  # Default
            
        form_layout.addRow("File Save Type:", self.file_type_combo)
        
        main_layout.addLayout(form_layout)
        main_layout.addStretch()
        
        # Connect checkbox signals to enable/disable text boxes
        self.max_shots_enabled_checkbox.toggled.connect(self.on_max_shots_toggled)
        self.auto_frames_per_shot_checkbox.toggled.connect(self.on_auto_frames_toggled)
        
        # Set initial states
        self.on_max_shots_toggled(self.max_shots_enabled_checkbox.isChecked())
        self.on_auto_frames_toggled(self.auto_frames_per_shot_checkbox.isChecked())
        
        # Buttons
        button_layout = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.apply_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(cancel_btn)
        main_layout.addLayout(button_layout)
    
    def on_max_shots_toggled(self, checked):
        """Enable/disable max shots text box based on checkbox state"""
        self.max_shots_edit.setEnabled(checked)
    
    def on_auto_frames_toggled(self, checked):
        """Enable/disable frames per shot text box based on checkbox state"""
        self.frames_per_shot_edit.setEnabled(not checked)
    
    def apply_settings(self):
        """Apply the acquisition settings to the controller"""
        if self.controller:

            acquisition_config = {}

            # Apply file format
            selected_format = self.file_type_combo.currentText()
            acquisition_config['file_format'] = selected_format

            # Apply auto frames per shot
            acquisition_config['auto_shots_per_parameter'] = self.shots_per_parameter_auto.isChecked()
            
            # Apply frames per shot (only if not auto)
            if not self.auto_frames_per_shot_checkbox.isChecked():
                frames_per_shot = int(self.frames_per_shot_edit.text())
                acquisition_config['frames_per_shot'] = frames_per_shot

            # Apply shots per parameter
            acquisition_config['shots_per_parameter'] = int(self.shots_per_parameter_edit.text())

            # Apply maximum shots
            if self.max_shots_enabled_checkbox.isChecked():
                max_shots = int(self.max_shots_edit.text())
                acquisition_config['max_shots'] = max_shots
            else:
                acquisition_config['max_shots'] = None

            self.controller.set_acquisition_config(acquisition_config)

        # Close the dialog
        self.accept()
