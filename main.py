"""Main application entry point - imports from gui package."""

import sys
import json
import logging
from PyQt5.QtWidgets import QApplication

from camera_control.gui import MainWindow, load_stylesheet
from camera_control.Controller import Controller

logging.basicConfig(level=logging.INFO)

# TODO: add support for internal trigger. Need to specify acquisition trigger period in that case.


if __name__ == "__main__":
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
