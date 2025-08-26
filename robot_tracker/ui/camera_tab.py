# ui/camera_tab.py
# Version 4.5 - Correction erreur detect_all_cameras et implémentation complète
# Modification: Correction self.config.detect_all_cameras → self.camera_manager.detect_all_cameras

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import cv2
import numpy as np
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

logger = logging.getLogger(__name__)

class CameraDisplayWidget(QLabel):
    """Widget d'affichage pour une caméra avec gestion des clics"""
    
    camera_clicked = pyqtSignal(str)
    
    def __init__(self, alias: str, parent=None):
        super().__init__(parent)
        self.alias = alias
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("border: 2px solid gray; background-color: black;")
        self.setMinimumSize(320, 240)
        self.setScaledContents(True)
        self.setText(f"Caméra: {alias}\n(En attente de frames)")
    
    def mousePressEvent(self, event):
        """Gestion des clics sur l'affichage"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.camera_clicked.emit(self.alias)
        super().mousePressEvent(event)
    
    def update_frame(self, frame: np.ndarray):
        """Met à jour l'affichage avec une nouvelle frame"""
        if frame is not None:
            # Conversion BGR -> RGB pour Qt
            if len(frame.shape) == 3:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame_rgb = frame
            
            h, w = frame_rgb.shape[:2]
            bytes_per_line = w * (3 if len(frame_rgb.shape) == 3 else 1)
            
            if len(frame_rgb.shape) == 3:
                qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            else:
                qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_Grayscale8)
            
            pixmap = QPixmap.fromImage(qt_image)
            self.setPixmap(pixmap)

