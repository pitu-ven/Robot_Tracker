# ui/target_tab.py
# Version 1.3 - Correction finale signature ROIManager
# Modification: Correction appel ROIManager avec config_manager comme paramètre

import cv2
import numpy as np
import time
from pathlib import Path
from typing import Dict, List, Optional
import logging

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QSplitter,
    QGroupBox, QPushButton, QLabel, QComboBox, QSpinBox, QCheckBox,
    QLineEdit, QTextEdit, QProgressBar, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSlider, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QPixmap, QImage, QFont, QIcon

# Import avec fallback pour éviter les erreurs d'import relatif
try:
    from core.aruco_config_loader import ArUcoConfigLoader
    from core.target_detector import TargetDetector, TargetType
    from core.roi_manager import ROIManager, ROIType
except ImportError:
    # Stubs temporaires pour éviter les erreurs lors du développement
    class ArUcoConfigLoader:
        def __init__(self, config): pass
        def get_detector_params(self): return {}
        def get_marker_configs(self): return []
    
    class TargetDetector:
        def __init__(self, config): pass
        def detect(self, frame): return [], []
        def set_roi(self, roi): pass
    
    class TargetType:
        ARUCO_MARKER = "aruco"
        COLORED_TARGET = "color"
        BLOB = "blob"
    
    class ROIManager:
        def __init__(self, config_manager): pass  # CORRECTION: Prendre config_manager en paramètre
        def add_roi(self, roi_type, points): return 0
        def get_rois(self): return []
        def update_roi(self, roi_id, points): pass
        def remove_roi(self, roi_id): pass
    
    class ROIType:
        RECTANGLE = "rectangle"
        POLYGON = "polygon"
        CIRCLE = "circle"

try:
    from ui.camera_display_widget import CameraDisplayWidget
except ImportError:
    # Stub pour CameraDisplayWidget si pas disponible
    from PyQt6.QtWidgets import QLabel
    class CameraDisplayWidget(QLabel):
        camera_clicked = pyqtSignal(str)
        def __init__(self, alias, parent=None):
            super().__init__(parent)
            self.alias = alias
            self.setText(f"Display: {alias}")

logger = logging.getLogger(__name__)

