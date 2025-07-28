#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/tests/aruco_demo.py
Démonstration du générateur ArUco - Version 1.0
Modification: Script de démonstration pour valider le générateur ArUco
"""

import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import Qt

# Ajout du chemin parent pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from robot_tracker.ui.aruco_generator import ArUcoGeneratorDialog
    from ui.main_window import ArUcoConfig
    from core.config_manager import ConfigManager
except ImportError as e:
    print(f"❌ Erreur import: {e}")
    print("💡 Exécutez depuis le répertoire robot_tracker/")
    sys.exit(1)

class ArUcoDemoWindow(QMainWindow):
    """Fenêtre de démonstration pour le générateur ArUco"""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.aruco_config = ArUcoConfig(self.config_manager)
        self.init_ui()
    
    def init_ui(self):
        """Initialise l'interface de démonstration"""
        self.setWindowTitle("🎯 Démo Générateur ArUco - Robot Tracker")
        self.setGeometry(100, 100, 400, 300)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Instructions
        from PyQt6.QtWidgets import QLabel
        instructions = QLabel("""
        <h2>🎯 Démonstration du Générateur ArUco</h2>
        <p>Ce générateur permet de créer et d'imprimer des codes ArUco 
        pour le tracking robotique.</p>
        
        <h3>Fonctionnalités :</h3>
        <ul>
        <li>✅ Génération de marqueurs ArUco</li>
        <li>✅ Plusieurs dictionnaires disponibles</li>
        <li>✅ Aperçu temps réel</li>
        <li>✅ Export en images haute qualité</li>
        <li>✅ Impression directe</li>
        <li>✅ Options de personnalisation</li>
        </ul>
        
        <p><b>Cliquez sur le bouton ci-dessous pour ouvrir le générateur.</b></p>
        """)
        instructions.setWordWrap(True)
        instructions.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(instructions)
        
        # Bouton de lancement
        launch_btn = QPushButton("🚀 Ouvrir le Générateur ArUco")
        launch_btn.setMinimumHeight(50)
        launch_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        launch_btn.clicked.connect(self.open_aruco_generator)
        layout.addWidget(launch_btn)
        
        # Bouton de test
        test_btn = QPushButton("🧪 Lancer les Tests")
        test_btn.setMinimumHeight(40)
        test_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        test_btn.clicked.connect(self.run_tests)
        layout.addWidget(test_btn)
        
        layout.addStretch()
    
    def open_aruco_generator(self):
        """Ouvre le générateur ArUco"""
        try:
            print("🎯 Ouverture du générateur ArUco...")
            
            dialog = ArUcoGeneratorDialog(self.aruco_config, self)
            dialog.exec()
            
            print("✅ Générateur ArUco fermé")
            
        except Exception as e:
            print(f"❌ Erreur ouverture générateur: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'ouverture:\n{e}")
    
    def run_tests(self):
        """Lance les tests du générateur"""
        try:
            print("🧪 Lancement des tests...")
            
            from robot_tracker.ui.aruco_generator import TestArUcoGenerator
            
            tester = TestArUcoGenerator()
            success = tester.run_all_tests()
            
            from PyQt6.QtWidgets import QMessageBox
            if success:
                QMessageBox.information(self, "Tests", "✅ Tous les tests sont passés avec succès!")
            else:
                QMessageBox.warning(self, "Tests", "⚠️ Certains tests ont échoué. Consultez la console.")
            
        except Exception as e:
            print(f"❌ Erreur lors des tests: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Erreur", f"Erreur lors des tests:\n{e}")

def check_dependencies():
    """Vérifie les dépendances nécessaires"""
    print("🔍 Vérification des dépendances...")
    
    dependencies = {
        'PyQt6': None,
        'OpenCV': None,
        'NumPy': None
    }
    
    try:
        import PyQt6
        dependencies['PyQt6'] = PyQt6.QtCore.PYQT_VERSION_STR
        print(f"✅ PyQt6: {dependencies['PyQt6']}")
    except ImportError:
        print("❌ PyQt6 manquant")
        return False
    
    try:
        import cv2
        dependencies['OpenCV'] = cv2.__version__
        print(f"✅ OpenCV: {dependencies['OpenCV']}")
        
        # Test spécifique ArUco
        dict_test = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        print("✅ Dictionnaires ArUco disponibles")
        
    except ImportError:
        print("❌ OpenCV manquant")
        return False
    except Exception as e:
        print(f"❌ Problème ArUco: {e}")
        return False
    
    try:
        import numpy as np
        dependencies['NumPy'] = np.__version__
        print(f"✅ NumPy: {dependencies['NumPy']}")
    except ImportError:
        print("❌ NumPy manquant")
        return False
    
    print("✅ Toutes les dépendances sont satisfaites")
    return True

def main():
    """Point d'entrée principal de la démonstration"""
    print("🎯 Démonstration du Générateur ArUco")
    print("Robot Trajectory Controller")
    print("=" * 50)
    
    # Vérification des dépendances
    if not check_dependencies():
        print("\n❌ Dépendances manquantes. Installation requise:")
        print("pip install PyQt6 opencv-python numpy")
        return 1
    
    # Vérification de la structure des fichiers
    current_dir = Path(__file__).parent.parent
    required_files = [
        'ui/aruco_generator.py',
        'core/config_manager.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not (current_dir / file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n❌ Fichiers manquants:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        print("\n💡 Assurez-vous d'exécuter depuis le répertoire robot_tracker/")
        return 1
    
    # Lancement de l'application
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("ArUco Generator Demo")
        app.setApplicationVersion("1.0")
        
        # Configuration du style
        app.setStyle("Fusion")
        
        # Création de la fenêtre
        window = ArUcoDemoWindow()
        window.show()
        
        print("\n🚀 Démonstration lancée!")
        print("💡 Utilisez l'interface pour tester le générateur ArUco")
        print("🔄 Fermez la fenêtre pour terminer")
        
        # Boucle événementielle
        exit_code = app.exec()
        
        print(f"\n👋 Démonstration terminée (code: {exit_code})")
        return exit_code
        
    except Exception as e:
        print(f"\n❌ Erreur lors du lancement: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Démonstration interrompue par l'utilisateur")
        sys.exit(1)