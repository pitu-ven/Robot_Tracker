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
        def detect_all_targets(self, frame): return []  # Correction ici
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
        # MODIFICATION ICI : Passer ROIType.RECTANGLE au lieu de 'rectangle'
        self.roi_rect_btn.clicked.connect(lambda: self._start_roi_creation(ROIType.RECTANGLE))
        
        self.roi_poly_btn = QPushButton(self._safe_get_config('ui', 'ui_labels.buttons.roi_polygon', '⬟ Polygone'))
        # MODIFICATION ICI : Passer ROIType.POLYGON au lieu de 'polygon'
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
        
        # NOUVEAU: Configuration pour interactions souris
        self.camera_display.setMouseTracking(False)  # Activé seulement lors création ROI
        self.current_frame_size = None  # Pour conversion coordonnées
        self.roi_preview_pos = None     # Position preview souris
        
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
        
        # NOUVEAU: Bouton annuler création ROI
        self.cancel_roi_btn = QPushButton("❌ Annuler ROI")
        self.cancel_roi_btn.clicked.connect(self._cancel_roi_creation)
        self.cancel_roi_btn.setVisible(False)  # Visible seulement pendant création
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
        """Vérifie automatiquement l'état des caméras actives"""
        try:
            # Utilisation de la propriété active_cameras au lieu de get_active_cameras()
            active_cameras = self.camera_manager.active_cameras
            
            if not active_cameras:
                # Aucune caméra active
                if self.camera_ready:
                    logger.info("📷 Plus de caméras actives détectées")
                    if self.is_tracking:
                        self._stop_tracking()
                    self.camera_ready = False
                    self.selected_camera_alias = None
            else:
                # Au moins une caméra active
                if not self.camera_ready or self.selected_camera_alias not in active_cameras:
                    # Auto-sélection de la première caméra disponible
                    first_camera = active_cameras[0]
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
        """Traite la frame courante avec optimisations performance"""
        if not self.camera_ready or not self.selected_camera_alias:
            return
        
        start_time = time.time()
        
        try:
            # Récupération frame avec timeout
            success, frame, depth_frame = self.camera_manager.get_camera_frame(self.selected_camera_alias)
            
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
                if processing_time > 33:  # Plus de 33ms
                    logger.debug(f"⚠️ Frame lente: {processing_time:.1f}ms")
                    
            else:
                if not self.camera_manager.is_camera_open(self.selected_camera_alias):
                    logger.warning(f"⚠️ Caméra {self.selected_camera_alias} non disponible")
                    self._check_camera_status()
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement frame: {e}")
            self._check_camera_status()
    
    def _detect_targets_in_frame(self):
        """Effectue la détection des cibles dans la frame courante"""
        if self.current_frame is None:
            return
        
        # Protection contre traitement concurrent
        if hasattr(self, '_processing_detection') and self._processing_detection:
            return
        
        self._processing_detection = True

        try:
            # CORRECTION: Utilisation de detect_all_targets au lieu de detect
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
        """Scan du dossier ArUco sélectionné - Version améliorée"""
        try:
            folder_path = Path(folder_path)
            logger.info(f"Scan du dossier ArUco: {folder_path}")
            self._debug_aruco_files(folder_path)
            # Scan avec aruco_config_loader amélioré
            detected_markers = self.aruco_loader.scan_aruco_folder(str(folder_path))
            
            # Validation des marqueurs - NOUVELLE LIGNE
            valid_count, issues = self.aruco_loader.validate_markers()
            
            # Mise à jour affichage
            self.aruco_folder_label.setText(f"📁 {folder_path.name}")
            self.aruco_folder_label.setStyleSheet("QLabel { color: green; }")
            
            if detected_markers:
                # NOUVELLE SECTION: Détection automatique du dictionnaire
                dict_type = self.aruco_loader._detect_common_dictionary()
                self.aruco_stats_label.setText(f"Marqueurs: {len(detected_markers)} détectés ({dict_type})")
                
                # NOUVELLE SECTION: Mise à jour du détecteur avec le bon dictionnaire
                if hasattr(self.target_detector, 'aruco_config'):
                    self.target_detector.aruco_config['dictionary_type'] = dict_type
                    logger.info(f"🎯 Dictionnaire mis à jour: {dict_type}")
                    # Réinitialiser le détecteur ArUco avec le bon dictionnaire
                    self.target_detector._init_aruco_detector()
            else:
                self.aruco_stats_label.setText("Marqueurs: 0 détecté")
                self.aruco_stats_label.setStyleSheet("QLabel { color: orange; }")
            
            # NOUVELLE SECTION: Affichage des problèmes de validation
            if issues:
                logger.warning(f"⚠️ Problèmes détectés: {'; '.join(issues[:3])}")
                if len(issues) > 3:
                    logger.warning(f"... et {len(issues) - 3} autres problèmes")
            
            # Activation boutons - LIGNE MODIFIÉE
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
        """Démarre la création d'une ROI - Support universel ROIType/string"""
        try:
            from core.roi_manager import ROIType
            
            # === DÉTECTION AUTOMATIQUE DU TYPE ===
            if isinstance(roi_type, ROIType):
                # Cas 1: Objet ROIType reçu directement (depuis lambda avec ROIType.RECTANGLE)
                logger.info(f"🔍 DEBUG: ROIType enum reçu directement: {roi_type}")
                roi_type_enum = roi_type
                roi_type_str = roi_type.value  # 'rectangle', 'polygon', etc.
                
            elif isinstance(roi_type, str):
                # Cas 2: String reçue (depuis lambda avec 'rectangle')
                logger.info(f"🔍 DEBUG: String reçue: '{roi_type}'")
                roi_type_mapping = {
                    'rectangle': ROIType.RECTANGLE,
                    'polygon': ROIType.POLYGON,
                    'circle': ROIType.CIRCLE
                }
                roi_type_enum = roi_type_mapping.get(roi_type.lower())
                roi_type_str = roi_type
                
                if roi_type_enum is None:
                    logger.error(f"❌ Type ROI string invalide: '{roi_type}' - Types supportés: {list(roi_type_mapping.keys())}")
                    return
                    
            else:
                # Cas 3: Type non supporté
                logger.error(f"❌ Type paramètre invalide: {type(roi_type)} (valeur: {roi_type})")
                return
            
            logger.info(f"🔍 DEBUG: ROI à créer: {roi_type_enum} (nom: '{roi_type_str}')")
            
            # === VÉRIFICATIONS PRÉALABLES ===
            if not hasattr(self, 'roi_manager') or self.roi_manager is None:
                logger.error("❌ ROIManager non initialisé")
                return
                
            # === DÉMARRAGE CRÉATION ===
            success = self.roi_manager.start_roi_creation(roi_type_enum)
            logger.info(f"🔍 DEBUG: start_roi_creation retourné: {success}")
            
            if success:
                logger.info(f"📐 Création ROI {roi_type_str} démarrée avec succès")
                
                # Activer interface création
                self._enable_roi_creation_mode(roi_type_enum)
                
            else:
                logger.warning("⚠️ Impossible de démarrer la création ROI")
                
        except ImportError as e:
            logger.error(f"❌ Erreur import ROIType: {e}")
        except Exception as e:
            logger.error(f"❌ Erreur création ROI: {e}")
            import traceback
            logger.error(f"Traceback complet: {traceback.format_exc()}")
    
    def _enable_roi_creation_mode(self, roi_type_enum):
        """Active le mode création de ROI avec l'enum"""
        try:
            from core.roi_manager import ROIType
            
            logger.info(f"🔍 DEBUG: Activation mode création pour {roi_type_enum}")
            
            # === VÉRIFICATIONS INTERFACE ===
            if not hasattr(self, 'camera_display') or self.camera_display is None:
                logger.error("❌ camera_display non initialisé")
                return
                
            # === ACTIVATION INTERFACE SOURIS ===
            self.camera_display.setMouseTracking(True)
            self.camera_display.mousePressEvent = self._on_display_mouse_press
            self.camera_display.mouseMoveEvent = self._on_display_mouse_move
            self.camera_display.mouseReleaseEvent = self._on_display_mouse_release
            logger.info("🔍 DEBUG: Événements souris installés")
            
            # === MISE À JOUR BOUTONS ===
            if hasattr(self, 'roi_rect_btn'):
                self.roi_rect_btn.setEnabled(False)
            if hasattr(self, 'roi_poly_btn'):
                self.roi_poly_btn.setEnabled(False)
            if hasattr(self, 'cancel_roi_btn'):
                self.cancel_roi_btn.setVisible(True)
            logger.info("🔍 DEBUG: Interface boutons mise à jour")
            
            # === MESSAGE UTILISATEUR SELON TYPE ===
            if roi_type_enum == ROIType.RECTANGLE:
                self._show_status_message("🖱️ Cliquez et glissez pour créer un rectangle", 0)
            elif roi_type_enum == ROIType.POLYGON:
                self._show_status_message("🖱️ Cliquez pour ajouter des points, double-clic pour terminer", 0)
            elif roi_type_enum == ROIType.CIRCLE:
                self._show_status_message("🖱️ Cliquez le centre puis un point du cercle", 0)
            else:
                self._show_status_message("🖱️ Mode création activé", 0)
                
            logger.info("✅ Mode création ROI activé avec succès")
            
        except Exception as e:
            logger.error(f"❌ Erreur activation mode création: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    # === GESTION ÉVÉNEMENTS SOURIS ===
    def _on_display_mouse_press(self, event):
        """Gestion clic souris sur l'affichage - Version détaillée"""
        pos_screen = (event.pos().x(), event.pos().y())
        logger.info(f"🔍 DEBUG: Clic souris détecté à {pos_screen}")
        
        if not hasattr(self, 'roi_manager') or not self.roi_manager.is_creating:
            logger.warning("⚠️ ROI Manager non en mode création")
            return
            
        # Conversion coordonnées écran vers image
        pos_image = self._screen_to_image_coords(event.pos())
        logger.info(f"🔍 DEBUG: Coordonnées converties: {pos_screen} -> {pos_image}")
        
        if pos_image is None:
            logger.warning("⚠️ Impossible de convertir coordonnées souris")
            return
            
        try:
            # Ajouter point à la ROI en cours
            completed = self.roi_manager.add_creation_point(pos_image)
            logger.info(f"🔍 DEBUG: Point ajouté, ROI terminée: {completed}")
            
            if completed:
                # ROI terminée (rectangle ou cercle)
                logger.info("✅ ROI complétée - Finalisation")
                self._finalize_roi_creation()
            else:
                # Continuer création (polygone ou première étape rectangle/cercle)
                logger.info("➡️ Création ROI en cours - Attente point suivant")
                self._update_roi_display()
                
        except Exception as e:
            logger.error(f"❌ Erreur ajout point ROI: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _on_display_mouse_move(self, event):
        """Gestion déplacement souris - Preview temps réel"""
        if not hasattr(self, 'roi_manager') or not self.roi_manager.is_creating:
            return
            
        # Mise à jour preview en temps réel
        pos_image = self._screen_to_image_coords(event.pos())
        if pos_image is not None:
            # Stocker position pour le rendu preview
            self.roi_preview_pos = pos_image
            # Le rendu sera fait automatiquement via _process_frame()

    def _on_display_mouse_release(self, event):
        """Gestion relâchement souris sur l'affichage"""
        # Pour rectangles, le relâchement pourrait compléter la création
        logger.info("🔍 DEBUG: Relâchement souris détecté")

    def _on_display_mouse_double_click(self, event):
        """Gestion double-clic - Finalisation polygones"""
        logger.info("🔍 DEBUG: Double-clic détecté")
        
        if (hasattr(self, 'roi_manager') and 
            self.roi_manager.is_creating and 
            self.roi_manager.creation_type == ROIType.POLYGON):
            
            logger.info("📐 Finalisation polygone via double-clic")
            success = self.roi_manager.complete_polygon_creation()
            if success:
                self._finalize_roi_creation()
                logger.info("✅ Polygone créé avec succès")
            else:
                logger.warning("⚠️ Impossible de finaliser le polygone")

    def _screen_to_image_coords(self, screen_pos):
        """Convertit coordonnées écran vers coordonnées image"""
        try:
            # Vérifier que nous avons une taille d'image
            if not hasattr(self, 'current_frame_size') or self.current_frame_size is None:
                logger.warning("⚠️ Taille frame non disponible pour conversion coordonnées")
                return None
                
            # Récupérer tailles
            display_size = self.camera_display.size()
            img_width, img_height = self.current_frame_size
            
            logger.info(f"🔍 DEBUG: Conversion coords - Display: {display_size.width()}x{display_size.height()}, "
                    f"Image: {img_width}x{img_height}, Click: {screen_pos.x()},{screen_pos.y()}")
            
            # Calcul du ratio et offset pour conserver aspect ratio
            display_ratio = display_size.width() / display_size.height()
            image_ratio = img_width / img_height
            
            if display_ratio > image_ratio:
                # Barres noires horizontales
                scale = display_size.height() / img_height
                scaled_width = img_width * scale
                offset_x = (display_size.width() - scaled_width) / 2
                offset_y = 0
            else:
                # Barres noires verticales
                scale = display_size.width() / img_width
                scaled_height = img_height * scale
                offset_x = 0
                offset_y = (display_size.height() - scaled_height) / 2
                
            # Conversion coordonnées
            image_x = int((screen_pos.x() - offset_x) / scale)
            image_y = int((screen_pos.y() - offset_y) / scale)
            
            logger.info(f"🔍 DEBUG: Coordonnées finales: ({image_x}, {image_y})")
            
            # Vérification limites
            if 0 <= image_x < img_width and 0 <= image_y < img_height:
                return (image_x, image_y)
            else:
                logger.warning(f"⚠️ Coordonnées hors limites: ({image_x}, {image_y})")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur conversion coordonnées: {e}")
            return None
        
    def _finalize_roi_creation(self):
        """Finalise la création d'une ROI et restaure l'interface"""
        try:
            logger.info("🔍 DEBUG: Début finalisation création ROI")
            
            # === DÉSACTIVATION INTERFACE SOURIS ===
            if hasattr(self, 'camera_display'):
                self.camera_display.setMouseTracking(False)
                self.camera_display.mousePressEvent = None
                self.camera_display.mouseMoveEvent = None
                self.camera_display.mouseReleaseEvent = None
                logger.info("🔍 DEBUG: Événements souris désinstallés")
            
            # === RESTAURATION BOUTONS ===
            if hasattr(self, 'roi_rect_btn'):
                self.roi_rect_btn.setEnabled(True)
            if hasattr(self, 'roi_poly_btn'):
                self.roi_poly_btn.setEnabled(True)
            if hasattr(self, 'cancel_roi_btn'):
                self.cancel_roi_btn.setVisible(False)
            logger.info("🔍 DEBUG: Interface boutons restaurée")
            
            # === NETTOYAGE INTERFACE ===
            if hasattr(self, 'status_label'):
                self.status_label.setVisible(False)
            
            # === MISE À JOUR COMPTEUR ===
            self._update_roi_count_display()
            
            # === NETTOYAGE VARIABLES TEMPORAIRES ===
            if hasattr(self, 'roi_preview_pos'):
                delattr(self, 'roi_preview_pos')
                
            logger.info("✅ Finalisation ROI terminée avec succès")
            self._show_status_message("✅ ROI créée avec succès !", 2000)
            
        except Exception as e:
            logger.error(f"❌ Erreur finalisation ROI: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _update_roi_count_display(self):
        """Met à jour l'affichage du nombre de ROI"""
        try:
            if hasattr(self, 'roi_manager') and hasattr(self, 'roi_info_label'):
                roi_count = len(self.roi_manager.rois)
                self.roi_info_label.setText(f"ROI actives: {roi_count}")
                logger.info(f"🔍 DEBUG: Compteur ROI mis à jour: {roi_count}")
            else:
                logger.warning("⚠️ Impossible de mettre à jour compteur ROI (attributs manquants)")
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour compteur ROI: {e}")

    def _update_roi_display(self):
        """Met à jour l'affichage avec les ROI"""
        # Cette méthode sera appelée automatiquement lors du rendu des frames
        # via _process_frame() -> roi_manager.draw_rois()
        pass

    def _show_status_message(self, message, duration_ms=3000):
        """Affiche un message de statut temporaire"""
        try:
            logger.info(f"💬 {message}")
            
            # Affichage dans barre de statut si elle existe
            if hasattr(self, 'status_label'):
                self.status_label.setText(message)
                self.status_label.setVisible(True)
                
                # Timer pour masquer automatiquement si durée > 0
                if duration_ms > 0:
                    if not hasattr(self, 'status_timer'):
                        from PyQt6.QtCore import QTimer
                        self.status_timer = QTimer()
                        
                    self.status_timer.timeout.connect(lambda: self.status_label.setVisible(False))
                    self.status_timer.start(duration_ms)
                
        except Exception as e:
            logger.error(f"❌ Erreur affichage message: {e}")

    def _clear_all_rois(self):
        """Efface toutes les ROI - VERSION CORRIGÉE"""
        try:
            roi_count = len(self.roi_manager.rois) if hasattr(self, 'roi_manager') else 0
            
            if hasattr(self, 'roi_manager') and self.roi_manager:
                self.roi_manager.rois.clear()
                self.roi_manager.selected_roi_id = None
                self.roi_manager.cancel_roi_creation()  # Annule création en cours
                
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

    def _process_frame(self):
        """Traitement des frames avec détection et rendu ROI"""
        if not self.camera_manager or not self.streaming_active:
            return
            
        try:
            # Récupération frame
            frame = self.camera_manager.get_latest_frame()
            if frame is None:
                return
                
            # Sauvegarde taille pour conversion coordonnées
            self.current_frame_size = (frame.shape[1], frame.shape[0])
            
            # Copie pour traitement
            display_frame = frame.copy()
            
            # Détection si activée
            if self.tracking_active and hasattr(self, 'target_detector'):
                try:
                    detections = self.target_detector.detect_all_targets(frame)
                    if detections:
                        display_frame = self._draw_detections(display_frame, detections)
                except Exception as e:
                    logger.warning(f"⚠️ Erreur détection: {e}")
            
            # NOUVEAU: Rendu des ROI
            if hasattr(self, 'roi_manager') and self.roi_manager:
                try:
                    display_frame = self.roi_manager.draw_rois(display_frame)
                    
                    # Dessin preview ROI en cours de création
                    if (self.roi_manager.is_creating and 
                        hasattr(self, 'roi_preview_pos') and 
                        self.roi_preview_pos):
                        display_frame = self._draw_roi_preview(display_frame)
                        
                except Exception as e:
                    logger.warning(f"⚠️ Erreur rendu ROI: {e}")
            
            # Conversion et affichage
            self._update_display_frame(display_frame)
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement frame: {e}")

    def _draw_roi_preview(self, frame):
        """Dessine l'aperçu de la ROI en cours de création"""
        try:
            preview_color = (0, 255, 255)  # Jaune cyan pour preview
            
            if (self.roi_manager.creation_type == ROIType.RECTANGLE and 
                len(self.roi_manager.temp_points) == 1):
                
                # Preview rectangle
                start_point = self.roi_manager.temp_points[0]
                end_point = self.roi_preview_pos
                
                cv2.rectangle(frame, start_point, end_point, preview_color, 2)
                
            elif (self.roi_manager.creation_type == ROIType.POLYGON and 
                self.roi_manager.temp_points):
                
                # Preview polygone
                points = self.roi_manager.temp_points + [self.roi_preview_pos]
                if len(points) >= 2:
                    points_array = np.array(points, dtype=np.int32)
                    cv2.polylines(frame, [points_array], False, preview_color, 2)
                    
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