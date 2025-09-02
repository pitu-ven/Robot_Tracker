# robot_tracker/ui/main_window.py
# Version 1.7 - Correction définitive signaux camera_opened
# Modification: Assurer cohérence entre signaux émis et signaux connectés

from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                           QStatusBar, QMenuBar, QToolBar, QMessageBox, QApplication, 
                           QDialog, QLabel)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont, QAction, QPalette, QColor
import sys
import logging

from .camera_tab import CameraTab
from .trajectory_tab import TrajectoryTab
from .target_tab import TargetTab  # Import du TargetTab simplifié
from .calibration_tab import CalibrationTab
from .measures_tab import MeasuresTab
from .aruco_generator import ArUcoGeneratorDialog
from core.camera_manager import CameraManager

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """Fenêtre principale avec signaux corrigés"""
    
    def __init__(self, config):
        super().__init__()
        
        # Configuration
        self.config = config
        self.tabs = {}
        
        # Camera manager centralisé - UNIQUE POINT DE GESTION CAMÉRA
        self.camera_manager = CameraManager(self.config)
        logger.info("🎥 CameraManager centralisé créé")
        
        # Interface
        self.init_ui()
        self.apply_theme()
        self.center_window()
        self.connect_inter_tab_signals()  # Nom plus explicite
        
        # Timer pour mise à jour périodique
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)
        
        logger.info("✅ MainWindow v1.6 initialisé (signaux corrigés)")
    
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        layout = QVBoxLayout(central_widget)
        
        # Configuration fenêtre depuis JSON
        window_config = self.config.get('ui', 'main_window', {})
        self.setWindowTitle(window_config.get('title', 'Robot Trajectory Controller v1.6'))
        
        width = window_config.get('width', 1400)
        height = window_config.get('height', 900)
        self.resize(width, height)
        
        # Création des onglets avec gestion signatures
        self.create_tabs_with_compatibility()
        
        # Menus et barres d'outils
        self.create_menu_bar()
        self.create_toolbar()
        self.create_status_bar()
    
    def create_tabs_with_compatibility(self):
        """Crée tous les onglets avec gestion compatibilité signatures"""
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        try:
            # 1. ONGLET CAMÉRA - MAÎTRE (signature mise à jour)
            self.tabs['camera'] = CameraTab(self.camera_manager, self.config)
            self.tab_widget.addTab(self.tabs['camera'], "📷 Caméra")
            logger.info("✅ Onglet Caméra créé (MAÎTRE)")
            
            # 2. ONGLET CIBLE - ESCLAVE (signature mise à jour)
            self.tabs['target'] = TargetTab(self.config, self.camera_manager)
            self.tab_widget.addTab(self.tabs['target'], "🎯 Cible")
            logger.info("✅ Onglet Cible créé (ESCLAVE)")
            
            # 3. AUTRES ONGLETS - Ancienne signature (compatibilité)
            self._create_legacy_tabs()
            
            logger.info(f"✅ {len(self.tabs)} onglets créés avec compatibilité signatures")
            
        except Exception as e:
            logger.error(f"❌ Erreur création onglets: {e}")
            # Fallback plus informatif
            self._create_fallback_interface(str(e))
    
    def _create_legacy_tabs(self):
        """Crée les onglets avec ancienne signature (transition)"""
        try:
            # Onglet Trajectoire - ancienne signature
            self.tabs['trajectory'] = TrajectoryTab(self.config)
            self.tab_widget.addTab(self.tabs['trajectory'], "📈 Trajectoire")
            logger.info("✅ Onglet Trajectoire créé (ancienne signature)")
            
        except Exception as e:
            logger.error(f"❌ Erreur TrajectoryTab: {e}")
            # Créer un onglet placeholder
            self.tabs['trajectory'] = self._create_placeholder_tab("Trajectoire", 
                "Onglet en cours de développement")
            self.tab_widget.addTab(self.tabs['trajectory'], "📈 Trajectoire")
        
        try:
            # Onglet Calibration - ancienne signature  
            self.tabs['calibration'] = CalibrationTab(self.config)
            self.tab_widget.addTab(self.tabs['calibration'], "🎖️ Calibration")
            logger.info("✅ Onglet Calibration créé (ancienne signature)")
            
        except Exception as e:
            logger.error(f"❌ Erreur CalibrationTab: {e}")
            self.tabs['calibration'] = self._create_placeholder_tab("Calibration",
                "Onglet en cours de développement")
            self.tab_widget.addTab(self.tabs['calibration'], "🎖️ Calibration")
        
        try:
            # Onglet Mesures - ancienne signature
            self.tabs['measures'] = MeasuresTab(self.config)
            self.tab_widget.addTab(self.tabs['measures'], "📊 Mesures") 
            logger.info("✅ Onglet Mesures créé (ancienne signature)")
            
        except Exception as e:
            logger.error(f"❌ Erreur MeasuresTab: {e}")
            self.tabs['measures'] = self._create_placeholder_tab("Mesures",
                "Onglet en cours de développement")
            self.tab_widget.addTab(self.tabs['measures'], "📊 Mesures")
    
    def _create_placeholder_tab(self, name: str, message: str) -> QWidget:
        """Crée un onglet placeholder en cas d'erreur"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        label = QLabel(f"🚧 Onglet {name}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 18px; font-weight: bold; color: orange;")
        layout.addWidget(label)
        
        info_label = QLabel(message)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        return widget
    
    def _create_fallback_interface(self, error_message: str):
        """Crée une interface de fallback en cas d'erreur critique"""
        logger.error("🚨 Création interface de fallback")
        
        # Interface minimale avec juste l'onglet caméra si possible
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        try:
            # Au minimum l'onglet caméra
            self.tabs['camera'] = CameraTab(self.camera_manager, self.config)
            self.tab_widget.addTab(self.tabs['camera'], "📷 Caméra")
            
            # Onglet d'erreur
            error_widget = QWidget()
            layout = QVBoxLayout(error_widget)
            
            error_label = QLabel("❌ Erreur de Chargement")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")
            layout.addWidget(error_label)
            
            detail_label = QLabel(f"Détails: {error_message}")
            detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)
            
            self.tab_widget.addTab(error_widget, "❌ Erreur")
            
        except Exception as e:
            logger.critical(f"❌ Impossible de créer interface fallback: {e}")
            QMessageBox.critical(self, "Erreur Critique", 
                f"Interface non disponible:\n{error_message}\n\nErreur fallback: {e}")
    
    def create_menu_bar(self):
        """Crée la barre de menu"""
        menubar = self.menuBar()
        
        # Menu Fichier
        file_menu = menubar.addMenu('&Fichier')
        
        # Action générateur ArUco
        aruco_action = QAction('&Générateur ArUco', self)
        aruco_action.setShortcut('Ctrl+G')
        aruco_action.triggered.connect(self.show_aruco_generator)
        file_menu.addAction(aruco_action)
        
        file_menu.addSeparator()
        
        # Action quitter
        exit_action = QAction('&Quitter', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Menu Caméra (actions globales)
        camera_menu = menubar.addMenu('&Caméra')
        
        start_all_action = QAction('Démarrer &Streaming Global', self)
        start_all_action.setShortcut('Ctrl+S')
        start_all_action.triggered.connect(self.start_global_streaming)
        camera_menu.addAction(start_all_action)
        
        stop_all_action = QAction('&Arrêter Streaming Global', self)
        stop_all_action.setShortcut('Ctrl+T')
        stop_all_action.triggered.connect(self.stop_global_streaming)
        camera_menu.addAction(stop_all_action)
    
    def create_toolbar(self):
        """Crée la barre d'outils"""
        toolbar = self.addToolBar('Actions Principales')
        
        # Action streaming global
        start_streaming_action = QAction('▶️ Démarrer Streaming', self)
        start_streaming_action.triggered.connect(self.start_global_streaming)
        toolbar.addAction(start_streaming_action)
        
        stop_streaming_action = QAction('⏹️ Arrêter Streaming', self)
        stop_streaming_action.triggered.connect(self.stop_global_streaming)
        toolbar.addAction(stop_streaming_action)
        
        toolbar.addSeparator()
        
        # Action générateur ArUco
        aruco_generator_action = QAction('🎯 Générateur ArUco', self)
        aruco_generator_action.triggered.connect(self.show_aruco_generator)
        toolbar.addAction(aruco_generator_action)
    
    def create_status_bar(self):
        """Crée la barre de statut"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Labels de statut
        self.camera_status = QLabel("Caméra: Arrêtée")
        self.tracking_status = QLabel("Tracking: Inactif")
        self.connection_status = QLabel("Signaux: En attente")
        
        self.status_bar.addWidget(self.camera_status)
        self.status_bar.addPermanentWidget(self.tracking_status)
        self.status_bar.addPermanentWidget(self.connection_status)
    
    def connect_inter_tab_signals(self):
        """Connecte les signaux inter-onglets avec vérification cohérence"""
        try:
            camera_tab = self.tabs.get('camera')
            target_tab = self.tabs.get('target')
            
            if not camera_tab or not target_tab:
                logger.warning("⚠️ Onglets principaux manquants pour signaux")
                self.connection_status.setText("Signaux: Onglets manquants")
                return
            
            connections_made = 0
            
            # === SIGNAUX MAÎTRE (CameraTab) → ESCLAVE (TargetTab) ===
            
            # 1. Ouverture de caméra - CORRECTION: Utiliser camera_opened
            if hasattr(camera_tab, 'camera_opened') and hasattr(target_tab, '_on_camera_changed'):
                camera_tab.camera_opened.connect(target_tab._on_camera_changed)
                connections_made += 1
                logger.info("📡 Signal camera_opened → target._on_camera_changed")
            else:
                # Diagnostic détaillé des signaux disponibles
                camera_signals = [attr for attr in dir(camera_tab) if not attr.startswith('_')]
                target_methods = [attr for attr in dir(target_tab) if attr.startswith('_on_')]
                
                logger.warning(f"⚠️ Signal camera_opened non disponible")
                logger.debug(f"Signaux camera_tab disponibles: {camera_signals}")
                logger.debug(f"Méthodes target_tab disponibles: {target_methods}")
            
            # 2. Fermeture de caméra
            if hasattr(camera_tab, 'camera_closed') and hasattr(target_tab, '_check_camera_status'):
                # Trigger aussi sur fermeture pour rafraîchir l'état
                camera_tab.camera_closed.connect(lambda alias: target_tab._check_camera_status())
                connections_made += 1
                logger.info("📡 Signal camera_closed → target._check_camera_status")
            
            # 3. Démarrage streaming  
            if hasattr(camera_tab, 'streaming_started') and hasattr(target_tab, '_on_streaming_started'):
                camera_tab.streaming_started.connect(target_tab._on_streaming_started)
                connections_made += 1
                logger.info("📡 Signal streaming_started → target._on_streaming_started")
            else:
                logger.warning("⚠️ Signal streaming_started non disponible")
            
            # 4. Arrêt streaming
            if hasattr(camera_tab, 'streaming_stopped') and hasattr(target_tab, '_on_streaming_stopped'):
                camera_tab.streaming_stopped.connect(target_tab._on_streaming_stopped)
                connections_made += 1
                logger.info("📡 Signal streaming_stopped → target._on_streaming_stopped")
            else:
                logger.warning("⚠️ Signal streaming_stopped non disponible")
            
            # === SIGNAUX FEEDBACK ESCLAVE → MAÎTRE ===
            
            # 5. Statut tracking vers système
            if hasattr(target_tab, 'tracking_started'):
                target_tab.tracking_started.connect(self._on_tracking_started)
                connections_made += 1
                logger.info("📡 Signal target.tracking_started → main._on_tracking_started")
            
            if hasattr(target_tab, 'tracking_stopped'):
                target_tab.tracking_stopped.connect(self._on_tracking_stopped)
                connections_made += 1
                logger.info("📡 Signal target.tracking_stopped → main._on_tracking_stopped")
            
            # 6. Détections vers autres onglets (si disponibles)
            trajectory_tab = self.tabs.get('trajectory')
            if (hasattr(target_tab, 'target_detected') and trajectory_tab and 
                hasattr(trajectory_tab, '_on_target_detected')):
                target_tab.target_detected.connect(trajectory_tab._on_target_detected)
                connections_made += 1
                logger.info("📡 Signal target_detected → trajectory._on_target_detected")
            
            # === SIGNAUX DE STATUT GLOBAUX ===
            
            # 7. Status changes pour barre de statut
            for tab_name, tab_instance in self.tabs.items():
                if hasattr(tab_instance, 'status_changed'):
                    tab_instance.status_changed.connect(self._on_tab_status_changed)
                    connections_made += 1
            
            # Mise à jour de la barre de statut
            self.connection_status.setText(f"Signaux: {connections_made} connectés")
            
            if connections_made > 0:
                logger.info(f"✅ Architecture maître-esclave: {connections_made} signaux connectés")
            else:
                logger.warning("⚠️ Aucun signal inter-onglet connecté")
                
        except Exception as e:
            logger.error(f"❌ Erreur connexion signaux inter-onglets: {e}")
            self.connection_status.setText("Signaux: Erreur")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _on_tracking_started(self):
        """Callback global quand le tracking démarre"""
        logger.info("🎬 Tracking global démarré")
        self.tracking_status.setText("Tracking: Actif")
        self.tracking_status.setStyleSheet("color: green; font-weight: bold;")
        
        # Notification à tous les onglets intéressés
        for tab_name, tab in self.tabs.items():
            if hasattr(tab, '_on_global_tracking_started') and tab_name != 'target':
                try:
                    tab._on_global_tracking_started()
                except Exception as e:
                    logger.warning(f"⚠️ Erreur notification tracking {tab_name}: {e}")
    
    def _on_tracking_stopped(self):
        """Callback global quand le tracking s'arrête"""
        logger.info("⏹️ Tracking global arrêté")
        self.tracking_status.setText("Tracking: Inactif")
        self.tracking_status.setStyleSheet("color: red;")
        
        # Notification à tous les onglets intéressés
        for tab_name, tab in self.tabs.items():
            if hasattr(tab, '_on_global_tracking_stopped') and tab_name != 'target':
                try:
                    tab._on_global_tracking_stopped()
                except Exception as e:
                    logger.warning(f"⚠️ Erreur notification tracking {tab_name}: {e}")
    
    def _on_tab_status_changed(self, status_info):
        """Callback pour les changements de statut des onglets"""
        try:
            # Mise à jour des compteurs globaux
            total_cameras = len(self.camera_manager.active_cameras) if self.camera_manager else 0
            self.camera_status.setText(f"Caméra: {total_cameras} active(s)")
            
            if total_cameras > 0:
                self.camera_status.setStyleSheet("color: green;")
            else:
                self.camera_status.setStyleSheet("color: red;")
                
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour statut: {e}")
    
    def start_global_streaming(self):
        """Démarre le streaming global via tous les onglets"""
        try:
            camera_tab = self.tabs.get('camera')
            if camera_tab and hasattr(camera_tab, '_start_streaming'):
                camera_tab._start_streaming()
                logger.info("🎬 Streaming global démarré via toolbar")
            else:
                logger.warning("⚠️ Impossible de démarrer streaming global")
                
        except Exception as e:
            logger.error(f"❌ Erreur démarrage streaming global: {e}")
    
    def stop_global_streaming(self):
        """Arrête le streaming global via tous les onglets"""
        try:
            camera_tab = self.tabs.get('camera')
            if camera_tab and hasattr(camera_tab, '_stop_streaming'):
                camera_tab._stop_streaming()
                logger.info("⏹️ Streaming global arrêté via toolbar")
            else:
                logger.warning("⚠️ Impossible d'arrêter streaming global")
                
        except Exception as e:
            logger.error(f"❌ Erreur arrêt streaming global: {e}")
    
    def show_aruco_generator(self):
        """Affiche le générateur ArUco"""
        try:
            dialog = ArUcoGeneratorDialog(self.config, self)
            dialog.exec()
        except Exception as e:
            logger.error(f"❌ Erreur générateur ArUco: {e}")
            QMessageBox.warning(self, "Erreur", f"Impossible d'ouvrir le générateur ArUco:\n{e}")
    
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
    
    def update_status(self):
        """Met à jour la barre de statut périodiquement"""
        try:
            # État des caméras via CameraManager
            active_cameras = len(self.camera_manager.active_cameras)
            if active_cameras > 0:
                self.camera_status.setText(f"Caméra: {active_cameras} active(s)")
            else:
                self.camera_status.setText("Caméra: Arrêtée")
            
            # État du tracking depuis TargetTab
            target_tab = self.tabs.get('target')
            if target_tab and hasattr(target_tab, 'is_tracking'):
                status = "Actif" if target_tab.is_tracking else "Inactif"
                self.tracking_status.setText(f"Tracking: {status}")
                
        except Exception as e:
            logger.debug(f"Erreur mise à jour statut: {e}")
    
    def closeEvent(self, event):
        """Gestionnaire de fermeture avec nettoyage proper"""
        logger.info("🚪 Fermeture MainWindow...")
        
        try:
            # 1. Arrêt du tracking si actif
            target_tab = self.tabs.get('target')
            if target_tab and hasattr(target_tab, 'cleanup'):
                target_tab.cleanup()
            
            # 2. Arrêt et fermeture CameraManager
            self.camera_manager.stop_streaming()
            self.camera_manager.close_all_cameras()
            
            # 3. Nettoyage de tous les onglets
            for tab_name, tab in self.tabs.items():
                if hasattr(tab, 'cleanup'):
                    try:
                        tab.cleanup()
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur nettoyage {tab_name}: {e}")
            
            # 4. Arrêt des timers
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
            
            logger.info("✅ MainWindow fermé proprement")
            
        except Exception as e:
            logger.error(f"❌ Erreur fermeture: {e}")
        
        event.accept()