class TargetTab(QWidget):
    """Onglet de détection et tracking de cibles - Version corrigée finale"""
    
    # Signaux
    target_detected = pyqtSignal(object)  # Detection result
    roi_changed = pyqtSignal(int)         # ROI ID
    tracking_started = pyqtSignal()
    tracking_stopped = pyqtSignal()
    
    def __init__(self, config_manager, camera_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.camera_manager = camera_manager
        
        # Configuration avec gestion robuste des valeurs None
        self.target_config = self._safe_get_config('tracking', 'target_detection', {})
        self.ui_config = self._safe_get_config('tracking', 'target_tab_ui', {})
        self.window_config = self.ui_config.get('window', {}) if self.ui_config else {}
        
        # État interne
        self.is_tracking = False
        self.selected_camera = None
        self.current_frame = None
        self.detection_results = []
        
        # Composants principaux (stubs temporaires)
        try:
            self.aruco_loader = ArUcoConfigLoader(self.config)
            self.target_detector = TargetDetector(self.config)
            # CORRECTION CRITIQUE: Passer config_manager au lieu de self.config
            self.roi_manager = ROIManager(self.config)  # config_manager = self.config
        except Exception as e:
            logger.warning(f"⚠️ Composants de détection non disponibles: {e}")
            # Fallback avec stubs
            self.aruco_loader = ArUcoConfigLoader(self.config)
            self.target_detector = TargetDetector(self.config)
            self.roi_manager = ROIManager(self.config)  # Stub prend config_manager
        
        # Interface utilisateur
        self._setup_ui()
        self._connect_signals()
        
        # Timer pour le processing
        self.processing_timer = QTimer()
        self.processing_timer.timeout.connect(self._process_frame)
        
        version = self._safe_get_config('ui', 'target_tab.version', '1.3')
        logger.info(f"🎯 TargetTab v{version} initialisé (correction signature ROIManager)")
    
    def _safe_get_config(self, section: str, key: str, default=None):
        """Accès sécurisé à la configuration avec gestion des erreurs"""
        try:
            if hasattr(self.config, 'get'):
                return self.config.get(section, key, default)
            else:
                return default
        except Exception as e:
            logger.warning(f"⚠️ Erreur lecture config {section}.{key}: {e}")
            return default
    
    def _setup_ui(self):
        """Initialise l'interface utilisateur (version simplifiée)"""
        layout = QHBoxLayout(self)
        
        # Panneau de contrôle (gauche)
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel)
        
        # Zone d'affichage (droite)
        display_area = self._create_display_area()
        layout.addWidget(display_area, 1)
    
    def _create_control_panel(self) -> QWidget:
        """Crée le panneau de contrôle"""
        panel = QWidget()
        panel.setFixedWidth(300)
        layout = QVBoxLayout(panel)
        
        # Sélection caméra
        camera_group = QGroupBox("📷 Caméra")
        camera_layout = QVBoxLayout(camera_group)
        
        self.camera_combo = QComboBox()
        self.camera_combo.currentTextChanged.connect(self._on_camera_selected)
        camera_layout.addWidget(self.camera_combo)
        
        refresh_btn = QPushButton("🔄 Actualiser")
        refresh_btn.clicked.connect(self._refresh_cameras)
        camera_layout.addWidget(refresh_btn)
        
        layout.addWidget(camera_group)
        
        # Contrôles de détection
        detection_group = QGroupBox("🎯 Détection")
        detection_layout = QVBoxLayout(detection_group)
        
        self.start_detection_btn = QPushButton("▶️ Démarrer détection")
        self.start_detection_btn.clicked.connect(self._start_detection)
        self.start_detection_btn.setEnabled(False)
        
        self.stop_detection_btn = QPushButton("⏹️ Arrêter détection")
        self.stop_detection_btn.clicked.connect(self._stop_detection)
        self.stop_detection_btn.setEnabled(False)
        
        detection_layout.addWidget(self.start_detection_btn)
        detection_layout.addWidget(self.stop_detection_btn)
        
        layout.addWidget(detection_group)
        
        # Statistiques
        stats_group = QGroupBox("📊 Statistiques")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_label = QLabel("Aucune détection")
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_group)
        
        # Log
        log_group = QGroupBox("📝 Journal")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(120)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        clear_log_btn = QPushButton("🗑️ Effacer")
        clear_log_btn.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_log_btn)
        
        layout.addWidget(log_group)
        
        layout.addStretch()
        return panel
    
    def _create_display_area(self) -> QWidget:
        """Crée la zone d'affichage"""
        area = QWidget()
        layout = QVBoxLayout(area)
        
        # Message par défaut
        self.default_message = QLabel(
            "🎯 Onglet Cible - Mode Développement\n\n"
            "Fonctionnalités disponibles :\n"
            "• Sélection de caméra\n"
            "• Interface de contrôle\n"
            "• Journalisation\n\n"
            "⚠️ Détection ArUco en cours de développement"
        )
        self.default_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.default_message.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 14px;
                padding: 20px;
                border: 2px dashed #ccc;
                border-radius: 10px;
                background-color: #f8f8f8;
            }
        """)
        layout.addWidget(self.default_message)
        
        return area
    
    def _connect_signals(self):
        """Connecte les signaux"""
        # Connexion avec le camera_manager si disponible
        if hasattr(self.camera_manager, 'frame_callbacks'):
            try:
                self.camera_manager.frame_callbacks.append(self._on_new_frame)
            except Exception as e:
                logger.debug(f"Erreur connexion callback frame: {e}")
    
    def _log(self, message: str):
        """Ajoute un message au log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # Limite le nombre de lignes
        max_lines = self._safe_get_config('ui', 'target_tab.log.max_lines', 50)
        if max_lines and max_lines > 0:
            lines = self.log_text.toPlainText().split('\n')
            if len(lines) > max_lines:
                self.log_text.setText('\n'.join(lines[-max_lines:]))
    
    def _refresh_cameras(self):
        """Actualise la liste des caméras"""
        self._log("🔍 Actualisation des caméras...")
        
        try:
            if hasattr(self.camera_manager, 'detect_all_cameras'):
                cameras = self.camera_manager.detect_all_cameras()
            else:
                cameras = []
            
            self.camera_combo.clear()
            
            for camera in cameras:
                if hasattr(camera, 'name') and hasattr(camera, 'camera_type'):
                    display_name = f"{camera.camera_type.value}: {camera.name}"
                    self.camera_combo.addItem(display_name, camera)
                else:
                    # Fallback pour objets non-standard
                    name = getattr(camera, 'name', str(camera))
                    self.camera_combo.addItem(f"Caméra: {name}", camera)
            
            count = len(cameras)
            self._log(f"✅ {count} caméra(s) détectée(s)")
            
        except Exception as e:
            self._log(f"❌ Erreur détection caméras: {e}")
            logger.error(f"Erreur actualisation caméras: {e}")
    
    def _on_camera_selected(self, text):
        """Gestion de la sélection d'une caméra"""
        camera_data = self.camera_combo.currentData()
        
        if camera_data:
            self.selected_camera = camera_data
            camera_name = getattr(camera_data, 'name', 'Caméra sélectionnée')
            self._log(f"📷 Caméra sélectionnée: {camera_name}")
            
            # Activation des contrôles si caméra disponible
            self.start_detection_btn.setEnabled(True)
        else:
            self.selected_camera = None
            self.start_detection_btn.setEnabled(False)
    
    def _start_detection(self):
        """Démarre la détection (stub)"""
        if not self.selected_camera:
            self._log("⚠️ Aucune caméra sélectionnée")
            return
        
        self._log("🎯 Démarrage de la détection...")
        
        try:
            # Vérification que la caméra est ouverte
            if hasattr(self.camera_manager, 'is_camera_open'):
                camera_alias = self._get_camera_alias()
                if not self.camera_manager.is_camera_open(camera_alias):
                    self._log("⚠️ Caméra non ouverte - Ouvrez-la depuis l'onglet Caméra")
                    return
            
            # Démarrage du processing
            self.is_tracking = True
            self.processing_timer.start(100)  # 10 FPS
            
            # Mise à jour des contrôles
            self.start_detection_btn.setEnabled(False)
            self.stop_detection_btn.setEnabled(True)
            
            self._log("✅ Détection démarrée")
            self.tracking_started.emit()
            
        except Exception as e:
            self._log(f"❌ Erreur démarrage détection: {e}")
            logger.error(f"Erreur démarrage détection: {e}")
    
    def _stop_detection(self):
        """Arrête la détection"""
        self._log("🛑 Arrêt de la détection...")
        
        try:
            self.is_tracking = False
            self.processing_timer.stop()
            
            # Mise à jour des contrôles
            self.start_detection_btn.setEnabled(self.selected_camera is not None)
            self.stop_detection_btn.setEnabled(False)
            
            # Reset des statistiques
            self.stats_label.setText("Aucune détection")
            
            self._log("✅ Détection arrêtée")
            self.tracking_stopped.emit()
            
        except Exception as e:
            self._log(f"❌ Erreur arrêt détection: {e}")
            logger.error(f"Erreur arrêt détection: {e}")
    
    def _get_camera_alias(self) -> str:
        """Génère l'alias pour la caméra courante"""
        if self.selected_camera and hasattr(self.selected_camera, 'camera_type'):
            return f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
        return ""
    
    def _process_frame(self):
        """Traite une frame pour la détection (stub)"""
        if not self.is_tracking or not self.selected_camera:
            return
        
        try:
            # Récupération de la frame depuis le camera_manager
            camera_alias = self._get_camera_alias()
            
            if hasattr(self.camera_manager, 'get_camera_frame'):
                ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(camera_alias)
                
                if ret and color_frame is not None:
                    self.current_frame = color_frame.copy()
                    
                    # Simulation de détection (pour les tests)
                    self._simulate_detection()
                    
                else:
                    # Pas de frame disponible
                    pass
            
        except Exception as e:
            logger.debug(f"Erreur processing frame: {e}")
    
    def _simulate_detection(self):
        """Simule une détection pour les tests"""
        if self.current_frame is not None:
            # Mise à jour des stats simulées
            h, w = self.current_frame.shape[:2]
            stats_text = f"Frame: {w}x{h}\nDétections: 0 (mode stub)\nFPS: ~10"
            self.stats_label.setText(stats_text)
    
    def _on_new_frame(self, alias: str, frame_data):
        """Callback pour nouvelle frame (si connecté au camera_manager)"""
        try:
            if self.is_tracking and alias == self._get_camera_alias():
                if 'color_frame' in frame_data:
                    self.current_frame = frame_data['color_frame'].copy()
        except Exception as e:
            logger.debug(f"Erreur callback frame: {e}")
    
    def on_camera_ready(self, camera_info):
        """Callback quand une caméra est prête (signal depuis camera_tab)"""
        try:
            self._log(f"📡 Caméra prête: {camera_info}")
            self._refresh_cameras()
        except Exception as e:
            logger.debug(f"Erreur callback camera_ready: {e}")
    
    @property
    def has_active_detection(self) -> bool:
        """Retourne True si la détection est active"""
        return self.is_tracking
    
    def cleanup(self):
        """Nettoyage lors de la fermeture"""
        try:
            if self.is_tracking:
                self._stop_detection()
            
            self.processing_timer.stop()
            self._log("🔄 Nettoyage TargetTab terminé")
            
        except Exception as e:
            logger.error(f"Erreur nettoyage TargetTab: {e}")
    
    def closeEvent(self, event):
        """Événement de fermeture"""
        self.cleanup()
        super().closeEvent(event)