#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/ui/camera_tab.py
Onglet de gestion des caméras avec streaming temps réel - Version 3.0
Modification: Intégration complète CameraManager avec visualisation multi-caméras
"""

import cv2
import numpy as np
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QSpinBox, QCheckBox,
    QGroupBox, QFrame, QSplitter, QTextEdit, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QSlider
)
from PyQt6.QtCore import QTimer, pyqtSignal, QThread, Qt, QSize
from PyQt6.QtGui import QPixmap, QImage, QFont, QIcon

import logging

try:
    from ..core.camera_manager import CameraManager, CameraType, CameraInfo
except ImportError:
    from core.camera_manager import CameraManager, CameraType, CameraInfo

logger = logging.getLogger(__name__)

class CameraDisplayWidget(QLabel):
    """Widget d'affichage d'une caméra avec overlay d'informations"""
    
    clicked = pyqtSignal(str)  # Signal émis lors du clic avec l'alias de la caméra
    
    def __init__(self, alias: str, parent=None):
        super().__init__(parent)
        self.alias = alias
        self.current_frame = None
        self.show_depth = False
        self.zoom_factor = 1.0
        
        # Configuration de l'affichage
        self.setMinimumSize(320, 240)
        self.setMaximumSize(800, 600)
        self.setScaledContents(True)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            QLabel {
                border: 2px solid #ccc;
                border-radius: 5px;
                background-color: #f0f0f0;
            }
            QLabel:hover {
                border-color: #007acc;
            }
        """)
        
        # Texte par défaut
        self.setText(f"Caméra: {alias}\nEn attente...")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Font pour le texte
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)
    
    def update_frame(self, color_frame: np.ndarray, depth_frame: np.ndarray = None):
        """Met à jour l'affichage avec une nouvelle frame"""
        try:
            if color_frame is None:
                return
            
            # Sélection de l'image à afficher
            if self.show_depth and depth_frame is not None:
                # Normalisation de la profondeur pour affichage
                depth_normalized = cv2.normalize(depth_frame, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                frame_to_display = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_JET)
            else:
                frame_to_display = color_frame.copy()
            
            # Application du zoom
            if self.zoom_factor != 1.0:
                h, w = frame_to_display.shape[:2]
                new_w, new_h = int(w * self.zoom_factor), int(h * self.zoom_factor)
                frame_to_display = cv2.resize(frame_to_display, (new_w, new_h))
            
            # Overlay d'informations
            self._add_overlay(frame_to_display)
            
            # Conversion pour Qt
            self.current_frame = frame_to_display
            self._update_qt_display(frame_to_display)
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour affichage {self.alias}: {e}")
    
    def _add_overlay(self, frame: np.ndarray):
        """Ajoute les informations en overlay sur l'image"""
        # Informations en haut à gauche
        overlay_text = [
            f"Camera: {self.alias}",
            f"Size: {frame.shape[1]}x{frame.shape[0]}",
            f"Mode: {'Depth' if self.show_depth else 'Color'}",
            f"Zoom: {self.zoom_factor:.1f}x"
        ]
        
        y_offset = 25
        for text in overlay_text:
            cv2.putText(frame, text, (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            y_offset += 25
        
        # Crosshair au centre
        h, w = frame.shape[:2]
        cv2.line(frame, (w//2 - 20, h//2), (w//2 + 20, h//2), (0, 255, 0), 2)
        cv2.line(frame, (w//2, h//2 - 20), (w//2, h//2 + 20), (0, 255, 0), 2)
    
    def _update_qt_display(self, frame: np.ndarray):
        """Met à jour l'affichage Qt avec la frame"""
        try:
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            
            q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
            pixmap = QPixmap.fromImage(q_image)
            
            self.setPixmap(pixmap)
            
        except Exception as e:
            logger.error(f"❌ Erreur conversion Qt: {e}")
    
    def mousePressEvent(self, event):
        """Gestion du clic sur l'affichage"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.alias)
    
    def toggle_depth_view(self):
        """Bascule entre vue couleur et profondeur"""
        self.show_depth = not self.show_depth
    
    def set_zoom(self, zoom: float):
        """Définit le facteur de zoom"""
        self.zoom_factor = max(0.1, min(5.0, zoom))

class CameraTab(QWidget):
    """Onglet de gestion des caméras avec streaming temps réel"""
    
    # Signaux
    camera_selected = pyqtSignal(str)  # Caméra sélectionnée
    frame_captured = pyqtSignal(str, object)  # Frame capturée
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        
        # Gestionnaire de caméras
        self.camera_manager = CameraManager(self.config)
        
        # État de l'interface
        self.available_cameras = []
        self.active_displays = {}  # alias -> CameraDisplayWidget
        self.is_streaming = False
        self.selected_camera = None
        
        # Timer pour mise à jour périodique
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_camera_frames)
        
        # Timer pour rafraîchissement des statistiques
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_statistics)
        
        # Initialisation de l'interface
        self._init_ui()
        self._connect_signals()
        
        # Détection initiale des caméras
        self._detect_cameras()
        
        logger.info("🎥 CameraTab initialisé")
    
    def _init_ui(self):
        """Initialise l'interface utilisateur"""
        layout = QHBoxLayout(self)
        
        # Création du splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Panel de contrôle (gauche)
        control_panel = self._create_control_panel()
        splitter.addWidget(control_panel)
        
        # Zone d'affichage des caméras (droite)
        display_area = self._create_display_area()
        splitter.addWidget(display_area)
        
        # Proportions du splitter
        splitter.setSizes([300, 700])
    
    def _create_control_panel(self) -> QWidget:
        """Crée le panel de contrôle des caméras"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # === Détection et sélection ===
        detection_group = QGroupBox("🔍 Détection & Sélection")
        detection_layout = QVBoxLayout(detection_group)
        
        # Bouton détection
        self.detect_btn = QPushButton("🔄 Détecter caméras")
        self.detect_btn.setMinimumHeight(35)
        detection_layout.addWidget(self.detect_btn)
        
        # Liste des caméras disponibles
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumHeight(30)
        detection_layout.addWidget(QLabel("Caméras disponibles:"))
        detection_layout.addWidget(self.camera_combo)
        
        # Boutons d'action
        btn_layout = QHBoxLayout()
        self.open_btn = QPushButton("📷 Ouvrir")
        self.close_btn = QPushButton("❌ Fermer")
        self.open_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        btn_layout.addWidget(self.open_btn)
        btn_layout.addWidget(self.close_btn)
        detection_layout.addLayout(btn_layout)
        
        layout.addWidget(detection_group)
        
        # === Streaming ===
        streaming_group = QGroupBox("🎬 Streaming")
        streaming_layout = QVBoxLayout(streaming_group)
        
        # Contrôles de streaming
        stream_btn_layout = QHBoxLayout()
        self.start_stream_btn = QPushButton("▶️ Démarrer")
        self.stop_stream_btn = QPushButton("⏹️ Arrêter")
        self.start_stream_btn.setEnabled(False)
        self.stop_stream_btn.setEnabled(False)
        stream_btn_layout.addWidget(self.start_stream_btn)
        stream_btn_layout.addWidget(self.stop_stream_btn)
        streaming_layout.addLayout(stream_btn_layout)
        
        # FPS et refresh rate
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("Refresh UI (ms):"))
        self.refresh_spinbox = QSpinBox()
        self.refresh_spinbox.setRange(16, 1000)  # 16ms = ~60 FPS max
        self.refresh_spinbox.setValue(50)  # 20 FPS par défaut
        self.refresh_spinbox.setSuffix(" ms")
        fps_layout.addWidget(self.refresh_spinbox)
        streaming_layout.addLayout(fps_layout)
        
        layout.addWidget(streaming_group)
        
        # === Affichage ===
        display_group = QGroupBox("🖼️ Affichage")
        display_layout = QVBoxLayout(display_group)
        
        # Zoom
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 500)  # 0.1x à 5.0x
        self.zoom_slider.setValue(100)  # 1.0x
        self.zoom_label = QLabel("1.0x")
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(self.zoom_label)
        display_layout.addLayout(zoom_layout)
        
        # Options d'affichage
        self.show_depth_cb = QCheckBox("Afficher profondeur (si disponible)")
        self.show_stats_cb = QCheckBox("Afficher statistiques")
        self.show_stats_cb.setChecked(True)
        display_layout.addWidget(self.show_depth_cb)
        display_layout.addWidget(self.show_stats_cb)
        
        layout.addWidget(display_group)
        
        # === Capture ===
        capture_group = QGroupBox("📸 Capture")
        capture_layout = QVBoxLayout(capture_group)
        
        self.capture_btn = QPushButton("📸 Capturer frame")
        self.save_btn = QPushButton("💾 Sauvegarder image")
        self.capture_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        capture_layout.addWidget(self.capture_btn)
        capture_layout.addWidget(self.save_btn)
        
        layout.addWidget(capture_group)
        
        # === Statistiques ===
        stats_group = QGroupBox("📊 Statistiques")
        stats_layout = QVBoxLayout(stats_group)
        
        # Tableau des statistiques
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(3)
        self.stats_table.setHorizontalHeaderLabels(["Propriété", "Valeur", "Unité"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.setMaximumHeight(200)
        stats_layout.addWidget(self.stats_table)
        
        layout.addWidget(stats_group)
        
        # === Log ===
        log_group = QGroupBox("📝 Journal")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setFont(QFont("Consolas", 8))
        log_layout.addWidget(self.log_text)
        
        # Bouton clear log
        self.clear_log_btn = QPushButton("🗑️ Effacer log")
        log_layout.addWidget(self.clear_log_btn)
        
        layout.addWidget(log_group)
        
        # Spacer en bas
        layout.addStretch()
        
        return panel
    
    def _create_display_area(self) -> QWidget:
        """Crée la zone d'affichage des caméras"""
        display_widget = QWidget()
        self.display_layout = QGridLayout(display_widget)
        
        # Label par défaut
        default_label = QLabel("Aucune caméra active\n\nSélectionnez et ouvrez une caméra\npour voir le streaming temps réel")
        default_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        default_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                border: 2px dashed #ccc;
                border-radius: 10px;
                padding: 50px;
                background-color: #f9f9f9;
            }
        """)
        self.display_layout.addWidget(default_label, 0, 0)
        
        return display_widget
    
    def _connect_signals(self):
        """Connecte les signaux de l'interface"""
        # Boutons principaux
        self.detect_btn.clicked.connect(self._detect_cameras)
        self.open_btn.clicked.connect(self._open_selected_camera)
        self.close_btn.clicked.connect(self._close_selected_camera)
        
        # Streaming
        self.start_stream_btn.clicked.connect(self._start_streaming)
        self.stop_stream_btn.clicked.connect(self._stop_streaming)
        
        # Capture
        self.capture_btn.clicked.connect(self._capture_frame)
        self.save_btn.clicked.connect(self._save_image)
        
        # Affichage
        self.zoom_slider.valueChanged.connect(self._update_zoom)
        self.show_depth_cb.toggled.connect(self._toggle_depth_view)
        self.refresh_spinbox.valueChanged.connect(self._update_refresh_rate)
        
        # Sélection
        self.camera_combo.currentTextChanged.connect(self._camera_selection_changed)
        
        # Log
        self.clear_log_btn.clicked.connect(self.log_text.clear)
    
    def _detect_cameras(self):
        """Détecte toutes les caméras disponibles"""
        self._log("🔍 Détection des caméras...")
        
        try:
            self.available_cameras = self.camera_manager.detect_all_cameras()
            
            # Mise à jour de la combo box
            self.camera_combo.clear()
            for camera in self.available_cameras:
                display_name = f"{camera.name} ({camera.camera_type.value})"
                self.camera_combo.addItem(display_name, camera)
            
            if self.available_cameras:
                self._log(f"✅ {len(self.available_cameras)} caméra(s) détectée(s)")
                self.open_btn.setEnabled(True)
            else:
                self._log("⚠️ Aucune caméra détectée")
                self.open_btn.setEnabled(False)
                
        except Exception as e:
            self._log(f"❌ Erreur détection: {e}")
    
    def _camera_selection_changed(self):
        """Gestion du changement de sélection de caméra"""
        current_data = self.camera_combo.currentData()
        if current_data:
            self.selected_camera = current_data
            self._log(f"📷 Caméra sélectionnée: {current_data.name}")
        else:
            self.selected_camera = None
    
    def _open_selected_camera(self):
        """Ouvre la caméra sélectionnée"""
        if not self.selected_camera:
            self._log("⚠️ Aucune caméra sélectionnée")
            return
        
        try:
            # Génération d'un alias unique
            alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
            
            # Vérification si déjà ouverte
            if alias in self.active_displays:
                self._log(f"⚠️ Caméra {alias} déjà ouverte")
                return
            
            self._log(f"📷 Ouverture {self.selected_camera.name}...")
            
            # Ouverture via le manager
            success = self.camera_manager.open_camera(self.selected_camera, alias)
            
            if success:
                # Création du widget d'affichage
                display_widget = CameraDisplayWidget(alias)
                display_widget.clicked.connect(self._camera_display_clicked)
                
                # Ajout à la grille d'affichage
                self._add_camera_display(alias, display_widget)
                
                # Activation des contrôles
                self._update_controls_state()
                
                self._log(f"✅ Caméra {alias} ouverte avec succès")
            else:
                self._log(f"❌ Échec ouverture {self.selected_camera.name}")
                
        except Exception as e:
            self._log(f"❌ Erreur ouverture caméra: {e}")
    
    def _close_selected_camera(self):
        """Ferme la caméra sélectionnée"""
        if not self.selected_camera:
            return
        
        alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
        self._close_camera(alias)
    
    def _close_camera(self, alias: str):
        """Ferme une caméra spécifique"""
        try:
            # Fermeture via le manager
            success = self.camera_manager.close_camera(alias)
            
            if success:
                # Suppression de l'affichage
                self._remove_camera_display(alias)
                
                # Mise à jour des contrôles
                self._update_controls_state()
                
                self._log(f"✅ Caméra {alias} fermée")
            else:
                self._log(f"❌ Erreur fermeture {alias}")
                
        except Exception as e:
            self._log(f"❌ Erreur fermeture caméra {alias}: {e}")
    
    def _add_camera_display(self, alias: str, display_widget: CameraDisplayWidget):
        """Ajoute un widget d'affichage à la grille"""
        # Suppression du label par défaut s'il existe
        if not self.active_displays:
            for i in reversed(range(self.display_layout.count())):
                self.display_layout.itemAt(i).widget().setParent(None)
        
        # Calcul de la position dans la grille
        num_cameras = len(self.active_displays)
        cols = min(2, num_cameras + 1)  # Max 2 colonnes
        row = num_cameras // cols
        col = num_cameras % cols
        
        # Ajout à la grille
        self.display_layout.addWidget(display_widget, row, col)
        self.active_displays[alias] = display_widget
        
        self._log(f"🖼️ Affichage {alias} ajouté à la grille")
    
    def _remove_camera_display(self, alias: str):
        """Supprime un widget d'affichage de la grille"""
        if alias in self.active_displays:
            widget = self.active_displays[alias]
            widget.setParent(None)
            del self.active_displays[alias]
            
            # Réorganisation de la grille
            self._reorganize_display_grid()
            
            self._log(f"🖼️ Affichage {alias} supprimé")
    
    def _reorganize_display_grid(self):
        """Réorganise la grille d'affichage"""
        if not self.active_displays:
            # Remise du label par défaut
            default_label = QLabel("Aucune caméra active\n\nSélectionnez et ouvrez une caméra\npour voir le streaming temps réel")
            default_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            default_label.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    color: #666;
                    border: 2px dashed #ccc;
                    border-radius: 10px;
                    padding: 50px;
                    background-color: #f9f9f9;
                }
            """)
            self.display_layout.addWidget(default_label, 0, 0)
            return
        
        # Repositionnement des widgets existants
        widgets = list(self.active_displays.values())
        for i, widget in enumerate(widgets):
            cols = min(2, len(widgets))
            row = i // cols
            col = i % cols
            self.display_layout.addWidget(widget, row, col)
    
    def _start_streaming(self):
        """Démarre le streaming temps réel"""
        if self.is_streaming:
            return
        
        if not self.active_displays:
            self._log("⚠️ Aucune caméra active pour le streaming")
            return
        
        try:
            self._log("🎬 Démarrage du streaming...")
            
            # Démarrage du streaming via le manager
            self.camera_manager.start_streaming(self._on_new_frames)
            
            # Démarrage des timers
            refresh_ms = self.refresh_spinbox.value()
            self.update_timer.start(refresh_ms)
            self.stats_timer.start(1000)  # Stats toutes les secondes
            
            self.is_streaming = True
            self._update_controls_state()
            
            self._log("✅ Streaming démarré")
            
        except Exception as e:
            self._log(f"❌ Erreur démarrage streaming: {e}")
    
    def _stop_streaming(self):
        """Arrête le streaming"""
        if not self.is_streaming:
            return
        
        try:
            self._log("🛑 Arrêt du streaming...")
            
            # Arrêt des timers
            self.update_timer.stop()
            self.stats_timer.stop()
            
            # Arrêt du streaming via le manager
            self.camera_manager.stop_streaming()
            
            self.is_streaming = False
            self._update_controls_state()
            
            self._log("✅ Streaming arrêté")
            
        except Exception as e:
            self._log(f"❌ Erreur arrêt streaming: {e}")
    
    def _on_new_frames(self, frames_data: dict):
        """Callback appelé lors de nouveaux frames"""
        # Cette méthode est appelée par le thread de streaming
        # Les mises à jour de l'interface se font dans _update_camera_frames
        pass
    
    def _update_camera_frames(self):
        """Met à jour l'affichage des frames de toutes les caméras"""
        if not self.is_streaming:
            return
        
        try:
            # Récupération des frames de toutes les caméras
            all_frames = self.camera_manager.get_all_frames()
            
            for alias, (ret, color_frame, depth_frame) in all_frames.items():
                if alias in self.active_displays and ret:
                    display_widget = self.active_displays[alias]
                    display_widget.update_frame(color_frame, depth_frame)
                    
        except Exception as e:
            self._log(f"❌ Erreur mise à jour frames: {e}")
    
    def _update_statistics(self):
        """Met à jour les statistiques affichées"""
        if not self.show_stats_cb.isChecked():
            return
        
        try:
            # Récupération des stats de toutes les caméras
            all_stats = self.camera_manager.get_all_stats()
            
            # Affichage dans le tableau (caméra sélectionnée ou première active)
            if self.selected_camera:
                alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
                if alias in all_stats:
                    self._display_camera_stats(all_stats[alias])
            elif all_stats:
                # Première caméra active
                first_alias = next(iter(all_stats))
                self._display_camera_stats(all_stats[first_alias])
                
        except Exception as e:
            self._log(f"❌ Erreur mise à jour stats: {e}")
    
    def _display_camera_stats(self, stats: dict):
        """Affiche les statistiques d'une caméra dans le tableau"""
        self.stats_table.setRowCount(0)
        
        # Propriétés à afficher
        display_props = [
            ("Nom", stats.get('name', 'N/A'), ""),
            ("Type", stats.get('type', 'N/A'), ""),
            ("Résolution", stats.get('resolution', stats.get('color_resolution', 'N/A')), "pixels"),
            ("FPS actuel", f"{stats.get('fps', 0):.1f}", "fps"),
            ("Frames total", str(stats.get('frame_count', 0)), ""),
            ("Dernière frame", time.strftime("%H:%M:%S", time.localtime(stats.get('last_timestamp', 0))), ""),
            ("État", "Actif" if stats.get('is_active', False) else "Inactif", "")
        ]
        
        # Ajout des propriétés spécifiques RealSense
        if stats.get('type') == 'realsense':
            depth_res = stats.get('depth_resolution', 'N/A')
            if depth_res != 'N/A':
                display_props.insert(3, ("Profondeur", depth_res, "pixels"))
        
        # Remplissage du tableau
        for i, (prop, value, unit) in enumerate(display_props):
            self.stats_table.insertRow(i)
            self.stats_table.setItem(i, 0, QTableWidgetItem(prop))
            self.stats_table.setItem(i, 1, QTableWidgetItem(str(value)))
            self.stats_table.setItem(i, 2, QTableWidgetItem(unit))
    
    def _update_controls_state(self):
        """Met à jour l'état des contrôles selon le contexte"""
        has_cameras = len(self.active_displays) > 0
        
        # Boutons de base
        self.close_btn.setEnabled(self.selected_camera is not None and has_cameras)
        
        # Streaming
        self.start_stream_btn.setEnabled(has_cameras and not self.is_streaming)
        self.stop_stream_btn.setEnabled(self.is_streaming)
        
        # Capture
        self.capture_btn.setEnabled(has_cameras and self.is_streaming)
        self.save_btn.setEnabled(has_cameras)
    
    def _update_refresh_rate(self):
        """Met à jour la fréquence de rafraîchissement"""
        if self.is_streaming:
            refresh_ms = self.refresh_spinbox.value()
            self.update_timer.setInterval(refresh_ms)
            self._log(f"🔄 Refresh rate: {1000/refresh_ms:.1f} FPS")
    
    def _update_zoom(self):
        """Met à jour le zoom de tous les affichages"""
        zoom_value = self.zoom_slider.value()
        zoom_factor = zoom_value / 100.0  # 100 = 1.0x
        self.zoom_label.setText(f"{zoom_factor:.1f}x")
        
        # Application à tous les affichages
        for display_widget in self.active_displays.values():
            display_widget.set_zoom(zoom_factor)
    
    def _toggle_depth_view(self):
        """Bascule l'affichage profondeur sur tous les widgets"""
        show_depth = self.show_depth_cb.isChecked()
        
        for display_widget in self.active_displays.values():
            display_widget.show_depth = show_depth
        
        self._log(f"👁️ Vue profondeur: {'Activée' if show_depth else 'Désactivée'}")
    
    def _camera_display_clicked(self, alias: str):
        """Gestion du clic sur un affichage de caméra"""
        self._log(f"🖱️ Clic sur caméra: {alias}")
        self.camera_selected.emit(alias)
    
    def _capture_frame(self):
        """Capture une frame de la caméra sélectionnée"""
        if not self.selected_camera:
            self._log("⚠️ Aucune caméra sélectionnée pour la capture")
            return
        
        alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
        
        try:
            ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(alias)
            
            if ret and color_frame is not None:
                # Émission du signal avec la frame
                frame_data = {
                    'alias': alias,
                    'color': color_frame,
                    'depth': depth_frame,
                    'timestamp': time.time()
                }
                self.frame_captured.emit(alias, frame_data)
                self._log(f"📸 Frame capturée: {alias}")
            else:
                self._log(f"❌ Impossible de capturer une frame de {alias}")
                
        except Exception as e:
            self._log(f"❌ Erreur capture frame: {e}")
    
    def _save_image(self):
        """Sauvegarde l'image de la caméra sélectionnée"""
        if not self.selected_camera:
            self._log("⚠️ Aucune caméra sélectionnée pour la sauvegarde")
            return
        
        # Sélection du fichier
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        default_name = f"camera_{self.selected_camera.camera_type.value}_{timestamp}.jpg"
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Sauvegarder image",
            default_name,
            "Images (*.jpg *.jpeg *.png);;Tous les fichiers (*)"
        )
        
        if filepath:
            alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
            success = self.camera_manager.save_camera_frame(alias, filepath)
            
            if success:
                self._log(f"💾 Image sauvegardée: {filepath}")
            else:
                self._log(f"❌ Erreur sauvegarde: {filepath}")
    
    def _log(self, message: str):
        """Ajoute un message au log avec timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self.log_text.append(formatted_message)
        
        # Auto-scroll
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
        
        # Limitation du nombre de lignes
        if self.log_text.document().blockCount() > 100:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
    
    def closeEvent(self, event):
        """Nettoyage lors de la fermeture"""
        try:
            self._stop_streaming()
            self.camera_manager.close_all_cameras()
            self._log("🔄 Nettoyage terminé")
        except Exception as e:
            logger.error(f"❌ Erreur nettoyage: {e}")
        
        event.accept()
    
    # === Méthodes publiques pour intégration ===
    
    def get_active_cameras(self) -> dict:
        """Retourne les caméras actives"""
        return {alias: data['info'] for alias, data in self.camera_manager.active_cameras.items()}
    
    def get_camera_intrinsics(self, alias: str) -> dict:
        """Récupère les paramètres intrinsèques d'une caméra"""
        return self.camera_manager.get_camera_intrinsics(alias)
    
    def is_camera_streaming(self) -> bool:
        """Indique si le streaming est actif"""
        return self.is_streaming
    
    def get_current_frame(self, alias: str) -> tuple:
        """Récupère la frame actuelle d'une caméra"""
        return self.camera_manager.get_camera_frame(alias)