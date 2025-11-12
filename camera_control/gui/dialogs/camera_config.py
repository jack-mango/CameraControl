"""Camera configuration dialog"""

import logging
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QPushButton, QWidget,
    QFormLayout, QComboBox, QCheckBox, QLineEdit, QTableWidget,
    QHeaderView, QTableWidgetItem
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator, QDoubleValidator

logger = logging.getLogger(__name__)


# TODO: Remove support for internal triggering at least for now.

class CameraConfigDialog(QDialog):
    def __init__(self, title, controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{title} Settings")
        self.resize(600, 300)
        self.controller = controller

        # main layout
        self.main_layout = QVBoxLayout(self)

        # --- Tabs ---
        self.tabs = QTabWidget()
        
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setElideMode(Qt.ElideNone)
        self.main_layout.addWidget(self.tabs)

        # Tab 1: Camera connection
        camera_info_tab = QWidget()
        camera_info_layout = QVBoxLayout(camera_info_tab)
        
        # Search button at top
        search_cameras_btn = QPushButton("Search for cameras")
        search_cameras_btn.clicked.connect(self.search_cameras)
        camera_info_layout.addWidget(search_cameras_btn)
        
        # Table for available cameras
        self.camera_table = QTableWidget()
        self.camera_table.setColumnCount(5)
        self.camera_table.setHorizontalHeaderLabels(["Index", "Model", "Serial Number", "Status", "Connection"])

        # Hide row numbers on the left
        self.camera_table.verticalHeader().setVisible(False)

        # Make table look nice
        self.camera_table.horizontalHeader().setStretchLastSection(False)
        self.camera_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.camera_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.camera_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.camera_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.camera_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
    
        camera_info_layout.addWidget(self.camera_table)
        self.tabs.addTab(camera_info_tab, "Camera Info")

        # Populate table with any previously found cameras via controller getter
        try:
            cameras = self.controller.get_found_cameras()
        except Exception:
            cameras = []

        if cameras:
            self._populate_camera_table(cameras)

        if controller.get_is_camera_connected():
            self.make_sensor_settings_tab()
            self.make_image_settings_tab()
            
            # Create button layout for Apply and Save to Config
            button_layout = QVBoxLayout()
            
            self.apply_btn = QPushButton("Apply")
            self.apply_btn.clicked.connect(self.apply_settings)
            button_layout.addWidget(self.apply_btn)
            
            self.save_to_config_btn = QPushButton("Save to Config")
            self.save_to_config_btn.clicked.connect(self.save_to_config)
            button_layout.addWidget(self.save_to_config_btn)
            
            self.main_layout.addLayout(button_layout)
            
            # Disable apply and save buttons if acquisition is in progress
            is_acquiring = self.controller.acquisition_in_progress()
            self.apply_btn.setEnabled(not is_acquiring)
            self.save_to_config_btn.setEnabled(not is_acquiring)
            if is_acquiring:
                self.apply_btn.setToolTip("Cannot change settings during acquisition")
                self.save_to_config_btn.setToolTip("Cannot change settings during acquisition")
        else:
            self.apply_btn = None
            self.save_to_config_btn = None
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        self.main_layout.addWidget(close_btn)

    def make_sensor_settings_tab(self):
        sensor_tab = QWidget()
        sensor_layout = QFormLayout(sensor_tab)
        
        self.camera_widgets = {}
        config = self.controller.get_camera_config()
        available_settings = self.controller.get_connected_camera_settings_list()
        for setting_name in available_settings.keys():
            setting_options = available_settings[setting_name]
            
            if isinstance(setting_options, list):
                combo = QComboBox()
                combo.setMinimumWidth(150)
                combo.addItems(setting_options)
                sensor_layout.addRow(setting_name + ":", combo)
                self.camera_widgets[setting_name] = combo
                if config:
                    setting_value = config[setting_name]
                else:
                    setting_value = setting_options[0]
                combo.setCurrentText(setting_value)
            elif isinstance(setting_options, dict):
                combo = QComboBox()
                combo.setMinimumWidth(150)
                combo.addItems(setting_options)
                sensor_layout.addRow(setting_name + ":", combo)
                self.camera_widgets[setting_name] = combo
                if config:
                    setting_value = config[setting_name]
                else:
                    setting_value = list(setting_options.values())[0]
                combo.setCurrentText(setting_value)
            elif isinstance(setting_options, bool):
                checkbox = QCheckBox()
                sensor_layout.addRow(setting_name + ":", checkbox)
                self.camera_widgets[setting_name] = checkbox
                if config:
                    setting_value = config[setting_name]
                else:
                    setting_value = False
                checkbox.setChecked(setting_value)
            elif isinstance(setting_options, int):
                if config:
                    setting_value = config[setting_name]
                else:
                    setting_value = 1
                line_edit = QLineEdit(str(setting_value))
                line_edit.setValidator(QIntValidator())
                sensor_layout.addRow(setting_name + ":", line_edit)
                self.camera_widgets[setting_name] = line_edit
            elif isinstance(setting_options, float):
                if config:
                    setting_value = config[setting_name]
                else:
                    setting_value = 1.0
                line_edit = QLineEdit(str(setting_value))
                line_edit.setValidator(QDoubleValidator())
                sensor_layout.addRow(setting_name + ":", line_edit)
                self.camera_widgets[setting_name] = line_edit
            else:
                raise ValueError
        self.tabs.addTab(sensor_tab, "Sensor Settings")

    def make_image_settings_tab(self):
        self.image_widgets = {}
        # Tab 3: Image settings
        image_settings_tab = QWidget()
        image_settings_layout = QFormLayout(image_settings_tab)
        config = self.controller.get_image_config()
        for setting_name, setting_value in config.items():
            line_edit = QLineEdit(str(setting_value))
            image_settings_layout.addRow(setting_name + ":", line_edit)
            self.image_widgets[setting_name] = line_edit
        self.tabs.addTab(image_settings_tab, "Image Settings")

    def apply_settings(self):
        """Extract values from widgets and save via controller"""
        # Extract camera settings
        new_camera_config = {}
        for setting_name, widget in self.camera_widgets.items():
            if isinstance(widget, QComboBox):
                new_camera_config[setting_name] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                new_camera_config[setting_name] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                text = widget.text()
                new_camera_config[setting_name] = text
        # Extract image settings
        new_image_config = {}
        for setting_name, widget in self.image_widgets.items():
            if isinstance(widget, QComboBox):
                new_image_config[setting_name] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                new_image_config[setting_name] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                text = widget.text()
                new_image_config[setting_name] = text

        for setting_name, widget in self.image_widgets.items():
            text = widget.text()
            new_image_config[setting_name] = text

        # Now save the new_camera_config via the controller
        self.controller.set_camera_config(new_camera_config)
        self.controller.set_image_config(new_image_config)
    
    def save_to_config(self):
        """Apply settings and save to config.json"""
        # Extract camera settings
        new_camera_config = {}
        for setting_name, widget in self.camera_widgets.items():
            if isinstance(widget, QComboBox):
                new_camera_config[setting_name] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                new_camera_config[setting_name] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                text = widget.text()
                new_camera_config[setting_name] = text
        # Extract image settings
        new_image_config = {}
        for setting_name, widget in self.image_widgets.items():
            if isinstance(widget, QComboBox):
                new_image_config[setting_name] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                new_image_config[setting_name] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                text = widget.text()
                new_image_config[setting_name] = text

        for setting_name, widget in self.image_widgets.items():
            text = widget.text()
            new_image_config[setting_name] = text

        # Save via the controller
        self.controller.set_camera_config(new_camera_config)
        self.controller.set_image_config(new_image_config)
        
        # Save to config.json
        self.controller.save_config()
    
    def search_cameras(self):
        """Search for cameras and populate table"""
        
        # Get list of cameras from controller
        cameras = self.controller.search_cameras()
        # Populate table (controller.search_cameras() will update controller's cache)
        self._populate_camera_table(cameras)
    
    def _populate_camera_table(self, cameras):
        """Populate the camera table with camera list"""
        
        # Clear existing rows
        self.camera_table.setRowCount(0)
        
        # Populate table
        for camera in cameras:
            row = self.camera_table.rowCount()
            self.camera_table.insertRow(row)
            
            # Index column (camera['idx'] is now an int, convert to str for display)
            idx = camera.get("idx", row)
            self.camera_table.setItem(row, 0, QTableWidgetItem(str(idx)))

            # Model column
            model = camera.get("model", "Unknown")
            self.camera_table.setItem(row, 1, QTableWidgetItem(model))

            # Serial number column
            serial = camera.get("serial_number", "N/A")
            self.camera_table.setItem(row, 2, QTableWidgetItem(serial))

            # Connection column - Connect button
            connect_btn = QPushButton("Connect")
            connect_btn.clicked.connect(lambda checked, cam=camera, r=row: self.toggle_camera_connection(cam, r))
            self.camera_table.setCellWidget(row, 4, connect_btn)
            
            # If this camera is currently connected, update button
            if self.controller.get_is_camera_connected():
                connected_idx = self.controller._camera_idx
                if connected_idx == camera.get("idx"):
                    connect_btn.setText("Disconnect")
                else:
                    connect_btn.setEnabled(False)

    def toggle_camera_connection(self, camera_info, row):
        """Toggle connection for a specific camera"""
        
        btn = self.camera_table.cellWidget(row, 4)
        if not btn:
            return
        
        if btn.text() == "Connect":
            # Connect to camera
            success = self.controller.connect_camera(camera_info)
            if success:
                btn.setText("Disconnect")
                self.make_sensor_settings_tab()
                self.make_image_settings_tab()
                
                # Create Apply button
                self.apply_btn = QPushButton("Apply")
                self.apply_btn.clicked.connect(self.apply_settings)
                self.main_layout.insertWidget(self.main_layout.count() - 1, self.apply_btn)
                
                # Create Save to Config button
                self.save_to_config_btn = QPushButton("Save to config")
                self.save_to_config_btn.clicked.connect(self.save_to_config)
                self.main_layout.insertWidget(self.main_layout.count() - 1, self.save_to_config_btn)
                
                # Disable apply and save buttons if acquisition is in progress
                is_acquiring = self.controller.acquisition_in_progress()
                self.apply_btn.setEnabled(not is_acquiring)
                self.save_to_config_btn.setEnabled(not is_acquiring)
                if is_acquiring:
                    self.apply_btn.setToolTip("Cannot change settings during acquisition")
                    self.save_to_config_btn.setToolTip("Cannot change settings during acquisition")
                
                # Disable other connect buttons
                for r in range(self.camera_table.rowCount()):
                    if r != row:
                        other_btn = self.camera_table.cellWidget(r, 4)
                        if other_btn and other_btn.text() == "Connect":
                            other_btn.setEnabled(False)
                
            else:
                logger.warning(f"Failed to connect to camera: {camera_info}")
        else:
            # Disconnect from camera (camera_info['idx'] is stored as an int)
            idx = camera_info.get("idx", row)
            success = self.controller.disconnect_camera(idx)
            if success:
                btn.setText("Connect")
                
                # Re-enable other connect buttons
                for r in range(self.camera_table.rowCount()):
                    other_btn = self.camera_table.cellWidget(r, 4)
                    if other_btn and other_btn.text() == "Connect":
                        other_btn.setEnabled(True)
