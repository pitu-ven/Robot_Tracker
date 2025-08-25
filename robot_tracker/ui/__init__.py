# robot_tracker/ui/__init__.py
# Version 2.0 - Correction imports pour compatibilité tests
# Modification: Imports absolus pour éviter les erreurs relatives

try:
    from ui.camera_tab import CameraTab
except ImportError:
    # Fallback pour les tests
    CameraTab = None

__all__ = ['CameraTab']