# ui/target_tab.py
# Version 1.0 - Création onglet Cible avec auto-configuration ArUco
# Modification: Implémentation interface complète avec panneau contrôle et affichage

import cv2
import numpy as np
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
        
        # Configuration depuis tracking_config.json existant
        self.target_config = self.config.get('tracking', 'target_detection', {})
        self.ui_config = self.config.get('tracking', 'target_tab_ui', {})
        self.window_config = self.ui_config.get('window', {})
        
        # Composants principaux
        self.aruco_loader = ArUcoConfigLoader(self.config)
        self.target_detector = TargetDetector(self.config)
        self.roi_manager = ROIManager(self.config)
        
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
        
        logger.info("TargetTab initialisé")
    
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
        
        # Types de cibles
        self.aruco_check = QCheckBox("Marqueurs ArUco")
        self.aruco_check.setChecked(True)
        self.aruco_check.toggled.connect(lambda checked: 
            self.target_detector.set_detection_enabled(TargetType.ARUCO, checked))
        
        self.reflective_check = QCheckBox("Marqueurs réfléchissants")
        self.reflective_check.setChecked(
            self.target_config.get('reflective_markers', {}).get('enabled', True))
        self.reflective_check.toggled.connect(lambda checked:
            self.target_detector.set_detection_enabled(TargetType.REFLECTIVE, checked))
        
        self.led_check = QCheckBox("LEDs colorées")
        self.led_check.setChecked(
            self.target_config.get('led_markers', {}).get('enabled', True))
        self.led_check.toggled.connect(lambda checked:
            self.target_detector.set_detection_enabled(TargetType.LED, checked))
        
        layout.addWidget(self.aruco_check)
        layout.addWidget(self.reflective_check)
        layout.addWidget(self.led_check)
        
        # Paramètres avancés
        advanced_btn = QPushButton("Paramètres avancés...")
        advanced_btn.clicked.connect(self._show_advanced_detection_params)
        layout.addWidget(advanced_btn)
        
        return group
    
    def _create_roi_group(self) -> QGroupBox:
        """Groupe de gestion des ROI"""
        group = QGroupBox("📐 Régions d'Intérêt")
        layout = QVBoxLayout(group)
        
        # Outils création
        tools_layout = QGridLayout()
        
        self.rect_roi_btn = QPushButton("Rectangle")
        self.rect_roi_btn.clicked.connect(lambda: self._start_roi_creation(ROIType.RECTANGLE))
        
        self.poly_roi_btn = QPushButton("Polygone")
        self.poly_roi_btn.clicked.connect(lambda: self._start_roi_creation(ROIType.POLYGON))
        
        self.circle_roi_btn = QPushButton("Cercle")
        self.circle_roi_btn.clicked.connect(lambda: self._start_roi_creation(ROIType.CIRCLE))
        
        self.clear_roi_btn = QPushButton("Effacer")
        self.clear_roi_btn.clicked.connect(self._clear_all_rois)
        
        tools_layout.addWidget(self.rect_roi_btn, 0, 0)
        tools_layout.addWidget(self.poly_roi_btn, 0, 1)
        tools_layout.addWidget(self.circle_roi_btn, 1, 0)
        tools_layout.addWidget(self.clear_roi_btn, 1, 1)
        
        layout.addLayout(tools_layout)
        
        # Liste ROI
        self.roi_list = QTableWidget(0, 2)
        self.roi_list.setHorizontalHeaderLabels(["Nom", "Type"])
        self.roi_list.horizontalHeader().setStretchLastSection(True)
        self.roi_list.setMaximumHeight(100)
        
        layout.addWidget(QLabel("ROI actives:"))
        layout.addWidget(self.roi_list)
        
        # Sauvegarde/chargement
        roi_file_layout = QHBoxLayout()
        save_roi_btn = QPushButton("Sauver")
        save_roi_btn.clicked.connect(self._save_rois)
        
        load_roi_btn = QPushButton("Charger")
        load_roi_btn.clicked.connect(self._load_rois)
        
        roi_file_layout.addWidget(save_roi_btn)
        roi_file_layout.addWidget(load_roi_btn)
        layout.addLayout(roi_file_layout)
        
        return group
    
    def _create_tracking_group(self) -> QGroupBox:
        """Groupe de contrôles de tracking"""
        group = QGroupBox("🎬 Tracking")
        layout = QVBoxLayout(group)
        
        # Contrôles principaux
        controls_layout = QHBoxLayout()
        
        self.start_tracking_btn = QPushButton("Démarrer")
        self.start_tracking_btn.clicked.connect(self._start_tracking)
        
        self.stop_tracking_btn = QPushButton("Arrêter")
        self.stop_tracking_btn.clicked.connect(self._stop_tracking)
        self.stop_tracking_btn.setEnabled(False)
        
        controls_layout.addWidget(self.start_tracking_btn)
        controls_layout.addWidget(self.stop_tracking_btn)
        layout.addLayout(controls_layout)
        
        # Options depuis tracking_config.json
        tracking_config = self.config.get('tracking', {})  # Config tracking existante
        
        self.kalman_check = QCheckBox("Filtrage Kalman")
        self.kalman_check.setChecked(
            tracking_config.get('kalman_filter', {}).get('enabled', True))
        
        self.prediction_check = QCheckBox("Prédiction")
        self.prediction_check.setChecked(
            tracking_config.get('prediction', {}).get('enabled', True))
        
        layout.addWidget(self.kalman_check)
        layout.addWidget(self.prediction_check)
        
        # Export
        export_layout = QHBoxLayout()
        
        self.export_format = QComboBox()
        # Export depuis tracking_config.json étendu
        export_formats = self.ui_config.get('export', {}).get('formats', ['csv'])
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
        camera_alias = "target_camera"  # Alias pour cette vue
        self.camera_display = CameraDisplayWidget(camera_alias, self.config)
        self.camera_display.clicked.connect(self._on_display_clicked)
        
        layout.addWidget(self.camera_display)
        
        # Barre de contrôles bas
        controls_bar = self._create_display_controls()
        layout.addWidget(controls_bar)
        
        return area
    
    def _create_display_controls(self) -> QWidget:
        """Crée la barre de contrôles d'affichage"""
        bar = QFrame()
        bar.setFrameStyle(QFrame.Shape.StyledPanel)
        bar.setMaximumHeight(self.window_config.get('controls_bar_height', 60))
        
        layout = QHBoxLayout(bar)
        
        # Contrôles zoom
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 500)  # 0.1x à 5.0x
        self.zoom_slider.setValue(100)  # 1.0x
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        
        self.zoom_label = QLabel("100%")
        
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(self.zoom_label)
        layout.addLayout(zoom_layout)
        
        layout.addStretch()
        
        # Contrôles affichage
        self.show_ids_check = QCheckBox("IDs")
        self.show_ids_check.setChecked(True)
        
        self.show_confidence_check = QCheckBox("Confiance")
        self.show_confidence_check.setChecked(True)
        
        self.show_roi_check = QCheckBox("ROI")
        self.show_roi_check.setChecked(True)
        
        layout.addWidget(self.show_ids_check)
        layout.addWidget(self.show_confidence_check)
        layout.addWidget(self.show_roi_check)
        
        # Capture
        capture_btn = QPushButton("📷 Capturer")
        capture_btn.clicked.connect(self._capture_frame)
        layout.addWidget(capture_btn)
        
        return bar
    
    def _connect_signals(self):
        """Connecte les signaux"""
        # Timer de mise à jour
        update_interval = self.window_config.get('update_interval_ms', 33)
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(update_interval)
        
        # Timer statistiques
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(1000)  # 1 seconde
        
        # Caméra
        if hasattr(self.camera_manager, 'frame_ready'):
            self.camera_manager.frame_ready.connect(self._on_new_frame)
    
    def _load_default_aruco_folder(self):
        """Charge le dossier ArUco par défaut"""
        default_folder = self.target_config.get('aruco', {}).get('default_markers_folder', './ArUco')
        folder_path = Path(default_folder)
        
        if folder_path.exists():
            self._scan_aruco_folder(str(folder_path))
    
    def _browse_aruco_folder(self):
        """Ouvre un dialogue pour sélectionner le dossier ArUco"""
        folder = QFileDialog.getExistingDirectory(
            self, "Sélectionner le dossier des marqueurs ArUco")
        
        if folder:
            self._scan_aruco_folder(folder)
    
    def _scan_aruco_folder(self, folder_path: str):
        """Scanne le dossier ArUco"""
        self.scan_progress.setVisible(True)
        self.scan_progress.setRange(0, 0)  # Mode indéterminé
        self.scan_status.setText("Scan en cours...")
        
        try:
            # Scan des marqueurs
            markers = self.aruco_loader.scan_aruco_folder(folder_path)
            
            # Mise à jour interface
            self.folder_label.setText(Path(folder_path).name)
            self.folder_label.setStyleSheet("color: black; font-weight: bold;")
            
            self._update_markers_table(markers)
            
            # Activation boutons
            self.rescan_btn.setEnabled(True)
            self.config_btn.setEnabled(len(markers) > 0)
            
            # Statut
            summary = self.aruco_loader.get_summary()
            if summary['status'] == 'ready':
                self.scan_status.setText(f"✅ {summary['total_markers']} marqueurs détectés")
            else:
                self.scan_status.setText(f"⚠️ {summary['total_markers']} marqueurs, {len(summary['issues'])} problèmes")
                
        except Exception as e:
            logger.error(f"Erreur scan ArUco: {e}")
            self.scan_status.setText(f"❌ Erreur: {str(e)}")
            
        finally:
            self.scan_progress.setVisible(False)
    
    def _update_markers_table(self, markers: Dict):
        """Met à jour le tableau des marqueurs"""
        self.markers_table.setRowCount(len(markers))
        
        for row, (marker_id, marker_info) in enumerate(markers.items()):
            # ID
            id_item = QTableWidgetItem(str(marker_id))
            self.markers_table.setItem(row, 0, id_item)
            
            # Taille
            size_item = QTableWidgetItem(f"{marker_info.get('size_mm', '?')}mm")
            self.markers_table.setItem(row, 1, size_item)
            
            # État
            state = "✅ OK" if marker_info.get('enabled', True) else "❌ Désactivé"
            state_item = QTableWidgetItem(state)
            self.markers_table.setItem(row, 2, state_item)
    
    def _rescan_aruco_folder(self):
        """Re-scanne le dossier ArUco actuel"""
        if hasattr(self.aruco_loader, 'folder_path') and self.aruco_loader.folder_path:
            self._scan_aruco_folder(str(self.aruco_loader.folder_path))
    
    def _generate_aruco_config(self):
        """Génère la configuration ArUco automatique"""
        try:
            config_path = self.aruco_loader.generate_config_file()
            
            QMessageBox.information(self, "Configuration générée",
                f"Configuration ArUco sauvée:\n{config_path}\n\n"
                "La détection ArUco est maintenant optimisée.")
                
            logger.info(f"Configuration ArUco générée: {config_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de générer la configuration:\n{str(e)}")
    
    def _start_roi_creation(self, roi_type: ROIType):
        """Démarre la création d'une ROI"""
        if self.roi_manager.start_roi_creation(roi_type):
            self.scan_status.setText(f"Création ROI {roi_type.value}... Cliquez sur l'image")
        else:
            QMessageBox.warning(self, "Limite atteinte", 
                f"Maximum {self.roi_manager.max_roi_count} ROI autorisées")
    
    def _clear_all_rois(self):
        """Efface toutes les ROI"""
        reply = QMessageBox.question(self, "Confirmation", 
            "Supprimer toutes les ROI ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.roi_manager.rois.clear()
            self._update_roi_list()
    
    def _update_roi_list(self):
        """Met à jour la liste des ROI"""
        rois = self.roi_manager.rois
        self.roi_list.setRowCount(len(rois))
        
        for row, roi in enumerate(rois):
            name_item = QTableWidgetItem(roi.name)
            type_item = QTableWidgetItem(roi.roi_type.value)
            
            self.roi_list.setItem(row, 0, name_item)
            self.roi_list.setItem(row, 1, type_item)
    
    def _save_rois(self):
        """Sauvegarde les ROI"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder ROI", "rois.json", "JSON (*.json)")
        
        if filename:
            if self.roi_manager.save_rois_to_file(filename):
                QMessageBox.information(self, "Sauvegardé", f"ROI sauvées dans:\n{filename}")
    
    def _load_rois(self):
        """Charge les ROI depuis un fichier"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Charger ROI", "", "JSON (*.json)")
        
        if filename:
            if self.roi_manager.load_rois_from_file(filename):
                self._update_roi_list()
                QMessageBox.information(self, "Chargé", f"ROI chargées depuis:\n{filename}")
    
    def _start_tracking(self):
        """Démarre le tracking"""
        self.is_tracking = True
        self.tracking_data = []
        
        self.start_tracking_btn.setEnabled(False)
        self.stop_tracking_btn.setEnabled(True)
        
        self.tracking_started.emit()
        logger.info("Tracking démarré")
    
    def _stop_tracking(self):
        """Arrête le tracking"""
        self.is_tracking = False
        
        self.start_tracking_btn.setEnabled(True)
        self.stop_tracking_btn.setEnabled(False)
        
        self.tracking_stopped.emit()
        logger.info(f"Tracking arrêté - {len(self.tracking_data)} points enregistrés")
    
    def _export_tracking_data(self):
        """Exporte les données de tracking"""
        if not self.tracking_data:
            QMessageBox.information(self, "Aucune donnée", "Aucune donnée de tracking à exporter")
            return
            
        format_ext = self.export_format.currentText()
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exporter données tracking", f"tracking_data.{format_ext}")
        
        if filename:
            # TODO: Implémentation export selon format
            logger.info(f"Export tracking: {filename} ({format_ext})")
    
    def _on_display_clicked(self, point):
        """Gestion des clics sur l'affichage"""
        if self.roi_manager.is_creating:
            # Ajout point pour ROI en création
            if self.roi_manager.add_creation_point(point):
                # ROI terminée
                self._update_roi_list()
                self.scan_status.setText("ROI créée")
        else:
            # Sélection ROI existante
            roi_id = self.roi_manager.select_roi(point)
            if roi_id:
                self.scan_status.setText(f"ROI {roi_id} sélectionnée")
    
    def _on_new_frame(self, frame):
        """Nouvelle frame de la caméra"""
        self.current_frame = frame.copy()
        
        if self.is_tracking and frame is not None:
            # Détection des cibles
            detections = self.target_detector.detect_all_targets(frame)
            self.detected_targets = detections
            
            # Enregistrement données
            for detection in detections:
                self.tracking_data.append({
                    'timestamp': detection.timestamp,
                    'type': detection.target_type.value,
                    'id': detection.id,
                    'center': detection.center,
                    'confidence': detection.confidence
                })
    
    def _update_display(self):
        """Met à jour l'affichage"""
        if self.current_frame is None:
            return
            
        display_frame = self.current_frame.copy()
        
        # Dessin des détections
        if self.detected_targets and self.show_ids_check.isChecked():
            display_frame = self.target_detector.draw_detections(display_frame, self.detected_targets)
        
        # Dessin des ROI
        if self.show_roi_check.isChecked():
            display_frame = self.roi_manager.draw_rois(display_frame)
        
        # Mise à jour widget d'affichage
        self.camera_display.update_frame(display_frame)
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        stats = self.target_detector.get_detection_stats()
        roi_summary = self.roi_manager.get_roi_summary()
        
        # Labels
        fps = 1.0 / max(0.001, stats['last_detection_time'])
        self.fps_label.setText(f"FPS: {fps:.1f}")
        self.detections_label.setText(f"Détections: {stats['total_detections']}")
        self.targets_label.setText(f"Cibles actives: {len(self.detected_targets)}")
        self.roi_label.setText(f"ROI: {roi_summary['active_rois']}/{roi_summary['total_rois']}")
        
        # Texte détaillé
        stats_text = f"Temps détection: {stats['avg_detection_time']*1000:.1f}ms\n"
        stats_text += f"ArUco: {stats['detections_by_type'].get(TargetType.ARUCO, 0)}\n"
        stats_text += f"Réfléchissants: {stats['detections_by_type'].get(TargetType.REFLECTIVE, 0)}\n"
        stats_text += f"LEDs: {stats['detections_by_type'].get(TargetType.LED, 0)}"
        
        self.stats_text.setText(stats_text)
    
    def _on_zoom_changed(self, value):
        """Gestion du zoom"""
        zoom_factor = value / 100.0
        self.zoom_label.setText(f"{value}%")
        self.camera_display.set_zoom(zoom_factor)
    
    def _capture_frame(self):
        """Capture la frame actuelle"""
        if self.current_frame is not None:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Sauvegarder capture", "capture.png", "PNG (*.png)")
            
            if filename:
                cv2.imwrite(filename, self.current_frame)
                QMessageBox.information(self, "Capture", f"Image sauvée:\n{filename}")
    
    def _show_advanced_detection_params(self):
        """Affiche les paramètres avancés de détection"""
        # TODO: Dialogue paramètres avancés
        QMessageBox.information(self, "À venir", "Paramètres avancés en développement")
    
    def on_camera_ready(self, camera_info):
        """Callback quand la caméra est prête"""
        logger.info(f"Caméra prête pour tracking: {camera_info}")
    
    def closeEvent(self, event):
        """Nettoyage à la fermeture"""
        if self.is_tracking:
            self._stop_tracking()
            
        self.update_timer.stop()
        self.stats_timer.stop()
        
        event.accept()