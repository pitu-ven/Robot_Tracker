# ui/main_window.py
# Version 1.3 - Correction intégration TargetTab avec camera_manager partagé
# Modification: Ajout camera_manager centralisé pour partage entre onglets

from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                           QStatusBar, QMenuBar, QToolBar, QMessageBox, QApplication, QDialog)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QFont, QAction, QPalette, QColor
import sys
import logging

from .camera_tab import CameraTab
from .trajectory_tab import TrajectoryTab
from .target_tab import TargetTab
from .calibration_tab import CalibrationTab
from .measures_tab import MeasuresTab
from .aruco_generator import ArUcoGeneratorDialog
from core.camera_manager import CameraManager  # Import ajouté

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
        
        # Interface
        self.create_menu_bar()
        self.create_toolbar()
        self.create_tabs()
        self.create_status_bar()
    
    def create_tabs(self):
        """Crée les onglets de l'application avec camera_manager partagé"""
        tab_configs = self.config.get('ui', 'tabs', {})
        tab_names = tab_configs.get('tab_names', ["Caméra", "Trajectoire", "Cible", "Calibration", "Mesures"])
        
        try:
            # Onglet 1: Caméra (utilise le camera_manager centralisé)
            self.tabs['camera'] = CameraTab(self.config, camera_manager=self.camera_manager)
            self.central_widget.addTab(self.tabs['camera'], tab_names[0])
            logger.info(f"📑 Onglet '{tab_names[0]}' créé avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur création onglet Caméra: {e}")
            # Création onglet d'erreur minimal
            error_widget = QWidget()
            error_layout = QVBoxLayout(error_widget)
            error_layout.addWidget(QLabel(f"Erreur onglet Caméra: {e}"))
            self.central_widget.addTab(error_widget, "⚠️ Caméra")
        
        try:
            # Onglet 2: Trajectoire
            self.tabs['trajectory'] = TrajectoryTab(self.config)
            self.central_widget.addTab(self.tabs['trajectory'], tab_names[1])
            logger.info(f"📑 Onglet '{tab_names[1]}' créé avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur création onglet Trajectoire: {e}")
            error_widget = QWidget()
            self.central_widget.addTab(error_widget, "⚠️ Trajectoire")
        
        try:
            # Onglet 3: Cible (CORRECTION: ajout camera_manager)
            self.tabs['target'] = TargetTab(self.config, self.camera_manager)
            self.central_widget.addTab(self.tabs['target'], tab_names[2])
            logger.info(f"📑 Onglet '{tab_names[2]}' créé avec succès")
            
            # Connexion des signaux entre onglets
            if 'camera' in self.tabs and hasattr(self.tabs['camera'], 'camera_selected'):
                self.tabs['camera'].camera_selected.connect(self.tabs['target'].on_camera_ready)
                logger.info("🔗 Signaux caméra → cible connectés")
                
        except Exception as e:
            logger.error(f"❌ Erreur création onglet Cible: {e}")
            # Widget d'erreur avec informations
            error_widget = QWidget()
            error_layout = QVBoxLayout(error_widget)
            error_layout.addWidget(QLabel(f"Erreur onglet Cible: {e}"))
            error_layout.addWidget(QLabel("Vérifiez les dépendances OpenCV et les fichiers de configuration"))
            self.central_widget.addTab(error_widget, "⚠️ Cible")
        
        try:
            # Onglet 4: Calibration
            self.tabs['calibration'] = CalibrationTab(self.config)
            self.central_widget.addTab(self.tabs['calibration'], tab_names[3])
            logger.info(f"📑 Onglet '{tab_names[3]}' créé avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur création onglet Calibration: {e}")
            error_widget = QWidget()
            self.central_widget.addTab(error_widget, "⚠️ Calibration")
        
        try:
            # Onglet 5: Mesures
            self.tabs['measures'] = MeasuresTab(self.config)
            self.central_widget.addTab(self.tabs['measures'], tab_names[4])
            logger.info(f"📑 Onglet '{tab_names[4]}' créé avec succès")
        except Exception as e:
            logger.error(f"❌ Erreur création onglet Mesures: {e}")
            error_widget = QWidget()
            self.central_widget.addTab(error_widget, "⚠️ Mesures")
        
        logger.info(f"📑 {len(self.tabs)} onglet(s) créé(s) avec succès")
        
        # Onglet par défaut
        default_tab = tab_configs.get('default_tab', 0)
        if 0 <= default_tab < self.central_widget.count():
            self.central_widget.setCurrentIndex(default_tab)
    
    def create_menu_bar(self):
        """Création de la barre de menu avec générateur ArUco"""
        layout_config = self.config.get('ui', 'layout', {})
        if not layout_config.get('menu_bar', True):
            return
        
        menubar = self.menuBar()
        
        # Menu Fichier
        file_menu = menubar.addMenu('&Fichier')
        
        open_action = QAction('&Ouvrir Trajectoire...', self)
        open_action.setShortcut('Ctrl+O')
        open_action.setStatusTip('Charger un fichier de trajectoire')
        open_action.triggered.connect(self.open_trajectory_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('&Quitter', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Quitter l\'application')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Menu Outils avec générateur ArUco
        tools_menu = menubar.addMenu('&Outils')
        
        aruco_action = QAction('&Générateur ArUco...', self)
        aruco_action.setShortcut('Ctrl+G')
        aruco_action.setStatusTip('Ouvrir le générateur de codes ArUco')
        aruco_action.triggered.connect(self.show_aruco_generator)
        tools_menu.addAction(aruco_action)
        
        # Menu Aide
        help_menu = menubar.addMenu('&Aide')
        
        about_action = QAction('&À propos...', self)
        about_status_tip = self.config.get('ui', 'main_window.about.status_tip', 'Informations sur l\'application')
        about_action.setStatusTip(about_status_tip)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        logger.info("📋 Barre de menu créée avec générateur ArUco")
    
    def create_toolbar(self):
        """Création de la barre d'outils"""
        layout_config = self.config.get('ui', 'layout', {})
        if not layout_config.get('toolbar', True):
            return
        
        toolbar = self.addToolBar('Outils')
        
        # Action démarrage acquisition
        start_action = QAction('▶️ Démarrer', self)
        start_action.setStatusTip('Démarrer l\'acquisition')
        start_action.triggered.connect(self.start_acquisition)
        toolbar.addAction(start_action)
        
        # Action arrêt acquisition
        stop_action = QAction('⏹️ Arrêter', self)
        stop_action.setStatusTip('Arrêter l\'acquisition')
        stop_action.triggered.connect(self.stop_acquisition)
        toolbar.addAction(stop_action)
        
        toolbar.addSeparator()
        
        # Action générateur ArUco
        aruco_action = QAction('🎯 ArUco', self)
        aruco_action.setStatusTip('Générateur de codes ArUco')
        aruco_action.triggered.connect(self.show_aruco_generator)
        toolbar.addAction(aruco_action)
        
        logger.info("🔧 Barre d'outils créée")
    
    def create_status_bar(self):
        """Création de la barre de statut"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('Prêt')
    
    def apply_theme(self):
        """Application du thème depuis la configuration"""
        theme_config = self.config.get('ui', 'theme', {})
        
        if theme_config.get('dark_mode', False):
            self.setStyleSheet("""
                QMainWindow { background-color: #2b2b2b; color: #ffffff; }
                QTabWidget::pane { border: 1px solid #555555; }
                QTabBar::tab { background-color: #3b3b3b; padding: 8px; margin: 2px; }
                QTabBar::tab:selected { background-color: #555555; }
            """)
    
    def center_window(self):
        """Centre la fenêtre sur l'écran"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.geometry()
            window_rect = self.geometry()
            
            x = (screen_rect.width() - window_rect.width()) // 2
            y = (screen_rect.height() - window_rect.height()) // 2
            
            self.move(x, y)
    
    def connect_signals(self):
        """Connexion des signaux entre composants"""
        # Connexion des signaux inter-onglets
        if 'camera' in self.tabs and 'target' in self.tabs:
            # Signal nouvelle frame caméra vers onglet cible
            if hasattr(self.tabs['camera'], 'frame_captured'):
                self.tabs['camera'].frame_captured.connect(self._on_camera_frame)
    
    def _on_camera_frame(self, alias, frame_data):
        """Callback réception frame caméra"""
        # Transmission vers onglet cible si actif
        if 'target' in self.tabs and hasattr(self.tabs['target'], '_on_new_frame'):
            self.tabs['target']._on_new_frame(frame_data.get('color'))
    
    def show_aruco_generator(self):
        """Affiche le générateur ArUco"""
        try:
            dialog = ArUcoGeneratorDialog(self.config, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir le générateur ArUco:\n{e}")
            logger.error(f"❌ Erreur générateur ArUco: {e}")
    
    def open_trajectory_file(self):
        """Ouvre un fichier de trajectoire"""
        # TODO: Implémentation ouverture fichier trajectoire
        QMessageBox.information(self, "Information", "Fonctionnalité en développement")
    
    def start_acquisition(self):
        """Démarre l'acquisition"""
        if 'camera' in self.tabs and hasattr(self.tabs['camera'], '_start_streaming'):
            self.tabs['camera']._start_streaming()
            self.status_bar.showMessage('Acquisition démarrée')
        else:
            self.status_bar.showMessage('Aucune caméra disponible')
    
    def stop_acquisition(self):
        """Arrête l'acquisition"""
        if 'camera' in self.tabs and hasattr(self.tabs['camera'], '_stop_streaming'):
            self.tabs['camera']._stop_streaming()
            self.status_bar.showMessage('Acquisition arrêtée')
    
    def update_status(self):
        """Met à jour la barre de statut"""
        if 'camera' in self.tabs and hasattr(self.tabs['camera'], 'is_streaming'):
            if self.tabs['camera'].is_streaming:
                # Affichage FPS si disponible
                fps = getattr(self.tabs['camera'], 'current_fps', 0)
                self.status_bar.showMessage(f'Acquisition en cours - {fps:.1f} FPS')
        
        # Mise à jour informations onglet cible
        if 'target' in self.tabs and hasattr(self.tabs['target'], 'is_tracking'):
            if self.tabs['target'].is_tracking:
                targets_count = len(getattr(self.tabs['target'], 'detected_targets', []))
                current_msg = self.status_bar.currentMessage()
                if 'Acquisition' in current_msg:
                    self.status_bar.showMessage(f'{current_msg} - {targets_count} cibles')
    
    def show_about(self):
        """Affiche les informations sur l'application"""
        about_text = f"""
        <h3>Robot Trajectory Controller</h3>
        <p>Version 1.3</p>
        <p>Système de contrôle de trajectoire robotique par vision industrielle.</p>
        <p>Avec générateur ArUco intégré et onglet Cible.</p>
        
        <p><b>Fonctionnalités:</b></p>
        <ul>
        <li>Tracking temps réel (2D/3D)</li>
        <li>Détection multi-cibles (ArUco, réfléchissants, LEDs)</li>
        <li>Calibration caméra-robot</li>
        <li>Génération de codes ArUco</li>
        <li>Analyse de trajectoires</li>
        <li>Rapports PDF automatiques</li>
        </ul>
        """
        
        QMessageBox.about(self, 'À propos', about_text)
    
    def closeEvent(self, event):
        """Gestion de la fermeture de l'application"""
        try:
            # Arrêt du timer
            self.update_timer.stop()
            
            # Nettoyage camera manager
            if hasattr(self, 'camera_manager'):
                self.camera_manager.close_all_cameras()
                logger.info("📷 Toutes les caméras fermées")
            
            # Nettoyage des onglets
            for tab_name, tab_instance in self.tabs.items():
                if hasattr(tab_instance, 'cleanup'):
                    tab_instance.cleanup()
                elif hasattr(tab_instance, 'closeEvent'):
                    # Simulation closeEvent pour l'onglet
                    try:
                        tab_instance.closeEvent(event)
                    except:
                        pass
            
            # Sauvegarde de la configuration si modifiée
            if hasattr(self.config, 'save_all_configs'):
                self.config.save_all_configs()
            
            logger.info("👋 Fermeture de l'application")
            event.accept()
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la fermeture: {e}")
            event.accept()  # Fermer quand même
    
    def resizeEvent(self, event):
        """Gestion du redimensionnement avec protection"""
        super().resizeEvent(event)
        
        try:
            new_size = event.size()
            
            # Vérification que la méthode set() existe
            if hasattr(self.config, 'set'):
                self.config.set('ui', 'window.width', new_size.width())
                self.config.set('ui', 'window.height', new_size.height())
            else:
                logger.debug(f"Méthode set() non disponible - taille: {new_size.width()}x{new_size.height()}")
        
        except Exception as e:
            logger.debug(f"Erreur sauvegarde taille fenêtre: {e}")
            pass


# Point d'entrée pour test
if __name__ == "__main__":
    from core.config_manager import ConfigManager
    from PyQt6.QtWidgets import QLabel
    
    app = QApplication(sys.argv)
    config = ConfigManager()
    window = MainWindow(config)
    window.show()
    
    sys.exit(app.exec())