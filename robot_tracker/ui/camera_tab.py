#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/ui/camera_tab.py
Onglet de gestion des caméras sans aucune valeur statique - Version 4.3
Modification: Correction finale des messages d'erreur et valeurs hardcodées
"""

import cv2
import numpy as np
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QSpinBox, QCheckBox,
    QGroupBox, QFrame, QSplitter, QTextEdit, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QFileDialog, QSlider, QScrollArea
)
from PyQt6.QtCore import QTimer, pyqtSignal, QThread, Qt, QSize
from PyQt6.QtGui import QPixmap, QImage, QFont, QIcon

import logging

try:
    from ..core.camera_manager import CameraManager, CameraType, CameraInfo
    from .camera_display_widget import CameraDisplayWidget
except ImportError:
    from core.camera_manager import CameraManager, CameraType, CameraInfo
    from ui.camera_display_widget import CameraDisplayWidget

logger = logging.getLogger(__name__)

class CameraTab(QWidget):
    """Onglet de gestion des caméras entièrement configuré via JSON"""
    
    # Signaux
    camera_selected = pyqtSignal(str)
    frame_captured = pyqtSignal(str, object)
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        
        # Gestionnaire de caméras
        self.camera_manager = CameraManager(self.config)
        
        # État de l'interface
        self.available_cameras = []
        self.active_displays = {}
        self.is_streaming = False
        self.selected_camera = None
        
        # Timers avec configuration
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_camera_frames)
        
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_statistics)
        
        # Initialisation
        self._init_ui()
        self._connect_signals()
        self._detect_cameras()
        
        version_number = self.config.get('ui', 'camera_tab.version', '4.3')
        logger.info(f"🎥 CameraTab v{version_number} initialisé (zéro valeur statique)")
    
    def _init_ui(self):
        """Initialise l'interface utilisateur avec configuration JSON"""
        layout = QHBoxLayout(self)
        
        # Splitter principal avec proportions configurables
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Panel de contrôle et zone d'affichage
        control_panel = self._create_control_panel()
        display_area = self._create_display_area()
        
        splitter.addWidget(control_panel)
        splitter.addWidget(display_area)
        
        # Proportions depuis configuration
        control_width = self.config.get('ui', 'camera_tab.layout.control_panel_width', 300)
        display_width = self.config.get('ui', 'camera_tab.layout.display_area_width', 900)
        splitter.setSizes([control_width, display_width])
    
    def _create_control_panel(self) -> QWidget:
        """Crée le panel de contrôle avec configuration JSON"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # === Détection et sélection ===
        detection_group_title = self.config.get('ui', 'camera_tab.labels.detection_group', "🔍 Détection & Sélection")
        detection_group = QGroupBox(detection_group_title)
        detection_layout = QVBoxLayout(detection_group)
        
        # Bouton détection avec taille configurable
        button_height = self.config.get('ui', 'camera_tab.controls.button_height', 35)
        detect_btn_text = self.config.get('ui', 'camera_tab.labels.detect_button', "🔄 Détecter caméras")
        self.detect_btn = QPushButton(detect_btn_text)
        self.detect_btn.setMinimumHeight(button_height)
        detection_layout.addWidget(self.detect_btn)
        
        # ComboBox avec taille configurable
        combo_height = self.config.get('ui', 'camera_tab.controls.combo_height', 30)
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumHeight(combo_height)
        
        combo_label_text = self.config.get('ui', 'camera_tab.labels.available_cameras', "Caméras disponibles:")
        detection_layout.addWidget(QLabel(combo_label_text))
        detection_layout.addWidget(self.camera_combo)
        
        # Boutons d'action
        btn_layout = QHBoxLayout()
        open_btn_text = self.config.get('ui', 'camera_tab.labels.open_button', "📷 Ouvrir")
        close_btn_text = self.config.get('ui', 'camera_tab.labels.close_button', "❌ Fermer")
        self.open_btn = QPushButton(open_btn_text)
        self.close_btn = QPushButton(close_btn_text)
        self.open_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        btn_layout.addWidget(self.open_btn)
        btn_layout.addWidget(self.close_btn)
        detection_layout.addLayout(btn_layout)
        
        layout.addWidget(detection_group)
        
        # === Streaming ===
        streaming_group_title = self.config.get('ui', 'camera_tab.labels.streaming_group', "🎬 Streaming")
        streaming_group = QGroupBox(streaming_group_title)
        streaming_layout = QVBoxLayout(streaming_group)
        
        stream_btn_layout = QHBoxLayout()
        start_btn_text = self.config.get('ui', 'camera_tab.labels.start_button', "▶️ Démarrer")
        stop_btn_text = self.config.get('ui', 'camera_tab.labels.stop_button', "⏹️ Arrêter")
        self.start_stream_btn = QPushButton(start_btn_text)
        self.stop_stream_btn = QPushButton(stop_btn_text)
        self.start_stream_btn.setEnabled(False)
        self.stop_stream_btn.setEnabled(False)
        stream_btn_layout.addWidget(self.start_stream_btn)
        stream_btn_layout.addWidget(self.stop_stream_btn)
        streaming_layout.addLayout(stream_btn_layout)
        
        # Refresh rate avec limites configurables
        fps_layout = QHBoxLayout()
        refresh_label_text = self.config.get('ui', 'camera_tab.labels.refresh_rate', "Refresh UI (ms):")
        fps_layout.addWidget(QLabel(refresh_label_text))
        self.refresh_spinbox = QSpinBox()
        
        refresh_min = self.config.get('ui', 'camera_tab.controls.refresh_rate_min', 16)
        refresh_max = self.config.get('ui', 'camera_tab.controls.refresh_rate_max', 1000)
        refresh_default = self.config.get('ui', 'camera_tab.controls.refresh_rate_default', 50)
        refresh_suffix = self.config.get('ui', 'camera_tab.labels.refresh_suffix', " ms")
        
        self.refresh_spinbox.setRange(refresh_min, refresh_max)
        self.refresh_spinbox.setValue(refresh_default)
        self.refresh_spinbox.setSuffix(refresh_suffix)
        fps_layout.addWidget(self.refresh_spinbox)
        streaming_layout.addLayout(fps_layout)
        
        layout.addWidget(streaming_group)
        
        # === Affichage avec vue double ===
        display_group_title = self.config.get('ui', 'camera_tab.labels.display_group', "🖼️ Affichage")
        display_group = QGroupBox(display_group_title)
        display_layout = QVBoxLayout(display_group)
        
        # Option vue profondeur
        depth_label = self.config.get('ui', 'camera_tab.labels.show_depth', "Afficher vue profondeur")
        depth_tooltip = self.config.get('ui', 'camera_tab.tooltips.show_depth', 
                                       "Active la vue profondeur à côté de la vue RGB (RealSense uniquement)")
        self.show_depth_cb = QCheckBox(depth_label)
        self.show_depth_cb.setToolTip(depth_tooltip)
        display_layout.addWidget(self.show_depth_cb)
        
        # Zoom avec configuration
        zoom_layout = QHBoxLayout()
        zoom_label_text = self.config.get('ui', 'camera_tab.labels.zoom', "Zoom:")
        zoom_layout.addWidget(QLabel(zoom_label_text))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        
        zoom_min = self.config.get('ui', 'camera_tab.controls.zoom_range_min', 10)
        zoom_max = self.config.get('ui', 'camera_tab.controls.zoom_range_max', 500)
        zoom_default = self.config.get('ui', 'camera_tab.controls.zoom_default', 100)
        zoom_initial_label = self.config.get('ui', 'camera_tab.labels.zoom_initial', "1.0x")
        
        self.zoom_slider.setRange(zoom_min, zoom_max)
        self.zoom_slider.setValue(zoom_default)
        self.zoom_label = QLabel(zoom_initial_label)
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(self.zoom_label)
        display_layout.addLayout(zoom_layout)
        
        # Options d'affichage
        stats_label = self.config.get('ui', 'camera_tab.labels.show_stats', "Afficher statistiques")
        self.show_stats_cb = QCheckBox(stats_label)
        stats_default_checked = self.config.get('ui', 'camera_tab.controls.stats_default_checked', True)
        self.show_stats_cb.setChecked(stats_default_checked)
        display_layout.addWidget(self.show_stats_cb)
        
        layout.addWidget(display_group)
        
        # === Capture ===
        capture_group_title = self.config.get('ui', 'camera_tab.labels.capture_group', "📸 Capture")
        capture_group = QGroupBox(capture_group_title)
        capture_layout = QVBoxLayout(capture_group)
        
        capture_btn_text = self.config.get('ui', 'camera_tab.labels.capture_frame', "📸 Capturer frame")
        save_btn_text = self.config.get('ui', 'camera_tab.labels.save_image', "💾 Sauvegarder image")
        
        self.capture_btn = QPushButton(capture_btn_text)
        self.save_btn = QPushButton(save_btn_text)
        self.capture_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        capture_layout.addWidget(self.capture_btn)
        capture_layout.addWidget(self.save_btn)
        
        layout.addWidget(capture_group)
        
        # === Statistiques ===
        stats_group_title = self.config.get('ui', 'camera_tab.labels.stats_group', "📊 Statistiques")
        stats_group = QGroupBox(stats_group_title)
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_table = QTableWidget()
        stats_columns = self.config.get('ui', 'camera_tab.statistics.columns', 
                                       ["Propriété", "Valeur", "Unité"])
        self.stats_table.setColumnCount(len(stats_columns))
        self.stats_table.setHorizontalHeaderLabels(stats_columns)
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        
        table_max_height = self.config.get('ui', 'camera_tab.statistics.table_max_height', 200)
        self.stats_table.setMaximumHeight(table_max_height)
        stats_layout.addWidget(self.stats_table)
        
        layout.addWidget(stats_group)
        
        # === Log ===
        log_group_title = self.config.get('ui', 'camera_tab.labels.log_group', "📝 Journal")
        log_group = QGroupBox(log_group_title)
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        log_max_height = self.config.get('ui', 'camera_tab.log.max_height', 120)
        self.log_text.setMaximumHeight(log_max_height)
        
        # Font configurée pour le log
        log_font = QFont()
        font_family = self.config.get('ui', 'camera_tab.log.font_family', 'Consolas')
        font_size = self.config.get('ui', 'camera_tab.log.font_size', 8)
        log_font.setFamily(font_family)
        log_font.setPointSize(font_size)
        self.log_text.setFont(log_font)
        log_layout.addWidget(self.log_text)
        
        clear_log_text = self.config.get('ui', 'camera_tab.labels.clear_log', "🗑️ Effacer log")
        self.clear_log_btn = QPushButton(clear_log_text)
        log_layout.addWidget(self.clear_log_btn)
        
        layout.addWidget(log_group)
        
        layout.addStretch()
        return panel
    
    def _create_display_area(self) -> QWidget:
        """Crée la zone d'affichage des caméras avec configuration"""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        display_widget = QWidget()
        self.display_layout = QGridLayout(display_widget)
        
        # Espacement configurable
        grid_spacing = self.config.get('ui', 'camera_tab.layout.grid_spacing', 15)
        self.display_layout.setSpacing(grid_spacing)
        
        # Label par défaut avec style configurable
        default_text = self.config.get('ui', 'camera_tab.labels.no_camera_active', 
                                     "Aucune caméra active\n\nSélectionnez et ouvrez une caméra\npour voir le streaming temps réel")
        default_label = QLabel(default_text)
        default_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Style depuis configuration avec couleur configurable
        text_color = self.config.get('ui', 'camera_display.colors.text_color', '#666')
        default_border = self.config.get('ui', 'camera_display.colors.default_border', '#ccc')
        background = self.config.get('ui', 'camera_display.colors.background', '#f9f9f9')
        label_font_size = self.config.get('ui', 'camera_tab.display.default_label_font_size', 14)
        label_padding = self.config.get('ui', 'camera_tab.display.default_label_padding', 50)
        label_border_radius = self.config.get('ui', 'camera_tab.display.default_label_border_radius', 10)
        
        label_style = f"""
            QLabel {{
                font-size: {label_font_size}px;
                color: {text_color};
                border: 2px dashed {default_border};
                border-radius: {label_border_radius}px;
                padding: {label_padding}px;
                background-color: {background};
            }}
        """
        default_label.setStyleSheet(label_style)
        self.display_layout.addWidget(default_label, 0, 0)
        
        scroll_area.setWidget(display_widget)
        return scroll_area
    
    def _connect_signals(self):
        """Connecte les signaux"""
        self.detect_btn.clicked.connect(self._detect_cameras)
        self.open_btn.clicked.connect(self._open_selected_camera)
        self.close_btn.clicked.connect(self._close_selected_camera)
        
        self.start_stream_btn.clicked.connect(self._start_streaming)
        self.stop_stream_btn.clicked.connect(self._stop_streaming)
        
        self.capture_btn.clicked.connect(self._capture_frame)
        self.save_btn.clicked.connect(self._save_image)
        
        self.zoom_slider.valueChanged.connect(self._update_zoom)
        self.show_depth_cb.toggled.connect(self._toggle_depth_view)
        self.refresh_spinbox.valueChanged.connect(self._update_refresh_rate)
        
        self.camera_combo.currentTextChanged.connect(self._camera_selection_changed)
        
        self.clear_log_btn.clicked.connect(self.log_text.clear)
    
    def _detect_cameras(self):
        """Détecte toutes les caméras disponibles"""
        detect_msg = self.config.get('ui', 'camera_tab.messages.detecting', "🔍 Détection des caméras...")
        self._log(detect_msg)
        
        try:
            self.available_cameras = self.camera_manager.detect_all_cameras()
            
            self.camera_combo.clear()
            for camera in self.available_cameras:
                display_name = f"{camera.name} ({camera.camera_type.value})"
                self.camera_combo.addItem(display_name, camera)
            
            if self.available_cameras:
                success_msg = self.config.get('ui', 'camera_tab.messages.cameras_found', 
                                            "✅ {count} caméra(s) détectée(s)")
                self._log(success_msg.format(count=len(self.available_cameras)))
                self.open_btn.setEnabled(True)
            else:
                no_camera_msg = self.config.get('ui', 'camera_tab.messages.no_cameras', 
                                               "⚠️ Aucune caméra détectée")
                self._log(no_camera_msg)
                self.open_btn.setEnabled(False)
                
        except Exception as e:
            error_msg = self.config.get('ui', 'camera_tab.messages.detection_error', 
                                       "Erreur détection: {error}")
            self._log(error_msg.format(error=e))
    
    def _camera_selection_changed(self):
        """Gestion du changement de sélection"""
        current_data = self.camera_combo.currentData()
        self.selected_camera = current_data
        
        if current_data:
            select_msg = self.config.get('ui', 'camera_tab.messages.camera_selected', 
                                        "📷 Caméra sélectionnée: {name}")
            self._log(select_msg.format(name=current_data.name))
            
            has_depth = current_data.camera_type == CameraType.REALSENSE
            self.show_depth_cb.setEnabled(has_depth)
            
            if not has_depth:
                self.show_depth_cb.setChecked(False)
                no_depth_tooltip = self.config.get('ui', 'camera_tab.tooltips.no_depth', 
                                                  "Vue profondeur disponible uniquement avec RealSense")
                self.show_depth_cb.setToolTip(no_depth_tooltip)
            else:
                depth_tooltip = self.config.get('ui', 'camera_tab.tooltips.depth_available', 
                                               "Active la vue profondeur à côté de la vue RGB")
                self.show_depth_cb.setToolTip(depth_tooltip)
    
    def _open_selected_camera(self):
        """Ouvre la caméra sélectionnée"""
        if not self.selected_camera:
            no_selection_msg = self.config.get('ui', 'camera_tab.messages.no_selection', 
                                              "⚠️ Aucune caméra sélectionnée")
            self._log(no_selection_msg)
            return
        
        try:
            alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
            
            if alias in self.active_displays:
                already_open_msg = self.config.get('ui', 'camera_tab.messages.already_open', 
                                                  "⚠️ Caméra {alias} déjà ouverte")
                self._log(already_open_msg.format(alias=alias))
                return
            
            opening_msg = self.config.get('ui', 'camera_tab.messages.opening', 
                                         "📷 Ouverture {name}...")
            self._log(opening_msg.format(name=self.selected_camera.name))
            
            success = self.camera_manager.open_camera(self.selected_camera, alias)
            
            if success:
                display_widget = CameraDisplayWidget(alias, self.config)
                display_widget.clicked.connect(self._camera_display_clicked)
                
                if self.show_depth_cb.isChecked():
                    display_widget.set_depth_view(True)
                
                self._add_camera_display(alias, display_widget)
                self._update_controls_state()
                
                success_msg = self.config.get('ui', 'camera_tab.messages.opened_success', 
                                             "✅ Caméra {alias} ouverte avec succès")
                self._log(success_msg.format(alias=alias))
            else:
                failed_msg = self.config.get('ui', 'camera_tab.messages.open_failed', 
                                           "❌ Échec ouverture {name}")
                self._log(failed_msg.format(name=self.selected_camera.name))
                
        except Exception as e:
            error_msg = self.config.get('ui', 'camera_tab.messages.open_error', 
                                       "Erreur ouverture caméra: {error}")
            self._log(error_msg.format(error=e))
    
    def _close_selected_camera(self):
        """Ferme la caméra sélectionnée"""
        if not self.selected_camera:
            return
        
        alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
        self._close_camera(alias)
    
    def _close_camera(self, alias: str):
        """Ferme une caméra spécifique"""
        try:
            success = self.camera_manager.close_camera(alias)
            
            if success:
                self._remove_camera_display(alias)
                self._update_controls_state()
                
                closed_msg = self.config.get('ui', 'camera_tab.messages.closed', 
                                            "✅ Caméra {alias} fermée")
                self._log(closed_msg.format(alias=alias))
            else:
                close_error_msg = self.config.get('ui', 'camera_tab.messages.close_error', 
                                                 "Erreur fermeture {alias}")
                self._log(close_error_msg.format(alias=alias))
                
        except Exception as e:
            close_exception_msg = self.config.get('ui', 'camera_tab.messages.close_exception', 
                                                 "Erreur fermeture caméra {alias}: {error}")
            self._log(close_exception_msg.format(alias=alias, error=e))
    
    def _add_camera_display(self, alias: str, display_widget: CameraDisplayWidget):
        """Ajoute un widget d'affichage à la grille avec configuration"""
        if not self.active_displays:
            for i in reversed(range(self.display_layout.count())):
                item = self.display_layout.itemAt(i)
                if item and item.widget():
                    item.widget().setParent(None)
        
        num_cameras = len(self.active_displays)
        max_cols_single = self.config.get('ui', 'camera_tab.layout.max_columns_single', 3)
        max_cols_dual = self.config.get('ui', 'camera_tab.layout.max_columns_dual', 2)
        
        cols = max_cols_dual if self.show_depth_cb.isChecked() else max_cols_single
        row = num_cameras // cols
        col = num_cameras % cols
        
        self.display_layout.addWidget(display_widget, row, col)
        self.active_displays[alias] = display_widget
        
        display_added_msg = self.config.get('ui', 'camera_tab.messages.display_added', 
                                           "🖼️ Affichage {alias} ajouté (vue double: {dual})")
        self._log(display_added_msg.format(alias=alias, dual=display_widget.show_depth))
    
    def _remove_camera_display(self, alias: str):
        """Supprime un widget d'affichage"""
        if alias in self.active_displays:
            widget = self.active_displays[alias]
            widget.setParent(None)
            del self.active_displays[alias]
            
            self._reorganize_display_grid()
            
            display_removed_msg = self.config.get('ui', 'camera_tab.messages.display_removed', 
                                                 "🖼️ Affichage {alias} supprimé")
            self._log(display_removed_msg.format(alias=alias))
    
    def _reorganize_display_grid(self):
        """Réorganise la grille d'affichage"""
        if not self.active_displays:
            default_text = self.config.get('ui', 'camera_tab.labels.no_camera_active', 
                                         "Aucune caméra active\n\nSélectionnez et ouvrez une caméra\npour voir le streaming temps réel")
            default_label = QLabel(default_text)
            default_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Style configuré avec couleurs de la config
            text_color = self.config.get('ui', 'camera_display.colors.text_color', '#666')
            default_border = self.config.get('ui', 'camera_display.colors.default_border', '#ccc')
            background = self.config.get('ui', 'camera_display.colors.background', '#f9f9f9')
            label_font_size = self.config.get('ui', 'camera_tab.display.default_label_font_size', 14)
            label_padding = self.config.get('ui', 'camera_tab.display.default_label_padding', 50)
            label_border_radius = self.config.get('ui', 'camera_tab.display.default_label_border_radius', 10)
            
            label_style = f"""
                QLabel {{
                    font-size: {label_font_size}px;
                    color: {text_color};
                    border: 2px dashed {default_border};
                    border-radius: {label_border_radius}px;
                    padding: {label_padding}px;
                    background-color: {background};
                }}
            """
            default_label.setStyleSheet(label_style)
            self.display_layout.addWidget(default_label, 0, 0)
            return
        
        widgets = list(self.active_displays.values())
        max_cols_single = self.config.get('ui', 'camera_tab.layout.max_columns_single', 3)
        max_cols_dual = self.config.get('ui', 'camera_tab.layout.max_columns_dual', 2)
        
        cols = max_cols_dual if self.show_depth_cb.isChecked() else max_cols_single
        
        for i, widget in enumerate(widgets):
            row = i // cols
            col = i % cols
            self.display_layout.addWidget(widget, row, col)
    
    def _start_streaming(self):
        """Démarre le streaming"""
        if self.is_streaming or not self.active_displays:
            return
        
        try:
            start_msg = self.config.get('ui', 'camera_tab.messages.starting_stream', 
                                       "🎬 Démarrage du streaming...")
            self._log(start_msg)
            
            self.camera_manager.start_streaming(self._on_new_frames)
            
            refresh_ms = self.refresh_spinbox.value()
            self.update_timer.start(refresh_ms)
            
            stats_interval = self.config.get('ui', 'camera_tab.statistics.update_interval', 1000)
            self.stats_timer.start(stats_interval)
            
            self.is_streaming = True
            self._update_controls_state()
            
            started_msg = self.config.get('ui', 'camera_tab.messages.stream_started', 
                                         "✅ Streaming démarré")
            self._log(started_msg)
            
        except Exception as e:
            start_error_msg = self.config.get('ui', 'camera_tab.messages.start_stream_error', 
                                             "Erreur démarrage streaming: {error}")
            self._log(start_error_msg.format(error=e))
    
    def _stop_streaming(self):
        """Arrête le streaming"""
        if not self.is_streaming:
            return
        
        try:
            stop_msg = self.config.get('ui', 'camera_tab.messages.stopping_stream', 
                                      "🛑 Arrêt du streaming...")
            self._log(stop_msg)
            
            self.update_timer.stop()
            self.stats_timer.stop()
            
            self.camera_manager.stop_streaming()
            
            self.is_streaming = False
            self._update_controls_state()
            
            stopped_msg = self.config.get('ui', 'camera_tab.messages.stream_stopped', 
                                         "✅ Streaming arrêté")
            self._log(stopped_msg)
            
        except Exception as e:
            stop_error_msg = self.config.get('ui', 'camera_tab.messages.stop_stream_error', 
                                            "Erreur arrêt streaming: {error}")
            self._log(stop_error_msg.format(error=e))
    
    def _on_new_frames(self, frames_data: dict):
        """Callback pour nouveaux frames"""
        pass
    
    def _update_camera_frames(self):
        """Met à jour l'affichage des frames"""
        if not self.is_streaming:
            return
        
        try:
            all_frames = self.camera_manager.get_all_frames()
            
            for alias, (ret, color_frame, depth_frame) in all_frames.items():
                if alias in self.active_displays and ret:
                    display_widget = self.active_displays[alias]
                    display_widget.update_frame(color_frame, depth_frame)
                    
        except Exception as e:
            frame_error_msg = self.config.get('ui', 'camera_tab.messages.frame_update_error', 
                                             "Erreur mise à jour frames: {error}")
            self._log(frame_error_msg.format(error=e))
    
    def _update_statistics(self):
        """Met à jour les statistiques"""
        if not self.show_stats_cb.isChecked():
            return
        
        try:
            all_stats = self.camera_manager.get_all_stats()
            
            if self.selected_camera:
                alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
                if alias in all_stats:
                    self._display_camera_stats(all_stats[alias])
            elif all_stats:
                first_alias = next(iter(all_stats))
                self._display_camera_stats(all_stats[first_alias])
                
        except Exception as e:
            stats_error_msg = self.config.get('ui', 'camera_tab.messages.stats_error', 
                                             "Erreur mise à jour stats: {error}")
            self._log(stats_error_msg.format(error=e))
    
    def _display_camera_stats(self, stats: dict):
        """Affiche les statistiques dans le tableau"""
        self.stats_table.setRowCount(0)
        
        # Labels configurables pour les propriétés
        name_label = self.config.get('ui', 'camera_tab.statistics.labels.name', "Nom")
        type_label = self.config.get('ui', 'camera_tab.statistics.labels.type', "Type")
        resolution_label = self.config.get('ui', 'camera_tab.statistics.labels.resolution', "Résolution")
        fps_label = self.config.get('ui', 'camera_tab.statistics.labels.fps', "FPS actuel")
        frames_label = self.config.get('ui', 'camera_tab.statistics.labels.frames', "Frames total")
        timestamp_label = self.config.get('ui', 'camera_tab.statistics.labels.timestamp', "Dernière frame")
        status_label = self.config.get('ui', 'camera_tab.statistics.labels.status', "État")
        
        # Unités configurables
        pixels_unit = self.config.get('ui', 'camera_tab.statistics.units.pixels', "pixels")
        fps_unit = self.config.get('ui', 'camera_tab.statistics.units.fps', "fps")
        empty_unit = self.config.get('ui', 'camera_tab.statistics.units.empty', "")
        
        # Valeurs d'état configurables
        active_text = self.config.get('ui', 'camera_tab.statistics.values.active', "Actif")
        inactive_text = self.config.get('ui', 'camera_tab.statistics.values.inactive', "Inactif")
        na_text = self.config.get('ui', 'camera_tab.statistics.values.na', "N/A")
        
        display_props = [
            (name_label, stats.get('name', na_text), empty_unit),
            (type_label, stats.get('type', na_text), empty_unit),
            (resolution_label, stats.get('resolution', stats.get('color_resolution', na_text)), pixels_unit),
            (fps_label, f"{stats.get('fps', 0):.1f}", fps_unit),
            (frames_label, str(stats.get('frame_count', 0)), empty_unit),
            (timestamp_label, time.strftime("%H:%M:%S", time.localtime(stats.get('last_timestamp', 0))), empty_unit),
            (status_label, active_text if stats.get('is_active', False) else inactive_text, empty_unit)
        ]
        
        if stats.get('type') == 'realsense':
            depth_res = stats.get('depth_resolution', na_text)
            if depth_res != na_text:
                depth_label = self.config.get('ui', 'camera_tab.statistics.labels.depth', "Profondeur")
                display_props.insert(3, (depth_label, depth_res, pixels_unit))
        
        for i, (prop, value, unit) in enumerate(display_props):
            self.stats_table.insertRow(i)
            self.stats_table.setItem(i, 0, QTableWidgetItem(prop))
            self.stats_table.setItem(i, 1, QTableWidgetItem(str(value)))
            self.stats_table.setItem(i, 2, QTableWidgetItem(unit))
    
    def _update_controls_state(self):
        """Met à jour l'état des contrôles"""
        has_cameras = len(self.active_displays) > 0
        
        self.close_btn.setEnabled(self.selected_camera is not None and has_cameras)
        self.start_stream_btn.setEnabled(has_cameras and not self.is_streaming)
        self.stop_stream_btn.setEnabled(self.is_streaming)
        self.capture_btn.setEnabled(has_cameras and self.is_streaming)
        self.save_btn.setEnabled(has_cameras)
    
    def _update_refresh_rate(self):
        """Met à jour la fréquence de rafraîchissement"""
        if self.is_streaming:
            refresh_ms = self.refresh_spinbox.value()
            self.update_timer.setInterval(refresh_ms)
            
            refresh_msg = self.config.get('ui', 'camera_tab.messages.refresh_rate', 
                                         "🔄 Refresh rate: {fps:.1f} FPS")
            fps_value = 1000 / refresh_ms
            self._log(refresh_msg.format(fps=fps_value))
    
    def _update_zoom(self):
        """Met à jour le zoom de tous les affichages"""
        zoom_value = self.zoom_slider.value()
        zoom_divisor = self.config.get('ui', 'camera_tab.controls.zoom_divisor', 100.0)
        zoom_factor = zoom_value / zoom_divisor
        zoom_format = self.config.get('ui', 'camera_tab.labels.zoom_format', "{:.1f}x")
        self.zoom_label.setText(zoom_format.format(zoom_factor))
        
        for display_widget in self.active_displays.values():
            display_widget.set_zoom(zoom_factor)
    
    def _toggle_depth_view(self):
        """Bascule l'affichage profondeur pour toutes les caméras"""
        show_depth = self.show_depth_cb.isChecked()
        
        for alias, display_widget in self.active_displays.items():
            cam_data = self.camera_combo.currentData()
            if cam_data and cam_data.camera_type == CameraType.REALSENSE:
                display_widget.set_depth_view(show_depth)
            else:
                display_widget.set_depth_view(False)
        
        self._reorganize_display_grid()
        
        depth_msg = self.config.get('ui', 'camera_tab.messages.depth_toggled', 
                                   "👁️ Vue profondeur: {state}")
        enabled_text = self.config.get('ui', 'camera_tab.messages.depth_enabled', "Activée")
        disabled_text = self.config.get('ui', 'camera_tab.messages.depth_disabled', "Désactivée")
        state = enabled_text if show_depth else disabled_text
        self._log(depth_msg.format(state=state))
    
    def _camera_display_clicked(self, alias: str):
        """Gestion du clic sur un affichage"""
        click_msg = self.config.get('ui', 'camera_tab.messages.camera_clicked', 
                                   "🖱️ Clic sur caméra: {alias}")
        self._log(click_msg.format(alias=alias))
        self.camera_selected.emit(alias)
    
    def _capture_frame(self):
        """Capture une frame de la caméra sélectionnée"""
        if not self.selected_camera:
            no_camera_msg = self.config.get('ui', 'camera_tab.messages.no_camera_capture', 
                                           "⚠️ Aucune caméra sélectionnée pour la capture")
            self._log(no_camera_msg)
            return
        
        alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
        
        try:
            ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(alias)
            
            if ret and color_frame is not None:
                frame_data = {
                    'alias': alias,
                    'color': color_frame,
                    'depth': depth_frame,
                    'timestamp': time.time()
                }
                self.frame_captured.emit(alias, frame_data)
                
                capture_msg = self.config.get('ui', 'camera_tab.messages.frame_captured', 
                                             "📸 Frame capturée: {alias}")
                self._log(capture_msg.format(alias=alias))
            else:
                capture_failed_msg = self.config.get('ui', 'camera_tab.messages.capture_failed', 
                                                    "❌ Impossible de capturer une frame de {alias}")
                self._log(capture_failed_msg.format(alias=alias))
                
        except Exception as e:
            capture_error_msg = self.config.get('ui', 'camera_tab.messages.capture_error', 
                                               "Erreur capture frame: {error}")
            self._log(capture_error_msg.format(error=e))
    
    def _save_image(self):
        """Sauvegarde l'image de la caméra sélectionnée"""
        if not self.selected_camera:
            no_camera_save_msg = self.config.get('ui', 'camera_tab.messages.no_camera_save', 
                                                "⚠️ Aucune caméra sélectionnée pour la sauvegarde")
            self._log(no_camera_save_msg)
            return
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename_template = self.config.get('ui', 'camera_tab.save.filename_template', 
                                           "camera_{type}_{timestamp}.jpg")
        default_name = filename_template.format(
            type=self.selected_camera.camera_type.value,
            timestamp=timestamp
        )
        
        image_formats = self.config.get('ui', 'camera_tab.save.image_formats', 
                                       "Images (*.jpg *.jpeg *.png);;Tous les fichiers (*)")
        save_title = self.config.get('ui', 'camera_tab.save.dialog_title', "Sauvegarder image")
        
        filepath, _ = QFileDialog.getSaveFileName(self, save_title, default_name, image_formats)
        
        if filepath:
            alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
            
            success = self.camera_manager.save_camera_frame(alias, filepath)
            
            if success:
                save_success_msg = self.config.get('ui', 'camera_tab.messages.save_success', 
                                                  "💾 Image RGB sauvegardée: {filepath}")
                self._log(save_success_msg.format(filepath=filepath))
                
                if (self.show_depth_cb.isChecked() and 
                    self.selected_camera.camera_type == CameraType.REALSENSE):
                    
                    depth_suffix = self.config.get('ui', 'camera_tab.save.depth_suffix', '_depth')
                    depth_ext = self.config.get('ui', 'camera_tab.save.depth_extension', '.png')
                    depth_filepath = filepath.replace('.jpg', f'{depth_suffix}{depth_ext}').replace('.png', f'{depth_suffix}{depth_ext}')
                    ret, _, depth_frame = self.camera_manager.get_camera_frame(alias)
                    
                    if ret and depth_frame is not None:
                        cv2.imwrite(depth_filepath, depth_frame)
                        depth_save_msg = self.config.get('ui', 'camera_tab.messages.depth_save_success', 
                                                        "💾 Image profondeur sauvegardée: {filepath}")
                        self._log(depth_save_msg.format(filepath=depth_filepath))
            else:
                save_error_msg = self.config.get('ui', 'camera_tab.messages.save_error', 
                                                "Erreur sauvegarde: {filepath}")
                self._log(save_error_msg.format(filepath=filepath))
    
    def _log(self, message: str):
        """Ajoute un message au log avec timestamp"""
        timestamp_format = self.config.get('ui', 'camera_tab.log.timestamp_format', "%H:%M:%S")
        message_format = self.config.get('ui', 'camera_tab.log.message_format', "[{timestamp}] {message}")
        
        timestamp = time.strftime(timestamp_format)
        formatted_message = message_format.format(timestamp=timestamp, message=message)
        
        self.log_text.append(formatted_message)
        
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
        
        max_lines = self.config.get('ui', 'camera_tab.log.max_lines', 100)
        if self.log_text.document().blockCount() > max_lines:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
    
    def closeEvent(self, event):
        """Nettoyage lors de la fermeture"""
        try:
            self._stop_streaming()
            self.camera_manager.close_all_cameras()
            
            cleanup_msg = self.config.get('ui', 'camera_tab.messages.cleanup', 
                                         "🔄 Nettoyage terminé")
            self._log(cleanup_msg)
        except Exception as e:
            logger.error(f"Erreur nettoyage: {e}")
        
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
    
    def set_depth_view_enabled(self, enabled: bool):
        """Active/désactive la vue profondeur pour toutes les caméras compatibles"""
        self.show_depth_cb.setChecked(enabled)
        self._toggle_depth_view()