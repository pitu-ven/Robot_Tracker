#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/ui/main_window.py
Fenêtre principale avec onglets - Version 1.0
Modification: Implémentation complète avec configuration JSON et 5 onglets
"""

from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                           QStatusBar, QMenuBar, QToolBar, QMessageBox, QApplication)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont, QAction, QPalette, QColor
import sys
import logging

from .camera_tab import CameraTab
from .trajectory_tab import TrajectoryTab
from .target_tab import TargetTab
from .calibration_tab import CalibrationTab
from .measures_tab import MeasuresTab

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """Fenêtre principale de l'application Robot Trajectory Controller"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        # Stockage des onglets
        self.tabs = {}
        self.tab_widget = None
        
        # Timer pour les mises à jour périodiques
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.periodic_update)
        
        # Configuration et affichage
        self.setup_ui()
        self.setup_connections()
        
        logger.info("✅ MainWindow initialisé avec succès")
    
    def setup_ui(self):
        """Configuration complète de l'interface utilisateur"""
        try:
            # Configuration de la fenêtre principale
            self.configure_window()
            
            # Application du thème
            self.apply_theme()
            
            # Création des composants principaux
            self.create_menu_bar()
            self.create_toolbar()
            self.create_tabs()
            self.create_status_bar()
            
            # Centrage et finalisation
            self.center_on_screen()
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la configuration UI: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur configuration interface: {e}")
    
    def configure_window(self):
        """Configuration de la fenêtre principale depuis JSON"""
        # Récupération des paramètres depuis la configuration
        title = self.config.get('ui', 'window.title', 'Robot Trajectory Controller')
        width = self.config.get('ui', 'window.width', 1400)
        height = self.config.get('ui', 'window.height', 900)
        resizable = self.config.get('ui', 'window.resizable', True)
        fullscreen = self.config.get('ui', 'window.fullscreen', False)
        
        # Application des paramètres
        self.setWindowTitle(title)
        self.resize(width, height)
        
        if not resizable:
            self.setFixedSize(width, height)
        
        if fullscreen:
            self.showMaximized()
        
        # Configuration de l'icône de l'application
        self.setWindowIcon(QIcon('icons/app_icon.png'))  # Si disponible
        
        logger.info(f"📐 Fenêtre configurée: {width}x{height}, titre: '{title}'")
    
    def apply_theme(self):
        """Application du thème depuis la configuration"""
        try:
            # Récupération des paramètres de thème
            style = self.config.get('ui', 'theme.style', 'Fusion')
            palette_type = self.config.get('ui', 'theme.palette', 'dark')
            font_family = self.config.get('ui', 'theme.font_family', 'Arial')
            font_size = self.config.get('ui', 'theme.font_size', 10)
            
            # Application du style
            QApplication.instance().setStyle(style)
            
            # Configuration de la police
            font = QFont(font_family, font_size)
            QApplication.instance().setFont(font)
            
            # Application de la palette de couleurs
            if palette_type == 'dark':
                self.apply_dark_palette()
            
            logger.info(f"🎨 Thème appliqué: {style}, palette: {palette_type}")
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur application thème: {e}")
    
    def apply_dark_palette(self):
        """Application d'une palette sombre"""
        palette = QPalette()
        
        # Couleurs pour le thème sombre
        palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
        
        QApplication.instance().setPalette(palette)
    
    def create_menu_bar(self):
        """Création de la barre de menu"""
        if not self.config.get('ui', 'layout.menu_bar', True):
            return
        
        menubar = self.menuBar()
        
        # Menu Fichier
        file_menu = menubar.addMenu('&Fichier')
        
        open_action = QAction('&Ouvrir Trajectoire...', self)
        open_action.setShortcut('Ctrl+O')
        open_action.setStatusTip('Charger un fichier de trajectoire')
        open_action.triggered.connect(self.open_trajectory_file)
        file_menu.addAction(open_action)
        
        save_action = QAction('&Sauvegarder Rapport...', self)
        save_action.setShortcut('Ctrl+S')
        save_action.setStatusTip('Sauvegarder le rapport PDF')
        save_action.triggered.connect(self.save_report)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('&Quitter', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Quitter l\'application')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Menu Configuration
        config_menu = menubar.addMenu('&Configuration')
        
        camera_config_action = QAction('&Caméras...', self)
        camera_config_action.setStatusTip('Configuration des caméras')
        camera_config_action.triggered.connect(self.configure_cameras)
        config_menu.addAction(camera_config_action)
        
        robot_config_action = QAction('&Robot...', self)
        robot_config_action.setStatusTip('Configuration de la communication robot')
        robot_config_action.triggered.connect(self.configure_robot)
        config_menu.addAction(robot_config_action)
        
        # Menu Aide
        help_menu = menubar.addMenu('&Aide')
        
        about_action = QAction('&À propos...', self)
        about_action.setStatusTip('Informations sur l\'application')
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        logger.info("📋 Barre de menu créée")
    
    def create_toolbar(self):
        """Création de la barre d'outils"""
        if not self.config.get('ui', 'layout.toolbar', True):
            return
        
        toolbar = self.addToolBar('Principal')
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        
        # Action Démarrer Tracking
        start_action = QAction('▶️ Démarrer', self)
        start_action.setStatusTip('Démarrer le tracking')
        start_action.triggered.connect(self.start_tracking)
        toolbar.addAction(start_action)
        
        # Action Arrêter
        stop_action = QAction('⏹️ Arrêter', self)
        stop_action.setStatusTip('Arrêter le tracking')
        stop_action.triggered.connect(self.stop_tracking)
        toolbar.addAction(stop_action)
        
        toolbar.addSeparator()
        
        # Action Calibration
        calibrate_action = QAction('🎯 Calibrer', self)
        calibrate_action.setStatusTip('Lancer la calibration')
        calibrate_action.triggered.connect(self.start_calibration)
        toolbar.addAction(calibrate_action)
        
        # Action Rapport
        report_action = QAction('📊 Rapport', self)
        report_action.setStatusTip('Générer un rapport PDF')
        report_action.triggered.connect(self.generate_report)
        toolbar.addAction(report_action)
        
        logger.info("🔧 Barre d'outils créée")
    
    def create_tabs(self):
        """Création des onglets principaux"""
        try:
            # Widget principal avec onglets
            self.tab_widget = QTabWidget()
            self.setCentralWidget(self.tab_widget)
            
            # Récupération des noms d'onglets depuis la configuration
            tab_names = self.config.get('ui', 'tabs.tab_names', 
                                      ['Caméra', 'Trajectoire', 'Cible', 'Calibration', 'Mesures'])
            
            # Création des onglets avec leur configuration
            tab_classes = [CameraTab, TrajectoryTab, TargetTab, CalibrationTab, MeasuresTab]
            
            for i, (tab_name, tab_class) in enumerate(zip(tab_names, tab_classes)):
                try:
                    # Création de l'instance de l'onglet
                    tab_instance = tab_class(self.config)
                    
                    # Ajout à l'interface
                    self.tab_widget.addTab(tab_instance, tab_name)
                    
                    # Stockage de la référence
                    self.tabs[tab_name.lower()] = tab_instance
                    
                    logger.info(f"📑 Onglet '{tab_name}' créé avec succès")
                    
                except Exception as e:
                    logger.error(f"❌ Erreur création onglet '{tab_name}': {e}")
                    # Création d'un onglet de substitution en cas d'erreur
                    placeholder = QWidget()
                    self.tab_widget.addTab(placeholder, f"{tab_name} (Erreur)")
            
            # Configuration de l'onglet par défaut
            default_tab = self.config.get('ui', 'tabs.default_tab', 0)
            if 0 <= default_tab < self.tab_widget.count():
                self.tab_widget.setCurrentIndex(default_tab)
            
            logger.info(f"📑 {len(self.tabs)} onglets créés avec succès")
            
        except Exception as e:
            logger.error(f"❌ Erreur création des onglets: {e}")
            # Interface minimal en cas d'erreur
            placeholder = QWidget()
            self.setCentralWidget(placeholder)
    
    def create_status_bar(self):
        """Création de la barre de status"""
        if not self.config.get('ui', 'layout.status_bar', True):
            return
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Message d'accueil
        self.status_bar.showMessage("🤖 Robot Trajectory Controller - Prêt", 3000)
        
        logger.info("📊 Barre de status créée")
    
    def setup_connections(self):
        """Configuration des connexions entre composants"""
        try:
            # Connexion entre onglets si nécessaire
            if 'caméra' in self.tabs and 'calibration' in self.tabs:
                # Exemple : partage des données caméra vers calibration
                pass
            
            # Timer pour les mises à jour périodiques (toutes les 100ms)
            self.update_timer.start(100)
            
            logger.info("🔗 Connexions établies")
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors des connexions: {e}")
    
    def periodic_update(self):
        """Mise à jour périodique de l'interface"""
        try:
            # Mise à jour de la barre de status avec des informations temps réel
            current_tab = self.tab_widget.currentWidget()
            if hasattr(current_tab, 'get_status_info'):
                status_info = current_tab.get_status_info()
                if status_info:
                    self.status_bar.showMessage(status_info)
        
        except Exception as e:
            # Erreur silencieuse pour éviter de surcharger les logs
            pass
    
    def center_on_screen(self):
        """Centre la fenêtre sur l'écran"""
        if not self.config.get('ui', 'window.center_on_screen', True):
            return
        
        try:
            # Obtenir la géométrie de l'écran
            screen = QApplication.primaryScreen().geometry()
            
            # Calculer la position centrée
            x = (screen.width() - self.width()) // 2
            y = (screen.height() - self.height()) // 2
            
            self.move(x, y)
            logger.info(f"🎯 Fenêtre centrée à ({x}, {y})")
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur centrage fenêtre: {e}")
    
    # === Actions des menus et toolbar ===
    
    def open_trajectory_file(self):
        """Ouvre un fichier de trajectoire"""
        if 'trajectoire' in self.tabs:
            self.tabs['trajectoire'].open_file_dialog()
            self.tab_widget.setCurrentWidget(self.tabs['trajectoire'])
    
    def save_report(self):
        """Sauvegarde un rapport"""
        if 'mesures' in self.tabs:
            self.tabs['mesures'].save_report_dialog()
            self.tab_widget.setCurrentWidget(self.tabs['mesures'])
    
    def configure_cameras(self):
        """Configuration des caméras"""
        if 'caméra' in self.tabs:
            self.tab_widget.setCurrentWidget(self.tabs['caméra'])
    
    def configure_robot(self):
        """Configuration du robot"""
        # Pour l'instant, affichage d'un message
        QMessageBox.information(self, "Configuration Robot", 
                              "Configuration robot disponible dans l'onglet Calibration")
    
    def start_tracking(self):
        """Démarre le tracking"""
        try:
            if 'cible' in self.tabs:
                self.tabs['cible'].start_tracking()
            self.status_bar.showMessage("🎯 Tracking démarré", 2000)
            logger.info("🚀 Tracking démarré")
        except Exception as e:
            logger.error(f"❌ Erreur démarrage tracking: {e}")
            QMessageBox.warning(self, "Erreur", f"Impossible de démarrer le tracking: {e}")
    
    def stop_tracking(self):
        """Arrête le tracking"""
        try:
            if 'cible' in self.tabs:
                self.tabs['cible'].stop_tracking()
            self.status_bar.showMessage("⏹️ Tracking arrêté", 2000)
            logger.info("⏹️ Tracking arrêté")
        except Exception as e:
            logger.error(f"❌ Erreur arrêt tracking: {e}")
    
    def start_calibration(self):
        """Lance la calibration"""
        if 'calibration' in self.tabs:
            self.tab_widget.setCurrentWidget(self.tabs['calibration'])
            self.tabs['calibration'].start_calibration_wizard()
    
    def generate_report(self):
        """Génère un rapport"""
        if 'mesures' in self.tabs:
            self.tab_widget.setCurrentWidget(self.tabs['mesures'])
            self.tabs['mesures'].generate_pdf_report()
    
    def show_about(self):
        """Affiche la boîte de dialogue À propos"""
        about_text = """
        <h3>Robot Trajectory Controller v1.0</h3>
        <p>Système de contrôle de trajectoire robotique par vision industrielle</p>
        <p><b>Caractéristiques :</b></p>
        <ul>
        <li>Tracking de points en temps réel</li>
        <li>Calibration caméra-robot automatique</li>
        <li>Support multi-formats de trajectoires</li>
        <li>Génération de rapports PDF</li>
        </ul>
        <p><b>Technologies :</b> PyQt6, OpenCV, Intel RealSense, Open3D</p>
        """
        QMessageBox.about(self, "À propos", about_text)
    
    # === Méthodes utilitaires ===
    
    def get_active_tab(self):
        """Retourne l'onglet actuellement actif"""
        return self.tab_widget.currentWidget()
    
    def switch_to_tab(self, tab_name):
        """Bascule vers un onglet spécifique"""
        if tab_name.lower() in self.tabs:
            self.tab_widget.setCurrentWidget(self.tabs[tab_name.lower()])
            return True
        return False
    
    def get_tab(self, tab_name):
        """Retourne une référence vers un onglet spécifique"""
        return self.tabs.get(tab_name.lower())
    
    # === Gestion des événements ===
    
    def closeEvent(self, event):
        """Gestion de la fermeture de l'application"""
        try:
            # Arrêt du timer
            self.update_timer.stop()
            
            # Nettoyage des onglets
            for tab_name, tab_instance in self.tabs.items():
                if hasattr(tab_instance, 'cleanup'):
                    tab_instance.cleanup()
            
            # Sauvegarde de la configuration si modifiée
            self.config.save_all_configs()
            
            logger.info("👋 Fermeture de l'application")
            event.accept()
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la fermeture: {e}")
            event.accept()  # Fermer quand même
    
    def resizeEvent(self, event):
        """Gestion du redimensionnement"""
        super().resizeEvent(event)
        
        # Sauvegarde optionnelle de la taille dans la configuration
        new_size = event.size()
        self.config.set('ui', 'window.width', new_size.width())
        self.config.set('ui', 'window.height', new_size.height())


# === Fonction utilitaire pour les tests ===
def create_test_window():
    """Crée une fenêtre de test"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from core.config_manager import ConfigManager
    
    app = QApplication(sys.argv)
    config = ConfigManager()
    window = MainWindow(config)
    window.show()
    
    return app, window


if __name__ == "__main__":
    # Test de la fenêtre principale
    app, window = create_test_window()
    sys.exit(app.exec())