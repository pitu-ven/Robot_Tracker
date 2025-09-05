# ui/target_tab.py
# Version 2.2 - Correction appel méthode detect_all_targets
# Modification: Utilisation de detect_all_targets au lieu de detect

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

logger = logging.getLogger(__name__)

try:
    from core.aruco_config_loader import ArUcoConfigLoader
    from core.target_detector import TargetDetector, TargetType
    from core.roi_manager import ROIManager, ROIType
    COMPONENTS_AVAILABLE = True
    logger.info("✅ Composants core importés avec succès")
except ImportError as e:
    logger.warning(f"⚠️ Import core échoué: {e}, utilisation de stubs")
    COMPONENTS_AVAILABLE = False
    
    # Stubs améliorés avec plus de méthodes
    class ArUcoConfigLoader:
        def __init__(self, config): 
            self.detected_markers = {}
            self.folder_path = None
        def scan_aruco_folder(self, folder_path): 
            self.folder_path = folder_path
            return {}
        def get_detector_params(self): return {}
        def get_latest_aruco_folder(self): return None
        def validate_markers(self): return 0, []
        def _detect_common_dictionary(self): return "4X4_50"
    
    class TargetDetector:
        def __init__(self, config): 
            self.detection_enabled = {
                'aruco': True, 'reflective': True, 'led': True
            }
            self.aruco_config = {}
        def detect_all_targets(self, frame): return []
        def set_roi(self, roi): pass
        def set_detection_enabled(self, target_type, enabled): pass
        def _init_aruco_detector(self): pass
        def update_detection_params(self, target_type, params): pass
    
    class TargetType:
        ARUCO = "aruco"
        REFLECTIVE = "reflective"
        LED = "led"
    
    class ROIManager:
        def __init__(self, config_manager): 
            self.is_creating = False
            self.rois = []
        def start_roi_creation(self, roi_type): self.is_creating = True
        def add_creation_point(self, point): return False
        def finish_roi(self): self.is_creating = False
        def get_active_rois(self): return []
        def has_active_rois(self): return False
        def draw_rois_on_frame(self, frame): return frame

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
        
        # ORDRE CORRECT :
        # 1. D'ABORD : Composants de détection
        self._init_detection_components()
        
        # 2. ENSUITE : Interface utilisateur
        self._setup_ui()
        self._connect_internal_signals()
        
        # 3. ENFIN : Auto-chargement ArUco (après que tout soit créé)
        self._auto_load_latest_aruco_folder()
        
        # Timer pour le traitement des frames
        self.processing_timer = QTimer()
        self.processing_timer.timeout.connect(self._process_current_frame)
        
        # Timer pour vérifier l'état des caméras
        self.camera_check_timer = QTimer()
        self.camera_check_timer.timeout.connect(self._check_camera_status)
        self.camera_check_timer.start(1000)  # Vérification chaque seconde
        
        version = self._safe_get_config('ui', 'target_tab.version', '2.2')
        logger.info(f"🎯 TargetTab v{version} initialisé (détection auto caméra)")
        
        # Vérification initiale de l'état des caméras
        self._check_camera_status()
        
        # Validation des composants
        validation_results = self._validate_component_methods()
        if not all(validation_results.values()):
            logger.warning("⚠️ Certains composants ne sont pas complètement fonctionnels")
            # Émission d'un signal pour informer de l'état
            self.status_changed.emit({
                'component_validation': validation_results,
                'timestamp': time.time()
            })
    
    def _init_detection_components(self):
        """Initialise les composants de détection avec validation"""
        try:
            if COMPONENTS_AVAILABLE:
                self.aruco_loader = ArUcoConfigLoader(self.config)
                self.target_detector = TargetDetector(self.config)
                self.roi_manager = ROIManager(self.config)
                logger.info("✅ Composants de détection réels initialisés")
            else:
                # Fallback avec stubs
                self.aruco_loader = ArUcoConfigLoader(self.config)
                self.target_detector = TargetDetector(self.config)
                self.roi_manager = ROIManager(self.config)
                logger.warning("⚠️ Utilisation de stubs pour composants détection")
                
            # Validation post-initialisation
            required_methods = [
                (self.aruco_loader, ['scan_aruco_folder', 'get_latest_aruco_folder']),
                (self.target_detector, ['detect_all_targets', 'set_detection_enabled']),
                (self.roi_manager, ['start_roi_creation', 'get_active_rois'])
            ]
            
            for component, methods in required_methods:
                for method in methods:
                    if not hasattr(component, method):
                        logger.warning(f"⚠️ Méthode manquante: {component.__class__.__name__}.{method}")
                        
        except Exception as e:
            logger.error(f"❌ Erreur initialisation composants: {e}")
            # Fallback complet
            self.aruco_loader = ArUcoConfigLoader(self.config)
            self.target_detector = TargetDetector(self.config)
            self.roi_manager = ROIManager(self.config)

    
    def _auto_load_latest_aruco_folder(self):
        """Charge automatiquement le dernier dossier ArUco disponible"""
        try:
            latest_folder = self.aruco_loader.get_latest_aruco_folder()
            if latest_folder:
                logger.info(f"🎯 Auto-chargement dossier ArUco: {latest_folder}")
                self._scan_aruco_folder(latest_folder)
            else:
                logger.info("ℹ️ Aucun dossier ArUco trouvé pour auto-chargement")
        except Exception as e:
            logger.warning(f"⚠️ Erreur auto-chargement ArUco: {e}")
    
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
        stats_group = self._create_statistics_group()
        layout.addWidget(stats_group)
        
        # Spacer pour pousser vers le haut
        layout.addStretch()
        
        return panel
    
    def _create_camera_status_group(self):
        """État de la caméra - Lecture seule, géré par onglet caméra"""
        group = QGroupBox(self._safe_get_config('ui', 'ui_labels.groups.camera_status', '📷 État Caméra'))
        layout = QVBoxLayout(group)
        
        # Status display
        self.camera_status_label = QLabel("❌ Aucune caméra active")
        self.camera_status_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
        layout.addWidget(self.camera_status_label)
        
        # Alias display
        self.camera_alias_label = QLabel("Alias: N/A")
        self.camera_alias_label.setStyleSheet("QLabel { color: gray; }")
        layout.addWidget(self.camera_alias_label)
        
        # Info message
        info_label = QLabel("ℹ️ Géré par l'onglet Caméra")
        info_label.setStyleSheet("QLabel { color: blue; font-style: italic; }")
        layout.addWidget(info_label)
        
        return group
    
    def _create_aruco_config_group(self):
        """Configuration ArUco avec bouton debug"""
        group = QGroupBox(self._safe_get_config('ui', 'ui_labels.groups.aruco_config', '🎯 Configuration ArUco'))
        layout = QVBoxLayout(group)
        
        # Sélection dossier
        folder_layout = QHBoxLayout()
        self.select_aruco_btn = QPushButton(self._safe_get_config('ui', 'ui_labels.buttons.select_aruco_folder', '📁 Sélectionner Dossier'))
        self.select_aruco_btn.clicked.connect(self._select_aruco_folder)
        self.rescan_btn = QPushButton(self._safe_get_config('ui', 'ui_labels.buttons.rescan_folder', '🔄'))
        self.rescan_btn.clicked.connect(self._rescan_aruco_folder)
        self.rescan_btn.setFixedWidth(40)
        self.rescan_btn.setEnabled(False)
        
        folder_layout.addWidget(self.select_aruco_btn)
        folder_layout.addWidget(self.rescan_btn)
        layout.addLayout(folder_layout)
        
        # Dossier sélectionné - TEXTE MODIFIÉ
        self.aruco_folder_label = QLabel("Auto-recherche en cours...")
        self.aruco_folder_label.setStyleSheet("QLabel { color: gray; }")
        layout.addWidget(self.aruco_folder_label)
        
        # Statistiques marqueurs - TEXTE MODIFIÉ
        self.aruco_stats_label = QLabel("Marqueurs: Recherche...")
        layout.addWidget(self.aruco_stats_label)
        
        # Boutons avancés - NOUVEAUX BOUTONS
        advanced_layout = QHBoxLayout()
        
        self.debug_btn = QPushButton("🔍 Debug")
        self.debug_btn.clicked.connect(self._show_aruco_debug_info)
        self.debug_btn.setEnabled(False)
        
        self.config_btn = QPushButton("⚙️ Config")
        self.config_btn.clicked.connect(self._show_aruco_advanced_config)
        self.config_btn.setEnabled(False)
        
        advanced_layout.addWidget(self.debug_btn)
        advanced_layout.addWidget(self.config_btn)
        layout.addLayout(advanced_layout)
        
        return group
    
    def _create_detection_types_group(self):
        """Types de détection activables"""
        group = QGroupBox(self._safe_get_config('ui', 'ui_labels.groups.detection_types', '🔍 Types de Détection'))
        layout = QVBoxLayout(group)
        
        # ArUco
        self.aruco_check = QCheckBox("ArUco Markers")
        self.aruco_check.setChecked(True)
        self.aruco_check.toggled.connect(self._on_detection_type_changed)
        layout.addWidget(self.aruco_check)
        
        # Réfléchissants
        self.reflective_check = QCheckBox("Marqueurs Réfléchissants")
        self.reflective_check.setChecked(True)
        self.reflective_check.toggled.connect(self._on_detection_type_changed)
        layout.addWidget(self.reflective_check)
        
        # LEDs
        self.led_check = QCheckBox("LEDs Colorées")
        self.led_check.setChecked(False)
        self.led_check.toggled.connect(self._on_detection_type_changed)
        layout.addWidget(self.led_check)
        
        return group
    
    def _create_roi_tools_group(self):
        """Outils de ROI"""
        group = QGroupBox(self._safe_get_config('ui', 'ui_labels.groups.roi_tools', '📐 Outils ROI'))
        layout = QVBoxLayout(group)
        
        # Boutons outils
        tools_layout = QHBoxLayout()
        
        self.roi_rect_btn = QPushButton(self._safe_get_config('ui', 'ui_labels.buttons.roi_rectangle', '⬜ Rectangle'))
        self.roi_rect_btn.clicked.connect(lambda: self._start_roi_creation('rectangle'))
        
        self.roi_poly_btn = QPushButton(self._safe_get_config('ui', 'ui_labels.buttons.roi_polygon', '⬟ Polygone'))
        self.roi_poly_btn.clicked.connect(lambda: self._start_roi_creation('polygon'))
        
        self.clear_roi_btn = QPushButton(self._safe_get_config('ui', 'ui_labels.buttons.clear_roi', '🗑️ Effacer'))
        self.clear_roi_btn.clicked.connect(self._clear_all_rois)
        
        tools_layout.addWidget(self.roi_rect_btn)
        tools_layout.addWidget(self.roi_poly_btn)
        tools_layout.addWidget(self.clear_roi_btn)
        layout.addLayout(tools_layout)
        
        # Info ROI
        self.roi_info_label = QLabel("ROI actives: 0")
        layout.addWidget(self.roi_info_label)
        
        return group
    
    def _create_tracking_controls_group(self):
        """Contrôles de tracking"""
        group = QGroupBox(self._safe_get_config('ui', 'ui_labels.groups.tracking_controls', '🎬 Contrôles Tracking'))
        layout = QVBoxLayout(group)
        
        # Boutons contrôle
        buttons_layout = QHBoxLayout()
        
        self.start_tracking_btn = QPushButton(self._safe_get_config('ui', 'ui_labels.buttons.start_tracking', '▶️ Démarrer'))
        self.start_tracking_btn.clicked.connect(self._start_tracking)
        
        self.stop_tracking_btn = QPushButton(self._safe_get_config('ui', 'ui_labels.buttons.stop_tracking', '⏹️ Arrêter'))
        self.stop_tracking_btn.clicked.connect(self._stop_tracking)
        self.stop_tracking_btn.setEnabled(False)
        
        buttons_layout.addWidget(self.start_tracking_btn)
        buttons_layout.addWidget(self.stop_tracking_btn)
        layout.addLayout(buttons_layout)
        
        # Paramètres
        params_layout = QGridLayout()
        
        # FPS cible
        params_layout.addWidget(QLabel("FPS Cible:"), 0, 0)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 120)
        self.fps_spin.setValue(30)
        self.fps_spin.setSuffix(" fps")
        params_layout.addWidget(self.fps_spin, 0, 1)
        
        # Confiance
        params_layout.addWidget(QLabel("Confiance:"), 1, 0)
        self.confidence_spin = QSpinBox()
        self.confidence_spin.setRange(0, 100)
        self.confidence_spin.setValue(80)
        self.confidence_spin.setSuffix(" %")
        params_layout.addWidget(self.confidence_spin, 1, 1)
        
        layout.addLayout(params_layout)
        
        return group
    
    def _create_statistics_group(self):
        """Statistiques de détection"""
        group = QGroupBox(self._safe_get_config('ui', 'ui_labels.groups.statistics', '📊 Statistiques'))
        layout = QVBoxLayout(group)
        
        self.stats_text = QTextEdit()
        self.stats_text.setMaximumHeight(120)
        self.stats_text.setReadOnly(True)
        self.stats_text.setText("En attente du tracking...")
        layout.addWidget(self.stats_text)
        
        return group
    
    def _create_display_area(self):
        """Zone d'affichage caméra avec overlays"""
        display_widget = QWidget()
        layout = QVBoxLayout(display_widget)
        
        # Zone d'affichage vidéo
        self.camera_display = QLabel("En attente du flux caméra...")
        self.camera_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_display.setStyleSheet("""
            QLabel {
                border: 2px dashed #ccc;
                background-color: #f0f0f0;
                color: #666;
                font-size: 16px;
            }
        """)
        self.camera_display.setMinimumSize(640, 480)
        layout.addWidget(self.camera_display)
        
        # Contrôles affichage
        controls_layout = QHBoxLayout()
        
        # Zoom
        controls_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(25, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        controls_layout.addWidget(self.zoom_slider)
        
        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(50)
        controls_layout.addWidget(self.zoom_label)
        
        controls_layout.addStretch()
        
        # Export données
        self.export_btn = QPushButton(self._safe_get_config('ui', 'ui_labels.buttons.export_data', '💾 Exporter Données'))
        self.export_btn.clicked.connect(self._export_tracking_data)
        self.export_btn.setEnabled(False)
        controls_layout.addWidget(self.export_btn)
        
        layout.addLayout(controls_layout)
        
        return display_widget
    
    def _connect_internal_signals(self):
        """Connecte les signaux internes de l'onglet"""
        # TODO: Connections internes si nécessaire
        pass
    
    # === SLOTS POUR SIGNAUX CAMERA_TAB ===
    
    def _on_camera_changed(self, camera_alias: str):
        """Slot appelé quand la caméra sélectionnée change"""
        logger.info(f"📷 Signal caméra changée reçu: {camera_alias}")
        
        # Vérifier si la caméra est bien active
        if not self.camera_manager.is_camera_open(camera_alias):
            logger.warning(f"⚠️ Caméra {camera_alias} non disponible")
            self.camera_ready = False
            self.selected_camera_alias = None
            self._update_camera_status()
            return
        
        # Arrêt du tracking si actif
        if self.is_tracking:
            self._stop_tracking()
        
        # Mise à jour caméra sélectionnée
        self.selected_camera_alias = camera_alias
        self.camera_ready = True
        self._update_camera_status()
        
        logger.info(f"✅ Caméra {camera_alias} sélectionnée pour détection")
    
    def _check_camera_status(self):
        """Vérifie automatiquement l'état des caméras actives - Version corrigée"""
        try:
            # FIX: Utilisation sécurisée de active_cameras
            if hasattr(self.camera_manager, 'active_cameras'):
                active_cameras = getattr(self.camera_manager, 'active_cameras', {})
                # Conversion en liste si c'est un dict
                if isinstance(active_cameras, dict):
                    active_camera_list = list(active_cameras.keys())
                elif isinstance(active_cameras, list):
                    active_camera_list = active_cameras
                else:
                    active_camera_list = []
            else:
                # Fallback si pas d'attribut active_cameras
                try:
                    if hasattr(self.camera_manager, 'get_active_cameras'):
                        active_camera_list = self.camera_manager.get_active_cameras()
                    else:
                        active_camera_list = []
                except:
                    active_camera_list = []

            if not active_camera_list:
                # Aucune caméra active
                if self.camera_ready:
                    logger.info("📷 Plus de caméras actives détectées")
                    if self.is_tracking:
                        self._stop_tracking()
                    self.camera_ready = False
                    self.selected_camera_alias = None
            else:
                # Au moins une caméra active
                if not self.camera_ready or self.selected_camera_alias not in active_camera_list:
                    # Auto-sélection de la première caméra disponible
                    first_camera = active_camera_list[0]
                    logger.info(f"📷 Auto-sélection caméra: {first_camera}")
                    self.selected_camera_alias = first_camera
                    self.camera_ready = True
            
            self._update_camera_status()
            
        except Exception as e:
            logger.error(f"❌ Erreur vérification caméras: {e}")
            self.camera_ready = False
            self.selected_camera_alias = None
            self._update_camera_status()
    
    def _update_camera_status(self):
        """Met à jour l'affichage du statut caméra"""
        if self.camera_ready and self.selected_camera_alias:
            self.camera_status_label.setText(f"✅ Caméra: {self.selected_camera_alias}")
            self.camera_status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
            self.camera_alias_label.setText(f"Alias: {self.selected_camera_alias}")
            self.camera_alias_label.setStyleSheet("QLabel { color: black; }")
            
            # Activation des boutons
            self.start_tracking_btn.setEnabled(not self.is_tracking)
        else:
            self.camera_status_label.setText("❌ Aucune caméra active")
            self.camera_status_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
            self.camera_alias_label.setText("Alias: N/A")
            self.camera_alias_label.setStyleSheet("QLabel { color: gray; }")
            
            # Désactivation des boutons
            self.start_tracking_btn.setEnabled(False)
            if self.is_tracking:
                self._stop_tracking()
    
    def _on_streaming_started(self):
        """Slot appelé quand le streaming démarre"""
        logger.info("🎬 Signal streaming démarré reçu")
        
        # Démarrer le traitement des frames si caméra prête
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
        """Traite la frame courante avec optimisations performance - Version améliorée"""
        if not self.camera_ready or not self.selected_camera_alias:
            return

        start_time = time.time()

        try:
            # FIX: Récupération frame avec gestion d'erreur améliorée
            if hasattr(self.camera_manager, 'get_camera_frame'):
                success, frame, depth_frame = self.camera_manager.get_camera_frame(self.selected_camera_alias)
            elif hasattr(self.camera_manager, 'get_latest_frame'):
                # Fallback si méthode différente
                result = self.camera_manager.get_latest_frame()
                if isinstance(result, tuple) and len(result) >= 2:
                    success, frame = result[0], result[1]
                    depth_frame = result[2] if len(result) > 2 else None
                else:
                    success, frame, depth_frame = False, None, None
            else:
                logger.warning("⚠️ Aucune méthode de récupération frame disponible")
                return

            if success and frame is not None:
                self.current_frame = frame.copy()
                self.current_depth_frame = depth_frame

                # Traitement de détection SEULEMENT si tracking actif
                if self.is_tracking:
                    # Skip detection si frame précédente pas encore traitée
                    if not hasattr(self, '_processing_detection') or not self._processing_detection:
                        self._detect_targets_in_frame()

                # Affichage avec overlays
                self._update_display()

                # Mesure performance réelle
                processing_time = (time.time() - start_time) * 1000  # ms
                if processing_time > 50:  # Plus de 50ms = problématique
                    logger.debug(f"⚠️ Frame lente: {processing_time:.1f}ms")

            else:
                # Vérification si caméra toujours disponible
                if hasattr(self.camera_manager, 'is_camera_open'):
                    if not self.camera_manager.is_camera_open(self.selected_camera_alias):
                        logger.warning(f"⚠️ Caméra {self.selected_camera_alias} non disponible")
                        self._check_camera_status()
                
        except Exception as e:
            logger.error(f"❌ Erreur traitement frame: {e}")
            # Force re-vérification état caméra
            self._check_camera_status()
    
    def _detect_targets_in_frame(self):
        """Effectue la détection des cibles dans la frame courante - Version améliorée"""
        if self.current_frame is None:
            return

        # Protection contre traitement concurrent
        if hasattr(self, '_processing_detection') and self._processing_detection:
            return

        self._processing_detection = True

        try:
            # AMÉLIORATION: Validation du détecteur avant utilisation
            if not hasattr(self.target_detector, 'detect_all_targets'):
                logger.warning("⚠️ Méthode detect_all_targets non disponible")
                return

            # Détection avec timeout
            import signal
            def timeout_handler(signum, frame):
                raise TimeoutError("Détection timeout")
            
            # Détection avec protection timeout (Linux/Mac uniquement)
            try:
                if hasattr(signal, 'SIGALRM'):  # Unix systems
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(1)  # 1 seconde max
                
                detected_results = self.target_detector.detect_all_targets(self.current_frame)
                
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)  # Cancel timeout
                    
            except TimeoutError:
                logger.warning("⚠️ Détection timeout, frame skippée")
                detected_results = []
            except Exception as detection_error:
                logger.error(f"❌ Erreur détection: {detection_error}")
                detected_results = []

            # Validation du résultat
            if not isinstance(detected_results, list):
                logger.warning(f"⚠️ Format retour détection invalide: {type(detected_results)}")
                detected_results = []

            # Filtrage par ROI si actives
            if hasattr(self.roi_manager, 'has_active_rois') and self.roi_manager.has_active_rois():
                filtered_detections = []
                for detection in detected_results:
                    if hasattr(detection, 'center') and hasattr(self.roi_manager, 'point_in_any_active_roi'):
                        if self.roi_manager.point_in_any_active_roi(detection.center):
                            filtered_detections.append(detection)
                detected_results = filtered_detections

            # Conversion des résultats pour compatibilité
            self.detected_targets = detected_results

            # Création des infos de détection
            detection_info = {
                'frame_size': self.current_frame.shape[:2],
                'detection_count': len(detected_results),
                'detection_time': time.time(),
                'target_types': []
            }
            
            # Extraction sécurisée des types
            for result in detected_results:
                if hasattr(result, 'target_type'):
                    if hasattr(result.target_type, 'value'):
                        detection_info['target_types'].append(result.target_type.value)
                    else:
                        detection_info['target_types'].append(str(result.target_type))

            # Mise à jour des statistiques
            self._update_detection_stats(detection_info)

            # Émission du signal pour autres onglets
            if detected_results:
                self.target_detected.emit({
                    'targets': detected_results,
                    'frame_info': detection_info,
                    'timestamp': time.time()
                })

        except Exception as e:
            logger.error(f"❌ Erreur détection globale: {e}")
        finally:
            self._processing_detection = False
    
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
            # TODO: Implémenter dessin ROI
        
        # Cibles détectées
        for target in self.detected_targets:
            try:
                center = target.center
                target_type = target.target_type
                
                if target_type == TargetType.ARUCO:
                    # === MARQUEURS ARUCO ===
                    
                    # Contour du marqueur (carré)
                    if len(target.corners) == 4:
                        corners = np.array(target.corners, dtype=np.int32)
                        cv2.polylines(frame, [corners], True, (0, 255, 0), 2)  # Vert
                    
                    # Axes 3D colorés
                    axis_length = int(target.size * 0.4)
                    rotation_rad = np.radians(target.rotation)
                    
                    # Axe X (Rouge)
                    x_end = (
                        int(center[0] + axis_length * np.cos(rotation_rad)),
                        int(center[1] + axis_length * np.sin(rotation_rad))
                    )
                    cv2.arrowedLine(frame, center, x_end, (0, 0, 255), 3, tipLength=0.3)
                    
                    # Axe Y (Vert)
                    y_end = (
                        int(center[0] - axis_length * np.sin(rotation_rad)),
                        int(center[1] + axis_length * np.cos(rotation_rad))
                    )
                    cv2.arrowedLine(frame, center, y_end, (0, 255, 0), 3, tipLength=0.3)
                    
                    # Axe Z (Bleu) - simulé
                    z_offset = int(axis_length * 0.6)
                    z_end = (center[0] - z_offset//4, center[1] - z_offset//4)
                    cv2.arrowedLine(frame, center, z_end, (255, 0, 0), 3, tipLength=0.3)
                    
                    # ID du marqueur avec fond
                    text = f"ID:{target.id}"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.7
                    thickness = 2
                    
                    # Taille du texte
                    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                    text_x = center[0] - text_size[0] // 2
                    text_y = center[1] - int(target.size * 0.6)
                    
                    # Fond blanc semi-transparent
                    overlay = frame.copy()
                    cv2.rectangle(overlay, 
                                (text_x - 8, text_y - text_size[1] - 5),
                                (text_x + text_size[0] + 8, text_y + 8),
                                (255, 255, 255), -1)
                    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
                    
                    # Texte noir
                    cv2.putText(frame, text, (text_x, text_y), 
                            font, font_scale, (0, 0, 0), thickness)
                    
                    # Cercle central
                    cv2.circle(frame, center, 4, (255, 255, 255), -1)
                    cv2.circle(frame, center, 4, (0, 0, 0), 1)
                    
                elif target_type == TargetType.REFLECTIVE:
                    # === MARQUEURS RÉFLÉCHISSANTS ===
                    
                    # Cercle principal
                    radius = int(target.size / 2)
                    cv2.circle(frame, center, radius, (0, 0, 255), 2)  # Rouge
                    
                    # Cercle interne
                    cv2.circle(frame, center, radius//2, (0, 0, 255), 1)
                    
                    # Point central
                    cv2.circle(frame, center, 3, (0, 0, 255), -1)
                    
                    # Croix de visée
                    cross_size = radius + 10
                    cv2.line(frame, 
                            (center[0] - cross_size, center[1]), 
                            (center[0] + cross_size, center[1]), 
                            (0, 0, 255), 1)
                    cv2.line(frame, 
                            (center[0], center[1] - cross_size), 
                            (center[0], center[1] + cross_size), 
                            (0, 0, 255), 1)
                    
                    # Étiquette
                    text = f"REF:{target.id}"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.5
                    cv2.putText(frame, text, 
                            (center[0] - 30, center[1] - radius - 10), 
                            font, font_scale, (0, 0, 255), 1)
                    
                elif target_type == TargetType.LED:
                    # === MARQUEURS LED ===
                    
                    # Couleur selon les données additionnelles
                    led_color = (0, 255, 255)  # Cyan par défaut
                    if target.additional_data and 'color' in target.additional_data:
                        color_name = target.additional_data['color']
                        color_map = {
                            'red': (0, 0, 255),
                            'green': (0, 255, 0), 
                            'blue': (255, 0, 0),
                            'yellow': (0, 255, 255),
                            'cyan': (255, 255, 0),
                            'magenta': (255, 0, 255)
                        }
                        led_color = color_map.get(color_name, (0, 255, 255))
                    
                    # Cercle LED avec effet de halo
                    radius = int(target.size / 2)
                    
                    # Halo externe
                    cv2.circle(frame, center, radius + 8, led_color, 1)
                    cv2.circle(frame, center, radius + 4, led_color, 1)
                    
                    # Cercle principal
                    cv2.circle(frame, center, radius, led_color, 2)
                    
                    # Centre brillant
                    cv2.circle(frame, center, 2, (255, 255, 255), -1)
                    
                    # Étiquette colorée
                    text = f"LED:{target.id}"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.5
                    
                    # Fond coloré pour l'étiquette
                    text_size = cv2.getTextSize(text, font, font_scale, 1)[0]
                    label_pos = (center[0] - text_size[0]//2, center[1] + radius + 20)
                    
                    cv2.rectangle(frame,
                                (label_pos[0] - 5, label_pos[1] - text_size[1] - 3),
                                (label_pos[0] + text_size[0] + 5, label_pos[1] + 3),
                                led_color, -1)
                    
                    cv2.putText(frame, text, label_pos,
                            font, font_scale, (0, 0, 0), 1)
            except Exception as e:
                logger.debug(f"Erreur overlay cible {target.id}: {e}")
                continue
    
    # === MÉTHODES UI CALLBACKS ===
    
    def _select_aruco_folder(self):
        """Sélection du dossier ArUco"""
        current_folder = self._safe_get_config('aruco', 'markers_folder', '.')
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Sélectionner le dossier ArUco", 
            current_folder
        )
        
        if folder:
            self._scan_aruco_folder(folder)
    
    def _debug_aruco_files(self, folder_path):
        """Debug les fichiers dans le dossier ArUco"""
        try:
            folder = Path(folder_path)
            if not folder.exists():
                logger.error(f"❌ Dossier inexistant: {folder_path}")
                return
            
            logger.info(f"🔍 CONTENU du dossier {folder.name}:")
            files = list(folder.glob("*"))
            
            for file in files[:10]:  # Limiter à 10 fichiers
                if file.is_file():
                    logger.info(f"  📄 Fichier: {file.name} ({file.suffix})")
                else:
                    logger.info(f"  📁 Dossier: {file.name}")
            
            if len(files) > 10:
                logger.info(f"  ... et {len(files) - 10} autres éléments")
                
            # Fichiers images spécifiquement
            image_files = []
            for ext in ['.png', '.jpg', '.jpeg']:
                image_files.extend(list(folder.glob(f"*{ext}")))
            
            logger.info(f"🖼️ FICHIERS IMAGES trouvés ({len(image_files)}):")
            for img_file in image_files[:10]:
                logger.info(f"  🖼️ {img_file.name}")
                
        except Exception as e:
            logger.error(f"❌ Erreur debug fichiers: {e}")

    def _scan_aruco_folder(self, folder_path):
        """Scan du dossier ArUco sélectionné - Version ultra-robuste"""
        try:
            folder_path = Path(folder_path)
            logger.info(f"🔍 Scan ArUco: {folder_path}")
            
            # Validation du dossier
            if not folder_path.exists():
                logger.error(f"❌ Dossier inexistant: {folder_path}")
                self.aruco_folder_label.setText("❌ Dossier inexistant")
                self.aruco_folder_label.setStyleSheet("QLabel { color: red; }")
                return
                
            if not folder_path.is_dir():
                logger.error(f"❌ Chemin n'est pas un dossier: {folder_path}")
                self.aruco_folder_label.setText("❌ N'est pas un dossier")
                self.aruco_folder_label.setStyleSheet("QLabel { color: red; }")
                return

            # Debug des fichiers
            self._debug_aruco_files(folder_path)
            
            # Scan avec gestion d'erreur robuste
            detected_markers = {}
            if hasattr(self.aruco_loader, 'scan_aruco_folder'):
                try:
                    detected_markers = self.aruco_loader.scan_aruco_folder(str(folder_path))
                    if not isinstance(detected_markers, dict):
                        logger.warning(f"⚠️ Format retour scan invalide: {type(detected_markers)}")
                        detected_markers = {}
                except Exception as scan_error:
                    logger.error(f"❌ Erreur scan ArUco: {scan_error}")
                    detected_markers = {}

            # Validation avec gestion d'erreur
            valid_count, issues = 0, []
            if hasattr(self.aruco_loader, 'validate_markers'):
                try:
                    valid_count, issues = self.aruco_loader.validate_markers()
                except Exception as validation_error:
                    logger.warning(f"⚠️ Erreur validation: {validation_error}")

            # Mise à jour affichage
            self.aruco_folder_label.setText(f"📁 {folder_path.name}")
            self.aruco_folder_label.setStyleSheet("QLabel { color: green; }")

            if detected_markers:
                # Détection automatique du dictionnaire avec fallback
                dict_type = "4X4_50"  # Valeur par défaut
                if hasattr(self.aruco_loader, '_detect_common_dictionary'):
                    try:
                        dict_type = self.aruco_loader._detect_common_dictionary()
                    except:
                        logger.warning("⚠️ Détection dictionnaire échouée, utilisation 4X4_50")
                
                self.aruco_stats_label.setText(f"Marqueurs: {len(detected_markers)} détectés ({dict_type})")
                
                # Mise à jour du détecteur avec validation
                if (hasattr(self.target_detector, 'aruco_config') and 
                    hasattr(self.target_detector, '_init_aruco_detector')):
                    try:
                        self.target_detector.aruco_config['dictionary_type'] = dict_type
                        logger.info(f"🎯 Dictionnaire mis à jour: {dict_type}")
                        self.target_detector._init_aruco_detector()
                    except Exception as detector_error:
                        logger.warning(f"⚠️ Erreur mise à jour détecteur: {detector_error}")
            else:
                self.aruco_stats_label.setText("Marqueurs: 0 détecté")
                self.aruco_stats_label.setStyleSheet("QLabel { color: orange; }")

            # Affichage des problèmes de validation
            if issues:
                logger.warning(f"⚠️ Problèmes détectés: {'; '.join(issues[:3])}")
                if len(issues) > 3:
                    logger.warning(f"... et {len(issues) - 3} autres problèmes")

            # Activation boutons
            self.rescan_btn.setEnabled(True)
            self.debug_btn.setEnabled(True)
            self.config_btn.setEnabled(True)

            logger.info(f"✅ ArUco: {len(detected_markers)} marqueurs détectés ({valid_count} valides)")

        except Exception as e:
            logger.error(f"❌ Erreur scan ArUco global: {e}")
            self.aruco_folder_label.setText("❌ Erreur de scan")
            self.aruco_folder_label.setStyleSheet("QLabel { color: red; }")
            self.aruco_stats_label.setText("Marqueurs: Erreur")
    
    def _rescan_aruco_folder(self):
        """Re-scan du dossier ArUco"""
        try:
            if hasattr(self.aruco_loader, 'folder_path') and self.aruco_loader.folder_path:
                folder_path = str(self.aruco_loader.folder_path)
                logger.info(f"🔄 Re-scan ArUco: {folder_path}")
                self._scan_aruco_folder(folder_path)
            else:
                logger.warning("⚠️ Aucun dossier ArUco à rescanner")
                QMessageBox.information(self, "Re-scan", "Aucun dossier ArUco sélectionné à rescanner")
        except Exception as e:
            logger.error(f"❌ Erreur re-scan ArUco: {e}")
            QMessageBox.warning(self, "Erreur", f"Erreur lors du re-scan:\n{e}")
    
    def _auto_load_latest_aruco_folder(self):
        """Charge automatiquement le dernier dossier ArUco disponible"""
        try:
            # Vérifier que l'UI est créée
            if not hasattr(self, 'aruco_folder_label'):
                logger.warning("⚠️ UI pas encore créée, auto-chargement reporté")
                return
                
            latest_folder = self.aruco_loader.get_latest_aruco_folder()
            if latest_folder:
                logger.info(f"🎯 Auto-chargement dossier ArUco: {latest_folder}")
                self._scan_aruco_folder(latest_folder)
            else:
                logger.info("ℹ️ Aucun dossier ArUco trouvé pour auto-chargement")
                # Mise à jour de l'interface même si pas de dossier trouvé
                if hasattr(self, 'aruco_folder_label'):
                    self.aruco_folder_label.setText("❌ Aucun dossier ArUco trouvé")
                    self.aruco_folder_label.setStyleSheet("QLabel { color: orange; }")
                    
        except Exception as e:
            logger.warning(f"⚠️ Erreur auto-chargement ArUco: {e}")
            if hasattr(self, 'aruco_folder_label'):
                self.aruco_folder_label.setText("❌ Erreur auto-chargement")
                self.aruco_folder_label.setStyleSheet("QLabel { color: red; }")

    def _show_aruco_debug_info(self):
        """Affiche les informations de débogage ArUco"""
        if not hasattr(self.aruco_loader, 'detected_markers') or not self.aruco_loader.detected_markers:
            QMessageBox.information(self, "Debug ArUco", "Aucun marqueur détecté à analyser")
            return
        
        debug_info = []
        debug_info.append("=== INFORMATIONS DEBUG ARUCO ===\n")
        
        # Informations générales
        debug_info.append(f"Dossier: {self.aruco_loader.folder_path}")
        debug_info.append(f"Marqueurs détectés: {len(self.aruco_loader.detected_markers)}")
        debug_info.append(f"Dictionnaire détecté: {self.aruco_loader._detect_common_dictionary()}\n")
        
        # Validation
        valid_count, issues = self.aruco_loader.validate_markers()
        debug_info.append(f"Marqueurs valides: {valid_count}")
        if issues:
            debug_info.append("Problèmes détectés:")
            for issue in issues[:10]:  # Limiter à 10 problèmes
                debug_info.append(f"  - {issue}")
            if len(issues) > 10:
                debug_info.append(f"  ... et {len(issues) - 10} autres problèmes")
        debug_info.append("")
        
        # Détails des marqueurs (premiers 10)
        debug_info.append("=== DÉTAILS MARQUEURS ===")
        markers_list = list(self.aruco_loader.detected_markers.items())[:10]
        for marker_id, marker_info in markers_list:
            debug_info.append(f"ID {marker_id}:")
            debug_info.append(f"  Fichier: {marker_info.get('filename', 'N/A')}")
            debug_info.append(f"  Taille: {marker_info.get('size_mm', 'N/A')}mm")
            debug_info.append(f"  Dictionnaire: {marker_info.get('dictionary', 'N/A')}")
            debug_info.append(f"  Pattern utilisé: {marker_info.get('pattern_used', 'N/A')}")
        
        if len(self.aruco_loader.detected_markers) > 10:
            debug_info.append(f"... et {len(self.aruco_loader.detected_markers) - 10} autres marqueurs")
        
        # Configuration du détecteur
        debug_info.append("\n=== CONFIGURATION DÉTECTEUR ===")
        if hasattr(self.target_detector, 'aruco_config'):
            config = self.target_detector.aruco_config
            debug_info.append(f"API utilisée: {'Moderne' if getattr(self.target_detector, 'use_modern_api', False) else 'Classique'}")
            debug_info.append(f"Dictionnaire config: {config.get('dictionary_type', 'N/A')}")
            debug_info.append(f"ArUco activé: {self.target_detector.detection_enabled.get(TargetType.ARUCO, False)}")
        
        # Affichage dans une fenêtre de dialogue
        msg = QMessageBox(self)
        msg.setWindowTitle("Debug ArUco")
        msg.setText("Informations de débogage ArUco:")
        msg.setDetailedText('\n'.join(debug_info))
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def _show_aruco_advanced_config(self):
        """Affiche la configuration avancée ArUco"""
        if not hasattr(self.target_detector, 'aruco_config'):
            QMessageBox.information(self, "Configuration", "Détecteur ArUco non initialisé")
            return
        
        # Récupération de la configuration actuelle
        config = self.target_detector.aruco_config.copy()
        detection_params = config.get('detection_params', {})
        
        # Création d'une fenêtre de dialogue simple pour les paramètres principaux
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDoubleSpinBox, QSpinBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Configuration ArUco Avancée")
        dialog.setModal(True)
        
        layout = QFormLayout(dialog)
        
        # Paramètres principaux
        min_perimeter = QDoubleSpinBox()
        min_perimeter.setRange(0.001, 1.0)
        min_perimeter.setValue(detection_params.get('minMarkerPerimeterRate', 0.03))
        min_perimeter.setSingleStep(0.01)
        min_perimeter.setDecimals(3)
        layout.addRow("Min Perimeter Rate:", min_perimeter)
        
        max_perimeter = QDoubleSpinBox()
        max_perimeter.setRange(1.0, 10.0)
        max_perimeter.setValue(detection_params.get('maxMarkerPerimeterRate', 4.0))
        max_perimeter.setSingleStep(0.5)
        max_perimeter.setDecimals(1)
        layout.addRow("Max Perimeter Rate:", max_perimeter)
        
        win_size_min = QSpinBox()
        win_size_min.setRange(3, 50)
        win_size_min.setValue(detection_params.get('adaptiveThreshWinSizeMin', 3))
        layout.addRow("Window Size Min:", win_size_min)
        
        win_size_max = QSpinBox()
        win_size_max.setRange(10, 100)
        win_size_max.setValue(detection_params.get('adaptiveThreshWinSizeMax', 23))
        layout.addRow("Window Size Max:", win_size_max)
        
        # Boutons
        from PyQt6.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Mise à jour des paramètres
            new_params = {
                'minMarkerPerimeterRate': min_perimeter.value(),
                'maxMarkerPerimeterRate': max_perimeter.value(),
                'adaptiveThreshWinSizeMin': win_size_min.value(),
                'adaptiveThreshWinSizeMax': win_size_max.value()
            }
            
            # Mise à jour dans le détecteur
            if hasattr(self.target_detector, 'update_detection_params'):
                self.target_detector.update_detection_params(TargetType.ARUCO, new_params)
                logger.info("✅ Paramètres ArUco mis à jour")
                QMessageBox.information(self, "Configuration", "Paramètres ArUco mis à jour avec succès!")
            else:
                logger.warning("⚠️ Impossible de mettre à jour les paramètres")
        
        dialog.deleteLater()

    def _on_detection_type_changed(self):
        """Callback changement types de détection"""
        if hasattr(self, 'target_detector'):
            # Mise à jour des types de détection activés
            try:
                if hasattr(self.target_detector, 'set_detection_enabled'):
                    from core.target_detector import TargetType
                    self.target_detector.set_detection_enabled(TargetType.ARUCO, self.aruco_check.isChecked())
                    self.target_detector.set_detection_enabled(TargetType.REFLECTIVE, self.reflective_check.isChecked())
                    self.target_detector.set_detection_enabled(TargetType.LED, self.led_check.isChecked())
                
                logger.info(f"🔍 Types détection: ArUco={self.aruco_check.isChecked()}, "
                          f"Réfléchissant={self.reflective_check.isChecked()}, "
                          f"LED={self.led_check.isChecked()}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur mise à jour détection: {e}")
    
    def _start_roi_creation(self, roi_type):
        """Démarre la création d'une ROI"""
        try:
            # Conversion string → ROIType enum
            from core.roi_manager import ROIType
            
            if roi_type == 'rectangle':
                roi_enum = ROIType.RECTANGLE
            elif roi_type == 'polygon':
                roi_enum = ROIType.POLYGON
            else:
                logger.warning(f"Type ROI non supporté: {roi_type}")
                return
            
            self.roi_manager.start_roi_creation(roi_enum)
            logger.info(f"📐 Création ROI {roi_type} démarrée")
            # TODO: Activer mode interactif sur l'affichage
            
        except Exception as e:
            logger.error(f"❌ Erreur création ROI: {e}")
    
    def _clear_all_rois(self):
        """Efface toutes les ROI"""
        try:
            roi_count = len(self.roi_manager.rois)
            self.roi_manager.rois.clear()
            self.roi_info_label.setText("ROI actives: 0")
            logger.info(f"🗑️ {roi_count} ROI effacées")
        except Exception as e:
            logger.error(f"❌ Erreur effacement ROI: {e}")
    
    def _start_tracking(self):
        """Démarre le tracking"""
        if not self.camera_ready:
            QMessageBox.warning(self, "Tracking", "Aucune caméra active disponible")
            return
        
        try:
            self.is_tracking = True
            
            # Mise à jour UI
            self.start_tracking_btn.setEnabled(False)
            self.stop_tracking_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            
            # Reset des données
            self.detected_targets = []
            self.tracking_history = []
            self.detection_stats = {
                'total_detections': 0,
                'fps': 0.0,
                'last_detection_time': 0.0
            }
            
            # Émission signal
            self.tracking_started.emit()
            
            logger.info("▶️ Tracking démarré")
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage tracking: {e}")
            self._stop_tracking()
    
    def _stop_tracking(self):
        """Arrête le tracking"""
        try:
            self.is_tracking = False
            
            # Mise à jour UI
            self.start_tracking_btn.setEnabled(self.camera_ready)
            self.stop_tracking_btn.setEnabled(False)
            
            # Émission signal
            self.tracking_stopped.emit()
            
            logger.info("⏹️ Tracking arrêté")
            
        except Exception as e:
            logger.error(f"❌ Erreur arrêt tracking: {e}")
    
    def _on_zoom_changed(self, value):
        """Callback changement zoom"""
        self.zoom_label.setText(f"{value}%")
        # Le redimensionnement se fait dans _update_display()
    
    def _update_detection_stats(self, detection_info):
        """Met à jour les statistiques de détection"""
        try:
            self.detection_stats['total_detections'] += detection_info.get('detection_count', 0)
            current_time = time.time()
            
            # Calcul FPS
            if self.detection_stats['last_detection_time'] > 0:
                time_diff = current_time - self.detection_stats['last_detection_time']
                if time_diff > 0:
                    instant_fps = 1.0 / time_diff
                    # Moyenne mobile
                    alpha = 0.1
                    self.detection_stats['fps'] = (
                        alpha * instant_fps + (1 - alpha) * self.detection_stats['fps']
                    )
            
            self.detection_stats['last_detection_time'] = current_time
            
            # Mise à jour affichage
            stats_text = f"""Détections totales: {self.detection_stats['total_detections']}
FPS de détection: {self.detection_stats['fps']:.1f}
Dernière détection: {detection_info.get('detection_count', 0)} cibles
Types détectés: {', '.join(detection_info.get('target_types', []))}"""
            
            self.stats_text.setText(stats_text)
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour stats: {e}")
    
    def _export_tracking_data(self):
        """Exporte les données de tracking"""
        if not self.tracking_history:
            QMessageBox.information(self, "Export", "Aucune donnée de tracking à exporter")
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
    
    def force_camera_refresh(self):
        """Force la vérification de l'état des caméras"""
        self._check_camera_status()

    def _validate_component_methods(self):
        """Valide que tous les composants ont les méthodes requises"""
        validation_results = {
            'aruco_loader': True,
            'target_detector': True, 
            'roi_manager': True
        }
        
        # Validation ArUcoConfigLoader
        required_aruco_methods = [
            'scan_aruco_folder', 'get_latest_aruco_folder', 
            'get_detector_params', 'validate_markers'
        ]
        for method in required_aruco_methods:
            if not hasattr(self.aruco_loader, method):
                logger.warning(f"⚠️ ArUcoConfigLoader.{method} manquant")
                validation_results['aruco_loader'] = False
        
        # Validation TargetDetector
        required_detector_methods = [
            'detect_all_targets', 'set_detection_enabled', 
            'set_roi', '_init_aruco_detector'
        ]
        for method in required_detector_methods:
            if not hasattr(self.target_detector, method):
                logger.warning(f"⚠️ TargetDetector.{method} manquant")
                validation_results['target_detector'] = False
        
        # Validation ROIManager
        required_roi_methods = [
            'start_roi_creation', 'get_active_rois', 
            'has_active_rois', 'draw_rois_on_frame'
        ]
        for method in required_roi_methods:
            if not hasattr(self.roi_manager, method):
                logger.warning(f"⚠️ ROIManager.{method} manquant")
                validation_results['roi_manager'] = False
        
        return validation_results
    
    # === NETTOYAGE ===
    
    def closeEvent(self, event):
        """Nettoyage lors de la fermeture"""
        try:
            # Arrêt des timers
            if self.processing_timer.isActive():
                self.processing_timer.stop()
            
            if self.camera_check_timer.isActive():
                self.camera_check_timer.stop()
            
            # Arrêt tracking si actif
            if self.is_tracking:
                self._stop_tracking()
            
            logger.info("🧹 TargetTab fermé proprement")
            
        except Exception as e:
            logger.error(f"❌ Erreur fermeture TargetTab: {e}")
        
        super().closeEvent(event)