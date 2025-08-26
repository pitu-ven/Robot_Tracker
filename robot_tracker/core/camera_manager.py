# ui/main_window.py
# Version 1.5 - Correction warning signaux inter-onglets
# Modification: Amélioration de la méthode connect_signals avec gestion robuste

from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                           QStatusBar, QMenuBar, QToolBar, QMessageBox, QApplication, 
                           QDialog, QLabel)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont, QAction, QPalette, QColor
import sys
import logging

from ui.camera_tab import CameraTab
from ui.trajectory_tab import TrajectoryTab
from ui.calibration_tab import CalibrationTab
from ui.aruco_generator import ArUcoGeneratorDialog
from core.camera_manager import CameraManager

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """Fenêtre principale avec camera_manager centralisé"""
    
    def __init__(self, config):
        super().__init__()
        
        # Configuration
        self.config = config
        self.tabs = {}
        
        # Camera manager centralisé pour partage entre onglets
        self.camera_manager = CameraManager(self.config)
        logger.info("🎥 CameraManager centralisé créé")
        
        # Interface
        self.init_ui()
        self.apply_theme()
        self.center_window()
        self.connect_signals()
        
        # Timer pour mise à jour périodique
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)
        
        logger.info("✅ MainWindow initialisé avec succès")
    
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        # Configuration fenêtre
        window_config = self.config.get('ui', 'window', {})
        
        title = window_config.get('title', 'Robot Trajectory Controller v1.0')
        width = window_config.get('width', 1920)
        height = window_config.get('height', 1057)
        
        self.setWindowTitle(title)
        self.resize(width, height)
        
        logger.info(f"📐 Fenêtre configurée: {width}x{height}, titre: '{title}'")
        
        # Widget central avec onglets
        self.central_widget = QTabWidget()
        self.setCentralWidget(self.central_widget)
        
        # Interface secondaire
        self.create_menu_bar()
        self.create_toolbar()
        self.create_status_bar()
        self.create_tabs()
    
    def create_menu_bar(self):
        """Crée la barre de menu"""
        menubar = self.menuBar()
        
        # Menu ArUco
        aruco_menu = menubar.addMenu('ArUco')
        
        generator_action = QAction('Générateur ArUco', self)
        generator_action.triggered.connect(self.show_aruco_generator)
        aruco_menu.addAction(generator_action)
        
        logger.info("📋 Barre de menu créée avec générateur ArUco")
    
    def create_toolbar(self):
        """Crée la barre d'outils"""
        toolbar = self.addToolBar('Outils')
        
        # Actions rapides
        generator_action = QAction('🎯 ArUco', self)
        generator_action.setToolTip('Générateur de marqueurs ArUco')
        generator_action.triggered.connect(self.show_aruco_generator)
        toolbar.addAction(generator_action)
        
        logger.info("🔧 Barre d'outils créée")
    
    def create_status_bar(self):
        """Crée la barre de statut"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Widgets de statut
        self.camera_status = QLabel("Caméra: Arrêtée")
        self.tracking_status = QLabel("Tracking: Inactif")
        
        self.status_bar.addWidget(self.camera_status)
        self.status_bar.addPermanentWidget(self.tracking_status)
    
    def create_tabs(self):
        """Crée tous les onglets"""
        try:
            # Onglet Caméra
            self.tabs['camera'] = CameraTab(self.camera_manager, self.config)
            self.central_widget.addTab(self.tabs['camera'], "🎥 Caméra")
            logger.info("📑 Onglet 'Caméra' créé avec succès")
            
            # Onglet Trajectoire
            self.tabs['trajectory'] = TrajectoryTab(self.config)
            self.central_widget.addTab(self.tabs['trajectory'], "📍 Trajectoire")
            logger.info("📑 Onglet 'Trajectoire' créé avec succès")
            
            # Onglet Cible avec fallback
            self._create_target_tab_with_fallback()
            
            # Onglet Calibration
            self.tabs['calibration'] = CalibrationTab(self.config)
            self.central_widget.addTab(self.tabs['calibration'], "⚙️ Calibration")
            logger.info("📑 Onglet 'Calibration' créé avec succès")
            
            # Onglet Mesures
            self.tabs['measures'] = MeasuresTab(self.config)
            self.central_widget.addTab(self.tabs['measures'], "📊 Mesures")
            logger.info("📑 Onglet 'Mesures' créé avec succès")
            
        except Exception as e:
            logger.error(f"❌ Erreur critique création onglets: {e}")
            self._show_critical_error(e)
    
    def _create_target_tab_with_fallback(self):
        """Crée l'onglet Cible avec fallback en cas d'erreur"""
        try:
            # Import dynamique pour éviter les erreurs de module
            from .target_tab import TargetTab
            
            self.tabs['target'] = TargetTab(self.config, self.camera_manager)
            self.central_widget.addTab(self.tabs['target'], "🎯 Cible")
            logger.info("📑 Onglet 'Cible' créé avec succès")
            
        except Exception as e:
            logger.error(f"❌ Erreur création onglet Cible: {e}")
            
            # Création d'un onglet de fallback
            error_widget = QWidget()
            error_layout = QVBoxLayout(error_widget)
            
            error_layout.addWidget(QLabel("❌ Erreur de chargement de l'onglet Cible"))
            error_layout.addWidget(QLabel(f"Détails: {str(e)}"))
            error_layout.addWidget(QLabel("Vérifiez la configuration tracking_config.json"))
            
            self.central_widget.addTab(error_widget, "⚠️ Cible (Erreur)")
            logger.warning("📑 Onglet 'Cible' créé en mode dégradé")
    
    def _show_critical_error(self, error):
        """Affiche une erreur critique"""
        QMessageBox.critical(
            self,
            "Erreur critique",
            f"Impossible de créer l'interface:\n{error}\n\nVérifiez la configuration."
        )
    
    def show_aruco_generator(self):
        """Affiche le générateur ArUco"""
        try:
            dialog = ArUcoGeneratorDialog(self.config, self)
            dialog.exec()
        except Exception as e:
            logger.error(f"❌ Erreur générateur ArUco: {e}")
            QMessageBox.warning(
                self,
                "Erreur",
                f"Impossible d'ouvrir le générateur ArUco:\n{e}"
            )
    
    def apply_theme(self):
        """Applique le thème de l'interface"""
        theme_config = self.config.get('ui', 'theme', {})
        
        if theme_config.get('dark_mode', False):
            app = QApplication.instance()
            app.setStyle('Fusion')
            
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
            
            app.setPalette(palette)
    
    def center_window(self):
        """Centre la fenêtre sur l'écran"""
        screen = QApplication.primaryScreen().availableGeometry()
        window = self.frameGeometry()
        
        center_point = screen.center()
        window.moveCenter(center_point)
        self.move(window.topLeft())
    
    def connect_signals(self):
        """Connecte les signaux entre composants avec vérification robuste"""
        try:
            # Vérification de l'existence des onglets
            camera_tab = self.tabs.get('camera')
            target_tab = self.tabs.get('target')
            trajectory_tab = self.tabs.get('trajectory')
            
            connections_made = 0
            
            # Connexions caméra → autres onglets
            if camera_tab:
                # Signal de sélection de caméra
                if hasattr(camera_tab, 'camera_selected'):
                    if target_tab and hasattr(target_tab, '_on_camera_changed'):
                        camera_tab.camera_selected.connect(target_tab._on_camera_changed)
                        connections_made += 1
                        logger.info("📡 Signal caméra → cible connecté")
                
                # Signal de démarrage streaming
                if hasattr(camera_tab, 'streaming_started'):
                    if target_tab and hasattr(target_tab, '_on_streaming_started'):
                        camera_tab.streaming_started.connect(target_tab._on_streaming_started)
                        connections_made += 1
                        logger.info("📡 Signal streaming → cible connecté")
            
            # Connexions cible → trajectoire
            if target_tab and trajectory_tab:
                if hasattr(target_tab, 'target_detected') and hasattr(trajectory_tab, '_on_target_detected'):
                    target_tab.target_detected.connect(trajectory_tab._on_target_detected)
                    connections_made += 1
                    logger.info("📡 Signal cible → trajectoire connecté")
            
            # Connexions pour mise à jour statut
            for tab_name, tab_instance in self.tabs.items():
                if hasattr(tab_instance, 'status_changed'):
                    tab_instance.status_changed.connect(self._on_tab_status_changed)
                    connections_made += 1
            
            if connections_made > 0:
                logger.info(f"✅ {connections_made} connexion(s) de signaux établie(s)")
            else:
                logger.info("📡 Aucun signal inter-onglet à connecter (normal si onglets basiques)")
                
        except Exception as e:
            logger.error(f"❌ Erreur connexion signaux: {e}")
            # Ne pas lever d'exception, continuer le démarrage
    
    def _on_tab_status_changed(self, status_info):
        """Callback pour les changements de statut des onglets"""
        try:
            # Mise à jour de la barre de statut selon les infos reçues
            if isinstance(status_info, dict):
                tab_name = status_info.get('tab', 'Unknown')
                message = status_info.get('message', 'Status changed')
                logger.debug(f"📊 Statut {tab_name}: {message}")
        except Exception as e:
            logger.debug(f"Erreur traitement statut: {e}")
    
    def update_status(self):
        """Met à jour la barre de statut"""
        try:
            # État des caméras
            camera_count = len(self.camera_manager.active_cameras)
            if camera_count > 0:
                self.camera_status.setText(f"Caméra: {camera_count} active(s)")
            else:
                self.camera_status.setText("Caméra: Arrêtée")
            
            # État du tracking
            if hasattr(self, 'tabs') and 'target' in self.tabs:
                if hasattr(self.tabs['target'], 'is_tracking'):
                    status = "Actif" if self.tabs['target'].is_tracking else "Inactif"
                    self.tracking_status.setText(f"Tracking: {status}")
                
        except Exception as e:
            logger.debug(f"Erreur mise à jour statut: {e}")
    
    def closeEvent(self, event):
        """Gestionnaire de fermeture"""
        logger.info("🚪 Fermeture de l'application...")
        
        # Arrêt des caméras
        try:
            self.camera_manager.stop_streaming()
            self.camera_manager.close_all_cameras()
        except Exception as e:
            logger.error(f"❌ Erreur fermeture caméras: {e}")
        
        # Arrêt des timers
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        
        event.accept()
        logger.info("✅ Application fermée proprement")