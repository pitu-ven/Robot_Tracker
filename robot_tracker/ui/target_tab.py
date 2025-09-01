# ui/target_tab.py
# Version 2.1 - Correction détection caméra active via CameraManager
# Modification: Utilisation directe CameraManager pour détecter caméras actives

import cv2
import numpy as np
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QSplitter,
    QGroupBox, QPushButton, QLabel, QComboBox, QSpinBox, QCheckBox,
    QLineEdit, QTextEdit, QProgressBar, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSlider, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QPixmap, QImage, QFont, QIcon, QPainter, QPen, QColor

# Import avec fallback pour éviter les erreurs d'import relatif
try:
    from core.aruco_config_loader import ArUcoConfigLoader
    from core.target_detector import TargetDetector, TargetType
    from core.roi_manager import ROIManager, ROIType
except ImportError:
    # Stubs temporaires pour éviter les erreurs lors du développement
    class ArUcoConfigLoader:
        def __init__(self, config): self.detected_markers = {}
        def scan_aruco_folder(self, folder_path): return {}
        def get_detector_params(self): return {}
    
    class TargetDetector:
        def __init__(self, config): 
            self.detection_enabled = {'aruco': True, 'reflective': True, 'led': True}
        def detect(self, frame): return [], []
        def set_roi(self, roi): pass
    
    class TargetType:
        ARUCO = "aruco"
        REFLECTIVE = "reflective"
        LED = "led"
    
    class ROIManager:
        def __init__(self, config_manager): 
            self.is_creating = False
            self.rois = []
        def start_roi_creation(self, roi_type): self.is_creating = True
        def add_point(self, point): pass
        def finish_roi(self): self.is_creating = False

    class ROIType:
        RECTANGLE = "rectangle"
        POLYGON = "polygon"

logger = logging.getLogger(__name__)

