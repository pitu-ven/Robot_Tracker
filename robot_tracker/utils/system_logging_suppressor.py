# robot_tracker/utils/system_logging_suppressor.py
# Version 1.0 - Suppresseur de logs système
# Modification: Suppression complète des logs externes en mode Faible

import os
import sys
import logging
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Optional


class SystemLoggingSuppressor:
    """Suppresseur de logs système pour mode verbosité Faible"""
    
    def __init__(self):
        self.original_stderr = None
        self.original_stdout = None
        self.devnull = None
        
    def suppress_all_external_logs(self) -> None:
        """Supprime tous les logs externes (OpenCV, système, etc.)"""
        
        # 1. Configuration des variables d'environnement OpenCV
        self._configure_opencv_environment()
        
        # 2. Configuration du logging Python pour modules externes
        self._configure_external_python_logging()
        
        # 3. Redirection des sorties système si nécessaire
        self._setup_system_redirection()
    
    def _configure_opencv_environment(self) -> None:
        """Configure les variables d'environnement pour OpenCV"""
        
        # Variables pour supprimer les messages OpenCV
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
    
    def _configure_external_python_logging(self) -> None:
        """Configure le logging Python pour les modules externes"""
        
        # Modules à mettre en silence complète
        silent_modules = [
            'cv2',
            'numpy',
            'matplotlib',
            'PIL',
            'PyQt6',
            'urllib3',
            'requests',
            'asyncio',
            'concurrent.futures'
        ]
        
        for module in silent_modules:
            logger = logging.getLogger(module)
            logger.setLevel(logging.CRITICAL)
            logger.propagate = False
    
    def _setup_system_redirection(self) -> None:
        """Configure la redirection des sorties système si nécessaire"""
        
        # Redirection des warnings Python
        import warnings
        warnings.filterwarnings('ignore')
        
        # Configuration du logger racine pour capturer les messages système
        root_logger = logging.getLogger()
        
        # Ajout d'un filtre personnalisé pour les messages système
        class SystemMessageFilter(logging.Filter):
            def filter(self, record):
                # Filtrer les messages contenant des patterns spécifiques
                message = record.getMessage().lower()
                
                # Patterns à supprimer en mode Faible
                suppress_patterns = [
                    'configuration',
                    'chargée',
                    'msmf',
                    'obsensor',
                    'camera index',
                    'readSample',
                    'grabFrame',
                    'cap_msmf',
                    'videoio'
                ]
                
                # Si le message contient un pattern à supprimer et que ce n'est pas une erreur critique
                if any(pattern in message for pattern in suppress_patterns):
                    if record.levelno < logging.ERROR:
                        return False
                
                return True
        
        # Application du filtre au logger racine
        root_logger.addFilter(SystemMessageFilter())
    
    def restore_logging(self) -> None:
        """Restaure le logging normal"""
        
        # Restauration des sorties système
        if self.original_stderr:
            sys.stderr = self.original_stderr
        if self.original_stdout:
            sys.stdout = self.original_stdout
            
        # Fermeture du devnull
        if self.devnull:
            self.devnull.close()
    
    def __enter__(self):
        """Context manager entry"""
        self.suppress_all_external_logs()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.restore_logging()


class QuietConfigManager:
    """Version silencieuse du ConfigManager pour mode Faible"""
    
    @staticmethod
    def load_configs_quietly(config_manager):
        """Charge les configurations sans afficher les messages de chargement"""
        
        # Sauvegarde du niveau de logging du config_manager
        config_logger = logging.getLogger('core.config_manager')
        original_level = config_logger.level
        
        try:
            # Mode silencieux temporaire
            config_logger.setLevel(logging.ERROR)
            
            # Rechargement des configurations
            config_manager.load_all_configs()
            
        finally:
            # Restauration du niveau original
            config_logger.setLevel(original_level)


def apply_faible_mode_suppressions():
    """Applique toutes les suppressions pour le mode Faible"""
    
    # Suppression des logs système
    suppressor = SystemLoggingSuppressor()
    suppressor.suppress_all_external_logs()
    
    # Configuration spéciale OpenCV
    try:
        import cv2
        cv2.setLogLevel(cv2.LOG_LEVEL_SILENT)
    except ImportError:
        pass
    
    # Suppression des warnings Python
    import warnings
    warnings.simplefilter('ignore')
    
    return suppressor


def setup_minimal_logging_for_faible():
    """Configure un logging minimal pour le mode Faible"""
    
    # Configuration d'un formateur minimal
    minimal_formatter = logging.Formatter('[%(levelname)s] %(message)s')
    
    # Configuration du handler console avec filtre strict
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(minimal_formatter)
    console_handler.setLevel(logging.WARNING)
    
    # Application au logger racine
    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # Supprime les handlers existants
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.WARNING)
    
    # Application des suppressions système
    apply_faible_mode_suppressions()


# Fonction utilitaire pour l'initialisation depuis main.py
def initialize_faible_mode():
    """Initialise complètement le mode Faible"""
    setup_minimal_logging_for_faible()
    return apply_faible_mode_suppressions()