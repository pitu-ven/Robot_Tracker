#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Onglet de calibration caméra-robot
"""

from PyQt6.QtWidgets import QWidget

class CalibrationTab(QWidget):
    """Onglet pour la calibration caméra-robot"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_ui()
    
    def setup_ui(self):
        """Configuration de l'interface"""
        # TODO: Implémenter l'interface calibration
        pass
