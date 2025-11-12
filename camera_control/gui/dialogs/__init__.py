"""Dialog widgets for camera control application"""

from .camera_config import CameraConfigDialog
from .socket_config import SocketConfigDialog
from .acquisition_settings import AcquisitionSettingsDialog

__all__ = [
    'CameraConfigDialog',
    'SocketConfigDialog',
    'AcquisitionSettingsDialog'
]
