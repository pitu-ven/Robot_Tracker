# robot_tracker/ui/main_window.py
# Version 1.2 - Correction complète ArUco
# Modification: Suppression ArUcoConfig obsolète, correction imports

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
from .aruco_generator import ArUcoGeneratorDialog  # Import direct corrigé

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """Fenêtre principale avec intégration ArUco corrigée"""
    
    def __init__(self, config):
        super().__init__()
        
        # Configuration
        self.config = config
        self.tabs = {}
        
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
        width = window_config.get('width', 1536)
        height = window_config.get('height', 937)
        
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
        """Crée les onglets de l'application"""
        tab_configs = self.config.get('ui', 'tabs', {})
        tab_names = tab_configs.get('tab_names', ["Caméra", "Trajectoire", "Cible", "Calibration", "Mesures"])
        
        # Onglet 1: Caméra
        self.tabs['camera'] = CameraTab(self.config)
        self.central_widget.addTab(self.tabs['camera'], tab_names[0])
        logger.info(f"📑 Onglet '{tab_names[0]}' créé avec succès")
        
        # Onglet 2: Trajectoire
        self.tabs['trajectory'] = TrajectoryTab(self.config)
        self.central_widget.addTab(self.tabs['trajectory'], tab_names[1])
        logger.info(f"📑 Onglet '{tab_names[1]}' créé avec succès")
        
        # Onglet 3: Cible
        self.tabs['target'] = TargetTab(self.config)
        self.central_widget.addTab(self.tabs['target'], tab_names[2])
        logger.info(f"📑 Onglet '{tab_names[2]}' créé avec succès")
        
        # Onglet 4: Calibration
        self.tabs['calibration'] = CalibrationTab(self.config)
        self.central_widget.addTab(self.tabs['calibration'], tab_names[3])
        logger.info(f"📑 Onglet '{tab_names[3]}' créé avec succès")
        
        # Onglet 5: Mesures
        self.tabs['measures'] = MeasuresTab(self.config)
        self.central_widget.addTab(self.tabs['measures'], tab_names[4])
        logger.info(f"📑 Onglet '{tab_names[4]}' créé avec succès")
        
        logger.info(f"📑 {len(self.tabs)} onglets créés avec succès")
        
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
        
        # Menu Configuration avec ArUco
        config_menu = menubar.addMenu('&Configuration')
        
        camera_config_action = QAction('&Caméras...', self)
        camera_config_action.setStatusTip('Configuration des caméras')
        camera_config_action.triggered.connect(self.configure_cameras)
        config_menu.addAction(camera_config_action)
        
        robot_config_action = QAction('&Robot...', self)
        robot_config_action.setStatusTip('Configuration de la communication robot')
        robot_config_action.triggered.connect(self.configure_robot)
        config_menu.addAction(robot_config_action)
        
        config_menu.addSeparator()
        
        # GÉNÉRATEUR ARUCO CORRIGÉ
        aruco_generator_action = QAction('🎯 &Générateur ArUco...', self)
        aruco_generator_action.setStatusTip('Générer et imprimer des codes ArUco')
        aruco_generator_action.triggered.connect(self.open_aruco_generator)
        config_menu.addAction(aruco_generator_action)
        
        # Menu Outils
        tools_menu = menubar.addMenu('&Outils')
        
        calibrate_action = QAction('&Calibrer Caméra-Robot...', self)
        calibrate_action.setStatusTip('Lancer la calibration caméra-robot')
        calibrate_action.triggered.connect(self.start_calibration)
        tools_menu.addAction(calibrate_action)
        
        # Menu Aide
        help_menu = menubar.addMenu('&Aide')
        
        about_action = QAction('&À propos...', self)
        about_action.setStatusTip('Informations sur l\'application')
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        logger.info("📋 Barre de menu créée avec générateur ArUco")
    
    def create_toolbar(self):
        """Création de la barre d'outils"""
        layout_config = self.config.get('ui', 'layout', {})
        if not layout_config.get('toolbar', True):
            return
        
        toolbar = self.addToolBar('Principal')
        
        # Actions principales
        start_action = QAction('▶️ Démarrer', self)
        start_action.setStatusTip('Démarrer l\'acquisition')
        start_action.triggered.connect(self.start_acquisition)
        toolbar.addAction(start_action)
        
        stop_action = QAction('⏹️ Arrêter', self)
        stop_action.setStatusTip('Arrêter l\'acquisition')
        stop_action.triggered.connect(self.stop_acquisition)
        toolbar.addAction(stop_action)
        
        toolbar.addSeparator()
        
        # ArUco dans la toolbar
        aruco_action = QAction('🎯 ArUco', self)
        aruco_action.setStatusTip('Générateur de codes ArUco')
        aruco_action.triggered.connect(self.open_aruco_generator)
        toolbar.addAction(aruco_action)
        
        logger.info("🔧 Barre d'outils créée")
    
    def create_status_bar(self):
        """Création de la barre de statut"""
        self.status_bar = self.statusBar()
        
        status_config = self.config.get('ui', 'status_bar', {})
        ready_message = status_config.get('ready_message', 'Prêt')
        
        self.status_bar.showMessage(ready_message)
        logger.info("📊 Barre de status créée")
    
    def apply_theme(self):
        """Application du thème depuis la configuration"""
        theme_config = self.config.get('ui', 'theme', {})
        style_name = theme_config.get('style', 'Fusion')
        
        QApplication.instance().setStyle(style_name)
        
        if theme_config.get('dark_mode', True):
            self.apply_dark_theme()
            logger.info(f"🎨 Thème appliqué: {style_name}, palette: dark")
        else:
            logger.info(f"🎨 Thème appliqué: {style_name}, palette: default")
        
        # Police personnalisée
        font_config = theme_config.get('font', {})
        if font_config:
            font = QFont(
                font_config.get('family', 'Segoe UI'),
                font_config.get('size', 10)
            )
            QApplication.instance().setFont(font)
    
    def apply_dark_theme(self):
        """Application du thème sombre"""
        palette = QPalette()
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
    
    def center_window(self):
        """Centre la fenêtre sur l'écran"""
        screen = QApplication.primaryScreen().geometry()
        window_geometry = self.geometry()
        
        x = (screen.width() - window_geometry.width()) // 2
        y = (screen.height() - window_geometry.height()) // 2
        
        self.move(x, y)
        logger.info(f"🎯 Fenêtre centrée à ({x}, {y})")
    
    def connect_signals(self):
        """Connecte les signaux de l'interface"""
        # Connexions des onglets si nécessaire
        logger.info("🔗 Connexions établies")
    
    def open_aruco_generator(self):
        """Ouvre le générateur ArUco - VERSION CORRIGÉE"""
        try:
            logger.info("🎯 Ouverture du générateur ArUco")
            
            # Vérification de la disponibilité d'OpenCV ArUco
            import cv2
            if not hasattr(cv2, 'aruco'):
                QMessageBox.warning(
                    self, "ArUco indisponible",
                    "Le module OpenCV ArUco n'est pas disponible.\n"
                    "Installez opencv-contrib-python pour utiliser cette fonctionnalité."
                )
                return
            
            # CORRECTION : Utiliser directement le ConfigManager
            dialog = ArUcoGeneratorDialog(self.config, self)
            result = dialog.exec()
            
            if result == QDialog.DialogCode.Accepted:
                logger.info("✅ Générateur ArUco fermé avec succès")
            else:
                logger.info("📝 Générateur ArUco fermé")
                
        except ImportError as e:
            QMessageBox.critical(
                self, "Erreur d'import",
                f"Impossible d'importer le générateur ArUco:\n{e}\n\n"
                "Vérifiez l'installation d'OpenCV et la structure des fichiers."
            )
            logger.error(f"❌ Erreur import ArUco: {e}")
        except Exception as e:
            logger.error(f"❌ Erreur ouverture générateur ArUco: {e}")
            QMessageBox.critical(
                self, "Erreur",
                f"Erreur lors de l'ouverture du générateur ArUco:\n{e}"
            )
    
    # Méthodes d'action
    def open_trajectory_file(self):
        """Ouvre un fichier de trajectoire"""
        from PyQt6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Ouvrir trajectoire',
            '', 'Fichiers trajectoire (*.val3 *.krl *.gcode);;Tous (*.*)'
        )
        
        if file_path:
            self.tabs['trajectory'].load_trajectory(file_path)
            self.status_bar.showMessage(f'Trajectoire chargée: {file_path}')
    
    def save_report(self):
        """Sauvegarde le rapport PDF"""
        from PyQt6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 'Sauvegarder rapport',
            'rapport_trajectoire.pdf', 'Fichiers PDF (*.pdf)'
        )
        
        if file_path:
            if self.tabs['measures'].generate_pdf_report(file_path):
                self.status_bar.showMessage(f'Rapport sauvegardé: {file_path}')
            else:
                QMessageBox.warning(self, 'Erreur', 'Erreur lors de la génération du rapport')
    
    def configure_cameras(self):
        """Configure les caméras"""
        self.tabs['camera'].show_configuration_dialog()
    
    def configure_robot(self):
        """Configure la communication robot"""
        QMessageBox.information(self, 'Info', 'Configuration robot (à implémenter)')
    
    def start_calibration(self):
        """Démarre la calibration"""
        self.tabs['calibration'].start_calibration_process()
    
    def start_acquisition(self):
        """Démarre l'acquisition"""
        self.tabs['camera'].start_acquisition()
        self.status_bar.showMessage('Acquisition démarrée')
    
    def stop_acquisition(self):
        """Arrête l'acquisition"""
        self.tabs['camera'].stop_acquisition()
        self.status_bar.showMessage('Acquisition arrêtée')
    
    def update_status(self):
        """Met à jour la barre de statut"""
        if hasattr(self.tabs.get('camera'), 'is_acquiring') and self.tabs['camera'].is_acquiring:
            fps = getattr(self.tabs['camera'], 'current_fps', 0)
            self.status_bar.showMessage(f'Acquisition en cours - {fps:.1f} FPS')
    
    def show_about(self):
        """Affiche les informations sur l'application"""
        about_text = f"""
        <h3>Robot Trajectory Controller</h3>
        <p>Version 1.2</p>
        <p>Système de contrôle de trajectoire robotique par vision industrielle.</p>
        <p>Avec générateur ArUco intégré.</p>
        
        <p><b>Fonctionnalités:</b></p>
        <ul>
        <li>Tracking temps réel (2D/3D)</li>
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
            
            # Nettoyage des onglets
            for tab_name, tab_instance in self.tabs.items():
                if hasattr(tab_instance, 'cleanup'):
                    tab_instance.cleanup()
            
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
    
    app = QApplication(sys.argv)
    config = ConfigManager()
    window = MainWindow(config)
    window.show()
    
    sys.exit(app.exec())