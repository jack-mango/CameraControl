"""Socket configuration dialog"""

import logging
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton
)

logger = logging.getLogger(__name__)


class SocketConfigDialog(QDialog):
    def __init__(self, socket_config, controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Socket Settings")
        self.resize(400, 200)
        self.socket_config = socket_config
        self.controller = controller

        # Main layout
        main_layout = QVBoxLayout(self)

        # Form for IP and Port
        form_layout = QFormLayout()
        
        # IP Address field
        self.ip_address_edit = QLineEdit(socket_config.get("ip_address", "192.168.1.113"))
        form_layout.addRow("IP Address:", self.ip_address_edit)
        
        # Port field
        self.port_edit = QLineEdit(str(socket_config.get("port", "5009")))
        form_layout.addRow("Port:", self.port_edit)
        
        main_layout.addLayout(form_layout)

        # Connect/Disconnect button
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_socket_connection)
        
        # Check if socket is already connected and update button state
        if self.controller.is_socket_connected:
            self.connect_btn.setText("Disconnect")
            self.ip_address_edit.setEnabled(False)
            self.port_edit.setEnabled(False)
        
        # Disable connect button if acquisition is in progress
        is_acquiring = self.controller.acquisition_in_progress()
        if is_acquiring:
            self.connect_btn.setEnabled(False)
            self.connect_btn.setToolTip("Cannot change socket connection during acquisition")

        # Save to config button
        self.save_to_config_btn = QPushButton("Save to config")
        self.save_to_config_btn.clicked.connect(self.save_to_config)
        
        # Disable save button if acquisition is in progress
        if is_acquiring:
            self.save_to_config_btn.setEnabled(False)
            self.save_to_config_btn.setToolTip("Cannot change settings during acquisition")
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        main_layout.addWidget(self.connect_btn)
        main_layout.addWidget(self.save_to_config_btn)
        main_layout.addWidget(close_btn)

    def toggle_socket_connection(self):
        """Toggle socket connection"""
        if self.connect_btn.text() == "Connect":
            # Get current values from text fields
            ip_address = self.ip_address_edit.text()
            port = int(self.port_edit.text())
            
            # Connect to socket
            self.controller.set_socket_config({"ip_address": ip_address, "port": port})
            success = self.controller.connect_socket()
            
            if success:
                logger.info(f"Connected to socket: {ip_address}:{port}")
                self.connect_btn.setText("Disconnect")
                self.ip_address_edit.setEnabled(False)
                self.port_edit.setEnabled(False)
            else:
                logger.warning(f"Failed to connect to socket: {ip_address}:{port}")
        else:
            # Disconnect
            success = self.controller.disconnect_socket()
            if success:
                self.connect_btn.setText("Connect")
                self.ip_address_edit.setEnabled(True)
                self.port_edit.setEnabled(True)
                logger.info("Disconnected from socket")

    def save_to_config(self):
        """Save socket settings to config.json"""
        # Get current values from text fields
        ip_address = self.ip_address_edit.text()
        port = int(self.port_edit.text())
        
        # Update socket config in controller
        self.controller.set_socket_config({"ip_address": ip_address, "port": port})
        
        # Save to config.json
        self.controller.save_config()
        logger.info(f"Socket settings saved to config: {ip_address}:{port}")
