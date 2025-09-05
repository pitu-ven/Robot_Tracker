# robot_tracker/main.py
# Version 1.1 - Ajout gestion verbosité logging
# Modification: Configuration du logging selon niveau de verbosité choisi

import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.config_manager import ConfigManager
from utils.logging_utils import setup_application_logging


def setup_logging_directory():
    """Crée le dossier logs s'il n'existe pas"""
    logs_dir = Path("logs")
    if not logs_dir.exists():
        logs_dir.mkdir(exist_ok=True)
        print(f"📁 Dossier logs créé: {logs_dir.absolute()}")


def main():
    """Point d'entrée principal de l'application"""
    
    # Création du dossier logs avant toute configuration
    setup_logging_directory()
    
    # Chargement de la configuration
    config = ConfigManager()
    
    # Vérification du mode de verbosité pour optimiser le chargement
    verbosity = config.get_logging_verbosity()
    
    # Si mode Faible, rechargement silencieux des configurations
    if verbosity == "Faible":
        from utils.system_logging_suppressor import QuietConfigManager
        QuietConfigManager.load_configs_quietly(config)
    
    # Configuration du logging selon la verbosité choisie
    setup_application_logging(config)
    
    # Récupération du logger après configuration
    logger = logging.getLogger(__name__)
    
    # Messages de démarrage adaptés au niveau de verbosité
    if verbosity != "Faible":
        available_levels = config.get_available_verbosity_levels()
        
        logger.info("🚀 Démarrage Robot Trajectory Controller")
        logger.info(f"📋 Verbosité des logs: {verbosity}")
        logger.debug(f"🔧 Niveaux disponibles: {available_levels}")
    
    # Création de l'application PyQt6
    app = QApplication(sys.argv)
    
    # Application du style depuis la config
    style = config.get('ui', 'theme.style', 'Fusion')
    app.setStyle(style)
    
    if verbosity == "Debug":
        logger.debug(f"🎨 Style appliqué: {style}")
    
    # Création de la fenêtre principale
    if verbosity not in ["Faible"]:
        logger.info("🖼️ Initialisation de l'interface principale...")
    
    window = MainWindow(config)
    window.show()
    
    if verbosity not in ["Faible"]:
        logger.info("✅ Application prête")
    
    # Lancement de la boucle principale
    try:
        return app.exec()
    except KeyboardInterrupt:
        if verbosity != "Faible":
            logger.info("⏹️ Arrêt demandé par l'utilisateur")
        return 0
    except Exception as e:
        if verbosity != "Faible":
            logger.error(f"❌ Erreur fatale: {e}")
        return 1
    finally:
        if verbosity == "Debug":
            logger.info("🔄 Fermeture de l'application")


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)