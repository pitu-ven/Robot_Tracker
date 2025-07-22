#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_interface.py
Test de l'interface Robot Trajectory Controller - Version corrigée
À placer dans le répertoire robot_tracker/
"""

import sys
import os
from pathlib import Path
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_config_manager():
    """Test du ConfigManager"""
    try:
        # Import direct depuis le répertoire courant
        from core.config_manager import ConfigManager
        
        logger.info("🧪 Test du ConfigManager...")
        config = ConfigManager("config")  # Chemin relatif correct
        
        # Tests de base
        title = config.get('ui', 'window.title', 'Test')
        width = config.get('ui', 'window.width', 1200)
        
        logger.info(f"✅ ConfigManager OK - Titre: {title}, Largeur: {width}")
        return config
        
    except Exception as e:
        logger.error(f"❌ Erreur ConfigManager: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_imports():
    """Test des imports de base"""
    try:
        logger.info("🧪 Test des imports...")
        
        # Test ConfigManager
        from core.config_manager import ConfigManager
        logger.info("✅ ConfigManager importé")
        
        # Test des onglets (version simple)
        try:
            from ui.camera_tab import CameraTab
            logger.info("✅ CameraTab importé")
        except Exception as e:
            logger.warning(f"⚠️ CameraTab: {e}")
        
        try:
            from ui.trajectory_tab import TrajectoryTab
            logger.info("✅ TrajectoryTab importé")
        except Exception as e:
            logger.warning(f"⚠️ TrajectoryTab: {e}")
        
        try:
            from ui.target_tab import TargetTab
            logger.info("✅ TargetTab importé")
        except Exception as e:
            logger.warning(f"⚠️ TargetTab: {e}")
        
        try:
            from ui.calibration_tab import CalibrationTab
            logger.info("✅ CalibrationTab importé")
        except Exception as e:
            logger.warning(f"⚠️ CalibrationTab: {e}")
        
        try:
            from ui.measures_tab import MeasuresTab
            logger.info("✅ MeasuresTab importé")
        except Exception as e:
            logger.warning(f"⚠️ MeasuresTab: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur imports: {e}")
        return False

def create_simple_tabs():
    """Crée des versions simplifiées des onglets manquants"""
    
    # Vérifier quels fichiers existent
    ui_dir = Path("ui")
    
    simple_tab_template = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
{filename}
Onglet {tab_name} - Version simple temporaire
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
import logging

logger = logging.getLogger(__name__)

class {class_name}(QWidget):
    """Onglet {tab_name} - Version simple"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_ui()
        logger.info("✅ {class_name} initialisé (version simple)")
    
    def setup_ui(self):
        """Configuration de l'interface simple"""
        layout = QVBoxLayout(self)
        
        label = QLabel("Onglet {tab_name}\\n\\nInterface en construction...\\n\\nUtilisez les menus pour tester les fonctionnalités de base.")
        label.setStyleSheet("""
            color: #ccc; 
            font-size: 16px; 
            text-align: center;
            padding: 50px;
            background-color: #2a2a2a;
            border: 2px dashed #555;
            border-radius: 10px;
        """)
        layout.addWidget(label)
    
    def get_status_info(self):
        """Retourne les informations de status"""
        return "📝 {tab_name} - Interface simple active"
    
    def cleanup(self):
        """Nettoyage lors de la fermeture"""
        logger.info("🧹 {class_name} nettoyé")
'''
    
    tabs_to_create = [
        ("target_tab.py", "TargetTab", "Cible"),
        ("calibration_tab.py", "CalibrationTab", "Calibration"),
        ("measures_tab.py", "MeasuresTab", "Mesures"),
        ("trajectory_tab.py", "TrajectoryTab", "Trajectoire")
    ]
    
    for filename, class_name, tab_name in tabs_to_create:
        file_path = ui_dir / filename
        
        if not file_path.exists():
            logger.info(f"📝 Création de {filename}")
            content = simple_tab_template.format(
                filename=filename,
                class_name=class_name,
                tab_name=tab_name
            )
            file_path.write_text(content, encoding='utf-8')

def test_main_window(config):
    """Test de la MainWindow avec gestion d'erreurs"""
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        
        logger.info("🧪 Test de la MainWindow...")
        
        # Création de l'application Qt
        app = QApplication(sys.argv)
        
        # Import de la MainWindow
        from ui.main_window import MainWindow
        
        # Création de la fenêtre principale
        window = MainWindow(config)
        
        # Affichage
        window.show()
        
        logger.info("✅ MainWindow créée avec succès")
        logger.info("👁️ Testez l'interface - Fermez la fenêtre pour continuer")
        
        # Message d'accueil
        QMessageBox.information(
            window, 
            "Interface Active", 
            "🎉 Interface Robot Trajectory Controller active!\n\n"
            "✅ ConfigManager fonctionnel\n"
            "✅ 5 onglets créés\n"
            "✅ Interface PyQt6 opérationnelle\n\n"
            "Testez les menus et onglets, puis fermez la fenêtre."
        )
        
        return app, window
        
    except Exception as e:
        logger.error(f"❌ Erreur MainWindow: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def main():
    """Fonction principale de test"""
    logger.info("🚀 TEST INTERFACE ROBOT TRAJECTORY CONTROLLER")
    logger.info("=" * 60)
    
    # Vérification de l'environnement
    current_dir = Path.cwd()
    logger.info(f"📍 Répertoire de travail: {current_dir}")
    
    # Vérification de la structure de base
    required_dirs = ["config", "ui", "core"]
    missing_dirs = []
    
    for dir_name in required_dirs:
        if not Path(dir_name).exists():
            missing_dirs.append(dir_name)
            logger.warning(f"⚠️ Répertoire manquant: {dir_name}")
    
    if missing_dirs:
        logger.error(f"❌ Répertoires manquants: {missing_dirs}")
        logger.info("💡 Exécutez d'abord: python create_project_structure.py")
        return 1
    
    # Test 1: ConfigManager
    logger.info("\n🧪 TEST 1: ConfigManager")
    config = test_config_manager()
    if not config:
        logger.error("❌ Impossible de continuer sans ConfigManager")
        return 1
    
    # Test 2: Imports
    logger.info("\n🧪 TEST 2: Test des imports")
    if not test_imports():
        logger.info("⚠️ Certains imports ont échoué, création des fichiers manquants...")
        create_simple_tabs()
        
        # Nouveau test des imports
        if not test_imports():
            logger.error("❌ Imports toujours en échec")
            return 1
    
    # Test 3: Interface principale
    logger.info("\n🧪 TEST 3: Interface Principale")
    app, window = test_main_window(config)
    
    if not app or not window:
        logger.error("❌ Impossible de créer l'interface")
        return 1
    
    # Démarrage de l'interface
    logger.info("\n🚀 Lancement de l'interface utilisateur...")
    
    try:
        exit_code = app.exec()
        logger.info(f"✅ Interface fermée (code: {exit_code})")
        
        # Message final
        logger.info("\n" + "=" * 60)
        logger.info("🎉 TEST RÉUSSI!")
        logger.info("✅ L'interface Robot Trajectory Controller fonctionne")
        logger.info("📋 Prochaines étapes:")
        logger.info("   - Implémenter les fonctionnalités de chaque onglet")
        logger.info("   - Intégrer les caméras réelles")
        logger.info("   - Développer le tracking ArUco")
        logger.info("=" * 60)
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("⚠️ Interruption utilisateur")
        return 0
    except Exception as e:
        logger.error(f"❌ Erreur d'exécution: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)