# robot_tracker/utils/system_logging_suppressor.py
# Version 1.1 - Suppresseur amélioré avec redirection stderr
# Modification: Amélioration suppression OpenCV et messages configuration

import os
import sys
import logging
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Optional


class EnhancedOpenCVSuppressor:
    """Suppresseur amélioré pour les messages OpenCV C++"""
    
    def __init__(self):
        self.original_stderr = sys.stderr
        self.is_active = False
    
    def activate(self):
        """Active la suppression des messages OpenCV"""
        if self.is_active:
            return
            
        # Redirection stderr avec filtrage intelligent
        sys.stderr = self._create_filtered_stderr()
        self.is_active = True
    
    def deactivate(self):
        """Désactive la suppression"""
        if not self.is_active:
            return
            
        sys.stderr = self.original_stderr
        self.is_active = False
    
    def _create_filtered_stderr(self):
        """Crée un stderr filtré pour OpenCV"""
        class FilteredStderr:
            def __init__(self, original_stderr):
                self.original_stderr = original_stderr
                
            def write(self, data):
                if isinstance(data, str):
                    data_lower = data.lower()
                    
                    # Patterns OpenCV à supprimer
                    opencv_patterns = [
                        'msmf', 'obsensor', 'camera index', 'readsample',
                        'grabframe', 'cap_msmf', 'videoio', 'onreadsample',
                        'async readsample', 'error status: -2147024809',
                        'global cap_msmf.cpp', 'global obsensor_uvc_stream_channel.cpp',
                        'warn:0@', 'error:1@'
                    ]
                    
                    # Vérifier si le message contient un pattern à supprimer
                    if any(pattern in data_lower for pattern in opencv_patterns):
                        return  # Supprimer le message
                
                # Écrire les autres messages normalement
                self.original_stderr.write(data)
                
            def flush(self):
                self.original_stderr.flush()
                
            def __getattr__(self, name):
                return getattr(self.original_stderr, name)
        
        return FilteredStderr(self.original_stderr)


class SystemLoggingSuppressor:
    """Suppresseur de logs système pour mode verbosité Faible"""
    
    def __init__(self):
        self.opencv_suppressor = EnhancedOpenCVSuppressor()
        self.original_log_filters = []
        
    def suppress_all_external_logs(self) -> None:
        """Supprime tous les logs externes (OpenCV, système, etc.)"""
        
        # 1. Configuration des variables d'environnement OpenCV
        self._configure_opencv_environment()
        
        # 2. Activation du suppresseur OpenCV amélioré
        self.opencv_suppressor.activate()
        
        # 3. Configuration du logging Python pour modules externes
        self._configure_external_python_logging()
        
        # 4. Configuration des filtres de logging
        self._setup_logging_filters()
    
    def _configure_opencv_environment(self) -> None:
        """Configure les variables d'environnement pour OpenCV"""
        
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
            'cv2', 'numpy', 'matplotlib', 'PIL', 'PyQt6',
            'urllib3', 'requests', 'asyncio', 'concurrent.futures'
        ]
        
        for module in silent_modules:
            logger = logging.getLogger(module)
            logger.setLevel(logging.CRITICAL)
            logger.propagate = False
    
    def _setup_logging_filters(self) -> None:
        """Configure des filtres de logging personnalisés"""
        
        # Redirection des warnings Python
        import warnings
        warnings.filterwarnings('ignore')
        
        # Filtre pour le logger racine
        class SystemMessageFilter(logging.Filter):
            def filter(self, record):
                message = record.getMessage().lower()
                
                # Patterns à supprimer en mode Faible
                suppress_patterns = [
                    'configuration', 'chargée', 'loaded', 'msmf', 'obsensor',
                    'camera index', 'readsample', 'grabframe', 'cap_msmf',
                    'videoio', 'démarrage', 'initialisation'
                ]
                
                # Supprimer si le message contient un pattern (sauf erreurs critiques)
                if any(pattern in message for pattern in suppress_patterns):
                    if record.levelno < logging.ERROR:
                        return False
                
                return True
        
        # Application du filtre
        root_logger = logging.getLogger()
        message_filter = SystemMessageFilter()
        root_logger.addFilter(message_filter)
        self.original_log_filters.append(message_filter)
    
    def restore_logging(self) -> None:
        """Restaure le logging normal"""
        
        # Désactivation du suppresseur OpenCV
        self.opencv_suppressor.deactivate()
        
        # Suppression des filtres ajoutés
        root_logger = logging.getLogger()
        for filter_obj in self.original_log_filters:
            root_logger.removeFilter(filter_obj)
        self.original_log_filters.clear()
    
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
    
    # Configuration spéciale OpenCV avec gestion des versions
    try:
        import cv2
        # Tentative avec différentes constantes selon la version OpenCV
        try:
            cv2.setLogLevel(cv2.LOG_LEVEL_SILENT)
        except AttributeError:
            try:
                cv2.setLogLevel(0)  # 0 = SILENT dans les anciennes versions
            except:
                pass  # Ignore si setLogLevel n'existe pas
    except ImportError:
        pass
    
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
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.WARNING)
    
    # Application des suppressions système
    apply_faible_mode_suppressions()


def initialize_faible_mode():
    """Initialise complètement le mode Faible"""
    setup_minimal_logging_for_faible()
    return apply_faible_mode_suppressions()