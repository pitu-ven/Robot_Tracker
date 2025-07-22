#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robot Trajectory Controller - Point d'entrée principal
"""

import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.config_manager import ConfigManager

def main():
    """Point d'entrée principal de l'application"""
    app = QApplication(sys.argv)
    
    # Chargement de la configuration
    config = ConfigManager()
    
    # Application du style depuis la config
    style = config.get('ui', 'theme.style', 'Fusion')
    app.setStyle(style)
    
    # Création de la fenêtre principale
    window = MainWindow(config)
    window.show()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
