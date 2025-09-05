# robot_tracker/main.py
# Version 1.2 - Correction suppression complète logs OpenCV et configuration
# Modification: Suppression AVANT chargement config + redirection stderr OpenCV

import sys
import logging
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.config_manager import ConfigManager
from utils.logging_utils import setup_application_logging


def setup_opencv_silence():
    """Configure la suppression des logs OpenCV AVANT tout import"""
    # Variables d'environnement OpenCV (doivent être définies AVANT import cv2)
    opencv_env_vars = {
        'OPENCV_LOG_LEVEL': 'SILENT',
        'OPENCV_VIDEOIO_PRIORITY_MSMF': '0',
        'OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS': '0',
        'OPENCV_VIDEOIO_DEBUG': '0',
        'OPENCV_FFMPEG_CAPTURE_OPTIONS': 'rtsp_transport;udp',
        'OPENCV_VIDEOIO_PRIORITY_LIST': 'CAP_V4L2'
    }
    
    for var, value in opencv_env_vars.items():
        os.environ[var] = value


def setup_early_log_suppression():
    """Configure la suppression des logs AVANT le chargement des configurations"""
    # Suppression warnings Python
    import warnings
    warnings.filterwarnings('ignore')
    
    # Configuration logging minimal initial
    logging.basicConfig(
        level=logging.ERROR,  # Seulement les erreurs au début
        format='[%(levelname)s] %(message)s',
        force=True
    )
    
    # Redirection stderr pour capturer les messages OpenCV C++
    class OpenCVStderrFilter:
        def __init__(self, original_stderr):
            self.original_stderr = original_stderr
            
        def write(self, data):
            # Filtrer les messages OpenCV spécifiques
            if isinstance(data, str):
                data_lower = data.lower()
                opencv_patterns = [
                    'msmf', 'obsensor', 'camera index', 'readsample', 
                    'grabframe', 'cap_msmf', 'videoio', 'onreadsample'
                ]
                
                # Si le message contient un pattern OpenCV, l'ignorer
                if any(pattern in data_lower for pattern in opencv_patterns):
                    return
                    
            # Sinon, écrire normalement
            self.original_stderr.write(data)
            
        def flush(self):
            self.original_stderr.flush()
    
    # Application du filtre stderr
    sys.stderr = OpenCVStderrFilter(sys.stderr)


def setup_logging_directory():
    """Crée le dossier logs s'il n'existe pas"""
    logs_dir = Path("logs")
    if not logs_dir.exists():
        logs_dir.mkdir(exist_ok=True)


def main():
    """Point d'entrée principal de l'application"""
    
    # ÉTAPE 1: Suppression OpenCV AVANT tout import
    setup_opencv_silence()
    setup_early_log_suppression()
    
    # ÉTAPE 2: Création du dossier logs
    setup_logging_directory()
    
    # ÉTAPE 3: Chargement configuration en mode silencieux
    config = ConfigManager(silent_mode=True)  # Mode silencieux pour éviter les messages INFO
    
    # ÉTAPE 4: Récupération du niveau de verbosité
    verbosity = config.get_logging_verbosity()
    
    # ÉTAPE 5: Configuration OpenCV selon verbosité
    try:
        import cv2
        if verbosity == "Faible":
            # Différentes versions d'OpenCV utilisent différentes constantes
            try:
                cv2.setLogLevel(cv2.LOG_LEVEL_SILENT)
            except AttributeError:
                try:
                    cv2.setLogLevel(0)  # 0 = SILENT dans les anciennes versions
                except:
                    pass  # Ignore si setLogLevel n'existe pas
        elif verbosity == "Moyenne":
            try:
                cv2.setLogLevel(cv2.LOG_LEVEL_WARNING)
            except AttributeError:
                try:
                    cv2.setLogLevel(2)  # 2 = WARNING
                except:
                    pass
        else:  # Debug
            try:
                cv2.setLogLevel(cv2.LOG_LEVEL_INFO)
            except AttributeError:
                try:
                    cv2.setLogLevel(1)  # 1 = INFO
                except:
                    pass
    except ImportError:
        pass
    
    # ÉTAPE 6: Configuration du logging applicatif selon verbosité
    setup_application_logging(config)
    
    # ÉTAPE 7: Rechargement des configs avec logging approprié
    if verbosity != "Faible":
        # Rechargement normal avec logs
        config.silent_mode = False
        config.load_all_configs()
    
    # ÉTAPE 8: Messages de démarrage selon verbosité
    logger = logging.getLogger(__name__)
    
    if verbosity != "Faible":
        logger.info("🚀 Démarrage Robot Trajectory Controller")
        logger.info(f"📋 Verbosité des logs: {verbosity}")
        
        if verbosity == "Debug":
            available_levels = config.get_available_verbosity_levels()
            logger.debug(f"🔧 Niveaux disponibles: {available_levels}")
    
    # ÉTAPE 9: Création de l'application PyQt6
    app = QApplication(sys.argv)
    
    # Application du style
    style = config.get('ui', 'theme.style', 'Fusion')
    app.setStyle(style)
    
    if verbosity == "Debug":
        logger.debug(f"🎨 Style appliqué: {style}")
    
    # ÉTAPE 10: Création de la fenêtre principale
    if verbosity not in ["Faible"]:
        logger.info("🖼️ Initialisation de l'interface principale...")
    
    window = MainWindow(config)
    window.show()
    
    if verbosity not in ["Faible"]:
        logger.info("✅ Application prête")
    
    # ÉTAPE 11: Lancement de la boucle principale
    try:
        return app.exec()
    except KeyboardInterrupt:
        if verbosity != "Faible":
            logger.info("⏹️ Arrêt demandé par l'utilisateur")
        return 0
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")  # Toujours afficher les erreurs
        return 1
    finally:
        if verbosity == "Debug":
            logger.info("🔄 Fermeture de l'application")


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)