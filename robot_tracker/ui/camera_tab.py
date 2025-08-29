# ui/camera_tab.py
# Version 4.9 - Correction détection RealSense pour vue profondeur
# Modification: Fix logique de détection du type RealSense dans _update_controls_state()

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
            """Met à jour la frame affichée - Version simple"""
            if color_frame is None:
                return
            
            try:
                height, width, channel = color_frame.shape
                bytes_per_line = 3 * width
                q_image = QImage(color_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
                pixmap = QPixmap.fromImage(q_image)
                self.setPixmap(pixmap)
            except Exception as e:
                logger.error(f"❌ Erreur mise à jour frame {self.alias}: {e}")


class CameraTab(QWidget):
    """Onglet principal de gestion des caméras avec support profondeur - v4.9"""
    
    # Signaux
    streaming_started = pyqtSignal()
    streaming_stopped = pyqtSignal()
    camera_opened = pyqtSignal(str)
    camera_closed = pyqtSignal(str)
    
    def __init__(self, camera_manager, config, parent=None):
        super().__init__(parent)
        self.camera_manager = camera_manager
        self.config = config
        
        # Variables d'état
        self.available_cameras = {}
        self.selected_camera = None
        self.active_displays = {}
        self.is_streaming = False
        
        # Paramètres configurables
        version = self.config.get('ui', 'camera_tab.version', '4.9')
        self.fps = self.config.get('ui', 'camera_tab.acquisition.default_fps', 30)
        self.stats_interval = self.config.get('ui', 'camera_tab.timers.stats_interval_ms', 1000)
        self.max_log_lines = self.config.get('ui', 'camera_tab.log.max_lines', 100)
        
        # Timers
        self.frame_timer = QTimer()
        self.frame_timer.timeout.connect(self._update_camera_frames)
        
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_stats)
        
        # Interface utilisateur
        self._init_ui()
        self._update_controls_state()
        
        logger.info(f"🎥 CameraTab v{version} initialisé (avec support profondeur)")
    
    def _init_ui(self):
        """Initialise l'interface utilisateur"""
        main_layout = QHBoxLayout(self)
        
        # Panneau de contrôle (gauche)
        control_panel = self._create_control_panel()
        control_width = self.config.get('ui', 'camera_tab.layout.control_panel_width', 280)
        control_panel.setMaximumWidth(control_width)
        
        # Zone d'affichage (droite)
        display_area = self._create_display_area()
        display_width = self.config.get('ui', 'camera_tab.layout.display_area_width', 800)
        display_area.setMinimumWidth(display_width)
        
        main_layout.addWidget(control_panel)
        main_layout.addWidget(display_area, 1)
    
    def _create_control_panel(self):
        """Crée le panneau de contrôle"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Détection et sélection des caméras
        detection_group = QGroupBox("🔍 Détection & Sélection")
        detection_layout = QVBoxLayout(detection_group)
        
        self.detect_btn = QPushButton("🔄 Détecter caméras")
        self.detect_btn.clicked.connect(self._detect_cameras)
        detection_layout.addWidget(self.detect_btn)
        
        detection_layout.addWidget(QLabel("Caméras disponibles:"))
        self.camera_list = QListWidget()
        self.camera_list.itemClicked.connect(self._on_camera_selected)
        detection_layout.addWidget(self.camera_list)
        
        # Boutons d'ouverture/fermeture
        button_layout = QHBoxLayout()
        self.open_btn = QPushButton("📷 Ouvrir")
        self.open_btn.clicked.connect(self._open_selected_camera)
        self.close_btn = QPushButton("🚫 Fermer")
        self.close_btn.clicked.connect(self._close_selected_camera)
        
        button_layout.addWidget(self.open_btn)
        button_layout.addWidget(self.close_btn)
        detection_layout.addLayout(button_layout)
        
        layout.addWidget(detection_group)
        
        # Contrôles de streaming
        streaming_group = QGroupBox("🎬 Streaming")
        streaming_layout = QVBoxLayout(streaming_group)
        
        stream_button_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶️ Démarrer")
        self.start_btn.clicked.connect(self._start_streaming)
        self.stop_btn = QPushButton("⏹️ Arrêter")
        self.stop_btn.clicked.connect(self._stop_streaming)
        
        stream_button_layout.addWidget(self.start_btn)
        stream_button_layout.addWidget(self.stop_btn)
        streaming_layout.addLayout(stream_button_layout)
        
        # FPS
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("Refresh UI (ms):"))
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(16, 1000)
        self.fps_spinbox.setValue(1000 // self.fps)
        self.fps_spinbox.valueChanged.connect(self._on_fps_changed)
        fps_layout.addWidget(self.fps_spinbox)
        streaming_layout.addLayout(fps_layout)
        
        layout.addWidget(streaming_group)
        
        # Options d'affichage
        display_group = QGroupBox("🖼️ Affichage")
        display_layout = QVBoxLayout(display_group)
        
        # CORRECTION CRITIQUE: Checkbox vue profondeur avec tooltips dynamiques
        self.depth_checkbox = QCheckBox("Vue Profondeur")
        self.depth_checkbox.toggled.connect(self._toggle_depth_view)
        display_layout.addWidget(self.depth_checkbox)
        
        # Zoom
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 500)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        self.zoom_label = QLabel("1.0x")
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(self.zoom_label)
        display_layout.addLayout(zoom_layout)
        
        # Statistiques
        self.stats_checkbox = QCheckBox("Afficher statistiques")
        self.stats_checkbox.toggled.connect(self._toggle_info_overlay)
        display_layout.addWidget(self.stats_checkbox)
        
        layout.addWidget(display_group)
        
        # Capture
        capture_group = QGroupBox("📸 Capture")
        capture_layout = QVBoxLayout(capture_group)
        
        self.capture_btn = QPushButton("📸 Capturer frame")
        self.capture_btn.clicked.connect(self._capture_frame)
        capture_layout.addWidget(self.capture_btn)
        
        self.save_btn = QPushButton("💾 Sauvegarder image")
        self.save_btn.clicked.connect(self._save_image)
        capture_layout.addWidget(self.save_btn)
        
        layout.addWidget(capture_group)
        
        # Statistiques
        stats_group = QGroupBox("📊 Statistiques")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(2)
        self.stats_table.setHorizontalHeaderLabels(["Métrique", "Valeur"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.setMaximumHeight(150)
        stats_layout.addWidget(self.stats_table)
        
        layout.addWidget(stats_group)
        
        # Journal
        log_group = QGroupBox("📝 Journal")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(100)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        clear_log_btn = QPushButton("🗑️ Effacer log")
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_layout.addWidget(clear_log_btn)
        
        layout.addWidget(log_group)
        layout.addStretch()
        
        return panel
    
    def _create_display_area(self):
        """Crée la zone d'affichage des caméras"""
        area = QWidget()
        main_layout = QVBoxLayout(area)
        
        # Scroll area pour plusieurs caméras
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Widget conteneur des displays
        display_container = QWidget()
        self.display_layout = QGridLayout(display_container)
        self.display_layout.setSpacing(self.config.get('ui', 'camera_tab.layout.grid_spacing', 15))
        
        # Message par défaut
        self.default_message = QLabel("Aucune caméra active\n\nSélectionnez et ouvrez une caméra\npour voir le streaming temps réel")
        self.default_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.default_message.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 16px;
                font-style: italic;
                padding: 50px;
            }
        """)
        self.display_layout.addWidget(self.default_message, 0, 0)
        
        scroll.setWidget(display_container)
        main_layout.addWidget(scroll)
        
        return area
    
    # CORRECTION CRITIQUE: Fonction de détection RealSense améliorée
    def _is_realsense_camera(self, camera_data) -> bool:
        """Détecte si une caméra est de type RealSense - Version corrigée"""
        if not camera_data:
            return False
        
        # Méthode 1: Vérification par dictionnaire (nouveau format)
        if isinstance(camera_data, dict):
            camera_type = camera_data.get('type', '').lower()
            camera_name = camera_data.get('name', '').lower()
            return 'realsense' in camera_type or 'realsense' in camera_name
        
        # Méthode 2: Vérification par attribut camera_type
        if hasattr(camera_data, 'camera_type'):
            camera_type_str = str(camera_data.camera_type).lower()
            return 'realsense' in camera_type_str
        
        # Méthode 3: Vérification par nom/attributs
        if hasattr(camera_data, 'name'):
            camera_name = str(camera_data.name).lower()
            if 'realsense' in camera_name:
                return True
        
        # Méthode 4: Vérification par alias
        alias = self._get_camera_alias()
        if alias and 'realsense' in alias.lower():
            return True
        
        # Méthode 5: Vérification dans le camera_manager
        if hasattr(self.camera_manager, 'cameras'):
            for serial, info in self.camera_manager.cameras.items():
                if info.get('type', '').lower() == 'realsense':
                    return True
        
        return False
    
    def _update_controls_state(self):
        """Met à jour l'état des contrôles - Version corrigée pour RealSense"""
        has_cameras = len(self.available_cameras) > 0
        has_camera = self.selected_camera is not None
        has_open_cameras = len(self.active_displays) > 0
        
        # Contrôles de base
        self.open_btn.setEnabled(has_camera)
        self.close_btn.setEnabled(has_open_cameras)
        
        self.start_btn.setEnabled(has_open_cameras and not self.is_streaming)
        self.stop_btn.setEnabled(has_open_cameras and self.is_streaming)
        
        self.capture_btn.setEnabled(has_open_cameras and self.is_streaming)
        self.save_btn.setEnabled(has_open_cameras and self.is_streaming)
        
        # CORRECTION CRITIQUE: Vue profondeur (uniquement pour RealSense)
        is_realsense = self._is_realsense_camera(self.selected_camera)
        
        if ADVANCED_DISPLAY and is_realsense:
            self.depth_checkbox.setEnabled(True)
            self.depth_checkbox.setToolTip("Active la vue profondeur à côté de la vue RGB")
            logger.debug(f"✅ Vue profondeur activée pour caméra RealSense")
        else:
            self.depth_checkbox.setEnabled(False)
            self.depth_checkbox.setChecked(False)
            if not ADVANCED_DISPLAY:
                self.depth_checkbox.setToolTip("Widget avancé requis pour la vue profondeur")
            elif not is_realsense:
                self.depth_checkbox.setToolTip("Vue profondeur disponible uniquement avec RealSense")
            else:
                self.depth_checkbox.setToolTip("Vue profondeur non disponible")
            
            logger.debug(f"⚠️ Vue profondeur désactivée - RealSense: {is_realsense}, Avancé: {ADVANCED_DISPLAY}")
    
    def _detect_cameras(self):
        """Détecte les caméras disponibles"""
        self._log("🔍 Détection des caméras...")
        
        try:
            detected = self.camera_manager.detect_cameras()
            self.available_cameras = detected
            
            self.camera_list.clear()
            
            for serial, camera_info in detected.items():
                name = camera_info.get('name', 'Caméra inconnue')
                camera_type = camera_info.get('type', 'unknown')
                item_text = f"{name} ({camera_type}) - {serial[:8]}..."
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, camera_info)
                self.camera_list.addItem(item)
            
            count = len(detected)
            if count > 0:
                self._log(f"✅ {count} caméra(s) détectée(s)")
            else:
                self._log("⚠️ Aucune caméra détectée")
                
            self._update_controls_state()
            
        except Exception as e:
            self._log(f"❌ Erreur détection: {e}")
            logger.error(f"Erreur détection caméras: {e}")
    
    def _on_camera_selected(self, item):
        """Gestion de la sélection d'une caméra"""
        self.selected_camera = item.data(Qt.ItemDataRole.UserRole)
        
        if self.selected_camera:
            name = self.selected_camera.get('name', 'Caméra sélectionnée')
            self._log(f"📷 Caméra sélectionnée: {name}")
            
        self._update_controls_state()
    
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
        
        if self.camera_manager.is_camera_open(alias):
            self._log(f"⚠️ Caméra {alias} déjà ouverte")
            return
        
        self._log(f"📷 Ouverture {camera_name}...")
        
        try:
            success = self.camera_manager.open_camera(self.selected_camera, alias)
            
            if success:
                self._log(f"✅ Caméra {alias} ouverte avec succès")
                self._add_camera_display(alias, camera_name)
                self.camera_opened.emit(alias)
                self._update_controls_state()
            else:
                self._log(f"❌ Échec ouverture {camera_name}")
                
        except Exception as e:
            self._log(f"❌ Erreur ouverture caméra: {e}")
            logger.error(f"Erreur ouverture caméra {camera_name}: {e}")
    
    def _close_selected_camera(self):
        """Ferme la caméra sélectionnée"""
        if not self.active_displays:
            self._log("⚠️ Aucune caméra ouverte")
            return
        
        # Ferme la première caméra active (ou toutes)
        aliases_to_close = list(self.active_displays.keys())
        
        for alias in aliases_to_close:
            try:
                self.camera_manager.close_camera(alias)
                self._remove_camera_display(alias)
                self._log(f"✅ Caméra {alias} fermée")
                self.camera_closed.emit(alias)
                
            except Exception as e:
                self._log(f"❌ Erreur fermeture {alias}: {e}")
                logger.error(f"Erreur fermeture caméra {alias}: {e}")
        
        self._update_controls_state()
    
    def _start_streaming(self):
        """Démarre le streaming"""
        if self.is_streaming:
            return
        
        self._log("🎬 Démarrage du streaming...")
        
        try:
            self.camera_manager.start_streaming()
            
            refresh_rate = self.fps_spinbox.value()
            self.frame_timer.start(refresh_rate)
            
            if self.stats_checkbox.isChecked():
                self.stats_timer.start(self.stats_interval)
            
            self.is_streaming = True
            self._log("✅ Streaming démarré")
            self.streaming_started.emit()
            self._update_controls_state()
            
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
            display_widget.clicked.connect(self._on_camera_display_clicked)
        else:
            display_widget = CameraDisplayWidget(alias, self.config)
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
        
        is_dual = self.depth_checkbox.isChecked() and ADVANCED_DISPLAY
        self._log(f"🖼️ Affichage {alias} ajouté (vue double: {is_dual})")
    
    def _remove_camera_display(self, alias: str):
        """Supprime un affichage de caméra"""
        if alias in self.active_displays:
            display_widget = self.active_displays[alias]
            self.display_layout.removeWidget(display_widget)
            display_widget.deleteLater()
            del self.active_displays[alias]
            
            self._log(f"🖼️ Affichage {alias} supprimé")
            
            if len(self.active_displays) == 0:
                self.default_message.show()
            else:
                self._reorganize_displays()
    
    def _reorganize_displays(self):
        """Réorganise l'affichage des caméras"""
        if not self.active_displays:
            return
        
        # Supprime tous les widgets du layout
        for alias, widget in self.active_displays.items():
            self.display_layout.removeWidget(widget)
        
        # Recalcule les positions
        if self.depth_checkbox.isChecked() and ADVANCED_DISPLAY:
            max_cols = self.config.get('ui', 'camera_tab.layout.max_columns_dual', 2)
        else:
            max_cols = self.config.get('ui', 'camera_tab.layout.max_columns_single', 3)
        
        for i, (alias, widget) in enumerate(self.active_displays.items()):
            row = i // max_cols
            col = i % max_cols
            self.display_layout.addWidget(widget, row, col)
    
    def _on_camera_display_clicked(self, alias: str):
        """Gestion du clic sur un affichage de caméra"""
        self._log(f"🖱️ Clic sur caméra {alias}")
    
    def _on_fps_changed(self, value):
        """Gestion du changement de FPS"""
        if self.is_streaming:
            self.frame_timer.setInterval(value)
        
        fps = 1000 / value if value > 0 else 0
        self._log(f"🔄 Refresh rate: {value}ms (~{fps:.1f} FPS)")
    
    def _on_zoom_changed(self, value):
        """Gestion du changement de zoom"""
        zoom_factor = value / 100.0
        self.zoom_label.setText(f"{zoom_factor:.1f}x")
        
        # Applique le zoom à tous les widgets d'affichage
        for display_widget in self.active_displays.values():
            if hasattr(display_widget, 'set_zoom'):
                display_widget.set_zoom(zoom_factor)
    
    def _update_stats(self):
        """Met à jour les statistiques d'affichage"""
        if not self.is_streaming:
            return
        
        try:
            stats_data = []
            
            # Statistiques globales
            stats_data.append(("Caméras actives", str(len(self.active_displays))))
            stats_data.append(("FPS cible", f"{1000/self.fps_spinbox.value():.1f}"))
            stats_data.append(("Vue profondeur", "Activée" if self.depth_checkbox.isChecked() else "Désactivée"))
            
            # Statistiques par caméra
            for alias in self.active_displays.keys():
                camera_stats = self.camera_manager.get_camera_stats(alias)
                if camera_stats:
                    fps = camera_stats.get('fps', 0)
                    stats_data.append((f"FPS {alias}", f"{fps:.1f}"))
            
            # Met à jour le tableau
            self.stats_table.setRowCount(len(stats_data))
            for i, (metric, value) in enumerate(stats_data):
                self.stats_table.setItem(i, 0, QTableWidgetItem(metric))
                self.stats_table.setItem(i, 1, QTableWidgetItem(value))
                
        except Exception as e:
            self._log(f"❌ Erreur mise à jour stats: {e}")
            logger.error(f"Erreur mise à jour statistiques: {e}")
    
    def _capture_frame(self):
        """Capture une frame de toutes les caméras actives"""
        if not self.is_streaming:
            self._log("⚠️ Streaming non actif")
            return
        
        captured_count = 0
        timestamp = int(time.time())
        
        for alias in self.active_displays.keys():
            try:
                ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(alias)
                
                if ret and color_frame is not None:
                    # Sauvegarde RGB
                    filename = f"capture_{alias}_{timestamp}_color.jpg"
                    cv2.imwrite(filename, color_frame)
                    captured_count += 1
                    
                    # Sauvegarde profondeur si disponible
                    if depth_frame is not None:
                        depth_filename = f"capture_{alias}_{timestamp}_depth.png"
                        cv2.imwrite(depth_filename, depth_frame)
                        
            except Exception as e:
                self._log(f"❌ Erreur capture {alias}: {e}")
        
        if captured_count > 0:
            self._log(f"📸 {captured_count} frame(s) capturée(s)")
        else:
            self._log("⚠️ Aucune frame capturée")
    
    def _save_image(self):
        """Sauvegarde l'image actuelle"""
        if not self.active_displays:
            self._log("⚠️ Aucune caméra active")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            "Sauvegarder l'image",
            f"capture_{int(time.time())}.jpg",
            "Images (*.jpg *.jpeg *.png *.bmp)"
        )
        
        if filename:
            # Sauvegarde la première caméra active
            first_alias = list(self.active_displays.keys())[0]
            try:
                ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(first_alias)
                
                if ret and color_frame is not None:
                    cv2.imwrite(filename, color_frame)
                    self._log(f"💾 Image sauvegardée: {filename}")
                    
                    # Sauvegarde aussi la profondeur si activée
                    if depth_frame is not None and self.depth_checkbox.isChecked():
                        depth_filename = filename.replace('.', '_depth.')
                        cv2.imwrite(depth_filename, depth_frame)
                        self._log(f"💾 Profondeur sauvegardée: {depth_filename}")
                else:
                    self._log("❌ Aucune frame disponible pour la sauvegarde")
                    
            except Exception as e:
                self._log(f"❌ Erreur sauvegarde: {e}")
                logger.error(f"Erreur sauvegarde image: {e}")
    
    def _log(self, message: str):
        """Ajoute un message au journal avec horodatage"""
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self.log_text.append(formatted_message)
        
        # Limite le nombre de lignes
        document = self.log_text.document()
        if document.blockCount() > self.max_log_lines:
            cursor = QTextCursor(document)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
        
        # Scroll automatique vers le bas
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def get_active_cameras(self) -> List[str]:
        """Retourne la liste des caméras actives"""
        return list(self.active_displays.keys())
    
    def is_camera_streaming(self) -> bool:
        """Vérifie si le streaming est actif"""
        return self.is_streaming
    
    def get_camera_frame_widget(self, alias: str):
        """Retourne le widget d'affichage d'une caméra"""
        return self.active_displays.get(alias)
    
    def set_depth_view_enabled(self, enabled: bool):
        """Active/désactive la vue profondeur depuis l'extérieur"""
        if self.depth_checkbox.isEnabled():
            self.depth_checkbox.setChecked(enabled)
    
    def closeEvent(self, event):
        """Nettoyage à la fermeture"""
        try:
            if self.is_streaming:
                self._stop_streaming()
            
            # Ferme toutes les caméras
            for alias in list(self.active_displays.keys()):
                self.camera_manager.close_camera(alias)
                
            logger.info("🚪 CameraTab fermé proprement")
            
        except Exception as e:
            logger.error(f"❌ Erreur fermeture CameraTab: {e}")
        
        super().closeEvent(event)