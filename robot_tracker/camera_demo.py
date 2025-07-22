#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
camera_demo.py
Démo rapide pour tester l'intégration des caméras - Version 1.0
Modification: Lanceur simple pour test interface caméras
"""

import sys
import os
import logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QStatusBar
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Ajout du chemin robot_tracker au PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
robot_tracker_path = os.path.join(current_dir, 'robot_tracker')
if os.path.exists(robot_tracker_path):
    sys.path.insert(0, robot_tracker_path)

class CameraDemoConfig:
    """Configuration optimisée pour la démo"""
    
    def __init__(self):
        self.settings = {
            # USB3 Camera - Configuration réduite pour démo
            'camera.usb3_camera.device_id': 0,
            'camera.usb3_camera.width': 640,  # Résolution réduite pour fluidité
            'camera.usb3_camera.height': 480,
            'camera.usb3_camera.fps': 30,
            'camera.usb3_camera.buffer_size': 1,
            'camera.usb3_camera.auto_exposure': True,
            'camera.usb3_camera.gain': 0,
            
            # RealSense Camera - Configuration optimisée
            'camera.realsense.device_serial': None,
            'camera.realsense.color_width': 640,
            'camera.realsense.color_height': 480,
            'camera.realsense.color_fps': 30,
            'camera.realsense.depth_width': 640,
            'camera.realsense.depth_height': 480,
            'camera.realsense.depth_fps': 30,
            'camera.realsense.enable_infrared': False,
            'camera.realsense.enable_filters': True,
            'camera.realsense.enable_align': True,
            'camera.realsense.spatial_magnitude': 2.0,
            'camera.realsense.spatial_smooth_alpha': 0.5,
            'camera.realsense.temporal_smooth_alpha': 0.4,
            
            # Camera Manager
            'camera.manager.auto_detect_interval': 10.0,
            'camera.manager.max_frame_buffer': 3,
        }
    
    def get(self, section: str, key: str, default=None):
        """Récupère une valeur de configuration"""
        full_key = f"{section}.{key}"
        return self.settings.get(full_key, default)

class CameraDemoWindow(QMainWindow):
    """Fenêtre principale de la démo caméras"""
    
    def __init__(self):
        super().__init__()
        
        # Configuration
        self.config = CameraDemoConfig()
        
        # Initialisation de l'interface
        self._init_ui()
        self._init_status_bar()
        
        # Timer pour mise à jour du statut
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(2000)  # Toutes les 2 secondes
    
    def _init_ui(self):
        """Initialise l'interface utilisateur"""
        self.setWindowTitle("🎥 Démo Caméras - Robot Tracker")
        self.setGeometry(100, 100, 1400, 900)
        
        # Style sombre moderne
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #404040;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 5px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #505050;
                border-color: #007acc;
            }
            QPushButton:pressed {
                background-color: #353535;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #666;
            }
        """)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Chargement de l'onglet caméra
        try:
            from ui.camera_tab import CameraTab
            
            self.camera_tab = CameraTab(self.config, self)
            layout.addWidget(self.camera_tab)
            
            # Connexion des signaux
            self.camera_tab.camera_selected.connect(self._on_camera_selected)
            self.camera_tab.frame_captured.connect(self._on_frame_captured)
            
            print("✅ Interface caméra chargée avec succès")
            
        except ImportError as e:
            print(f"❌ Erreur import CameraTab: {e}")
            self._show_error_widget(f"Erreur chargement interface:\n{e}")
        except Exception as e:
            print(f"❌ Erreur initialisation CameraTab: {e}")
            self._show_error_widget(f"Erreur initialisation:\n{e}")
    
    def _show_error_widget(self, error_message: str):
        """Affiche un widget d'erreur en cas de problème"""
        from PyQt6.QtWidgets import QLabel, QTextEdit
        
        error_widget = QWidget()
        error_layout = QVBoxLayout(error_widget)
        
        title = QLabel("❌ Erreur de chargement")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ff6b6b; margin: 20px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        details = QTextEdit()
        details.setText(error_message)
        details.setReadOnly(True)
        details.setMaximumHeight(200)
        
        help_text = QLabel("""
💡 Vérifications à effectuer:

1. Structure des fichiers:
   robot_tracker/
   ├── hardware/
   │   ├── usb3_camera_driver.py
   │   └── realsense_driver.py
   ├── core/
   │   └── camera_manager.py
   └── ui/
       └── camera_tab.py

2. Dépendances Python:
   pip install PyQt6 opencv-python
   pip install pyrealsense2  # Pour RealSense (optionnel)

3. Matériel:
   - Caméra USB connectée
   - ou Intel RealSense D435/D455

4. Permissions:
   - Accès à la caméra autorisé
   - Pilotes installés (RealSense SDK)
        """)
        help_text.setStyleSheet("color: #cccccc; margin: 10px;")
        
        error_layout.addWidget(title)
        error_layout.addWidget(details)
        error_layout.addWidget(help_text)
        
        self.setCentralWidget(error_widget)
    
    def _init_status_bar(self):
        """Initialise la barre de statut"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #333;
                color: #ccc;
                border-top: 1px solid #555;
            }
        """)
        
        self.status_bar.showMessage("🚀 Démo caméras prête - Détectez et ouvrez une caméra pour commencer")
    
    def _update_status(self):
        """Met à jour la barre de statut"""
        try:
            if hasattr(self, 'camera_tab'):
                active_cameras = self.camera_tab.get_active_cameras()
                is_streaming = self.camera_tab.is_camera_streaming()
                
                if active_cameras:
                    cam_count = len(active_cameras)
                    stream_status = "🎬 Streaming" if is_streaming else "⏸️ Arrêté"
                    message = f"📷 {cam_count} caméra(s) active(s) - {stream_status}"
                else:
                    message = "💤 Aucune caméra active - Utilisez 'Détecter caméras' pour commencer"
                
                self.status_bar.showMessage(message)
            
        except Exception as e:
            self.status_bar.showMessage(f"❌ Erreur statut: {e}")
    
    def _on_camera_selected(self, alias: str):
        """Callback lors de la sélection d'une caméra"""
        print(f"📷 Caméra sélectionnée: {alias}")
        self.status_bar.showMessage(f"📷 Caméra sélectionnée: {alias}", 3000)
    
    def _on_frame_captured(self, alias: str, frame_data: dict):
        """Callback lors de la capture d'une frame"""
        print(f"📸 Frame capturée: {alias}")
        
        color_shape = frame_data['color'].shape if frame_data.get('color') is not None else 'N/A'
        depth_shape = frame_data['depth'].shape if frame_data.get('depth') is not None else 'N/A'
        
        message = f"📸 Capture {alias}: Couleur {color_shape}"
        if depth_shape != 'N/A':
            message += f", Profondeur {depth_shape}"
        
        self.status_bar.showMessage(message, 5000)
    
    def closeEvent(self, event):
        """Nettoyage lors de la fermeture"""
        print("🔄 Fermeture de la démo...")
        
        try:
            if hasattr(self, 'camera_tab'):
                # Nettoyage via l'onglet caméra
                self.camera_tab.close()
            
            self.status_timer.stop()
            print("✅ Nettoyage terminé")
            
        except Exception as e:
            print(f"❌ Erreur lors du nettoyage: {e}")
        
        event.accept()

