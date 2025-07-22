#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_camera_integration.py
Script de test complet pour l'intégration des caméras - Version 1.0
Modification: Test complet USB3 + RealSense + interface Qt
"""

import sys
import os
import logging
import time
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration dummy pour les tests
class DummyConfig:
    """Configuration dummy pour les tests"""
    
    def __init__(self):
        self.data = {
            # USB3 Camera
            'camera.usb3_camera.device_id': 0,
            'camera.usb3_camera.width': 1280,
            'camera.usb3_camera.height': 720,
            'camera.usb3_camera.fps': 30,
            'camera.usb3_camera.buffer_size': 1,
            'camera.usb3_camera.auto_exposure': True,
            'camera.usb3_camera.gain': 0,
            
            # RealSense Camera
            'camera.realsense.device_serial': None,  # Auto-detect
            'camera.realsense.color_width': 1280,
            'camera.realsense.color_height': 720,
            'camera.realsense.color_fps': 30,
            'camera.realsense.depth_width': 1280,
            'camera.realsense.depth_height': 720,
            'camera.realsense.depth_fps': 30,
            'camera.realsense.enable_infrared': False,
            'camera.realsense.enable_filters': True,
            'camera.realsense.enable_align': True,
            'camera.realsense.spatial_magnitude': 2.0,
            'camera.realsense.spatial_smooth_alpha': 0.5,
            'camera.realsense.temporal_smooth_alpha': 0.4,
            
            # Camera Manager
            'camera.manager.auto_detect_interval': 5.0,
            'camera.manager.max_frame_buffer': 5,
        }
    
    def get(self, section: str, key: str, default=None):
        """Récupère une valeur de configuration"""
        full_key = f"{section}.{key}"
        return self.data.get(full_key, default)

def test_hardware_drivers():
    """Test des drivers hardware individuellement"""
    print("🔧 Test des drivers hardware")
    print("=" * 50)
    
    config = DummyConfig()
    
    # 1. Test USB3 Camera
    print("\n📷 Test USB3 Camera Driver...")
    try:
        from hardware.usb3_camera_driver import USB3Camera, list_available_cameras, test_camera
        
        # Détection
        usb_cameras = list_available_cameras()
        print(f"Caméras USB détectées: {len(usb_cameras)}")
        
        if usb_cameras:
            # Test de la première caméra
            device_id = usb_cameras[0]['device_id']
            print(f"Test caméra USB {device_id}...")
            success = test_camera(device_id, duration=2.0)
            print(f"Résultat: {'✅ Succès' if success else '❌ Échec'}")
        
    except ImportError as e:
        print(f"❌ USB3 Driver non disponible: {e}")
    except Exception as e:
        print(f"❌ Erreur test USB3: {e}")
    
    # 2. Test RealSense Camera
    print("\n🎥 Test RealSense Camera Driver...")
    try:
        from hardware.realsense_driver import RealSenseCamera, list_available_realsense, test_realsense
        
        # Détection
        rs_cameras = list_available_realsense()
        print(f"Caméras RealSense détectées: {len(rs_cameras)}")
        
        if rs_cameras:
            # Test de la première caméra
            device_serial = rs_cameras[0]['serial']
            print(f"Test RealSense {device_serial}...")
            success = test_realsense(device_serial, duration=2.0)
            print(f"Résultat: {'✅ Succès' if success else '❌ Échec'}")
        
    except ImportError as e:
        print(f"❌ RealSense Driver non disponible: {e}")
    except Exception as e:
        print(f"❌ Erreur test RealSense: {e}")

def test_camera_manager():
    """Test du gestionnaire de caméras"""
    print("\n🎛️ Test Camera Manager")
    print("=" * 50)
    
    try:
        from core.camera_manager import CameraManager, test_camera_manager
        
        # Test complet du manager
        success = test_camera_manager(duration=3.0)
        print(f"Résultat CameraManager: {'✅ Succès' if success else '❌ Échec'}")
        
    except ImportError as e:
        print(f"❌ CameraManager non disponible: {e}")
    except Exception as e:
        print(f"❌ Erreur test CameraManager: {e}")

class TestMainWindow(QMainWindow):
    """Fenêtre principale de test"""
    
    def __init__(self):
        super().__init__()
        self.config = DummyConfig()
        self._init_ui()
    
    def _init_ui(self):
        """Initialise l'interface de test"""
        self.setWindowTitle("🎥 Test Intégration Caméras - Robot Tracker")
        self.setGeometry(100, 100, 1200, 800)
        
        # Widget central avec onglets
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Onglets de test
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # Onglet caméra principal
        try:
            from ui.camera_tab import CameraTab
            
            self.camera_tab = CameraTab(self.config)
            tab_widget.addTab(self.camera_tab, "🎥 Caméras")
            
            # Connexion des signaux
            self.camera_tab.camera_selected.connect(self._on_camera_selected)
            self.camera_tab.frame_captured.connect(self._on_frame_captured)
            
            print("✅ Onglet caméra chargé avec succès")
            
        except ImportError as e:
            print(f"❌ Impossible de charger l'onglet caméra: {e}")
            # Création d'un onglet placeholder
            from PyQt6.QtWidgets import QLabel
            placeholder = QLabel(f"Erreur chargement onglet caméra:\n{e}")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tab_widget.addTab(placeholder, "❌ Caméras (Erreur)")
    
    def _on_camera_selected(self, alias: str):
        """Callback sélection de caméra"""
        print(f"📷 Caméra sélectionnée: {alias}")
    
    def _on_frame_captured(self, alias: str, frame_data: dict):
        """Callback capture de frame"""
        print(f"📸 Frame capturée de {alias} à {time.strftime('%H:%M:%S')}")
        if frame_data.get('depth') is not None:
            print(f"   - Couleur: {frame_data['color'].shape}")
            print(f"   - Profondeur: {frame_data['depth'].shape}")
        else:
            print(f"   - Couleur: {frame_data['color'].shape}")

