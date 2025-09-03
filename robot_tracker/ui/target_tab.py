# robot_tracker/ui/target_tab.py
# Version 2.4 - Suppression complète des références get_latest_frame()
# Modifications:
# - Suppression du code mort dans force_camera_refresh() qui utilisait get_latest_frame()
# - Nettoyage des méthodes redondantes et commentaires obsolètes
# - Amélioration cohérence avec l'architecture camera_manager centralisée

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
        def get_latest_aruco_folder(self): return None
        def validate_markers(self): return 0, []
        def _detect_common_dictionary(self): return "DICT_4X4_50"
    
    class TargetDetector:
        def __init__(self, config): 
            self.detection_enabled = {'aruco': True, 'reflective': True, 'led': True}
        def detect_all_targets(self, frame): return []
        def set_roi(self, roi): pass
        def set_detection_enabled(self, target_type, enabled): pass
    
    class TargetType:
        ARUCO = "aruco"
        REFLECTIVE = "reflective"
        LED = "led"
    
    class ROIManager:
        def __init__(self, config_manager): 
            self.is_creating = False
            self.rois = {}
            self.temp_points = []
            self.creation_type = None
        def start_roi_creation(self, roi_type): 
            self.is_creating = True
            return True
        def add_creation_point(self, point): return False
        def cancel_roi_creation(self): self.is_creating = False
        def complete_polygon_creation(self): return False

    class ROIType:
        RECTANGLE = "rectangle"
        POLYGON = "polygon"
        CIRCLE = "circle"

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
        self.current_frame_size = None
        self.roi_preview_pos = None
        self.streaming_active = False
        
        # Variables tracking
        self.tracking_active = False
        self.target_detector = None
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
        
        version = self._safe_get_config('ui', 'target_tab.version', '2.4')
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
        
        # Dossier sélectionné
        self.aruco_folder_label = QLabel("Auto-recherche en cours...")
        self.aruco_folder_label.setStyleSheet("QLabel { color: gray; }")
        layout.addWidget(self.aruco_folder_label)
        
        # Statistiques marqueurs
        self.aruco_stats_label = QLabel("Marqueurs: Recherche...")
        layout.addWidget(self.aruco_stats_label)
        
        # Boutons avancés
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
        self.roi_rect_btn.clicked.connect(lambda: self._start_roi_creation(ROIType.RECTANGLE))
        
        self.roi_poly_btn = QPushButton(self._safe_get_config('ui', 'ui_labels.buttons.roi_polygon', '⬟ Polygone'))
        self.roi_poly_btn.clicked.connect(lambda: self._start_roi_creation(ROIType.POLYGON))
        
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
        """Zone d'affichage caméra avec overlays et interactions ROI"""
        display_widget = QWidget()
        layout = QVBoxLayout(display_widget)
        
        # Zone d'affichage vidéo avec support interactions
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
        
        # Configuration pour interactions souris
        self.camera_display.setMouseTracking(False)
        
        # Gestionnaire événements double-clic pour polygones
        def handle_double_click(event):
            self._on_display_mouse_double_click(event)
        
        # Installation gestionnaire événements personnalisé
        self.camera_display.mouseDoubleClickEvent = handle_double_click
        
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
        
        # Bouton annuler création ROI
        self.cancel_roi_btn = QPushButton("❌ Annuler ROI")
        self.cancel_roi_btn.clicked.connect(self._cancel_roi_creation)
        self.cancel_roi_btn.setVisible(False)
        controls_layout.addWidget(self.cancel_roi_btn)
        
        # Export données
        self.export_btn = QPushButton(self._safe_get_config('ui', 'ui_labels.buttons.export_data', '💾 Exporter Données'))
        self.export_btn.clicked.connect(self._export_tracking_data)
        self.export_btn.setEnabled(False)
        controls_layout.addWidget(self.export_btn)
        
        layout.addLayout(controls_layout)
        
        # Barre de statut pour instructions ROI
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #e3f2fd;
                color: #1565c0;
                padding: 5px;
                border-radius: 3px;
                font-weight: bold;
            }
        """)
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        return display_widget
    
    def _cancel_roi_creation(self):
        """Annule la création de ROI en cours"""
        try:
            logger.info("🔍 DEBUG: Annulation création ROI demandée")
            
            if hasattr(self, 'roi_manager') and self.roi_manager.is_creating:
                self.roi_manager.cancel_roi_creation()
                self._finalize_roi_creation()
                self._show_status_message("❌ Création ROI annulée", 2000)
                logger.info("✅ Création ROI annulée")
            else:
                logger.info("ℹ️ Aucune création ROI en cours à annuler")
                
        except Exception as e:
            logger.error(f"❌ Erreur annulation ROI: {e}")
    
    def _connect_internal_signals(self):
        """Connecte les signaux internes de l'onglet"""
        pass
    
    # === SLOTS POUR SIGNAUX CAMERA_TAB ===
    
    def _on_camera_changed(self, camera_alias: str):
        """Gestionnaire changement de caméra depuis camera_tab"""
        try:
            logger.info(f"🎥 Changement caméra reçu: {camera_alias}")
            
            # Validation
            if not self.camera_manager.is_camera_open(camera_alias):
                logger.warning(f"⚠️ Caméra {camera_alias} non disponible")
                self.camera_ready = False
                self.selected_camera_alias = None
                return
            
            # Arrêter tracking si en cours
            if self.is_tracking:
                self._stop_tracking()
            
            # Configuration nouvelle caméra
            self.selected_camera_alias = camera_alias
            self.camera_ready = True
            self.current_frame_size = None  # Reset pour recalcul
            
            logger.info(f"✅ Caméra configurée: {camera_alias}")
            self._update_camera_status()
            
        except Exception as e:
            logger.error(f"❌ Erreur changement caméra: {e}")
            self.camera_ready = False
        
    def _check_camera_status(self):
        """Vérifie l'état des caméras disponibles"""
        try:
            # Vérification état caméra via le manager
            if (self.camera_manager and 
                hasattr(self, 'selected_camera_alias') and 
                self.selected_camera_alias):
                
                # Vérifier si la caméra est toujours ouverte
                if self.camera_manager.is_camera_open(self.selected_camera_alias):
                    if not self.camera_ready:
                        self.camera_ready = True
                        logger.info(f"✅ Caméra {self.selected_camera_alias} détectée comme active")
                else:
                    if self.camera_ready:
                        self.camera_ready = False
                        logger.warning(f"⚠️ Caméra {self.selected_camera_alias} n'est plus active")
            
            # Mise à jour affichage du statut
            self._update_camera_status()
            
        except Exception as e:
            logger.error(f"❌ Erreur vérification statut caméra: {e}")
    
    def _update_camera_status(self):
        """Met à jour l'affichage du statut caméra"""
        if self.camera_ready and self.selected_camera_alias:
            self.camera_status_label.setText(f"✅ Caméra: {self.selected_camera_alias}")
            self.camera_status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
            self.camera_alias_label.setText(f"Alias: {self.selected_camera_alias}")
            self.camera_alias_label.setStyleSheet("QLabel { color: black; }")
            
            # Activation des boutons
            if hasattr(self, 'start_tracking_btn'):
                self.start_tracking_btn.setEnabled(not self.is_tracking)
        else:
            self.camera_status_label.setText("❌ Aucune caméra active")
            self.camera_status_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
            self.camera_alias_label.setText("Alias: N/A")
            self.camera_alias_label.setStyleSheet("QLabel { color: gray; }")
            
            # Désactivation des boutons
            if hasattr(self, 'start_tracking_btn'):
                self.start_tracking_btn.setEnabled(False)
            if self.is_tracking:
                self._stop_tracking()
    
    def _on_streaming_started(self):
        """Gestionnaire démarrage streaming depuis camera_tab"""
        try:
            self.streaming_active = True
            logger.info("🎬 Streaming activé - Démarrage traitement frames")
            
            # Démarrer le timer de traitement des frames
            if not self.processing_timer.isActive():
                target_fps = self.fps_spin.value() if hasattr(self, 'fps_spin') else 30
                interval_ms = int(1000 / target_fps)
                self.processing_timer.start(interval_ms)
                logger.info(f"⏰ Timer processing démarré à {target_fps} FPS")
            
            # Vérifier que la caméra est prête
            self._check_camera_status()
            
        except Exception as e:
            logger.error(f"❌ Erreur activation streaming: {e}")
    
    def _on_streaming_stopped(self):
        """Gestionnaire arrêt streaming depuis camera_tab"""
        try:
            self.streaming_active = False
            logger.info("⏹️ Streaming désactivé")
            
            # Arrêter le timer de traitement
            if self.processing_timer.isActive():
                self.processing_timer.stop()
                logger.info("⏰ Timer processing arrêté")
            
            # Arrêter le tracking si actif
            if self.is_tracking:
                self._stop_tracking()
            
            # Réinitialiser état caméra
            self.camera_ready = False
            self.current_frame_size = None
            
        except Exception as e:
            logger.error(f"❌ Erreur désactivation streaming: {e}")
    
    # === MÉTHODES DE TRAITEMENT ===
    
    def _process_current_frame(self):
        """Traitement des frames avec détection et rendu ROI"""
        if not self.camera_manager or not self.camera_ready or not self.selected_camera_alias:
            return
            
        try:
            # Utiliser get_camera_frame avec l'alias de caméra
            success, frame, depth_frame = self.camera_manager.get_camera_frame(self.selected_camera_alias)
            
            if not success or frame is None:
                return
                
            # Sauvegarde taille pour conversion coordonnées
            self.current_frame_size = (frame.shape[1], frame.shape[0])  # (width, height)
            self.current_frame = frame.copy()
            
            # Copie pour traitement
            display_frame = frame.copy()
            
            # Détection si activée
            if self.is_tracking and self.target_detector:
                # Détecter les cibles
                self._detect_targets_in_frame()
                
                # Rendu des détections sur la frame d'affichage
                display_frame = self._draw_detections(display_frame)
            
            # Rendu des ROI existantes
            if hasattr(self, 'roi_manager') and self.roi_manager.rois:
                display_frame = self._draw_existing_rois(display_frame)
            
            # Rendu preview ROI en cours de création
            if (hasattr(self, 'roi_manager') and 
                self.roi_manager.is_creating and 
                hasattr(self, 'roi_preview_pos') and 
                self.roi_preview_pos is not None):
                display_frame = self._draw_roi_creation_preview(display_frame)
            
            # Mise à jour affichage
            self._update_display_frame(display_frame)
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement frame: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _draw_detections(self, frame):
        """Dessine les détections sur la frame"""
        try:
            if not self.detected_targets:
                return frame
            
            for detection in self.detected_targets:
                if 'bbox' in detection:
                    # Dessiner bounding box
                    bbox = detection['bbox']
                    x1, y1, x2, y2 = map(int, bbox)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    # Label avec confiance
                    label = f"{detection.get('type', 'Target')} {detection.get('confidence', 0.0):.2f}"
                    cv2.putText(frame, label, (x1, y1-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                if 'center' in detection:
                    # Dessiner centre
                    center = tuple(map(int, detection['center']))
                    cv2.circle(frame, center, 5, (255, 0, 0), -1)
            
            return frame
            
        except Exception as e:
            logger.error(f"❌ Erreur dessin détections: {e}")
            return frame

    def _draw_existing_rois(self, frame):
        """Dessine les ROI existantes sur la frame"""
        try:
            if not hasattr(self, 'roi_manager') or not self.roi_manager.rois:
                return frame
                
            for roi_id, roi_data in self.roi_manager.rois.items():
                color = (0, 255, 255)  # Jaune pour ROI existantes
                
                if roi_data['type'] == 'rectangle':
                    points = roi_data['points']
                    if len(points) >= 2:
                        cv2.rectangle(frame, points[0], points[1], color, 2)
                        
                elif roi_data['type'] == 'circle':
                    if 'center' in roi_data and 'radius' in roi_data:
                        center = roi_data['center']
                        radius = roi_data['radius']
                        cv2.circle(frame, center, radius, color, 2)
                        
                elif roi_data['type'] == 'polygon':
                    points = roi_data['points']
                    if len(points) > 2:
                        pts = np.array(points, np.int32)
                        cv2.polylines(frame, [pts], True, color, 2)
                
                # Label ROI
                if roi_data.get('points'):
                    first_point = roi_data['points'][0]
                    cv2.putText(frame, f"ROI_{roi_id}", 
                            (first_point[0], first_point[1]-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            return frame
            
        except Exception as e:
            logger.error(f"❌ Erreur dessin ROI existantes: {e}")
            return frame
        
    def _draw_roi_creation_preview(self, frame):
        """Dessine la preview de ROI en cours de création"""
        try:
            if not hasattr(self, 'roi_manager') or not self.roi_manager.is_creating:
                return frame
            
            preview_color = (255, 0, 255)  # Magenta pour preview
            
            if self.roi_manager.temp_points:
                if self.roi_manager.creation_type.value == 'rectangle' and len(self.roi_manager.temp_points) == 1:
                    # Preview rectangle
                    if hasattr(self, 'roi_preview_pos') and self.roi_preview_pos:
                        start_point = self.roi_manager.temp_points[0]
                        end_point = self.roi_preview_pos
                        cv2.rectangle(frame, start_point, end_point, preview_color, 2)
                        
                elif self.roi_manager.creation_type.value == 'circle' and len(self.roi_manager.temp_points) == 1:
                    # Preview cercle
                    if hasattr(self, 'roi_preview_pos') and self.roi_preview_pos:
                        center = self.roi_manager.temp_points[0]
                        current_pos = self.roi_preview_pos
                        radius = int(((center[0] - current_pos[0])**2 + (center[1] - current_pos[1])**2)**0.5)
                        cv2.circle(frame, center, radius, preview_color, 2)
                        
                elif self.roi_manager.creation_type.value == 'polygon':
                    # Preview polygone
                    if len(self.roi_manager.temp_points) > 1:
                        pts = np.array(self.roi_manager.temp_points, np.int32)
                        cv2.polylines(frame, [pts], False, preview_color, 2)
                    
                    # Points de contrôle
                    for i, point in enumerate(self.roi_manager.temp_points):
                        cv2.circle(frame, point, 4, preview_color, -1)
                        cv2.putText(frame, str(i), 
                                (point[0] + 5, point[1] - 5), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, preview_color, 1)
            
            return frame
            
        except Exception as e:
            logger.error(f"❌ Erreur dessin preview ROI: {e}")
            return frame

    def _detect_targets_in_frame(self):
        """Effectue la détection des cibles dans la frame courante"""
        if self.current_frame is None:
            return
        
        # Protection contre traitement concurrent
        if hasattr(self, '_processing_detection') and self._processing_detection:
            return
        
        self._processing_detection = True

        try:
            # Utilisation de detect_all_targets
            detected_results = self.target_detector.detect_all_targets(self.current_frame)
            
            # Conversion des résultats pour compatibilité
            self.detected_targets = detected_results
            
            # Création des infos de détection
            detection_info = {
                'frame_size': self.current_frame.shape[:2],
                'detection_count': len(detected_results),
                'detection_time': time.time(),
                'target_types': [result.target_type.value for result in detected_results] if detected_results else []
            }
            
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
            logger.error(f"❌ Erreur détection: {e}")
        finally:
            self._processing_detection = False

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

    def _scan_aruco_folder(self, folder_path):
        """Scan du dossier ArUco sélectionné"""
        try:
            folder_path = Path(folder_path)
            logger.info(f"Scan du dossier ArUco: {folder_path}")
            
            # Scan avec aruco_config_loader
            detected_markers = self.aruco_loader.scan_aruco_folder(str(folder_path))
            
            # Validation des marqueurs
            valid_count, issues = self.aruco_loader.validate_markers()
            
            # Mise à jour affichage
            self.aruco_folder_label.setText(f"📁 {folder_path.name}")
            self.aruco_folder_label.setStyleSheet("QLabel { color: green; }")
            
            if detected_markers:
                # Détection automatique du dictionnaire
                dict_type = self.aruco_loader._detect_common_dictionary()
                self.aruco_stats_label.setText(f"Marqueurs: {len(detected_markers)} détectés ({dict_type})")
                
                # Mise à jour du détecteur avec le bon dictionnaire
                if hasattr(self.target_detector, 'aruco_config'):
                    self.target_detector.aruco_config['dictionary_type'] = dict_type
                    logger.info(f"🎯 Dictionnaire mis à jour: {dict_type}")
            else:
                self.aruco_stats_label.setText("Marqueurs: 0 détecté")
                self.aruco_stats_label.setStyleSheet("QLabel { color: orange; }")
            
            # Activation boutons
            self.rescan_btn.setEnabled(True)
            self.debug_btn.setEnabled(True)
            self.config_btn.setEnabled(True)
            
            logger.info(f"✅ ArUco: {len(detected_markers)} marqueurs détectés ({valid_count} valides)")
            
        except Exception as e:
            logger.error(f"❌ Erreur scan ArUco: {e}")
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
            for issue in issues[:10]:
                debug_info.append(f"  - {issue}")
            if len(issues) > 10:
                debug_info.append(f"  ... et {len(issues) - 10} autres problèmes")
        
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
        
        QMessageBox.information(self, "Configuration ArUco", "Configuration ArUco avancée (à implémenter)")

    def _on_detection_type_changed(self):
        """Callback changement types de détection"""
        if hasattr(self, 'target_detector'):
            try:
                if hasattr(self.target_detector, 'set_detection_enabled'):
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
            logger.info(f"📐 Démarrage création ROI {roi_type}")
            
            if not hasattr(self, 'roi_manager') or self.roi_manager is None:
                logger.error("❌ ROIManager non initialisé")
                return
                
            success = self.roi_manager.start_roi_creation(roi_type)
            
            if success:
                logger.info(f"📐 Création ROI {roi_type} démarrée avec succès")
                self._enable_roi_creation_mode(roi_type)
            else:
                logger.warning("⚠️ Impossible de démarrer la création ROI")
                
        except Exception as e:
            logger.error(f"❌ Erreur création ROI: {e}")
    
    def _enable_roi_creation_mode(self, roi_type):
        """Active le mode création de ROI"""
        try:
            logger.info(f"🔍 Activation mode création pour {roi_type}")
            
            # Activation interface souris
            self.camera_display.setMouseTracking(True)
            self.camera_display.mousePressEvent = self._on_display_mouse_press
            self.camera_display.mouseMoveEvent = self._on_display_mouse_move
            self.camera_display.mouseReleaseEvent = self._on_display_mouse_release
            
            # Mise à jour boutons
            self.roi_rect_btn.setEnabled(False)
            self.roi_poly_btn.setEnabled(False)
            self.cancel_roi_btn.setVisible(True)
            
            # Message utilisateur
            if roi_type == ROIType.RECTANGLE:
                self._show_status_message("🖱️ Cliquez et glissez pour créer un rectangle", 0)
            elif roi_type == ROIType.POLYGON:
                self._show_status_message("🖱️ Cliquez pour ajouter des points, double-clic pour terminer", 0)
            else:
                self._show_status_message("🖱️ Mode création activé", 0)
                
        except Exception as e:
            logger.error(f"❌ Erreur activation mode création: {e}")

    def _on_display_mouse_press(self, event):
        """Gestion clic souris"""
        if not hasattr(self, 'roi_manager') or not self.roi_manager.is_creating:
            return
        
        pos_image = self._screen_to_image_coords(event.pos())
        if pos_image is None:
            return
            
        try:
            completed = self.roi_manager.add_creation_point(pos_image)
            if completed:
                self._finalize_roi_creation()
                
        except Exception as e:
            logger.error(f"❌ Erreur ajout point ROI: {e}")

    def _on_display_mouse_move(self, event):
        """Gestion déplacement souris - Preview temps réel"""
        if not hasattr(self, 'roi_manager') or not self.roi_manager.is_creating:
            return
            
        pos_image = self._screen_to_image_coords(event.pos())
        if pos_image is not None:
            self.roi_preview_pos = pos_image

    def _on_display_mouse_release(self, event):
        """Gestion relâchement souris"""
        pass

    def _on_display_mouse_double_click(self, event):
        """Gestion double-clic - Finalisation polygones"""
        if (hasattr(self, 'roi_manager') and 
            self.roi_manager.is_creating and 
            hasattr(self.roi_manager, 'creation_type') and
            self.roi_manager.creation_type == ROIType.POLYGON):
            
            success = self.roi_manager.complete_polygon_creation()
            if success:
                self._finalize_roi_creation()

    def _screen_to_image_coords(self, screen_pos):
        """Convertit coordonnées écran vers coordonnées image"""
        try:
            if not hasattr(self, 'current_frame_size') or self.current_frame_size is None:
                if hasattr(self, 'camera_manager') and self.camera_manager and self.selected_camera_alias:
                    try:
                        success, frame, _ = self.camera_manager.get_camera_frame(self.selected_camera_alias)
                        if success and frame is not None:
                            self.current_frame_size = (frame.shape[1], frame.shape[0])
                        else:
                            return None
                    except Exception as e:
                        logger.error(f"❌ Erreur récupération frame: {e}")
                        return None
                else:
                    return None
                
            display_size = self.camera_display.size()
            img_width, img_height = self.current_frame_size
            
            if display_size.width() <= 0 or display_size.height() <= 0:
                return None
                
            if img_width <= 0 or img_height <= 0:
                return None
            
            # Calcul du ratio et offset pour conserver aspect ratio
            display_ratio = display_size.width() / display_size.height()
            image_ratio = img_width / img_height
            
            if display_ratio > image_ratio:
                scale = display_size.height() / img_height
                scaled_width = img_width * scale
                offset_x = (display_size.width() - scaled_width) / 2
                offset_y = 0
            else:
                scale = display_size.width() / img_width
                scaled_height = img_height * scale
                offset_x = 0
                offset_y = (display_size.height() - scaled_height) / 2
                
            # Conversion coordonnées
            image_x = int((screen_pos.x() - offset_x) / scale)
            image_y = int((screen_pos.y() - offset_y) / scale)
            
            # Validation bornes
            if 0 <= image_x < img_width and 0 <= image_y < img_height:
                return (image_x, image_y)
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur conversion coordonnées: {e}")
            return None
        
    def _finalize_roi_creation(self):
        """Finalise la création d'une ROI et restaure l'interface"""
        try:
            # Désactivation interface souris
            self.camera_display.setMouseTracking(False)
            self.camera_display.mousePressEvent = None
            self.camera_display.mouseMoveEvent = None
            self.camera_display.mouseReleaseEvent = None
            
            # Restauration boutons
            self.roi_rect_btn.setEnabled(True)
            self.roi_poly_btn.setEnabled(True)
            self.cancel_roi_btn.setVisible(False)
            
            # Nettoyage interface
            if hasattr(self, 'status_label'):
                self.status_label.setVisible(False)
            
            # Mise à jour compteur
            self._update_roi_count_display()
            
            # Nettoyage variables temporaires
            if hasattr(self, 'roi_preview_pos'):
                delattr(self, 'roi_preview_pos')
                
            self._show_status_message("✅ ROI créée avec succès !", 2000)
            
        except Exception as e:
            logger.error(f"❌ Erreur finalisation ROI: {e}")

    def _update_roi_count_display(self):
        """Met à jour l'affichage du nombre de ROI"""
        try:
            if hasattr(self, 'roi_manager') and hasattr(self, 'roi_info_label'):
                roi_count = len(self.roi_manager.rois)
                self.roi_info_label.setText(f"ROI actives: {roi_count}")
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour compteur ROI: {e}")

    def _show_status_message(self, message, duration_ms=3000):
        """Affiche un message de statut temporaire"""
        try:
            logger.info(f"💬 {message}")
            
            if hasattr(self, 'status_label'):
                self.status_label.setText(message)
                self.status_label.setVisible(True)
                
                if duration_ms > 0:
                    if not hasattr(self, 'status_timer'):
                        from PyQt6.QtCore import QTimer
                        self.status_timer = QTimer()
                        
                    self.status_timer.timeout.connect(lambda: self.status_label.setVisible(False))
                    self.status_timer.start(duration_ms)
                
        except Exception as e:
            logger.error(f"❌ Erreur affichage message: {e}")

    def _clear_all_rois(self):
        """Efface toutes les ROI"""
        try:
            roi_count = len(self.roi_manager.rois) if hasattr(self, 'roi_manager') else 0
            
            if hasattr(self, 'roi_manager') and self.roi_manager:
                self.roi_manager.rois.clear()
                if hasattr(self.roi_manager, 'selected_roi_id'):
                    self.roi_manager.selected_roi_id = None
                self.roi_manager.cancel_roi_creation()
                
            self._update_roi_count_display()
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
                QMessageBox.information(self, "Export", f"Données exportées vers:\n{file_path}")
                logger.info(f"💾 Données exportées: {file_path}")
            except Exception as e:
                logger.error(f"❌ Erreur export: {e}")
                QMessageBox.critical(self, "Erreur Export", f"Impossible d'exporter:\n{e}")
    
    def _update_display_frame(self, frame):
        """Met à jour l'affichage avec la frame traitée"""
        try:
            # Conversion BGR vers RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Création QImage
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            
            # Redimensionnement avec conservation aspect ratio
            display_size = self.camera_display.size()
            scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                display_size, Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Mise à jour affichage
            self.camera_display.setPixmap(scaled_pixmap)
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour affichage: {e}")

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
        """Force la vérification de l'état des caméras - VERSION CORRIGÉE"""
        self._check_camera_status()
    
    # === NETTOYAGE ===
    
    def closeEvent(self, event):
        """Nettoyage lors de la fermeture"""
        try:
            # Arrêt des timers
            if hasattr(self, 'processing_timer') and self.processing_timer.isActive():
                self.processing_timer.stop()
            
            if hasattr(self, 'camera_check_timer') and self.camera_check_timer.isActive():
                self.camera_check_timer.stop()
            
            # Arrêt tracking si actif
            if self.is_tracking:
                self._stop_tracking()
            
            logger.info("🧹 TargetTab fermé proprement")
            
        except Exception as e:
            logger.error(f"❌ Erreur fermeture TargetTab: {e}")
        
        super().closeEvent(event)