#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
camera_demo.py - Robot_Tracker/robot_tracker/camera_demo.py
Démo rapide pour tester l'intégration des caméras - Version 1.1
Modification: Correction des chemins de fichiers pour détection correcte
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

# Ajout du chemin courant au PYTHONPATH pour les imports locaux
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def check_dependencies():
    """Vérification des dépendances Python requises"""
    print("🔍 Vérification des dépendances...")
    
    dependencies = {}
    
    # PyQt6
    try:
        import PyQt6
        dependencies['PyQt6'] = True
        print("✅ PyQt6 disponible")
    except ImportError:
        dependencies['PyQt6'] = False
        print("❌ PyQt6 manquant - pip install PyQt6")
    
    # OpenCV
    try:
        import cv2
        dependencies['cv2'] = True
        print("✅ OpenCV disponible")
    except ImportError:
        dependencies['cv2'] = False
        print("❌ OpenCV manquant - pip install opencv-python")
    
    # NumPy
    try:
        import numpy
        dependencies['numpy'] = True
        print("✅ NumPy disponible")
    except ImportError:
        dependencies['numpy'] = False
        print("❌ NumPy manquant - pip install numpy")
    
    # RealSense (optionnel)
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

class CameraDemoConfig:
    """Configuration simplifiée pour la démo"""
    
    def __init__(self):
        self.settings = {
            # USB3 Camera
            'camera.usb3_camera.device_id': 0,
            'camera.usb3_camera.width': 640,
            'camera.usb3_camera.height': 480,
            'camera.usb3_camera.fps': 30,
            
            # RealSense Camera
            'camera.realsense.color_width': 640,
            'camera.realsense.color_height': 480,
            'camera.realsense.color_fps': 30,
            'camera.realsense.depth_width': 640,
            'camera.realsense.depth_height': 480,
            'camera.realsense.depth_fps': 30,
        }
    
    def get(self, section: str, key: str, default=None):
        """Récupère une valeur de configuration"""
        full_key = f"{section}.{key}"
        return self.settings.get(full_key, default)

class CameraDemoWindow(QMainWindow):
    """Fenêtre principale de la démo caméras"""
    
    def __init__(self):
        super().__init__()
        self.config = CameraDemoConfig()
        self.camera_tab = None
        self.init_ui()
        self.load_camera_interface()
    
    def init_ui(self):
        """Initialisation de l'interface utilisateur"""
        self.setWindowTitle("🎥 Robot Tracker - Démo Caméras")
        self.setGeometry(100, 100, 1200, 800)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        self.main_layout = QVBoxLayout(central_widget)
        
        # Barre de statut
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("⏳ Chargement interface caméra...")
    
    def load_camera_interface(self):
        """Charge l'interface caméra"""
        try:
            # Import dynamique pour gérer les erreurs
            from ui.camera_tab import CameraTab
            from core.camera_manager import CameraManager
            
            # Création du gestionnaire de caméras
            camera_manager = CameraManager(self.config)
            
            # Création de l'onglet caméra
            self.camera_tab = CameraTab(self.config, camera_manager)
            self.main_layout.addWidget(self.camera_tab)
            
            # Connexion des signaux
            self.camera_tab.camera_selected.connect(self._on_camera_selected)
            self.camera_tab.frame_captured.connect(self._on_frame_captured)
            
            self.status_bar.showMessage("✅ Interface caméra chargée - Prêt pour la démo")
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
   - Autoriser l'accès à la caméra
        """)
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #666666; font-size: 12px; margin: 10px;")
        
        error_layout.addWidget(title)
        error_layout.addWidget(details)
        error_layout.addWidget(help_text)
        
        self.main_layout.addWidget(error_widget)
        self.status_bar.showMessage("❌ Erreur - Vérifiez la structure des fichiers")
    
    def _on_camera_selected(self, camera_info):
        """Gère la sélection d'une caméra"""
        camera_name = camera_info.get('name', 'Caméra inconnue')
        self.status_bar.showMessage(f"📷 Caméra sélectionnée: {camera_name}")
        print(f"📷 Caméra sélectionnée: {camera_name}")
    
    def _on_frame_captured(self, frame_data):
        """Gère la capture d'une frame"""
        self.status_bar.showMessage("📸 Frame capturée")

def main():
    """Point d'entrée principal de la démo"""
    print("🎥 Démo Caméras - Robot Tracker")
    print("=" * 50)
    
    # Vérification des dépendances
    if not check_dependencies():
        print("\n💡 Installez les dépendances manquantes et relancez la démo")
        return 1
    
    # Vérification de la structure des fichiers (chemin corrigé)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    required_files = [
        'hardware/usb3_camera_driver.py',
        'hardware/realsense_driver.py',
        'core/camera_manager.py',
        'ui/camera_tab.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = os.path.join(current_dir, file_path)
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