# core/logging_manager.py
# Version 2.0 - Ajout du contrôle OpenCV logging

import logging
import cv2
import os
import sys
from enum import Enum

class LogLevel(Enum):
    """Niveaux de logging disponibles"""
    FAIBLE = 1
    MOYEN = 2
    ELEVE = 3

class LoggingManager:
    """Gestionnaire centralisé pour tous les systèmes de logging"""
    
    _instance = None
    _current_level = LogLevel.FAIBLE
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggingManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self._setup_logging()
    
    def _setup_logging(self):
        """Configuration initiale du logging"""
        self.set_level(self._current_level)
    
    def set_level(self, level: LogLevel):
        """Définit le niveau de logging global"""
        self._current_level = level
        self._configure_python_logging()
        self._configure_opencv_logging()
        self._configure_warnings()
    
    def _configure_python_logging(self):
        """Configure le logging Python standard"""
        if self._current_level == LogLevel.FAIBLE:
            logging_level = logging.WARNING
        elif self._current_level == LogLevel.MOYEN:
            logging_level = logging.INFO
        else:  # ELEVE
            logging_level = logging.DEBUG
        
        # Configuration du logger root
        logging.basicConfig(
            level=logging_level,
            format='%(levelname)s:%(name)s:%(message)s'
        )
        
        # Configuration spécifique pour les loggers du projet
        project_loggers = [
            'core.config_manager',
            'core.camera_manager',
            'core.tracking_manager',
            'core.robot_manager',
            'core.aruco_manager'
        ]
        
        for logger_name in project_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging_level)
    
    def _configure_opencv_logging(self):
        """Configure le logging OpenCV"""
        if self._current_level == LogLevel.FAIBLE:
            # Masquer tous les messages OpenCV
            cv2.setLogLevel(cv2.LOG_LEVEL_SILENT)
        elif self._current_level == LogLevel.MOYEN:
            # Afficher seulement les erreurs
            cv2.setLogLevel(cv2.LOG_LEVEL_ERROR)
        else:  # ELEVE
            # Afficher tous les messages (warnings + erreurs)
            cv2.setLogLevel(cv2.LOG_LEVEL_WARNING)
    
    def _configure_warnings(self):
        """Configure les warnings Python"""
        import warnings
        
        if self._current_level == LogLevel.FAIBLE:
            # Masquer tous les warnings
            warnings.filterwarnings('ignore')
        elif self._current_level == LogLevel.MOYEN:
            # Afficher seulement les warnings importants
            warnings.filterwarnings('default', category=UserWarning)
            warnings.filterwarnings('ignore', category=DeprecationWarning)
            warnings.filterwarnings('ignore', category=FutureWarning)
        else:  # ELEVE
            # Afficher tous les warnings
            warnings.filterwarnings('default')
    
    def get_level(self) -> LogLevel:
        """Retourne le niveau de logging actuel"""
        return self._current_level
    
    def log(self, message: str, level: str = 'info'):
        """Méthode utilitaire pour logger des messages"""
        logger = logging.getLogger('robot_tracker')
        
        if level.lower() == 'debug':
            logger.debug(message)
        elif level.lower() == 'info':
            logger.info(message)
        elif level.lower() == 'warning':
            logger.warning(message)
        elif level.lower() == 'error':
            logger.error(message)
        else:
            logger.info(message)

# Instance globale
logging_manager = LoggingManager()