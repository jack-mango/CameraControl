"""Acquisition settings dialog"""


from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLineEdit, QCheckBox, QComboBox, QPushButton
)
from PyQt5.QtGui import QIntValidator

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
        
        # Get acquisition config from controller to populate default values
        acquisition_config = None
        if self.controller:
            acquisition_config = self.controller.get_acquisition_config()
        
        # Frames per shot
        frames_per_shot_default = str(acquisition_config.get('frames_per_shot', 10)) if acquisition_config else "10"
        self.frames_per_shot_edit = QLineEdit(frames_per_shot_default)
        self.frames_per_shot_edit.setValidator(QIntValidator(1, 10))
        form_layout.addRow("Frames per Shot:", self.frames_per_shot_edit)

        shots_per_parameter_layout = QHBoxLayout()
        shots_per_parameter_default = str(acquisition_config.get('shots_per_parameter', 1)) if acquisition_config else "1"
        self.shots_per_parameter_edit = QLineEdit(shots_per_parameter_default)
        self.shots_per_parameter_auto = QCheckBox("Auto")
        auto_shots_default = acquisition_config.get('auto_shots_per_parameter', False) if acquisition_config else False
        self.shots_per_parameter_auto.setChecked(auto_shots_default)
        shots_per_parameter_layout.addWidget(self.shots_per_parameter_edit)
        shots_per_parameter_layout.addWidget(self.shots_per_parameter_auto)
        form_layout.addRow("Shots per Parameter:", shots_per_parameter_layout)

        # Maximum shots
        max_shots_layout = QHBoxLayout()
        max_shots_default = acquisition_config.get('max_shots', 100) if acquisition_config else 100
        max_shots_enabled = max_shots_default is not None
        max_shots_value = str(max_shots_default) if max_shots_enabled else "100"
        self.max_shots_edit = QLineEdit(max_shots_value)
        self.max_shots_edit.setValidator(QIntValidator(1, 100000))
        self.max_shots_enabled_checkbox = QCheckBox("Enable Limit")
        self.max_shots_enabled_checkbox.setChecked(max_shots_enabled)
        max_shots_layout.addWidget(self.max_shots_edit)
        max_shots_layout.addWidget(self.max_shots_enabled_checkbox)
        form_layout.addRow("Maximum Shots:", max_shots_layout)

        # File save type dropdown
        self.file_type_combo = QComboBox()
        self.file_type_combo.setMinimumWidth(150)
        self.file_type_combo.addItems(['.hdf5', '.npz', '.mat'])
        
        # Set current format from controller config
        if acquisition_config:
            current_format = acquisition_config.get('file_format', '.mat')
            self.file_type_combo.setCurrentText(current_format)
        else:
            self.file_type_combo.setCurrentText('.mat')  # Default
            
        form_layout.addRow("File Save Type:", self.file_type_combo)
        
        main_layout.addLayout(form_layout)
        main_layout.addStretch()
        
        # Connect checkbox signals to enable/disable text boxes
        self.max_shots_enabled_checkbox.toggled.connect(self.on_max_shots_toggled)
        
        # Set initial states
        self.on_max_shots_toggled(self.max_shots_enabled_checkbox.isChecked())
        
        # Connect to socket connection signal for dynamic updates
        if self.controller:
            self.controller.socket_connection_signal.connect(self.on_socket_connection_changed)
            # Set initial state based on current socket connection
            self.on_socket_connection_changed(self.controller.is_socket_connected)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self.apply_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(cancel_btn)
        main_layout.addLayout(button_layout)
        
        # Disable apply button if acquisition is in progress
        if self.controller:
            is_acquiring = self.controller.acquisition_in_progress()
            self.apply_btn.setEnabled(not is_acquiring)
            if is_acquiring:
                self.apply_btn.setToolTip("Cannot change settings during acquisition")
    
    def on_max_shots_toggled(self, checked):
        """Enable/disable max shots text box based on checkbox state"""
        self.max_shots_edit.setEnabled(checked)
    
    def on_socket_connection_changed(self, is_connected):
        """
        Update auto shots per parameter checkbox based on socket connection status.
        
        Args:
            is_connected: True if socket is connected, False otherwise
        """
        self.shots_per_parameter_auto.setEnabled(is_connected)
        if is_connected:
            self.shots_per_parameter_auto.setToolTip("")
        else:
            # Uncheck and disable if socket disconnects
            self.shots_per_parameter_auto.setChecked(False)
            self.shots_per_parameter_auto.setToolTip("Socket must be connected to use auto mode")
    
    def apply_settings(self):
        """Apply the acquisition settings to the controller"""
        if self.controller:

            acquisition_config = {}

            # Apply file format
            selected_format = self.file_type_combo.currentText()
            acquisition_config['file_format'] = selected_format

            # Apply auto frames per shot
            acquisition_config['auto_shots_per_parameter'] = self.shots_per_parameter_auto.isChecked()
            
            # Apply frames per shot
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
