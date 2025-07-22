#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Onglet de gestion des trajectoires
"""

from PyQt6.QtWidgets import QWidget

class TrajectoryTab(QWidget):
    """Onglet pour le chargement et visualisation des trajectoires"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_ui()
    
    def setup_ui(self):
        """Configuration de l'interface"""
        # TODO: Implémenter l'interface trajectoire
        pass
