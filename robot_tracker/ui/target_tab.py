#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Onglet de définition des cibles
"""

from PyQt6.QtWidgets import QWidget

class TargetTab(QWidget):
    """Onglet pour la définition et sélection des cibles"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_ui()
    
    def setup_ui(self):
        """Configuration de l'interface"""
        # TODO: Implémenter l'interface cible
        pass
