#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fenêtre principale avec onglets
"""

from PyQt6.QtWidgets import QMainWindow, QTabWidget, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont

from .camera_tab import CameraTab
from .trajectory_tab import TrajectoryTab
from .target_tab import TargetTab
from .calibration_tab import CalibrationTab
from .measures_tab import MeasuresTab

class MainWindow(QMainWindow):
    """Fenêtre principale de l'application"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_ui()
    
    def setup_ui(self):
        """Configuration de l'interface utilisateur"""
        # Configuration de la fenêtre depuis JSON
        # TODO: Implémenter la configuration depuis JSON
        
        # Création des onglets
        self.setup_tabs()
    
    def setup_tabs(self):
        """Création et configuration des onglets"""
        # TODO: Implémenter la création dynamique des onglets
        pass
    
    def center_on_screen(self):
        """Centre la fenêtre sur l'écran"""
        # TODO: Implémenter le centrage
        pass