def test_qt_interface():
    """Test de l'interface Qt complète"""
    print("\n🖥️ Test Interface Qt")
    print("=" * 50)
    
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("Robot Tracker - Test Caméras")
        
        # Fenêtre principale
        window = TestMainWindow()
        window.show()
        
        print("✅ Interface Qt lancée")
        print("💡 Testez manuellement:")
        print("   1. Détection des caméras")
        print("   2. Ouverture d'une caméra")
        print("   3. Démarrage du streaming")
        print("   4. Capture d'images")
        print("   5. Changement de zoom/profondeur")
        print("\n🔄 Fermez la fenêtre pour terminer le test")
        
        # Boucle événementielle
        return app.exec()
        
    except Exception as e:
        print(f"❌ Erreur interface Qt: {e}")
        return 1

def run_integration_tests():
    """Lance tous les tests d'intégration"""
    print("🚀 Tests d'intégration caméras - Robot Tracker")
    print("=" * 60)
    
    # Configuration du path pour les imports
    current_dir = os.path.dirname(os.path.abspath(__file__))
    robot_tracker_dir = os.path.join(current_dir, 'robot_tracker')
    if os.path.exists(robot_tracker_dir):
        sys.path.insert(0, robot_tracker_dir)
    
    # Tests séquentiels
    try:
        # 1. Test des drivers
        test_hardware_drivers()
        
        # 2. Test du manager
        test_camera_manager()
        
        # 3. Test de l'interface (interactif)
        if '--no-gui' not in sys.argv:
            return test_qt_interface()
        else:
            print("\n🖥️ Test interface Qt ignoré (--no-gui)")
            return 0
            
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrompus par l'utilisateur")
        return 1
    except Exception as e:
        print(f"\n❌ Erreur générale: {e}")
        return 1

def show_help():
    """Affiche l'aide"""
    print("""
🎥 Test d'intégration caméras - Robot Tracker

Usage: python test_camera_integration.py [options]

Options:
  --no-gui          Ne lance pas l'interface Qt (tests CLI uniquement)
  --help, -h        Affiche cette aide

Tests effectués:
  1. 🔧 Drivers hardware (USB3 + RealSense)
  2. 🎛️ Gestionnaire de caméras
  3. 🖥️ Interface Qt complète (interactif)

Prérequis:
  - Python 3.8+
  - PyQt6
  - OpenCV (cv2)
  - pyrealsense2 (optionnel, pour RealSense)
  - Caméra USB ou Intel RealSense connectée

Structure attendue:
  robot_tracker/
  ├── hardware/
  │   ├── usb3_camera_driver.py
  │   └── realsense_driver.py
  ├── core/
  │   └── camera_manager.py
  └── ui/
      └── camera_tab.py

Exemples d'usage:
  python test_camera_integration.py              # Tests complets avec GUI
  python test_camera_integration.py --no-gui     # Tests CLI uniquement
""")

if __name__ == "__main__":
    # Gestion des arguments
    if '--help' in sys.argv or '-h' in sys.argv:
        show_help()
        sys.exit(0)
    
    # Lancement des tests
    exit_code = run_integration_tests()
    sys.exit(exit_code)