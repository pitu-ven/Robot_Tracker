# ui/camera_tab.py
# Version 4.8 - Correction complète avec vue profondeur
# Modification: Correction erreur init_ui + implémentation vue profondeur

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

# Initialisation du logger
logger = logging.getLogger(__name__)

# Import du CameraDisplayWidget avancé avec support profondeur
try:
    from ui.camera_display_widget import CameraDisplayWidget
    ADVANCED_DISPLAY = True
    logger.debug("✅ CameraDisplayWidget avancé importé (support profondeur)")
except ImportError:
    # Fallback - widget simple sans profondeur
    ADVANCED_DISPLAY = False
    logger.warning("⚠️ Fallback vers widget simple (pas de profondeur)")
    
    class CameraDisplayWidget(QLabel):
        """Widget d'affichage simple pour une caméra - Fallback"""
        
        camera_clicked = pyqtSignal(str)
        
        def __init__(self, alias: str, config=None, parent=None):
            super().__init__(parent)
            self.alias = alias
            self.config = config
            self.show_depth = False
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setStyleSheet("border: 2px solid gray; background-color: black;")
            self.setMinimumSize(320, 240)
            self.setScaledContents(True)
            self.setText(f"Caméra: {alias}\n(En attente de frames)")
        
        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                self.camera_clicked.emit(self.alias)
            super().mousePressEvent(event)
        
        def update_frame(self, color_frame: np.ndarray, depth_frame: np.ndarray = None):
            """Met à jour avec RGB seulement (pas de profondeur)"""
            if color_frame is not None:
                frame_rgb = cv2.cvtColor(color_frame, cv2.COLOR_BGR2RGB)
                h, w = frame_rgb.shape[:2]
                bytes_per_line = w * 3
                qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                self.setPixmap(QPixmap.fromImage(qt_image))
        
        def set_depth_view(self, enabled: bool):
            """Pas de support profondeur dans le widget simple"""
            self.show_depth = False