class TargetTab(QWidget):
    """Onglet Cible - Focus détection/suivi avec détection automatique caméra"""
    
    # Signaux
    target_detected = pyqtSignal(dict)       # Signal cible détectée
    tracking_started = pyqtSignal()          # Signal tracking démarré
    tracking_stopped = pyqtSignal()          # Signal tracking arrêté
    status_changed = pyqtSignal(dict)        # Signal changement d'état
    
    def __init__(self, config_manager, camera_manager, parent=None):
        super().__init__(parent)
        
        # Configuration et managers
        self.config = config_manager
        self.camera_manager = camera_manager  # Référence au manager centralisé
        
        # État de l'onglet
        self.is_tracking = False
        self.current_frame = None
        self.current_depth_frame = None
        self.camera_ready = False
        self.selected_camera_alias = None
        
        # Données de tracking
        self.detected_targets = []
        self.tracking_history = []
        self.detection_stats = {
            'total_detections': 0,
            'fps': 0.0,
            'last_detection_time': 0.0
        }
        
        # Composants de détection
        self._init_detection_components()
        
        # Interface utilisateur
        self._setup_ui()
        self._connect_internal_signals()
        
        # Timer pour le traitement des frames
        self.processing_timer = QTimer()
        self.processing_timer.timeout.connect(self._process_current_frame)
        
        # Timer pour vérifier l'état des caméras
        self.camera_check_timer = QTimer()
        self.camera_check_timer.timeout.connect(self._check_camera_status)
        self.camera_check_timer.start(1000)  # Vérification chaque seconde
        
        version = self._safe_get_config('ui', 'target_tab.version', '2.1')
        logger.info(f"🎯 TargetTab v{version} initialisé (détection auto caméra)")
        
        # Vérification initiale de l'état des caméras
        self._check_camera_status()
    
    def _init_detection_components(self):
        """Initialise les composants de détection"""
        try:
            self.aruco_loader = ArUcoConfigLoader(self.config)
            self.target_detector = TargetDetector(self.config)
            self.roi_manager = ROIManager(self.config)
        except Exception as e:
            logger.warning(f"⚠️ Composants détection non disponibles: {e}")
            # Fallback avec stubs
            self.aruco_loader = ArUcoConfigLoader(self.config)
            self.target_detector = TargetDetector(self.config)
            self.roi_manager = ROIManager(self.config)
    
    def _safe_get_config(self, section: str, key: str, default=None):
        """Accès sécurisé à la configuration"""
        try:
            return self.config.get(section, key, default) if hasattr(self.config, 'get') else default
        except Exception:
            return default
    
    def _setup_ui(self):
        """Configure l'interface utilisateur simplifiée"""
        main_layout = QHBoxLayout(self)
        
        # Panneau de contrôle (gauche) - Focus détection
        control_panel = self._create_control_panel()
        control_width = self._safe_get_config('ui', 'target_tab.layout.control_panel_width', 320)
        control_panel.setMaximumWidth(control_width)
        
        # Zone d'affichage (droite) - Flux caméra + overlays
        display_area = self._create_display_area()
        
        main_layout.addWidget(control_panel)
        main_layout.addWidget(display_area, 1)
    
    def _create_control_panel(self):
        """Crée le panneau de contrôle focalisé sur la détection"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 1. État de la caméra (détection automatique)
        camera_status_group = self._create_camera_status_group()
        layout.addWidget(camera_status_group)
        
        # 2. Configuration ArUco
        aruco_group = self._create_aruco_config_group()
        layout.addWidget(aruco_group)
        
        # 3. Types de détection
        detection_types_group = self._create_detection_types_group()
        layout.addWidget(detection_types_group)
        
        # 4. Outils ROI
        roi_tools_group = self._create_roi_tools_group()
        layout.addWidget(roi_tools_group)
        
        # 5. Contrôles tracking
        tracking_controls_group = self._create_tracking_controls_group()
        layout.addWidget(tracking_controls_group)
        
        # 6. Statistiques
        stats_group = self._create_stats_group()
        layout.addWidget(stats_group)
        
        layout.addStretch()  # Pousse tout vers le haut
        
        return panel
    
    def _create_camera_status_group(self):
        """Groupe d'affichage de l'état caméra (détection automatique)"""
        group = QGroupBox("📷 État Caméra")
        layout = QVBoxLayout(group)
        
        self.camera_status_label = QLabel("❌ Aucune caméra active")
        self.camera_status_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.camera_status_label)
        
        self.camera_info_label = QLabel("Vérification automatique via CameraManager...")
        self.camera_info_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.camera_info_label)
        
        # Bouton refresh manuel
        self.refresh_camera_btn = QPushButton("🔄 Actualiser État Caméra")
        self.refresh_camera_btn.clicked.connect(self._check_camera_status)
        layout.addWidget(self.refresh_camera_btn)
        
        return group
    
    def _check_camera_status(self):
        """Vérifie l'état des caméras via CameraManager"""
        try:
            # Récupération des caméras actives depuis CameraManager (LISTE d'alias)
            active_cameras = self.camera_manager.active_cameras
            
            if not active_cameras:
                # Aucune caméra active
                self.camera_ready = False
                self.selected_camera_alias = None
                self.camera_status_label.setText("❌ Aucune caméra active")
                self.camera_status_label.setStyleSheet("color: red; font-weight: bold;")
                self.camera_info_label.setText("Démarrez une caméra dans l'onglet Caméra")
                
            else:
                # Au moins une caméra active
                self.camera_ready = True
                
                # Prendre la première caméra active par défaut
                if not self.selected_camera_alias or self.selected_camera_alias not in active_cameras:
                    self.selected_camera_alias = active_cameras[0]
                
                # Récupération des infos de la caméra depuis detected cameras
                camera_info = self.camera_manager.get_camera_info(self.selected_camera_alias)
                
                if camera_info:
                    camera_name = camera_info.get('name', self.selected_camera_alias)
                else:
                    camera_name = self.selected_camera_alias
                
                self.camera_status_label.setText(f"✅ Caméra: {camera_name}")
                self.camera_status_label.setStyleSheet("color: green; font-weight: bold;")
                self.camera_info_label.setText(f"Alias: {self.selected_camera_alias}")
                
                logger.debug(f"📷 Caméra active détectée: {self.selected_camera_alias} ({camera_name})")
            
            # Mise à jour des contrôles
            self._update_tracking_controls_state()
            
        except Exception as e:
            logger.error(f"❌ Erreur vérification état caméra: {e}")
            self.camera_ready = False
            self.camera_status_label.setText("❌ Erreur détection caméra")
            self.camera_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.camera_info_label.setText(f"Erreur: {str(e)}")
    
    def _create_aruco_config_group(self):
        """Groupe de configuration ArUco"""
        group = QGroupBox("🎯 Configuration ArUco")
        layout = QVBoxLayout(group)
        
        # Sélection dossier
        folder_layout = QHBoxLayout()
        self.aruco_folder_btn = QPushButton("📁 Sélectionner Dossier")
        self.aruco_folder_btn.clicked.connect(self._select_aruco_folder)
        folder_layout.addWidget(self.aruco_folder_btn)
        
        self.rescan_btn = QPushButton("🔄")
        self.rescan_btn.setEnabled(False)
        self.rescan_btn.clicked.connect(self._rescan_aruco_folder)
        self.rescan_btn.setFixedWidth(40)
        folder_layout.addWidget(self.rescan_btn)
        layout.addLayout(folder_layout)
        
        # Chemin dossier
        self.aruco_path_label = QLabel("Aucun dossier sélectionné")
        self.aruco_path_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.aruco_path_label)
        
        # Liste marqueurs détectés
        self.markers_info_label = QLabel("Marqueurs: 0 détectés")
        layout.addWidget(self.markers_info_label)
        
        # Bouton configuration avancée
        self.config_btn = QPushButton("⚙️ Configuration Avancée")
        self.config_btn.setEnabled(False)
        self.config_btn.clicked.connect(self._show_aruco_advanced_config)
        layout.addWidget(self.config_btn)
        
        return group
    
    def _create_detection_types_group(self):
        """Groupe de sélection des types de détection"""
        group = QGroupBox("🔍 Types de Détection")
        layout = QVBoxLayout(group)
        
        self.aruco_check = QCheckBox("ArUco Markers")
        self.aruco_check.setChecked(True)
        self.aruco_check.toggled.connect(self._toggle_detection_type)
        layout.addWidget(self.aruco_check)
        
        self.reflective_check = QCheckBox("Marqueurs Réfléchissants")
        self.reflective_check.setChecked(True)
        self.reflective_check.toggled.connect(self._toggle_detection_type)
        layout.addWidget(self.reflective_check)
        
        self.led_check = QCheckBox("LEDs Colorées")
        self.led_check.setChecked(False)
        self.led_check.toggled.connect(self._toggle_detection_type)
        layout.addWidget(self.led_check)
        
        return group
    
    def _create_roi_tools_group(self):
        """Groupe d'outils ROI"""
        group = QGroupBox("📐 Outils ROI")
        layout = QVBoxLayout(group)
        
        # Boutons outils
        tools_layout = QHBoxLayout()
        self.roi_rect_btn = QPushButton("⬜ Rectangle")
        self.roi_rect_btn.clicked.connect(lambda: self._start_roi_creation(ROIType.RECTANGLE))
        tools_layout.addWidget(self.roi_rect_btn)
        
        self.roi_polygon_btn = QPushButton("⬟ Polygone")
        self.roi_polygon_btn.clicked.connect(lambda: self._start_roi_creation(ROIType.POLYGON))
        tools_layout.addWidget(self.roi_polygon_btn)
        layout.addLayout(tools_layout)
        
        # Actions ROI
        actions_layout = QHBoxLayout()
        self.clear_roi_btn = QPushButton("🗑️ Effacer")
        self.clear_roi_btn.clicked.connect(self._clear_rois)
        actions_layout.addWidget(self.clear_roi_btn)
        
        self.roi_info_label = QLabel("ROI: 0 actives")
        actions_layout.addWidget(self.roi_info_label)
        layout.addLayout(actions_layout)
        
        return group
    
    def _create_tracking_controls_group(self):
        """Groupe de contrôles du tracking"""
        group = QGroupBox("🎬 Contrôles Tracking")
        layout = QVBoxLayout(group)
        
        # Boutons principaux
        buttons_layout = QHBoxLayout()
        self.start_tracking_btn = QPushButton("▶️ Démarrer")
        self.start_tracking_btn.clicked.connect(self._start_tracking)
        self.start_tracking_btn.setEnabled(False)
        buttons_layout.addWidget(self.start_tracking_btn)
        
        self.stop_tracking_btn = QPushButton("⏹️ Arrêter")
        self.stop_tracking_btn.clicked.connect(self._stop_tracking)
        self.stop_tracking_btn.setEnabled(False)
        buttons_layout.addWidget(self.stop_tracking_btn)
        layout.addLayout(buttons_layout)
        
        # Paramètres
        params_layout = QGridLayout()
        params_layout.addWidget(QLabel("FPS Cible:"), 0, 0)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(5, 60)
        self.fps_spin.setValue(30)
        self.fps_spin.valueChanged.connect(self._update_fps_target)
        params_layout.addWidget(self.fps_spin, 0, 1)
        
        params_layout.addWidget(QLabel("Confiance:"), 1, 0)
        self.confidence_spin = QSpinBox()
        self.confidence_spin.setRange(50, 99)
        self.confidence_spin.setValue(80)
        self.confidence_spin.setSuffix("%")
        params_layout.addWidget(self.confidence_spin, 1, 1)
        layout.addLayout(params_layout)
        
        return group
    
    def _create_stats_group(self):
        """Groupe de statistiques"""
        group = QGroupBox("📊 Statistiques")
        layout = QVBoxLayout(group)
        
        self.targets_label = QLabel("Cibles: 0 détectées")
        layout.addWidget(self.targets_label)
        
        self.fps_label = QLabel("FPS: 0.0")
        layout.addWidget(self.fps_label)
        
        self.history_label = QLabel("Historique: 0 points")
        layout.addWidget(self.history_label)
        
        return group
    
    def _create_display_area(self):
        """Crée la zone d'affichage vidéo"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Zone d'affichage principale
        self.camera_display = QLabel()
        self.camera_display.setStyleSheet("border: 1px solid gray; background-color: black;")
        self.camera_display.setScaledContents(True)
        self.camera_display.setMinimumHeight(480)
        self.camera_display.setText("En attente du flux caméra...")
        self.camera_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Événements souris pour ROI
        self.camera_display.mousePressEvent = self._on_display_click
        self.camera_display.mouseMoveEvent = self._on_display_move
        
        layout.addWidget(self.camera_display)
        
        # Barre de contrôles d'affichage
        controls_layout = QHBoxLayout()
        
        # Zoom
        controls_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(25, 400)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self._update_zoom)
        controls_layout.addWidget(self.zoom_slider)
        
        self.zoom_label = QLabel("100%")
        controls_layout.addWidget(self.zoom_label)
        
        controls_layout.addStretch()
        
        # Export
        self.export_btn = QPushButton("💾 Exporter Données")
        self.export_btn.clicked.connect(self._export_tracking_data)
        self.export_btn.setEnabled(False)
        controls_layout.addWidget(self.export_btn)
        
        layout.addLayout(controls_layout)
        
        return widget
    
    def _connect_internal_signals(self):
        """Connecte les signaux internes de l'onglet"""
        pass  # Les connexions sont déjà faites dans les créations de widgets
    
    # === SLOTS POUR COMMUNICATION INTER-ONGLETS ===
    
    def _on_camera_changed(self, camera_alias: str):
        """Slot appelé quand la caméra change (via camera_opened signal)"""
        logger.info(f"📷 Signal caméra changée reçu: {camera_alias}")
        
        # Force une vérification de l'état
        self._check_camera_status()
    
    def _on_streaming_started(self):
        """Slot appelé quand le streaming démarre dans l'onglet Caméra"""
        logger.info("🎬 Signal streaming démarré reçu")
        
        # Force une vérification de l'état
        self._check_camera_status()
        
        # Si une caméra est disponible, démarrer le traitement
        if self.camera_ready and self.selected_camera_alias:
            fps_target = self.fps_spin.value()
            interval_ms = int(1000 / fps_target)
            self.processing_timer.start(interval_ms)
            logger.info(f"🎬 Traitement frames démarré à {fps_target}fps")
    
    def _on_streaming_stopped(self):
        """Slot appelé quand le streaming s'arrête"""
        logger.info("⏹️ Signal streaming arrêté reçu")
        
        # Arrêt du processing
        self.processing_timer.stop()
        if self.is_tracking:
            self._stop_tracking()
        
        # Reset affichage
        self.camera_display.setText("En attente du flux caméra...")
        
        # Force une vérification de l'état
        self._check_camera_status()
    
    # === MÉTHODES DE TRAITEMENT ===
    
    def _process_current_frame(self):
        """Traite la frame courante du CameraManager"""
        if not self.camera_ready or not self.selected_camera_alias:
            return
        
        try:
            # Récupération frame depuis CameraManager centralisé
            success, frame, depth_frame = self.camera_manager.get_camera_frame(self.selected_camera_alias)
            
            if success and frame is not None:
                self.current_frame = frame.copy()
                self.current_depth_frame = depth_frame
                
                # Traitement de détection si tracking actif
                if self.is_tracking:
                    self._detect_targets_in_frame()
                
                # Affichage avec overlays
                self._update_display()
            else:
                # Frame non disponible - vérifier si caméra toujours active
                if not self.camera_manager.is_camera_open(self.selected_camera_alias):
                    logger.warning(f"⚠️ Caméra {self.selected_camera_alias} non disponible")
                    self._check_camera_status()
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement frame: {e}")
            # Re-vérifier l'état en cas d'erreur
            self._check_camera_status()
    
    def _detect_targets_in_frame(self):
        """Effectue la détection des cibles dans la frame courante"""
        if self.current_frame is None:
            return
        
        try:
            # Appel du détecteur (à implémenter complètement dans target_detector.py)
            detected_targets, detection_info = self.target_detector.detect(self.current_frame)
            
            self.detected_targets = detected_targets
            
            # Mise à jour des statistiques
            self._update_detection_stats(detection_info)
            
            # Émission du signal pour autres onglets
            if detected_targets:
                self.target_detected.emit({
                    'targets': detected_targets,
                    'frame_info': detection_info,
                    'timestamp': time.time()
                })
        
        except Exception as e:
            logger.error(f"❌ Erreur détection: {e}")
    
    def _update_display(self):
        """Met à jour l'affichage avec la frame et les overlays"""
        if self.current_frame is None:
            return
        
        try:
            display_frame = self.current_frame.copy()
            
            # Ajout des overlays
            self._draw_overlays(display_frame)
            
            # Conversion pour affichage Qt
            height, width, channel = display_frame.shape
            bytes_per_line = 3 * width
            q_image = QImage(display_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
            
            # Application du zoom
            zoom_factor = self.zoom_slider.value() / 100.0
            if zoom_factor != 1.0:
                q_image = q_image.scaled(int(width * zoom_factor), int(height * zoom_factor), 
                                       Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            pixmap = QPixmap.fromImage(q_image)
            self.camera_display.setPixmap(pixmap)
            
        except Exception as e:
            logger.error(f"❌ Erreur affichage: {e}")
    
    def _draw_overlays(self, frame):
        """Dessine les overlays sur la frame"""
        if not hasattr(self, 'detected_targets'):
            return
        
        # ROI actives
        for roi in self.roi_manager.rois:
            color = (0, 255, 255)  # Jaune
            thickness = 2
            # Dessiner selon le type de ROI (rectangle, polygone, etc.)
            # TODO: Implémenter le dessin des ROI
        
        # Cibles détectées
        for target in self.detected_targets:
            # TODO: Dessiner les cibles selon leur type
            pass
    
    def _update_detection_stats(self, detection_info):
        """Met à jour les statistiques de détection"""
        self.detection_stats['total_detections'] += len(self.detected_targets)
        
        # Calcul FPS
        current_time = time.time()
        if hasattr(self, '_last_detection_time'):
            fps = 1.0 / (current_time - self._last_detection_time)
            self.detection_stats['fps'] = fps
        self._last_detection_time = current_time
        
        # Mise à jour interface
        self._update_stats_display()
    
    def _update_stats_display(self):
        """Met à jour l'affichage des statistiques"""
        self.targets_label.setText(f"Cibles: {len(self.detected_targets)} détectées")
        self.fps_label.setText(f"FPS: {self.detection_stats.get('fps', 0.0):.1f}")
        self.history_label.setText(f"Historique: {len(self.tracking_history)} points")
    
    # === GESTIONNAIRES D'ÉVÉNEMENTS ===
    
    def _select_aruco_folder(self):
        """Sélectionne le dossier de marqueurs ArUco"""
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner dossier ArUco")
        if folder:
            self._scan_aruco_folder(folder)
    
    def _scan_aruco_folder(self, folder_path: str):
        """Scanne le dossier ArUco sélectionné"""
        try:
            markers = self.aruco_loader.scan_aruco_folder(folder_path)
            
            # Mise à jour interface
            self.aruco_path_label.setText(f"📁 {folder_path}")
            self.markers_info_label.setText(f"Marqueurs: {len(markers)} détectés")
            
            # Activation des boutons
            self.rescan_btn.setEnabled(True)
            self.config_btn.setEnabled(True)
            
            logger.info(f"✅ ArUco: {len(markers)} marqueurs détectés")
            
        except Exception as e:
            logger.error(f"❌ Erreur scan ArUco: {e}")
            QMessageBox.warning(self, "Erreur", f"Impossible de scanner le dossier:\n{e}")
    
    def _rescan_aruco_folder(self):
        """Rescanne le dossier ArUco"""
        if hasattr(self.aruco_loader, 'folder_path') and self.aruco_loader.folder_path:
            self._scan_aruco_folder(str(self.aruco_loader.folder_path))
    
    def _show_aruco_advanced_config(self):
        """Affiche la configuration avancée ArUco"""
        QMessageBox.information(self, "Configuration", "Configuration avancée ArUco - À implémenter")
    
    def _toggle_detection_type(self):
        """Gère l'activation/désactivation des types de détection"""
        sender = self.sender()
        
        if sender == self.aruco_check:
            self.target_detector.detection_enabled[TargetType.ARUCO] = sender.isChecked()
        elif sender == self.reflective_check:
            self.target_detector.detection_enabled[TargetType.REFLECTIVE] = sender.isChecked()
        elif sender == self.led_check:
            self.target_detector.detection_enabled[TargetType.LED] = sender.isChecked()
        
        logger.info(f"🔧 Type détection {sender.text()}: {'activé' if sender.isChecked() else 'désactivé'}")
    
    def _start_roi_creation(self, roi_type):
        """Démarre la création d'une ROI"""
        self.roi_manager.start_roi_creation(roi_type)
        logger.info(f"📐 Création ROI {roi_type.value} démarrée")
    
    def _clear_rois(self):
        """Efface toutes les ROI"""
        self.roi_manager.rois.clear()
        self.roi_info_label.setText("ROI: 0 actives")
        logger.info("🗑️ ROI effacées")
    
    def _on_display_click(self, event):
        """Gère les clics sur l'affichage pour les ROI"""
        if self.roi_manager.is_creating:
            point = (event.pos().x(), event.pos().y())
            self.roi_manager.add_point(point)
            # TODO: Logique de création ROI selon le type
    
    def _on_display_move(self, event):
        """Gère le déplacement souris pour les ROI"""
        if self.roi_manager.is_creating:
            # TODO: Mise à jour preview ROI
            pass
    
    def _start_tracking(self):
        """Démarre le tracking"""
        if not self.camera_ready:
            QMessageBox.warning(self, "Attention", 
                "Aucune caméra active détectée.\n\n"
                "1. Allez dans l'onglet Caméra\n"
                "2. Sélectionnez et ouvrez une caméra\n"
                "3. Démarrez le streaming\n"
                "4. Revenez dans cet onglet")
            return
        
        self.is_tracking = True
        self.tracking_history.clear()
        
        # Mise à jour interface
        self._update_tracking_controls_state()
        
        # Émission signal
        self.tracking_started.emit()
        
        logger.info("▶️ Tracking démarré")
    
    def _stop_tracking(self):
        """Arrête le tracking"""
        self.is_tracking = False
        
        # Mise à jour interface
        self._update_tracking_controls_state()
        
        # Activation export
        if self.tracking_history:
            self.export_btn.setEnabled(True)
        
        # Émission signal
        self.tracking_stopped.emit()
        
        logger.info("⏹️ Tracking arrêté")
    
    def _update_fps_target(self, fps):
        """Met à jour la fréquence de traitement"""
        if self.processing_timer.isActive():
            interval_ms = int(1000 / fps)
            self.processing_timer.start(interval_ms)
        logger.info(f"🎯 FPS cible: {fps}")
    
    def _update_zoom(self, value):
        """Met à jour le niveau de zoom"""
        self.zoom_label.setText(f"{value}%")
        if self.current_frame is not None:
            self._update_display()
    
    def _update_tracking_controls_state(self):
        """Met à jour l'état des contrôles de tracking"""
        camera_ok = self.camera_ready and self.selected_camera_alias is not None
        
        if self.is_tracking:
            self.start_tracking_btn.setEnabled(False)
            self.stop_tracking_btn.setEnabled(True)
        else:
            self.start_tracking_btn.setEnabled(camera_ok)
            self.stop_tracking_btn.setEnabled(False)
    
    def _export_tracking_data(self):
        """Exporte les données de tracking"""
        if not self.tracking_history:
            QMessageBox.information(self, "Information", "Aucune donnée de tracking à exporter.")
            return
        
        # Dialogue de sauvegarde
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Exporter données de tracking", 
            f"tracking_data_{int(time.time())}.csv",
            "CSV Files (*.csv);;JSON Files (*.json)"
        )
        
        if file_path:
            try:
                # TODO: Implémenter export réel
                QMessageBox.information(self, "Export", f"Données exportées vers:\n{file_path}")
                logger.info(f"💾 Données exportées: {file_path}")
            except Exception as e:
                logger.error(f"❌ Erreur export: {e}")
                QMessageBox.critical(self, "Erreur Export", f"Impossible d'exporter:\n{e}")
    
    # === MÉTHODES PUBLIQUES POUR INTEGRATION ===
    
    def get_tracking_status(self) -> dict:
        """Retourne l'état actuel du tracking"""
        return {
            'is_tracking': self.is_tracking,
            'camera_ready': self.camera_ready,
            'selected_camera': self.selected_camera_alias,
            'detected_targets': len(self.detected_targets),
            'tracking_points': len(self.tracking_history),
            'detection_stats': self.detection_stats
        }
    
    def set_detection_parameters(self, params: dict):
        """Configure les paramètres de détection depuis l'extérieur"""
        try:
            if 'fps_target' in params:
                self.fps_spin.setValue(params['fps_target'])
            
            if 'confidence_threshold' in params:
                self.confidence_spin.setValue(params['confidence_threshold'])
            
            if 'detection_types' in params:
                types = params['detection_types']
                self.aruco_check.setChecked(types.get('aruco', True))
                self.reflective_check.setChecked(types.get('reflective', True))
                self.led_check.setChecked(types.get('led', False))
            
            logger.info("🔧 Paramètres de détection mis à jour")
            
        except Exception as e:
            logger.error(f"❌ Erreur configuration paramètres: {e}")
    
    def load_aruco_folder(self, folder_path: str):
        """Charge un dossier ArUco depuis l'extérieur"""
        if Path(folder_path).exists():
            self._scan_aruco_folder(folder_path)
        else:
            logger.warning(f"⚠️ Dossier ArUco introuvable: {folder_path}")
    
    # === MÉTHODES DE NETTOYAGE ===
    
    def cleanup(self):
        """Nettoie les ressources avant fermeture"""
        logger.info("🧹 Nettoyage TargetTab...")
        
        # Arrêt du tracking
        if self.is_tracking:
            self._stop_tracking()
        
        # Arrêt des timers
        if self.processing_timer.isActive():
            self.processing_timer.stop()
        
        if self.camera_check_timer.isActive():
            self.camera_check_timer.stop()
        
        # Nettoyage des données
        self.detected_targets.clear()
        self.tracking_history.clear()
        
        logger.info("✅ TargetTab nettoyé")
    
    def closeEvent(self, event):
        """Gestionnaire de fermeture"""
        self.cleanup()
        event.accept()