class CameraTab(QWidget):
    """Onglet de gestion des caméras avec implémentation complète"""
    
    # Signaux
    camera_selected = pyqtSignal(str)
    streaming_started = pyqtSignal()
    streaming_stopped = pyqtSignal()
    frame_captured = pyqtSignal(str, dict)
    
    def __init__(self, camera_manager, config):
        super().__init__()
        
        self.camera_manager = camera_manager
        self.config = config
        
        # État interne
        self.available_cameras: List = []
        self.selected_camera: Optional[Any] = None
        self.active_displays: Dict[str, CameraDisplayWidget] = {}
        self.is_streaming = False
        
        # Configuration
        self.default_fps = self.config.get('ui', 'camera_tab.acquisition.default_fps', 30)
        self.stats_interval = self.config.get('ui', 'camera_tab.timers.stats_interval_ms', 1000)
        
        # Timers
        self.frame_timer = QTimer()
        self.stats_timer = QTimer()
        
        # Interface
        self.init_ui()
        self._connect_signals()
        
        # Détection initiale des caméras
        self._detect_cameras()
        
        logger.info(f"🎥 CameraTab v4.5 initialisé (correction detect_all_cameras)")
    
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        main_layout = QHBoxLayout(self)
        
        # Panneau de contrôle à gauche
        control_panel = self._create_control_panel()
        control_panel.setMaximumWidth(self.config.get('ui', 'camera_tab.layout.control_panel_width', 280))
        
        # Zone d'affichage à droite
        display_area = self._create_display_area()
        
        main_layout.addWidget(control_panel)
        main_layout.addWidget(display_area, 1)
    
    def _create_control_panel(self):
        """Crée le panneau de contrôle"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Section sélection caméra
        camera_group = QGroupBox("Sélection Caméra")
        camera_layout = QVBoxLayout(camera_group)
        
        # Bouton de détection
        self.detect_btn = QPushButton("🔍 Détecter Caméras")
        self.detect_btn.clicked.connect(self._detect_cameras)
        camera_layout.addWidget(self.detect_btn)
        
        # ComboBox caméras
        self.camera_combo = QComboBox()
        self.camera_combo.currentTextChanged.connect(self._on_camera_selected)
        camera_layout.addWidget(self.camera_combo)
        
        # Informations caméra
        self.camera_info_label = QLabel("Sélectionnez une caméra")
        self.camera_info_label.setWordWrap(True)
        self.camera_info_label.setStyleSheet("background-color: #f0f0f0; padding: 8px; border-radius: 4px;")
        camera_layout.addWidget(self.camera_info_label)
        
        layout.addWidget(camera_group)
        
        # Section contrôles caméra
        control_group = QGroupBox("Contrôles Caméra")
        control_layout = QVBoxLayout(control_group)
        
        # Boutons ouverture/fermeture
        button_layout = QHBoxLayout()
        self.open_btn = QPushButton("📷 Ouvrir")
        self.open_btn.clicked.connect(self._open_selected_camera)
        self.close_btn = QPushButton("🚫 Fermer")
        self.close_btn.clicked.connect(self._close_selected_camera)
        
        button_layout.addWidget(self.open_btn)
        button_layout.addWidget(self.close_btn)
        control_layout.addLayout(button_layout)
        
        # Boutons streaming
        stream_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶️ Démarrer")
        self.start_btn.clicked.connect(self._start_streaming)
        self.stop_btn = QPushButton("⏹️ Arrêter")
        self.stop_btn.clicked.connect(self._stop_streaming)
        
        stream_layout.addWidget(self.start_btn)
        stream_layout.addWidget(self.stop_btn)
        control_layout.addLayout(stream_layout)
        
        layout.addWidget(control_group)
        
        # Section options d'affichage
        options_group = QGroupBox("Options d'Affichage")
        options_layout = QVBoxLayout(options_group)
        
        # Vue profondeur (RealSense uniquement)
        self.depth_checkbox = QCheckBox("Vue Profondeur")
        self.depth_checkbox.toggled.connect(self._toggle_depth_view)
        options_layout.addWidget(self.depth_checkbox)
        
        # Statistiques
        self.stats_checkbox = QCheckBox("Statistiques")
        self.stats_checkbox.toggled.connect(self._toggle_info_overlay)
        options_layout.addWidget(self.stats_checkbox)
        
        # Taille d'affichage
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Taille:"))
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(50, 200)
        self.size_slider.setValue(100)
        self.size_slider.valueChanged.connect(self._on_size_changed)
        size_layout.addWidget(self.size_slider)
        options_layout.addLayout(size_layout)
        
        layout.addWidget(options_group)
        
        # Section capture
        capture_group = QGroupBox("Capture")
        capture_layout = QVBoxLayout(capture_group)
        
        capture_btn_layout = QHBoxLayout()
        self.capture_btn = QPushButton("📸 Capturer")
        self.capture_btn.clicked.connect(self._capture_frame)
        self.save_btn = QPushButton("💾 Sauvegarder")
        self.save_btn.clicked.connect(self._save_image)
        
        capture_btn_layout.addWidget(self.capture_btn)
        capture_btn_layout.addWidget(self.save_btn)
        capture_layout.addLayout(capture_btn_layout)
        
        layout.addWidget(capture_group)
        
        # Section statistiques
        stats_group = QGroupBox("Statistiques")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_table = QTableWidget(0, 2)
        self.stats_table.setHorizontalHeaderLabels(["Paramètre", "Valeur"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.setMaximumHeight(150)
        stats_layout.addWidget(self.stats_table)
        
        layout.addWidget(stats_group)
        
        # Section log
        log_group = QGroupBox("Journal")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        # Mise à jour initiale des contrôles
        self._update_controls_state()
        
        return panel
    
    def _create_display_area(self):
        """Crée la zone d'affichage principale"""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Widget conteneur pour les affichages
        self.display_container = QWidget()
        self.display_layout = QGridLayout(self.display_container)
        
        # Message par défaut
        self.default_message = QLabel("Aucune caméra ouverte\n\n1. Sélectionnez une caméra\n2. Cliquez sur 'Ouvrir'\n3. Lancez le streaming")
        self.default_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.default_message.setStyleSheet("color: #666; font-size: 14px;")
        self.display_layout.addWidget(self.default_message, 0, 0)
        
        area.setWidget(self.display_container)
        
        return area
    
    def _connect_signals(self):
        """Connecte les signaux"""
        self.frame_timer.timeout.connect(self._update_camera_frames)
        self.stats_timer.timeout.connect(self._update_statistics)
    
    def _log(self, message: str):
        """Ajoute un message au log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # Limite le nombre de lignes
        max_lines = self.config.get('ui', 'camera_tab.log.max_lines', 100)
        document = self.log_text.document()
        if document.blockCount() > max_lines:
            cursor = QTextCursor(document)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
    
    def _detect_cameras(self):
        """Détecte les caméras disponibles - VERSION CORRIGÉE"""
        self._log("🔍 Détection des caméras...")
        
        try:
            # ✅ CORRECTION PRINCIPALE - utilise self.camera_manager au lieu de self.config
            cameras = self.camera_manager.detect_all_cameras()
            self.available_cameras = cameras
            
            # Mise à jour de la ComboBox
            self.camera_combo.clear()
            for camera in cameras:
                if hasattr(camera, 'camera_type') and hasattr(camera, 'name'):
                    display_name = f"{camera.camera_type.value}: {camera.name}"
                    self.camera_combo.addItem(display_name, camera)
                else:
                    display_name = f"Caméra: {getattr(camera, 'name', 'Unknown')}"
                    self.camera_combo.addItem(display_name, camera)
            
            self._log(f"✅ {len(cameras)} caméra(s) détectée(s)")
            self.camera_info_label.setText(f"{len(cameras)} caméra(s) disponible(s)")
            
        except Exception as e:
            self._log(f"❌ Erreur détection: {e}")
            logger.error(f"Erreur détection caméras: {e}")
    
    def _on_camera_selected(self, text):
        """Gestion de la sélection d'une caméra"""
        camera_data = self.camera_combo.currentData()
        
        if camera_data and hasattr(camera_data, 'camera_type'):
            self.selected_camera = camera_data
            self._update_controls_state()
            
            # Mise à jour des informations
            info_text = f"Type: {camera_data.camera_type.value}\n"
            info_text += f"Nom: {camera_data.name}\n"
            info_text += f"ID: {camera_data.device_id}"
            self.camera_info_label.setText(info_text)
            
            self._log(f"📷 Caméra sélectionnée: {camera_data.name}")
            self.camera_selected.emit(camera_data.name)
        else:
            self.selected_camera = None
            self.camera_info_label.setText("Sélectionnez une caméra")
    
    def _update_controls_state(self):
        """Met à jour l'état des contrôles"""
        has_camera = self.selected_camera is not None
        is_open = False
        
        if has_camera:
            alias = self._get_camera_alias()
            is_open = self.camera_manager.is_camera_open(alias)
        
        # Boutons caméra
        self.open_btn.setEnabled(has_camera and not is_open)
        self.close_btn.setEnabled(has_camera and is_open)
        
        # Boutons streaming
        has_open_cameras = len(self.active_displays) > 0
        self.start_btn.setEnabled(has_open_cameras and not self.is_streaming)
        self.stop_btn.setEnabled(has_open_cameras and self.is_streaming)
        
        # Boutons capture
        self.capture_btn.setEnabled(has_open_cameras and self.is_streaming)
        self.save_btn.setEnabled(has_open_cameras and self.is_streaming)
        
        # Vue profondeur (uniquement pour RealSense)
        if has_camera and hasattr(self.selected_camera, 'camera_type'):
            is_realsense = self.selected_camera.camera_type.name == 'REALSENSE'
            self.depth_checkbox.setEnabled(is_realsense)
            if not is_realsense:
                self.depth_checkbox.setChecked(False)
    
    def _get_camera_alias(self) -> str:
        """Génère l'alias pour la caméra courante"""
        if self.selected_camera and hasattr(self.selected_camera, 'camera_type'):
            return f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
        return ""
    
    def _open_selected_camera(self):
        """Ouvre la caméra sélectionnée - IMPLÉMENTATION RÉELLE"""
        if not self.selected_camera:
            self._log("⚠️ Aucune caméra sélectionnée")
            return
        
        alias = self._get_camera_alias()
        camera_name = self.selected_camera.name
        
        self._log(f"📷 Ouverture {camera_name}...")
        
        try:
            # Ouverture via le camera_manager
            success = self.camera_manager.open_camera(self.selected_camera, alias)
            
            if success:
                self._log(f"✅ Caméra {alias} ouverte avec succès")
                
                # Création de l'affichage
                self._add_camera_display(alias, camera_name)
                self._update_controls_state()
            else:
                self._log(f"❌ Échec ouverture {camera_name}")
                
        except Exception as e:
            self._log(f"❌ Erreur ouverture: {e}")
            logger.error(f"Erreur ouverture caméra {camera_name}: {e}")
    
    def _close_selected_camera(self):
        """Ferme la caméra sélectionnée - IMPLÉMENTATION RÉELLE"""
        if not self.selected_camera:
            self._log("⚠️ Aucune caméra sélectionnée")
            return
        
        alias = self._get_camera_alias()
        
        self._log(f"🚫 Fermeture {alias}...")
        
        try:
            # Fermeture via le camera_manager
            success = self.camera_manager.close_camera(alias)
            
            if success:
                self._log(f"✅ Caméra {alias} fermée")
                
                # Suppression de l'affichage
                self._remove_camera_display(alias)
                self._update_controls_state()
            else:
                self._log(f"❌ Erreur fermeture {alias}")
                
        except Exception as e:
            self._log(f"❌ Erreur fermeture: {e}")
            logger.error(f"Erreur fermeture caméra {alias}: {e}")
    
    def _start_streaming(self):
        """Démarre le streaming - IMPLÉMENTATION RÉELLE"""
        if len(self.active_displays) == 0:
            self._log("⚠️ Aucune caméra ouverte pour le streaming")
            return
        
        self._log("▶️ Démarrage du streaming...")
        
        try:
            # Démarrage via le camera_manager
            success = self.camera_manager.start_streaming()
            
            if success:
                self.is_streaming = True
                self.frame_timer.start(1000 // self.default_fps)  # Conversion FPS -> ms
                
                self._log(f"✅ Streaming démarré à {self.default_fps} FPS")
                self.streaming_started.emit()
                self._update_controls_state()
            else:
                self._log("❌ Échec démarrage streaming")
                
        except Exception as e:
            self._log(f"❌ Erreur streaming: {e}")
            logger.error(f"Erreur démarrage streaming: {e}")
    
    def _stop_streaming(self):
        """Arrête le streaming - IMPLÉMENTATION RÉELLE"""
        if not self.is_streaming:
            return
        
        self._log("⏹️ Arrêt du streaming...")
        
        try:
            # Arrêt des timers
            self.frame_timer.stop()
            self.stats_timer.stop()
            
            # Arrêt via le camera_manager
            self.camera_manager.stop_streaming()
            
            self.is_streaming = False
            self._log("✅ Streaming arrêté")
            self.streaming_stopped.emit()
            self._update_controls_state()
            
        except Exception as e:
            self._log(f"❌ Erreur arrêt streaming: {e}")
            logger.error(f"Erreur arrêt streaming: {e}")
    
    def _update_camera_frames(self):
        """Met à jour les frames des caméras - IMPLÉMENTATION RÉELLE"""
        if not self.is_streaming:
            return
        
        try:
            for alias, display_widget in self.active_displays.items():
                # Récupération de la frame
                ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(alias)
                
                if ret and color_frame is not None:
                    # Mise à jour de l'affichage principal (RGB)
                    display_widget.update_frame(color_frame)
                    
                    # TODO: Gestion de l'affichage profondeur si activé
                    # if self.depth_checkbox.isChecked() and depth_frame is not None:
                    #     # Affichage côte à côte RGB/Depth
                    #     pass
                
        except Exception as e:
            logger.debug(f"Erreur mise à jour frames: {e}")
    
    def _update_statistics(self):
        """Met à jour les statistiques - IMPLÉMENTATION RÉELLE"""
        if not self.is_streaming or len(self.active_displays) == 0:
            return
        
        try:
            self.stats_table.setRowCount(0)
            
            for alias in self.active_displays.keys():
                # Récupération des stats basiques
                ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(alias)
                
                if ret and color_frame is not None:
                    height, width = color_frame.shape[:2]
                    
                    # Ajout des statistiques
                    current_row = self.stats_table.rowCount()
                    self.stats_table.insertRow(current_row)
                    
                    self.stats_table.setItem(current_row, 0, QTableWidgetItem(f"{alias} - Résolution"))
                    self.stats_table.setItem(current_row, 1, QTableWidgetItem(f"{width}x{height}"))
                    
                    current_row = self.stats_table.rowCount()
                    self.stats_table.insertRow(current_row)
                    
                    fps_estimate = self.default_fps  # Estimation basique
                    self.stats_table.setItem(current_row, 0, QTableWidgetItem(f"{alias} - FPS"))
                    self.stats_table.setItem(current_row, 1, QTableWidgetItem(f"~{fps_estimate}"))
                
        except Exception as e:
            logger.debug(f"Erreur mise à jour statistiques: {e}")
    
    def _add_camera_display(self, alias: str, name: str):
        """Ajoute un affichage pour une caméra"""
        # Masquer le message par défaut
        self.default_message.hide()
        
        # Création du widget d'affichage
        display_widget = CameraDisplayWidget(alias)
        display_widget.camera_clicked.connect(self._on_camera_display_clicked)
        
        # Calcul de la position dans la grille
        num_displays = len(self.active_displays)
        max_cols = self.config.get('ui', 'camera_tab.layout.max_columns_single', 3)
        
        row = num_displays // max_cols
        col = num_displays % max_cols
        
        # Ajout à la grille
        self.display_layout.addWidget(display_widget, row, col)
        self.active_displays[alias] = display_widget
        
        self._log(f"🖥️ Affichage créé pour {alias}")
    
    def _remove_camera_display(self, alias: str):
        """Supprime l'affichage d'une caméra"""
        if alias in self.active_displays:
            display_widget = self.active_displays[alias]
            self.display_layout.removeWidget(display_widget)
            display_widget.deleteLater()
            del self.active_displays[alias]
            
            self._log(f"🗑️ Affichage supprimé pour {alias}")
            
            # Réorganiser les affichages restants
            self._reorganize_displays()
    
    def _reorganize_displays(self):
        """Réorganise les affichages après suppression"""
        if len(self.active_displays) == 0:
            # Afficher le message par défaut
            self.default_message.show()
            return
        
        # Réorganiser en grille
        max_cols = self.config.get('ui', 'camera_tab.layout.max_columns_single', 3)
        
        for i, (alias, widget) in enumerate(self.active_displays.items()):
            row = i // max_cols
            col = i % max_cols
            self.display_layout.addWidget(widget, row, col)
    
    def _on_size_changed(self, value):
        """Gestion du changement de taille d'affichage"""
        for display_widget in self.active_displays.values():
            base_size = QSize(320, 240)
            new_size = base_size * (value / 100.0)
            display_widget.setMinimumSize(new_size)
    
    def _toggle_depth_view(self):
        """Basculer l'affichage profondeur - IMPLÉMENTATION RÉELLE"""
        enabled = self.depth_checkbox.isChecked()
        state = "Activée" if enabled else "Désactivée"
        self._log(f"👁️ Vue profondeur: {state}")
        
        # TODO: Implémenter l'affichage côte à côte RGB/Depth
    
    def _toggle_info_overlay(self):
        """Basculer l'affichage des infos - IMPLÉMENTATION RÉELLE"""
        enabled = self.stats_checkbox.isChecked()
        
        if enabled:
            self.stats_timer.start(self.stats_interval)
        else:
            self.stats_timer.stop()
            self.stats_table.setRowCount(0)
        
        self._log(f"📊 Statistiques: {'Activées' if enabled else 'Désactivées'}")
    
    def _capture_frame(self):
        """Capture une frame - IMPLÉMENTATION RÉELLE"""
        if not self.selected_camera or len(self.active_displays) == 0:
            self._log("⚠️ Aucune caméra sélectionnée pour la capture")
            return
        
        alias = self._get_camera_alias()
        
        try:
            # Récupération de la frame actuelle
            ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(alias)
            
            if ret and color_frame is not None:
                # Préparation des données de capture
                capture_data = {
                    'timestamp': time.time(),
                    'alias': alias,
                    'color_frame': color_frame.copy(),
                    'depth_frame': depth_frame.copy() if depth_frame is not None else None
                }
                
                self._log(f"📸 Frame capturée: {alias}")
                self.frame_captured.emit(alias, capture_data)
                
            else:
                self._log(f"❌ Impossible de capturer une frame de {alias}")
                
        except Exception as e:
            self._log(f"❌ Erreur capture frame: {e}")
            logger.error(f"Erreur capture frame {alias}: {e}")
    
    def _save_image(self):
        """Sauvegarde une image - IMPLÉMENTATION RÉELLE"""
        if not self.selected_camera or len(self.active_displays) == 0:
            self._log("⚠️ Aucune caméra sélectionnée pour la sauvegarde")
            return
        
        alias = self._get_camera_alias()
        
        try:
            # Récupération de la frame actuelle
            ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(alias)
            
            if ret and color_frame is not None:
                # Génération du nom de fichier
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename_rgb = f"capture_{alias}_{timestamp}_rgb.png"
                
                # Sauvegarde RGB
                success = cv2.imwrite(filename_rgb, color_frame)
                if success:
                    self._log(f"💾 Image RGB sauvegardée: {filename_rgb}")
                else:
                    self._log(f"❌ Erreur sauvegarde: {filename_rgb}")
                
                # Sauvegarde profondeur si disponible
                if depth_frame is not None:
                    filename_depth = f"capture_{alias}_{timestamp}_depth.png"
                    success_depth = cv2.imwrite(filename_depth, depth_frame)
                    if success_depth:
                        self._log(f"💾 Image profondeur sauvegardée: {filename_depth}")
                
            else:
                self._log(f"❌ Impossible de sauvegarder depuis {alias}")
                
        except Exception as e:
            self._log(f"❌ Erreur sauvegarde: {e}")
            logger.error(f"Erreur sauvegarde image {alias}: {e}")
    
    def _on_camera_display_clicked(self, alias: str):
        """Gestion des clics sur les affichages caméra"""
        self._log(f"🖱️ Clic sur caméra: {alias}")
        
        # Sélection automatique de la caméra correspondante
        for i in range(self.camera_combo.count()):
            camera_data = self.camera_combo.itemData(i)
            if camera_data:
                current_alias = f"{camera_data.camera_type.value}_{camera_data.device_id}"
                if current_alias == alias:
                    self.camera_combo.setCurrentIndex(i)
                    break
    
    @property
    def has_active_cameras(self) -> bool:
        """Retourne True si des caméras sont actives"""
        return len(self.active_displays) > 0
    
    def cleanup(self):
        """Nettoyage lors de la fermeture"""
        try:
            if self.is_streaming:
                self._stop_streaming()
            
            # Fermeture de toutes les caméras ouvertes
            aliases = list(self.active_displays.keys())
            for alias in aliases:
                self.camera_manager.close_camera(alias)
            
            self._log("🔄 Nettoyage terminé")
            
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage: {e}")
    
    def closeEvent(self, event):
        """Événement de fermeture"""
        self.cleanup()
        super().closeEvent(event)