class CameraTab(QWidget):
    """Onglet de gestion des caméras avec support profondeur complet"""
    
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
        
        # CORRECTION: Initialisation de l'interface
        self._init_ui()
        self._connect_signals()
        
        # Détection initiale des caméras
        self._detect_cameras()
        
        version = "4.8"
        support_profondeur = "avec" if ADVANCED_DISPLAY else "sans"
        logger.info(f"🎥 CameraTab v{version} initialisé ({support_profondeur} support profondeur)")

    def _init_ui(self):
        """Initialise l'interface utilisateur - CORRECTION nom méthode"""
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
        
        self.detect_btn = QPushButton("🔍 Détecter Caméras")
        self.detect_btn.clicked.connect(self._detect_cameras)
        camera_layout.addWidget(self.detect_btn)
        
        self.camera_combo = QComboBox()
        self.camera_combo.currentTextChanged.connect(self._on_camera_selected)
        camera_layout.addWidget(self.camera_combo)
        
        self.camera_info_label = QLabel("Sélectionnez une caméra")
        self.camera_info_label.setWordWrap(True)
        self.camera_info_label.setStyleSheet("background-color: #f0f0f0; padding: 8px; border-radius: 4px;")
        camera_layout.addWidget(self.camera_info_label)
        
        layout.addWidget(camera_group)
        
        # Section contrôles caméra
        control_group = QGroupBox("Contrôles Caméra")
        control_layout = QVBoxLayout(control_group)
        
        button_layout = QHBoxLayout()
        self.open_btn = QPushButton("📷 Ouvrir")
        self.open_btn.clicked.connect(self._open_selected_camera)
        self.close_btn = QPushButton("🚫 Fermer")
        self.close_btn.clicked.connect(self._close_selected_camera)
        
        button_layout.addWidget(self.open_btn)
        button_layout.addWidget(self.close_btn)
        control_layout.addLayout(button_layout)
        
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
        
        self.depth_checkbox = QCheckBox("Vue Profondeur")
        self.depth_checkbox.toggled.connect(self._toggle_depth_view)
        options_layout.addWidget(self.depth_checkbox)
        
        self.stats_checkbox = QCheckBox("Statistiques")
        self.stats_checkbox.toggled.connect(self._toggle_info_overlay)
        options_layout.addWidget(self.stats_checkbox)
        
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
        
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(2)
        self.stats_table.setHorizontalHeaderLabels(["Caméra", "Valeur"])
        self.stats_table.setMaximumHeight(120)
        stats_layout.addWidget(self.stats_table)
        
        layout.addWidget(stats_group)
        
        # Section log
        log_group = QGroupBox("Journal")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setFont(QFont("Consolas", 8))
        log_layout.addWidget(self.log_text)
        
        clear_log_btn = QPushButton("🗑️ Effacer")
        clear_log_btn.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_log_btn)
        
        layout.addWidget(log_group)
        
        return panel
    
    def _create_display_area(self):
        """Crée la zone d'affichage des caméras"""
        area = QScrollArea()
        area.setWidgetResizable(True)
        
        self.display_container = QWidget()
        self.display_layout = QGridLayout(self.display_container)
        
        self.default_message = QLabel("Aucune caméra active\n\n1. Détectez les caméras\n2. Sélectionnez une caméra\n3. Cliquez sur 'Ouvrir'\n4. Lancez le streaming")
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
        
        max_lines = self.config.get('ui', 'camera_tab.log.max_lines', 100)
        document = self.log_text.document()
        if document.blockCount() > max_lines:
            cursor = QTextCursor(document)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
    
    def _detect_cameras(self):
        """Détecte les caméras disponibles"""
        self._log("🔍 Détection des caméras...")
        
        try:
            cameras = self.camera_manager.detect_all_cameras()
            self.available_cameras = cameras
            
            self.camera_combo.clear()
            for camera in cameras:
                if isinstance(camera, dict):
                    camera_type = camera.get('type', 'unknown')
                    name = camera.get('name', 'Unknown Device')
                    serial = camera.get('serial', 'unknown')
                    
                    serial_short = serial[-8:] if len(serial) > 8 else serial
                    display_name = f"{name} ({camera_type} - {serial_short})"
                    self.camera_combo.addItem(display_name, camera)
                elif hasattr(camera, 'camera_type') and hasattr(camera, 'name'):
                    display_name = f"{camera.camera_type.value}: {camera.name}"
                    self.camera_combo.addItem(display_name, camera)
                else:
                    name = getattr(camera, 'name', str(camera))
                    display_name = f"Caméra: {name}"
                    self.camera_combo.addItem(display_name, camera)
            
            self._log(f"✅ {len(cameras)} caméra(s) détectée(s)")
            self.camera_info_label.setText(f"{len(cameras)} caméra(s) disponible(s)")
            
        except Exception as e:
            self._log(f"❌ Erreur détection: {e}")
            logger.error(f"Erreur détection caméras: {e}")
    
    def _on_camera_selected(self, text):
        """Gestion de la sélection d'une caméra"""
        camera_data = self.camera_combo.currentData()
        
        if camera_data:
            self.selected_camera = camera_data
            self._update_controls_state()
            
            if isinstance(camera_data, dict):
                camera_type = camera_data.get('type', 'unknown')
                name = camera_data.get('name', 'Unknown Device')
                serial = camera_data.get('serial', 'unknown')
                device_index = camera_data.get('device_index', 'N/A')
                
                info_text = f"Type: {camera_type}\nNom: {name}\nSerial: {serial}\nIndex: {device_index}"
                self.camera_info_label.setText(info_text)
                self._log(f"📷 Caméra sélectionnée: {name}")
                self.camera_selected.emit(name)
                
            elif hasattr(camera_data, 'camera_type'):
                info_text = f"Type: {camera_data.camera_type.value}\nNom: {camera_data.name}\nID: {camera_data.device_id}"
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
        
        self.open_btn.setEnabled(has_camera and not is_open)
        self.close_btn.setEnabled(has_camera and is_open)
        
        has_open_cameras = len(self.active_displays) > 0
        self.start_btn.setEnabled(has_open_cameras and not self.is_streaming)
        self.stop_btn.setEnabled(has_open_cameras and self.is_streaming)
        
        self.capture_btn.setEnabled(has_open_cameras and self.is_streaming)
        self.save_btn.setEnabled(has_open_cameras and self.is_streaming)
        
        # Vue profondeur (uniquement pour RealSense)
        if has_camera:
            is_realsense = False
            
            if isinstance(self.selected_camera, dict):
                camera_type = self.selected_camera.get('type', '').lower()
                is_realsense = 'realsense' in camera_type
            elif hasattr(self.selected_camera, 'camera_type'):
                camera_type_str = str(self.selected_camera.camera_type).lower()
                is_realsense = 'realsense' in camera_type_str
            
            self.depth_checkbox.setEnabled(is_realsense and ADVANCED_DISPLAY)
            if not (is_realsense and ADVANCED_DISPLAY):
                self.depth_checkbox.setChecked(False)
    
    def _get_camera_alias(self) -> str:
        """Génère l'alias pour la caméra courante"""
        if not self.selected_camera:
            return ""
        
        if isinstance(self.selected_camera, dict):
            camera_type = self.selected_camera.get('type', 'unknown')
            device_index = self.selected_camera.get('device_index', 0)
            return f"{camera_type}_{device_index}"
        elif hasattr(self.selected_camera, 'camera_type') and hasattr(self.selected_camera, 'device_id'):
            camera_type = getattr(self.selected_camera.camera_type, 'value', str(self.selected_camera.camera_type))
            return f"{camera_type}_{self.selected_camera.device_id}"
        elif isinstance(self.selected_camera, str):
            return f"camera_{hash(self.selected_camera) % 10000}"
        else:
            return f"unknown_{id(self.selected_camera) % 10000}"
    
    def _open_selected_camera(self):
        """Ouvre la caméra sélectionnée"""
        if not self.selected_camera:
            self._log("⚠️ Aucune caméra sélectionnée")
            return
        
        alias = self._get_camera_alias()
        
        # Gestion robuste du nom de caméra
        camera_name = "Caméra inconnue"
        if isinstance(self.selected_camera, dict):
            camera_name = self.selected_camera.get('name', 'Caméra dictionnaire')
        elif hasattr(self.selected_camera, 'name'):
            camera_name = self.selected_camera.name
        elif isinstance(self.selected_camera, str):
            camera_name = self.selected_camera
        else:
            camera_name = str(self.selected_camera)
        
        self._log(f"📷 Ouverture {camera_name}...")
        
        try:
            success = self.camera_manager.open_camera(self.selected_camera, alias)
            
            if success:
                self._log(f"✅ Caméra {alias} ouverte avec succès")
                self._add_camera_display(alias, camera_name)
                self._update_controls_state()
            else:
                self._log(f"❌ Échec ouverture {camera_name}")
                
        except Exception as e:
            self._log(f"❌ Erreur ouverture caméra: {e}")
            logger.error(f"Erreur ouverture caméra {camera_name}: {e}")
    
    def _close_selected_camera(self):
        """Ferme la caméra sélectionnée"""
        if not self.selected_camera:
            self._log("⚠️ Aucune caméra sélectionnée")
            return
        
        alias = self._get_camera_alias()
        
        try:
            success = self.camera_manager.close_camera(alias)
            
            if success:
                self._log(f"✅ Caméra {alias} fermée")
                self._remove_camera_display(alias)
                self._update_controls_state()
            else:
                self._log(f"❌ Erreur fermeture {alias}")
                
        except Exception as e:
            self._log(f"❌ Erreur fermeture caméra {alias}: {e}")
            logger.error(f"Erreur fermeture caméra {alias}: {e}")
    
    def _start_streaming(self):
        """Démarre le streaming"""
        if len(self.active_displays) == 0:
            self._log("⚠️ Aucune caméra ouverte pour le streaming")
            return
        
        self._log("▶️ Démarrage du streaming...")
        
        try:
            success = self.camera_manager.start_streaming()
            
            if success:
                self.is_streaming = True
                self.frame_timer.start(1000 // self.default_fps)
                
                self._log(f"✅ Streaming démarré à {self.default_fps} FPS")
                self.streaming_started.emit()
                self._update_controls_state()
            else:
                self._log("❌ Échec démarrage streaming")
                
        except Exception as e:
            self._log(f"❌ Erreur streaming: {e}")
            logger.error(f"Erreur démarrage streaming: {e}")
    
    def _stop_streaming(self):
        """Arrête le streaming"""
        if not self.is_streaming:
            return
        
        self._log("⏹️ Arrêt du streaming...")
        
        try:
            self.frame_timer.stop()
            self.stats_timer.stop()
            self.camera_manager.stop_streaming()
            
            self.is_streaming = False
            self._log("✅ Streaming arrêté")
            self.streaming_stopped.emit()
            self._update_controls_state()
            
        except Exception as e:
            self._log(f"❌ Erreur arrêt streaming: {e}")
            logger.error(f"Erreur arrêt streaming: {e}")
    
    def _toggle_depth_view(self):
        """Basculer l'affichage profondeur - IMPLÉMENTATION RÉELLE"""
        enabled = self.depth_checkbox.isChecked()
        state = "Activée" if enabled else "Désactivée"
        self._log(f"👁️ Vue profondeur: {state}")
        
        if not ADVANCED_DISPLAY:
            self._log("⚠️ Widget simple - Pas de support profondeur")
            self.depth_checkbox.setChecked(False)
            return
        
        # Mise à jour de tous les widgets d'affichage actifs
        updated_count = 0
        for alias, display_widget in self.active_displays.items():
            if hasattr(display_widget, 'set_depth_view'):
                display_widget.set_depth_view(enabled)
                updated_count += 1
                self._log(f"🔄 Vue profondeur {alias}: {'ON' if enabled else 'OFF'}")
        
        if updated_count > 0:
            self._reorganize_displays()
            self._log(f"✅ Vue profondeur mise à jour pour {updated_count} affichage(s)")
        else:
            self._log("⚠️ Aucun affichage compatible avec la vue profondeur")
    
    def _toggle_info_overlay(self):
        """Basculer l'affichage des infos"""
        enabled = self.stats_checkbox.isChecked()
        
        if enabled:
            self.stats_timer.start(self.stats_interval)
        else:
            self.stats_timer.stop()
            self.stats_table.setRowCount(0)
        
        self._log(f"📊 Statistiques: {'Activées' if enabled else 'Désactivées'}")
    
    def _update_camera_frames(self):
        """Met à jour les frames de toutes les caméras actives - Version avec profondeur"""
        if not self.is_streaming or len(self.active_displays) == 0:
            return
        
        try:
            for alias, display_widget in self.active_displays.items():
                ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(alias)
                
                if ret and color_frame is not None:
                    if ADVANCED_DISPLAY and hasattr(display_widget, 'update_frame'):
                        # Widget avancé - supporte RGB + Depth
                        display_widget.update_frame(color_frame, depth_frame)
                    elif hasattr(display_widget, 'update_frame'):
                        # Widget simple - RGB seulement
                        display_widget.update_frame(color_frame)
                    
        except Exception as e:
            self._log(f"❌ Erreur mise à jour frames: {e}")
            logger.error(f"Erreur mise à jour frames: {e}")
    
    def _add_camera_display(self, alias: str, name: str):
        """Ajoute un affichage pour une caméra - Version avec support profondeur"""
        self.default_message.hide()
        
        if ADVANCED_DISPLAY:
            display_widget = CameraDisplayWidget(alias, self.config)
            # CORRECTION: Le widget avancé émet 'clicked' pas 'camera_clicked'
            display_widget.clicked.connect(self._on_camera_display_clicked)
        else:
            display_widget = CameraDisplayWidget(alias, self.config)
            # Le widget simple émet 'camera_clicked'
            display_widget.camera_clicked.connect(self._on_camera_display_clicked)
        
        if ADVANCED_DISPLAY and hasattr(display_widget, 'set_depth_view'):
            depth_enabled = self.depth_checkbox.isChecked()
            display_widget.set_depth_view(depth_enabled)
        
        num_displays = len(self.active_displays)
        
        if self.depth_checkbox.isChecked() and ADVANCED_DISPLAY:
            max_cols = self.config.get('ui', 'camera_tab.layout.max_columns_dual', 2)
        else:
            max_cols = self.config.get('ui', 'camera_tab.layout.max_columns_single', 3)
        
        row = num_displays // max_cols
        col = num_displays % max_cols
        
        self.display_layout.addWidget(display_widget, row, col)
        self.active_displays[alias] = display_widget
        
        dual_mode = "dual" if (self.depth_checkbox.isChecked() and ADVANCED_DISPLAY) else "single"
        self._log(f"🖼️ Affichage {alias} ajouté (mode: {dual_mode})")
    
    def _remove_camera_display(self, alias: str):
        """Supprime l'affichage d'une caméra"""
        if alias in self.active_displays:
            display_widget = self.active_displays[alias]
            self.display_layout.removeWidget(display_widget)
            display_widget.deleteLater()
            del self.active_displays[alias]
            
            self._log(f"🗑️ Affichage supprimé pour {alias}")
            self._reorganize_displays()
    
    def _reorganize_displays(self):
        """Réorganise les affichages"""
        if len(self.active_displays) == 0:
            self.default_message.show()
            return
        
        if self.depth_checkbox.isChecked() and ADVANCED_DISPLAY:
            max_cols = self.config.get('ui', 'camera_tab.layout.max_columns_dual', 2)
        else:
            max_cols = self.config.get('ui', 'camera_tab.layout.max_columns_single', 3)
        
        for i, (alias, widget) in enumerate(self.active_displays.items()):
            row = i // max_cols
            col = i % max_cols
            self.display_layout.addWidget(widget, row, col)
    
    def _capture_frame(self):
        """Capture une frame"""
        if not self.selected_camera or len(self.active_displays) == 0:
            self._log("⚠️ Aucune caméra sélectionnée pour la capture")
            return
        
        alias = self._get_camera_alias()
        
        try:
            ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(alias)
            
            if ret and color_frame is not None:
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
        """Sauvegarde une image"""
        if not self.selected_camera or len(self.active_displays) == 0:
            self._log("⚠️ Aucune caméra sélectionnée pour la sauvegarde")
            return
        
        alias = self._get_camera_alias()
        
        try:
            ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(alias)
            
            if ret and color_frame is not None:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename_rgb = f"capture_{alias}_{timestamp}_rgb.png"
                
                success = cv2.imwrite(filename_rgb, color_frame)
                if success:
                    self._log(f"💾 Image RGB sauvegardée: {filename_rgb}")
                else:
                    self._log(f"❌ Erreur sauvegarde: {filename_rgb}")
                
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
    
    def _update_statistics(self):
        """Met à jour les statistiques"""
        try:
            current_row = 0
            self.stats_table.setRowCount(len(self.active_displays))
            
            for alias in self.active_displays:
                camera_item = QTableWidgetItem(alias)
                fps_estimate = int(1000 / max(1, self.frame_timer.interval()))
                
                self.stats_table.setItem(current_row, 0, camera_item)
                self.stats_table.setItem(current_row, 1, QTableWidgetItem(f"~{fps_estimate} FPS"))
                current_row += 1
                
        except Exception as e:
            logger.debug(f"Erreur mise à jour statistiques: {e}")
    
    def _on_size_changed(self, value):
        """Gestion du changement de taille d'affichage"""
        for display_widget in self.active_displays.values():
            if hasattr(display_widget, 'set_zoom'):
                display_widget.set_zoom(value / 100.0)
            else:
                base_size = QSize(320, 240)
                new_size = base_size * (value / 100.0)
                display_widget.setMinimumSize(new_size)
    
    def _on_camera_display_clicked(self, alias: str):
        """Gestion des clics sur les affichages caméra"""
        self._log(f"🖱️ Clic sur caméra: {alias}")
        
        for i in range(self.camera_combo.count()):
            camera_data = self.camera_combo.itemData(i)
            if camera_data:
                current_alias = ""
                
                if isinstance(camera_data, dict):
                    camera_type = camera_data.get('type', 'unknown')
                    device_index = camera_data.get('device_index', 0)
                    current_alias = f"{camera_type}_{device_index}"
                elif hasattr(camera_data, 'camera_type') and hasattr(camera_data, 'device_id'):
                    camera_type = getattr(camera_data.camera_type, 'value', str(camera_data.camera_type))
                    current_alias = f"{camera_type}_{camera_data.device_id}"
                elif isinstance(camera_data, str):
                    current_alias = f"camera_{hash(camera_data) % 10000}"
                
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