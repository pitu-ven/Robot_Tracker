# robot_tracker/hardware/__init__.py
"""
Module hardware - Drivers pour caméras et communication robot - Version 1.2
Modification: Correction des noms et ajout d'alias pour compatibilité
"""

from .usb3_camera_driver import USB3CameraDriver, list_available_cameras, test_camera
from .realsense_driver import RealSenseCamera, list_available_realsense, test_realsense

# Alias pour compatibilité avec les différentes conventions de nommage
USB3Camera = USB3CameraDriver
RealSenseDriver = RealSenseCamera

__all__ = [
    'USB3CameraDriver', 'USB3Camera', 
    'RealSenseCamera', 'RealSenseDriver',
    'list_available_cameras', 'list_available_realsense', 
    'test_camera', 'test_realsense'
]