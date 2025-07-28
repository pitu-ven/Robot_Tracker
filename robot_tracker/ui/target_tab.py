# ui/target_tab.py
# Version 1.1 - Correction erreur configuration et gestion robuste des valeurs None
# Modification: Ajout vérifications nullité et valeurs par défaut

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

try:
    from ..core.aruco_config_loader import ArUcoConfigLoader
    from ..core.target_detector import TargetDetector, TargetType
    from ..core.roi_manager import ROIManager, ROIType
    from .camera_display_widget import CameraDisplayWidget
except ImportError:
    from core.aruco_config_loader import ArUcoConfigLoader
    from core.target_detector import TargetDetector, TargetType
    from core.roi_manager import ROIManager, ROIType
    from ui.camera_display_widget import CameraDisplayWidget

logger = logging.getLogger(__name__)

class TargetTab(QWidget):
    """Onglet de détection et tracking de cibles"""
    
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
        
        # Composants principaux
        try:
            self.aruco_loader = ArUcoConfigLoader(self.config)
            self.target_detector = TargetDetector(self.config)
            self.roi_manager = ROIManager(self.config)
        except Exception as e:
            logger.error(f"❌ Erreur initialisation composants: {e}")
            raise
        
        # État de l'interface
        self.current_frame = None
        self.is_tracking = False
        self.detected_targets = []
        self.tracking_data = []
        
        # Timers
        self.update_timer = QTimer()
        self.stats_timer = QTimer()
        
        # Interface
        self._init_ui()
        self._connect_signals()
        self._load_default_aruco_folder()
        
        logger.info("🎯 TargetTab initialisé avec succès")
    
    def _safe_get_config(self, section: str, key: str, default: any) -> any:
        """Récupération sécurisée de configuration avec gestion des None"""
        try:
            value = self.config.get(section, key, default)
            return value if value is not None else default
        except Exception as e:
            logger.warning(f"⚠️ Erreur récupération config {section}.{key}: {e}")
            return default
    
    def _init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QHBoxLayout(self)
        
        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panneau de contrôle et zone d'affichage
        control_panel = self._create_control_panel()
        display_area = self._create_display_area()
        
        splitter.addWidget(control_panel)
        splitter.addWidget(display_area)
        
        # Proportions depuis config
        control_width = self.window_config.get('control_panel_width', 320)
        splitter.setSizes([control_width, 800])  # Reste pour l'affichage
        
        layout.addWidget(splitter)
    
    def _create_control_panel(self) -> QWidget:
        """Crée le panneau de contrôle"""
        panel = QWidget()
        panel.setMaximumWidth(self.window_config.get('control_panel_width', 320))
        layout = QVBoxLayout(panel)
        
        # Configuration ArUco
        aruco_group = self._create_aruco_config_group()
        layout.addWidget(aruco_group)
        
        # Configuration détection
        detection_group = self._create_detection_config_group()
        layout.addWidget(detection_group)
        
        # Gestion ROI
        roi_group = self._create_roi_group()
        layout.addWidget(roi_group)
        
        # Contrôles tracking
        tracking_group = self._create_tracking_group()
        layout.addWidget(tracking_group)
        
        # Statistiques
        stats_group = self._create_stats_group()
        layout.addWidget(stats_group)
        
        layout.addStretch()
        return panel
    
    def _create_aruco_config_group(self) -> QGroupBox:
        """Groupe de configuration ArUco"""
        group = QGroupBox("🎯 Configuration ArUco")
        layout = QVBoxLayout(group)
        
        # Sélection dossier
        folder_layout = QHBoxLayout()
        self.folder_label = QLabel("Aucun dossier")
        self.folder_label.setStyleSheet("color: gray; font-style: italic;")
        
        self.browse_btn = QPushButton("Parcourir...")
        self.browse_btn.clicked.connect(self._browse_aruco_folder)
        
        folder_layout.addWidget(QLabel("Dossier:"))
        folder_layout.addWidget(self.folder_label, 1)
        folder_layout.addWidget(self.browse_btn)
        layout.addLayout(folder_layout)
        
        # Statut scan
        self.scan_status = QLabel("Prêt")
        self.scan_progress = QProgressBar()
        self.scan_progress.setVisible(False)
        
        layout.addWidget(self.scan_status)
        layout.addWidget(self.scan_progress)
        
        # Liste marqueurs détectés
        self.markers_table = QTableWidget(0, 3)
        self.markers_table.setHorizontalHeaderLabels(["ID", "Taille", "État"])
        self.markers_table.horizontalHeader().setStretchLastSection(True)
        self.markers_table.setMaximumHeight(150)
        
        layout.addWidget(QLabel("Marqueurs détectés:"))
        layout.addWidget(self.markers_table)
        
        # Actions
        actions_layout = QHBoxLayout()
        self.rescan_btn = QPushButton("Re-scanner")
        self.rescan_btn.clicked.connect(self._rescan_aruco_folder)
        self.rescan_btn.setEnabled(False)
        
        self.config_btn = QPushButton("Config Auto")
        self.config_btn.clicked.connect(self._generate_aruco_config)
        self.config_btn.setEnabled(False)
        
        actions_layout.addWidget(self.rescan_btn)
        actions_layout.addWidget(self.config_btn)
        layout.addLayout(actions_layout)
        
        return group
    
    def _create_detection_config_group(self) -> QGroupBox:
        """Groupe de configuration de détection"""
        group = QGroupBox("⚙️ Détection")
        layout = QVBoxLayout(group)
        
        # Types de cibles avec vérification de configuration
        self.aruco_check = QCheckBox("Marqueurs ArUco")
        self.aruco_check.setChecked(True)
        self.aruco_check.toggled.connect(lambda checked: 
            self._safe_toggle_detection(TargetType.ARUCO, checked))
        
        reflective_enabled = self.target_config.get('reflective_markers', {}).get('enabled', True) if self.target_config else True
        self.reflective_check = QCheckBox("Marqueurs réfléchissants")
        self.reflective_check.setChecked(reflective_enabled)
        self.reflective_check.toggled.connect(lambda checked:
            self._safe_toggle_detection(TargetType.REFLECTIVE, checked))
        
        led_enabled = self.target_config.get('led_markers', {}).get('enabled', True) if self.target_config else True
        self.led_check = QCheckBox("LEDs colorées")
        self.led_check.setChecked(led_enabled)
        self.led_check.toggled.connect(lambda checked:
            self._safe_toggle_detection(TargetType.LED, checked))
        
        layout.addWidget(self.aruco_check)
        layout.addWidget(self.reflective_check)
        layout.addWidget(self.led_check)
        
        # Paramètres avancés
        advanced_btn = QPushButton("Paramètres avancés...")
        advanced_btn.clicked.connect(self._show_advanced_detection_params)
        layout.addWidget(advanced_btn)
        
        return group
    
    def _safe_toggle_detection(self, target_type: TargetType, enabled: bool):
        """Toggle sécurisé des types de détection"""
        try:
            self.target_detector.set_detection_enabled(target_type, enabled)
        except Exception as e:
            logger.error(f"❌ Erreur toggle détection {target_type}: {e}")
    
    def _create_roi_group(self) -> QGroupBox:
        """Groupe de gestion des ROI"""
        group = QGroupBox("📐 Régions d'intérêt (ROI)")
        layout = QVBoxLayout(group)
        
        # Boutons création ROI
        creation_layout = QGridLayout()
        
        rect_btn = QPushButton("Rectangle")
        rect_btn.clicked.connect(lambda: self._start_roi_creation(ROIType.RECTANGLE))
        
        circle_btn = QPushButton("Cercle")
        circle_btn.clicked.connect(lambda: self._start_roi_creation(ROIType.CIRCLE))
        
        polygon_btn = QPushButton("Polygone")
        polygon_btn.clicked.connect(lambda: self._start_roi_creation(ROIType.POLYGON))
        
        creation_layout.addWidget(rect_btn, 0, 0)
        creation_layout.addWidget(circle_btn, 0, 1)
        creation_layout.addWidget(polygon_btn, 1, 0, 1, 2)
        
        layout.addLayout(creation_layout)
        
        # Liste des ROI actives
        self.roi_list = QTableWidget(0, 4)
        self.roi_list.setHorizontalHeaderLabels(["ID", "Type", "Taille", "Actions"])
        self.roi_list.horizontalHeader().setStretchLastSection(True)
        self.roi_list.setMaximumHeight(120)
        
        layout.addWidget(QLabel("ROI actives:"))
        layout.addWidget(self.roi_list)
        
        # Actions ROI
        roi_actions = QHBoxLayout()
        
        clear_roi_btn = QPushButton("Effacer tout")
        clear_roi_btn.clicked.connect(self._clear_all_roi)
        
        invert_roi_btn = QPushButton("Inverser")
        invert_roi_btn.clicked.connect(self._invert_roi_selection)
        
        roi_actions.addWidget(clear_roi_btn)
        roi_actions.addWidget(invert_roi_btn)
        layout.addLayout(roi_actions)
        
        return group
    
    def _create_tracking_group(self) -> QGroupBox:
        """Groupe de contrôle du tracking"""
        group = QGroupBox("🎯 Contrôle Tracking")
        layout = QVBoxLayout(group)
        
        # Boutons Start/Stop
        controls_layout = QHBoxLayout()
        
        self.start_tracking_btn = QPushButton("Démarrer")
        self.start_tracking_btn.clicked.connect(self._start_tracking)
        
        self.stop_tracking_btn = QPushButton("Arrêter")
        self.stop_tracking_btn.clicked.connect(self._stop_tracking)
        self.stop_tracking_btn.setEnabled(False)
        
        controls_layout.addWidget(self.start_tracking_btn)
        controls_layout.addWidget(self.stop_tracking_btn)
        layout.addLayout(controls_layout)
        
        # Options avec gestion sécurisée de la configuration
        tracking_config = self._safe_get_config('tracking', '', {})
        
        kalman_enabled = False
        prediction_enabled = False
        
        if tracking_config:
            kalman_config = tracking_config.get('kalman_filter')
            if kalman_config and isinstance(kalman_config, dict):
                kalman_enabled = kalman_config.get('enabled', True)
            
            prediction_config = tracking_config.get('prediction')
            if prediction_config and isinstance(prediction_config, dict):
                prediction_enabled = prediction_config.get('enabled', True)
        
        self.kalman_check = QCheckBox("Filtrage Kalman")
        self.kalman_check.setChecked(kalman_enabled)
        
        self.prediction_check = QCheckBox("Prédiction")
        self.prediction_check.setChecked(prediction_enabled)
        
        layout.addWidget(self.kalman_check)
        layout.addWidget(self.prediction_check)
        
        # Export
        export_layout = QHBoxLayout()
        
        self.export_format = QComboBox()
        # Export formats avec gestion sécurisée
        export_formats = ['csv', 'json']  # Valeurs par défaut
        if self.ui_config:
            export_config = self.ui_config.get('export', {})
            if export_config:
                export_formats = export_config.get('formats', export_formats)
        
        self.export_format.addItems(export_formats)
        
        export_btn = QPushButton("Exporter")
        export_btn.clicked.connect(self._export_tracking_data)
        
        export_layout.addWidget(QLabel("Format:"))
        export_layout.addWidget(self.export_format)
        export_layout.addWidget(export_btn)
        layout.addLayout(export_layout)
        
        return group
    
    def _create_stats_group(self) -> QGroupBox:
        """Groupe d'affichage des statistiques"""
        group = QGroupBox("📊 Statistiques")
        layout = QVBoxLayout(group)
        
        # Labels de statistiques
        self.fps_label = QLabel("FPS: 0")
        self.detections_label = QLabel("Détections: 0")
        self.targets_label = QLabel("Cibles actives: 0")
        self.roi_label = QLabel("ROI: 0")
        
        layout.addWidget(self.fps_label)
        layout.addWidget(self.detections_label)
        layout.addWidget(self.targets_label)
        layout.addWidget(self.roi_label)
        
        # Graphique temps réel (simple)
        self.stats_text = QTextEdit()
        self.stats_text.setMaximumHeight(80)
        self.stats_text.setReadOnly(True)
        layout.addWidget(self.stats_text)
        
        return group
    
    def _create_display_area(self) -> QWidget:
        """Crée la zone d'affichage vidéo"""
        area = QWidget()
        layout = QVBoxLayout(area)
        
        # Widget d'affichage caméra
        try:
            self.camera_display = CameraDisplayWidget(self.config)
            layout.addWidget(self.camera_display)
        except Exception as e:
            logger.error(f"❌ Erreur création CameraDisplayWidget: {e}")
            # Fallback avec QLabel simple
            self.camera_display = QLabel("Affichage caméra non disponible")
            self.camera_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.camera_display.setStyleSheet("border: 1px solid gray; background: #f0f0f0;")
            self.camera_display.setMinimumHeight(480)
            layout.addWidget(self.camera_display)
        
        # Contrôles d'affichage
        display_controls = self._create_display_controls()
        layout.addWidget(display_controls)
        
        return area
    
    def _create_display_controls(self) -> QWidget:
        """Crée les contrôles d'affichage"""
        controls = QFrame()
        controls.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(controls)
        
        # Zoom
        layout.addWidget(QLabel("Zoom:"))
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(25, 500)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        
        self.zoom_label = QLabel("100%")
        
        layout.addWidget(self.zoom_slider)
        layout.addWidget(self.zoom_label)
        
        # Overlays
        layout.addWidget(QLabel("|"))
        
        self.show_detections = QCheckBox("Détections")
        self.show_detections.setChecked(True)
        
        self.show_roi = QCheckBox("ROI")
        self.show_roi.setChecked(True)
        
        self.show_trajectories = QCheckBox("Trajectoires")
        self.show_trajectories.setChecked(True)
        
        layout.addWidget(self.show_detections)
        layout.addWidget(self.show_roi)
        layout.addWidget(self.show_trajectories)
        
        layout.addStretch()
        return controls
    
    def _connect_signals(self):
        """Connecte les signaux internes"""
        # Timer de mise à jour
        update_interval = self.window_config.get('update_interval_ms', 33)
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(update_interval)
        
        # Timer statistiques
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(1000)  # 1 seconde
        
        # Signaux caméra
        if hasattr(self.camera_manager, 'frame_received'):
            self.camera_manager.frame_received.connect(self._on_frame_received)
    
    def _load_default_aruco_folder(self):
        """Charge le dossier ArUco par défaut"""
        if not self.target_config:
            return
            
        aruco_config = self.target_config.get('aruco', {})
        if not aruco_config.get('auto_detect_folder', False):
            return
        
        default_folder = aruco_config.get('default_markers_folder', './ArUco')
        folder_path = Path(default_folder)
        
        if folder_path.exists():
            logger.info(f"🎯 Chargement dossier ArUco par défaut: {folder_path}")
            self._scan_aruco_folder(str(folder_path))
    
    # ==================== MÉTHODES D'ÉVÉNEMENTS ====================
    
    def _browse_aruco_folder(self):
        """Parcourir un dossier ArUco"""
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Sélectionner le dossier ArUco",
            str(Path.home())
        )
        
        if folder:
            self._scan_aruco_folder(folder)
    
    def _scan_aruco_folder(self, folder_path: str):
        """Scanner un dossier ArUco"""
        try:
            self.scan_progress.setVisible(True)
            self.scan_progress.setValue(0)
            self.scan_status.setText("Scan en cours...")
            
            # Utilisation de l'ArUcoConfigLoader
            markers = self.aruco_loader.scan_folder(folder_path)
            
            self.scan_progress.setValue(100)
            self.scan_status.setText(f"{len(markers)} marqueur(s) trouvé(s)")
            
            # Mise à jour de l'interface
            self.folder_label.setText(Path(folder_path).name)
            self.folder_label.setStyleSheet("color: black; font-weight: bold;")
            
            self._update_markers_table(markers)
            
            # Activation des boutons
            self.rescan_btn.setEnabled(True)
            self.config_btn.setEnabled(True)
            
            self.scan_progress.setVisible(False)
            
        except Exception as e:
            logger.error(f"❌ Erreur scan dossier ArUco: {e}")
            self.scan_status.setText(f"Erreur: {e}")
            self.scan_progress.setVisible(False)
    
    def _update_markers_table(self, markers: List):
        """Met à jour la table des marqueurs"""
        self.markers_table.setRowCount(len(markers))
        
        for row, marker in enumerate(markers):
            # ID
            id_item = QTableWidgetItem(str(marker.get('id', 'N/A')))
            self.markers_table.setItem(row, 0, id_item)
            
            # Taille
            size = marker.get('size', 'N/A')
            size_item = QTableWidgetItem(f"{size}px" if isinstance(size, int) else str(size))
            self.markers_table.setItem(row, 1, size_item)
            
            # État
            status_item = QTableWidgetItem("✅ Prêt")
            self.markers_table.setItem(row, 2, status_item)
    
    def _rescan_aruco_folder(self):
        """Re-scanner le dossier ArUco"""
        current_folder = self.aruco_loader.current_folder
        if current_folder:
            self._scan_aruco_folder(current_folder)
    
    def _generate_aruco_config(self):
        """Génère la configuration ArUco automatiquement"""
        try:
            config = self.aruco_loader.generate_auto_config()
            
            if config:
                QMessageBox.information(
                    self,
                    "Configuration générée",
                    f"Configuration ArUco générée avec succès!\n"
                    f"- {len(config.get('markers', []))} marqueurs configurés\n"
                    f"- Dictionnaire: {config.get('dictionary', 'N/A')}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Erreur génération",
                    "Impossible de générer la configuration.\nVérifiez que des marqueurs sont détectés."
                )
                
        except Exception as e:
            logger.error(f"❌ Erreur génération config ArUco: {e}")
            QMessageBox.critical(
                self,
                "Erreur",
                f"Erreur lors de la génération:\n{e}"
            )
    
    def _show_advanced_detection_params(self):
        """Affiche les paramètres avancés de détection"""
        QMessageBox.information(
            self,
            "Paramètres avancés",
            "Fonctionnalité en développement.\n"
            "Utilisez le fichier tracking_config.json pour modifier\n"
            "les paramètres de détection avancés."
        )
    
    def _start_roi_creation(self, roi_type: ROIType):
        """Démarre la création d'une ROI"""
        try:
            self.roi_manager.start_creation(roi_type)
            self.scan_status.setText(f"Création {roi_type.value} - Cliquez sur l'image")
        except Exception as e:
            logger.error(f"❌ Erreur création ROI: {e}")
    
    def _clear_all_roi(self):
        """Efface toutes les ROI"""
        reply = QMessageBox.question(
            self,
            "Confirmation",
            "Supprimer toutes les régions d'intérêt ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.roi_manager.clear_all()
            self._update_roi_list()
    
    def _invert_roi_selection(self):
        """Inverse la sélection des ROI"""
        self.roi_manager.invert_selection()
        self._update_roi_list()
    
    def _update_roi_list(self):
        """Met à jour la liste des ROI"""
        rois = self.roi_manager.get_all_rois()
        self.roi_list.setRowCount(len(rois))
        
        for row, roi in enumerate(rois):
            # ID
            self.roi_list.setItem(row, 0, QTableWidgetItem(str(roi.id)))
            
            # Type
            self.roi_list.setItem(row, 1, QTableWidgetItem(roi.type.value))
            
            # Taille
            size_info = f"{roi.width}x{roi.height}" if hasattr(roi, 'width') else "N/A"
            self.roi_list.setItem(row, 2, QTableWidgetItem(size_info))
            
            # Actions (placeholder)
            self.roi_list.setItem(row, 3, QTableWidgetItem("🗑️"))
    
    def _start_tracking(self):
        """Démarre le tracking"""
        try:
            if not self.camera_manager.active_cameras:
                QMessageBox.warning(
                    self,
                    "Caméra requise",
                    "Veuillez d'abord démarrer une caméra dans l'onglet Caméra."
                )
                return
            
            self.is_tracking = True
            self.tracking_data.clear()
            
            # Interface
            self.start_tracking_btn.setEnabled(False)
            self.stop_tracking_btn.setEnabled(True)
            
            # Signal
            self.tracking_started.emit()
            
            logger.info("🎯 Tracking démarré")
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage tracking: {e}")
            QMessageBox.critical(self, "Erreur", f"Impossible de démarrer le tracking:\n{e}")
    
    def _stop_tracking(self):
        """Arrête le tracking"""
        self.is_tracking = False
        
        # Interface
        self.start_tracking_btn.setEnabled(True)
        self.stop_tracking_btn.setEnabled(False)
        
        # Signal
        self.tracking_stopped.emit()
        
        logger.info("🛑 Tracking arrêté")
    
    def _export_tracking_data(self):
        """Exporte les données de tracking"""
        if not self.tracking_data:
            QMessageBox.information(
                self,
                "Aucune donnée",
                "Aucune donnée de tracking à exporter."
            )
            return
        
        format_selected = self.export_format.currentText()
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter les données de tracking",
            f"tracking_data.{format_selected}",
            f"{format_selected.upper()} files (*.{format_selected})"
        )
        
        if filename:
            try:
                # TODO: Implémenter l'export réel
                QMessageBox.information(
                    self,
                    "Export réussi",
                    f"Données exportées vers:\n{filename}"
                )
            except Exception as e:
                logger.error(f"❌ Erreur export: {e}")
                QMessageBox.critical(self, "Erreur export", str(e))
    
    def _on_zoom_changed(self, value: int):
        """Gestion du changement de zoom"""
        self.zoom_label.setText(f"{value}%")
        
        if hasattr(self.camera_display, 'set_zoom'):
            self.camera_display.set_zoom(value / 100.0)
    
    def _on_frame_received(self, frame):
        """Traitement d'une nouvelle frame"""
        if not self.is_tracking:
            return
        
        try:
            self.current_frame = frame
            
            # Détection des cibles
            detections = self.target_detector.detect_all_targets(frame)
            self.detected_targets = detections
            
            # Enregistrement pour le tracking
            if detections:
                timestamp = time.time()
                for detection in detections:
                    tracking_point = {
                        'timestamp': timestamp,
                        'center': detection.center,
                        'type': detection.target_type.value,
                        'confidence': detection.confidence
                    }
                    self.tracking_data.append(tracking_point)
            
            # Signal de détection
            for detection in detections:
                self.target_detected.emit(detection)
                
        except Exception as e:
            logger.error(f"❌ Erreur traitement frame: {e}")
    
    def _update_display(self):
        """Met à jour l'affichage"""
        if not self.current_frame:
            return
        
        try:
            # Copie de la frame pour overlay
            display_frame = self.current_frame.copy()
            
            # Overlays conditionnels
            if self.show_detections.isChecked() and self.detected_targets:
                display_frame = self._draw_detections(display_frame)
            
            if self.show_roi.isChecked():
                display_frame = self._draw_rois(display_frame)
            
            if self.show_trajectories.isChecked():
                display_frame = self._draw_trajectories(display_frame)
            
            # Affichage
            if hasattr(self.camera_display, 'update_frame'):
                self.camera_display.update_frame(display_frame)
            
        except Exception as e:
            logger.debug(f"Erreur mise à jour affichage: {e}")
    
    def _draw_detections(self, frame):
        """Dessine les détections sur la frame"""
        for detection in self.detected_targets:
            # Couleur selon le type
            colors = {
                TargetType.ARUCO: (0, 255, 0),      # Vert
                TargetType.REFLECTIVE: (255, 0, 0),  # Rouge
                TargetType.LED: (0, 0, 255)          # Bleu
            }
            
            color = colors.get(detection.target_type, (255, 255, 255))
            center = detection.center
            
            # Cercle central
            cv2.circle(frame, center, 5, color, -1)
            
            # Contour si disponible
            if hasattr(detection, 'corners') and detection.corners:
                corners = np.array(detection.corners, dtype=int)
                cv2.polylines(frame, [corners], True, color, 2)
            
            # ID et confiance
            text = f"ID:{detection.id} ({detection.confidence:.2f})"
            cv2.putText(frame, text, (center[0] + 10, center[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        return frame
    
    def _draw_rois(self, frame):
        """Dessine les ROI sur la frame"""
        rois = self.roi_manager.get_all_rois()
        
        for roi in rois:
            color = (255, 255, 0)  # Jaune
            
            if roi.type == ROIType.RECTANGLE:
                pt1 = (int(roi.x), int(roi.y))
                pt2 = (int(roi.x + roi.width), int(roi.y + roi.height))
                cv2.rectangle(frame, pt1, pt2, color, 2)
            
            elif roi.type == ROIType.CIRCLE:
                center = (int(roi.center_x), int(roi.center_y))
                cv2.circle(frame, center, int(roi.radius), color, 2)
        
        return frame
    
    def _draw_trajectories(self, frame):
        """Dessine les trajectoires sur la frame"""
        if len(self.tracking_data) < 2:
            return frame
        
        # Points de trajectoire (derniers N points)
        max_points = 50
        recent_points = self.tracking_data[-max_points:]
        
        if len(recent_points) >= 2:
            points = [point['center'] for point in recent_points]
            points = np.array(points, dtype=int)
            
            # Ligne de trajectoire
            cv2.polylines(frame, [points], False, (0, 255, 255), 2)
            
            # Point actuel plus gros
            if len(points) > 0:
                cv2.circle(frame, tuple(points[-1]), 8, (0, 255, 255), -1)
        
        return frame
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        try:
            # FPS (estimation basique)
            self.fps_label.setText(f"FPS: {len(self.tracking_data) % 60}")
            
            # Détections
            self.detections_label.setText(f"Détections: {len(self.detected_targets)}")
            
            # Cibles actives
            active_targets = len([d for d in self.detected_targets if d.confidence > 0.5])
            self.targets_label.setText(f"Cibles actives: {active_targets}")
            
            # ROI
            roi_count = len(self.roi_manager.get_all_rois())
            self.roi_label.setText(f"ROI: {roi_count}")
            
            # Texte détaillé
            stats_text = f"Tracking: {'Actif' if self.is_tracking else 'Inactif'}\n"
            stats_text += f"Points enregistrés: {len(self.tracking_data)}\n"
            stats_text += f"Dernière détection: {time.strftime('%H:%M:%S') if self.detected_targets else 'Aucune'}"
            
            self.stats_text.setText(stats_text)
            
        except Exception as e:
            logger.debug(f"Erreur mise à jour stats: {e}")