def check_dependencies():
    """Vérifie les dépendances nécessaires"""
    print("🔍 Vérification des dépendances...")
    
    dependencies = {
        'PyQt6': False,
        'cv2': False,
        'numpy': False,
        'pyrealsense2': False
    }
    
    # Test PyQt6
    try:
        import PyQt6
        dependencies['PyQt6'] = True
        print("✅ PyQt6 disponible")
    except ImportError:
        print("❌ PyQt6 non disponible - pip install PyQt6")
    
    # Test OpenCV
    try:
        import cv2
        dependencies['cv2'] = True
        print("✅ OpenCV disponible")
    except ImportError:
        print("❌ OpenCV non disponible - pip install opencv-python")
    
    # Test NumPy
    try:
        import numpy
        dependencies['numpy'] = True
        print("✅ NumPy disponible")
    except ImportError:
        print("❌ NumPy non disponible - pip install numpy")
    
    # Test RealSense (optionnel)
    try:
        import pyrealsense2
        dependencies['pyrealsense2'] = True
        print("✅ RealSense SDK disponible")
    except ImportError:
        print("⚠️ RealSense SDK non disponible (optionnel) - pip install pyrealsense2")
    
    # Vérification critique
    critical_deps = ['PyQt6', 'cv2', 'numpy']
    missing_critical = [dep for dep in critical_deps if not dependencies[dep]]
    
    if missing_critical:
        print(f"\n❌ Dépendances critiques manquantes: {', '.join(missing_critical)}")
        return False
    else:
        print("\n✅ Toutes les dépendances critiques sont disponibles")
        return True

def main():
    """Point d'entrée principal de la démo"""
    print("🎥 Démo Caméras - Robot Tracker")
    print("=" * 50)
    
    # Vérification des dépendances
    if not check_dependencies():
        print("\n💡 Installez les dépendances manquantes et relancez la démo")
        return 1
    
    # Vérification de la structure des fichiers
    robot_tracker_path = os.path.join(os.path.dirname(__file__), 'robot_tracker')
    required_files = [
        'hardware/usb3_camera_driver.py',
        'hardware/realsense_driver.py',
        'core/camera_manager.py',
        'ui/camera_tab.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = os.path.join(robot_tracker_path, file_path)
        if not os.path.exists(full_path):
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n❌ Fichiers manquants dans robot_tracker/:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        print("\n💡 Assurez-vous que tous les fichiers sont présents")
        return 1
    
    # Lancement de l'application Qt
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("Robot Tracker - Démo Caméras")
        app.setApplicationVersion("1.0")
        
        # Fenêtre principale
        window = CameraDemoWindow()
        window.show()
        
        print("\n🚀 Démo lancée avec succès!")
        print("💡 Instructions:")
        print("   1. Cliquez sur '🔄 Détecter caméras'")
        print("   2. Sélectionnez une caméra dans la liste")
        print("   3. Cliquez sur '📷 Ouvrir'")
        print("   4. Cliquez sur '▶️ Démarrer' pour le streaming")
        print("   5. Testez les fonctionnalités (zoom, profondeur, capture)")
        print("\n🔄 Fermez la fenêtre pour terminer")
        
        # Boucle événementielle
        exit_code = app.exec()
        print(f"\n👋 Démo terminée (code: {exit_code})")
        return exit_code
        
    except Exception as e:
        print(f"\n❌ Erreur lancement démo: {e}")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Démo interrompue par l'utilisateur")
        sys.exit(1)