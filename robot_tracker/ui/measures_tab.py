#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Onglet de mesures et rapports
"""

from PyQt6.QtWidgets import QWidget

class MeasuresTab(QWidget):
    """Onglet pour les mesures et génération de rapports"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_ui()
    
    def setup_ui(self):
        """Configuration de l'interface"""
        # TODO: Implémenter l'interface mesures
        pass
