# ui/camera_tab.py
# Version 4.4 - Support camera_manager externe partagé complet
# Modification: Fichier complet avec paramètre camera_manager pour partage entre onglets

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
    """Onglet de gestion des caméras avec support camera_manager partagé"""
    
    # Signaux
    camera_selected = pyqtSignal(str)
    frame_captured = pyqtSignal(str, object)
    camera_started = pyqtSignal(str)  # Signal pour autres onglets
    
    def __init__(self, config, camera_manager=None, parent=None):
        super().__init__(parent)
        self.config = config
        
        # Gestionnaire de caméras (externe ou créé localement)
        if camera_manager is not None:
            self.camera_manager = camera_manager
            self.owns_camera_manager = False
            logger.info("🎥 CameraTab utilise camera_manager externe")
        else:
            self.camera_manager = CameraManager(self.config)
            self.owns_camera_manager = True
            logger.info("🎥 CameraTab crée son propre camera_manager")
        
        # État de l'interface
        self.available_cameras = []
        self.active_displays = {}
        self.is_streaming = False
        self.selected_camera = None
        self.current_fps = 0.0
        self.frame_count = 0
        
        # Timers avec configuration
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_camera_frames)
        
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._update_statistics)
        
        # Initialisation
        self._init_ui()
        self._connect_signals()
        self._detect_cameras()
        
        version_number = self.config.get('ui', 'camera_tab.version', '4.4')
        logger.info(f"🎥 CameraTab v{version_number} initialisé (camera_manager partagé)")
    
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
        control_width = self.config.get('ui', 'camera_tab.layout.control_panel_width', 280)
        display_width = self.config.get('ui', 'camera_tab.layout.display_area_width', 800)
        splitter.setSizes([control_width, display_width])
    
    def _create_control_panel(self) -> QWidget:
        """Crée le panneau de contrôle"""
        panel = QWidget()
        panel_width = self.config.get('ui', 'camera_tab.layout.control_panel_width', 280)
        panel.setMaximumWidth(panel_width)
        
        layout = QVBoxLayout(panel)
        
        # Sélection caméra
        camera_group = self._create_camera_selection_group()
        layout.addWidget(camera_group)
        
        # Contrôles acquisition
        acquisition_group = self._create_acquisition_controls_group()
        layout.addWidget(acquisition_group)
        
        # Paramètres affichage
        display_group = self._create_display_settings_group()
        layout.addWidget(display_group)
        
        # Statistiques
        stats_group = self._create_statistics_group()
        layout.addWidget(stats_group)
        
        layout.addStretch()
        return panel
    
    def _create_camera_selection_group(self) -> QGroupBox:
        """Groupe de sélection des caméras"""
        group = QGroupBox("📷 Sélection Caméra")
        layout = QVBoxLayout(group)
        
        # ComboBox caméras
        self.camera_combo = QComboBox()
        self.camera_combo.currentTextChanged.connect(self._on_camera_selected)
        layout.addWidget(self.camera_combo)
        
        # Informations caméra sélectionnée
        self.camera_info_label = QLabel("Aucune caméra sélectionnée")
        self.camera_info_label.setWordWrap(True)
        self.camera_info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.camera_info_label)
        
        # Boutons contrôle
        buttons_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Actualiser")
        self.refresh_btn.clicked.connect(self._detect_cameras)
        
        self.open_btn = QPushButton("▶️ Ouvrir")
        self.open_btn.clicked.connect(self._open_selected_camera)
        self.open_btn.setEnabled(False)
        
        self.close_btn = QPushButton("⏹️ Fermer")
        self.close_btn.clicked.connect(self._close_selected_camera)
        self.close_btn.setEnabled(False)
        
        buttons_layout.addWidget(self.refresh_btn)
        buttons_layout.addWidget(self.open_btn)
        buttons_layout.addWidget(self.close_btn)
        layout.addLayout(buttons_layout)
        
        return group
    
    def _create_acquisition_controls_group(self) -> QGroupBox:
        """Groupe de contrôles d'acquisition"""
        group = QGroupBox("🎬 Acquisition")
        layout = QVBoxLayout(group)
        
        # Boutons streaming
        streaming_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶️ Démarrer")
        self.start_btn.clicked.connect(self._start_streaming)
        self.start_btn.setEnabled(False)
        
        self.stop_btn = QPushButton("⏹️ Arrêter")
        self.stop_btn.clicked.connect(self._stop_streaming)
        self.stop_btn.setEnabled(False)
        
        streaming_layout.addWidget(self.start_btn)
        streaming_layout.addWidget(self.stop_btn)
        layout.addLayout(streaming_layout)
        
        # Boutons capture/sauvegarde
        capture_layout = QHBoxLayout()
        
        self.capture_btn = QPushButton("📸 Capturer")
        self.capture_btn.clicked.connect(self._capture_frame)
        self.capture_btn.setEnabled(False)
        
        self.save_btn = QPushButton("💾 Sauver")
        self.save_btn.clicked.connect(self._save_image)
        self.save_btn.setEnabled(False)
        
        capture_layout.addWidget(self.capture_btn)
        capture_layout.addWidget(self.save_btn)
        layout.addLayout(capture_layout)
        
        # Paramètres d'acquisition
        params_layout = QVBoxLayout()
        
        # FPS cible
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("FPS cible:"))
        
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 60)
        self.fps_spinbox.setValue(self.config.get('ui', 'camera_tab.acquisition.default_fps', 30))
        self.fps_spinbox.valueChanged.connect(self._on_fps_changed)
        
        fps_layout.addWidget(self.fps_spinbox)
        params_layout.addLayout(fps_layout)
        
        layout.addLayout(params_layout)
        
        return group
    
    def _create_display_settings_group(self) -> QGroupBox:
        """Groupe de paramètres d'affichage"""
        group = QGroupBox("🖼️ Affichage")
        layout = QVBoxLayout(group)
        
        # Vue profondeur
        self.show_depth_cb = QCheckBox("Vue profondeur (RealSense)")
        self.show_depth_cb.toggled.connect(self._toggle_depth_view)
        layout.addWidget(self.show_depth_cb)
        
        # Zoom
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 300)  # 0.1x à 3.0x
        self.zoom_slider.setValue(100)  # 1.0x
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        
        self.zoom_label = QLabel("100%")
        
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(self.zoom_label)
        layout.addLayout(zoom_layout)
        
        # Options d'affichage
        display_options = QVBoxLayout()
        
        self.show_info_cb = QCheckBox("Informations overlay")
        self.show_info_cb.setChecked(True)
        self.show_info_cb.toggled.connect(self._toggle_info_overlay)
        
        self.show_fps_cb = QCheckBox("Afficher FPS")
        self.show_fps_cb.setChecked(True)
        
        display_options.addWidget(self.show_info_cb)
        display_options.addWidget(self.show_fps_cb)
        layout.addLayout(display_options)
        
        return group
    
    def _create_statistics_group(self) -> QGroupBox:
        """Groupe de statistiques"""
        group = QGroupBox("📊 Statistiques")
        layout = QVBoxLayout(group)
        
        # Labels statistiques
        self.fps_label = QLabel("FPS: 0.0")
        self.cameras_label = QLabel("Caméras: 0/0")
        self.frames_label = QLabel("Images: 0")
        self.resolution_label = QLabel("Résolution: N/A")
        
        layout.addWidget(self.fps_label)
        layout.addWidget(self.cameras_label)
        layout.addWidget(self.frames_label)
        layout.addWidget(self.resolution_label)
        
        # Zone de log
        log_header = QLabel("Logs:")
        log_header.setStyleSheet("font-weight: bold;")
        layout.addWidget(log_header)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(120)
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: monospace; font-size: 9px;")
        layout.addWidget(self.log_text)
        
        # Bouton de nettoyage des logs
        clear_logs_btn = QPushButton("🗑️ Effacer logs")
        clear_logs_btn.clicked.connect(lambda: self.log_text.clear())
        layout.addWidget(clear_logs_btn)
        
        return group
    
    def _create_display_area(self) -> QWidget:
        """Crée la zone d'affichage des caméras"""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setStyleSheet("QScrollArea { border: 1px solid #ccc; }")
        
        # Widget conteneur pour la grille
        display_widget = QWidget()
        self.display_layout = QGridLayout(display_widget)
        self.display_layout.setSpacing(10)
        
        # Message d'aide initial
        self.help_label = QLabel("""
        <div style='text-align: center; color: #666; padding: 50px;'>
            <h3>🎥 Gestion des Caméras</h3>
            <p>1. Sélectionnez une caméra dans la liste</p>
            <p>2. Cliquez sur "Ouvrir" pour l'initialiser</p>
            <p>3. Utilisez "Démarrer" pour lancer l'acquisition</p>
            <br>
            <p><i>Aucune caméra ouverte actuellement</i></p>
        </div>
        """)
        self.help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display_layout.addWidget(self.help_label, 0, 0)
        
        area.setWidget(display_widget)
        return area
    
    def _connect_signals(self):
        """Connecte les signaux internes"""
        # Les signaux sont déjà connectés dans les méthodes de création
        pass
    
    def _detect_cameras(self):
        """Détecte les caméras disponibles"""
        self._log("🔍 Détection des caméras...")
        
        try:
            self.available_cameras = self.camera_manager.detect_cameras()
            self._update_camera_combo()
            
            cameras_found_msg = self.config.get('ui', 'camera_tab.messages.cameras_detected', 
                                               "🔍 {count} caméra(s) détectée(s)")
            self._log(cameras_found_msg.format(count=len(self.available_cameras)))
            
            # Mise à jour des statistiques
            self.cameras_label.setText(f"Caméras: {len(self.active_displays)}/{len(self.available_cameras)}")
            
        except Exception as e:
            error_msg = self.config.get('ui', 'camera_tab.messages.detection_error', 
                                       "❌ Erreur détection caméras: {error}")
            self._log(error_msg.format(error=e))
    
    def _update_camera_combo(self):
        """Met à jour la combobox des caméras"""
        self.camera_combo.clear()
        
        if not self.available_cameras:
            self.camera_combo.addItem("Aucune caméra détectée")
            self.camera_info_label.setText("Aucune caméra disponible")
            return
        
        for camera in self.available_cameras:
            display_name = f"{camera.camera_type.value}: {camera.name}"
            self.camera_combo.addItem(display_name, camera)
        
        self.camera_info_label.setText(f"{len(self.available_cameras)} caméra(s) disponible(s)")
    
    def _on_camera_selected(self, text):
        """Gestion de la sélection d'une caméra"""
        camera_data = self.camera_combo.currentData()
        
        if camera_data and isinstance(camera_data, CameraInfo):
            self.selected_camera = camera_data
            self._update_controls_state()
            
            # Mise à jour des informations
            info_text = f"Type: {camera_data.camera_type.value}\n"
            info_text += f"Nom: {camera_data.name}\n"
            info_text += f"ID: {camera_data.device_id}"
            self.camera_info_label.setText(info_text)
            
            selected_msg = self.config.get('ui', 'camera_tab.messages.camera_selected', 
                                          "📷 Caméra sélectionnée: {name}")
            self._log(selected_msg.format(name=camera_data.name))
        else:
            self.selected_camera = None
            self.camera_info_label.setText("Sélectionnez une caméra")
    
    def _update_controls_state(self):
        """Met à jour l'état des contrôles"""
        has_camera = self.selected_camera is not None
        is_open = False
        
        if has_camera:
            alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
            is_open = self.camera_manager.is_camera_open(alias)
        
        # Boutons caméra
        self.open_btn.setEnabled(has_camera and not is_open)
        self.close_btn.setEnabled(has_camera and is_open)
        
        # Boutons streaming
        has_open_cameras = len(self.active_displays) > 0
        self.start_btn.setEnabled(has_open_cameras and not self.is_streaming)
        self.stop_btn.setEnabled(has_open_cameras and self.is_streaming)
        
        # Boutons capture
        self.capture_btn.setEnabled(has_camera and is_open)
        self.save_btn.setEnabled(has_camera and is_open)
        
        # Options d'affichage
        has_realsense = has_camera and self.selected_camera.camera_type == CameraType.REALSENSE
        self.show_depth_cb.setEnabled(has_realsense)
    
    def _open_selected_camera(self):
        """Ouvre la caméra sélectionnée"""
        if not self.selected_camera:
            return
        
        self._log(f"🔄 Ouverture caméra {self.selected_camera.name}...")
        
        try:
            alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
            success = self.camera_manager.open_camera(alias, self.selected_camera)
            
            if success:
                # Création widget d'affichage
                display_widget = CameraDisplayWidget(alias, self.config)
                display_widget.clicked.connect(lambda: self._camera_display_clicked(alias))
                
                self._add_camera_display(alias, display_widget)
                self._update_controls_state()
                
                opened_msg = self.config.get('ui', 'camera_tab.messages.opened', 
                                           "✅ Caméra {name} ouverte")
                self._log(opened_msg.format(name=self.selected_camera.name))
                
                # Test de capture pour obtenir la résolution
                self._test_camera_resolution(alias)
                
            else:
                failed_msg = self.config.get('ui', 'camera_tab.messages.open_failed', 
                                           "❌ Échec ouverture {name}")
                self._log(failed_msg.format(name=self.selected_camera.name))
                
        except Exception as e:
            error_msg = self.config.get('ui', 'camera_tab.messages.open_error', 
                                       'Erreur ouverture caméra: {error}')
            self._log(error_msg.format(error=e))
    
    def _test_camera_resolution(self, alias: str):
        """Teste la résolution de la caméra"""
        try:
            ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(alias)
            if ret and color_frame is not None:
                height, width = color_frame.shape[:2]
                self.resolution_label.setText(f"Résolution: {width}x{height}")
        except:
            self.resolution_label.setText("Résolution: N/A")
    
    def _close_selected_camera(self):
        """Ferme la caméra sélectionnée"""
        if not self.selected_camera:
            return
        
        alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
        self._close_camera(alias)
    
    def _close_camera(self, alias: str):
        """Ferme une caméra spécifique"""
        self._log(f"🔄 Fermeture caméra {alias}...")
        
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
                                                 'Erreur fermeture: {alias}')
                self._log(close_error_msg.format(alias=alias))
                
        except Exception as e:
            close_exception_msg = self.config.get('ui', 'camera_tab.messages.close_exception', 
                                                 'Exception fermeture: {alias} - {error}')
            self._log(close_exception_msg.format(alias=alias, error=e))
    
    def _add_camera_display(self, alias: str, display_widget: CameraDisplayWidget):
        """Ajoute un widget d'affichage à la grille"""
        # Suppression du message d'aide
        if hasattr(self, 'help_label') and self.help_label.parent():
            self.help_label.setParent(None)
        
        # Nettoyage grille si première caméra
        if not self.active_displays:
            for i in reversed(range(self.display_layout.count())):
                item = self.display_layout.itemAt(i)
                if item and item.widget():
                    item.widget().setParent(None)
        
        num_cameras = len(self.active_displays)
        max_cols_single = self.config.get('ui', 'camera_tab.layout.max_columns_single', 3)
        max_cols_dual = self.config.get('ui', 'camera_tab.layout.max_columns_dual', 2)
        
        # Adaptation selon vue profondeur
        cols = max_cols_dual if self.show_depth_cb.isChecked() else max_cols_single
        row = num_cameras // cols
        col = num_cameras % cols
        
        self.display_layout.addWidget(display_widget, row, col)
        self.active_displays[alias] = display_widget
        
        display_added_msg = self.config.get('ui', 'camera_tab.messages.display_added', 
                                           "🖼️ Affichage {alias} ajouté")
        self._log(display_added_msg.format(alias=alias))
        
        # Mise à jour statistiques
        self.cameras_label.setText(f"Caméras: {len(self.active_displays)}/{len(self.available_cameras)}")
    
    def _remove_camera_display(self, alias: str):
        """Supprime un widget d'affichage"""
        if alias in self.active_displays:
            widget = self.active_displays[alias]
            widget.setParent(None)
            del self.active_displays[alias]
            
            # Réorganisation grille
            self._reorganize_display_grid()
            
            # Remettre l'aide si plus de caméras
            if not self.active_displays:
                self.display_layout.addWidget(self.help_label, 0, 0)
            
            # Mise à jour statistiques
            self.cameras_label.setText(f"Caméras: {len(self.active_displays)}/{len(self.available_cameras)}")
    
    def _reorganize_display_grid(self):
        """Réorganise la grille d'affichage"""
        if not self.active_displays:
            return
            
        # Nettoyage layout
        for i in reversed(range(self.display_layout.count())):
            item = self.display_layout.itemAt(i)
            if item and item.widget() and item.widget() != self.help_label:
                item.widget().setParent(None)
        
        # Réajout dans l'ordre
        max_cols_single = self.config.get('ui', 'camera_tab.layout.max_columns_single', 3)
        max_cols_dual = self.config.get('ui', 'camera_tab.layout.max_columns_dual', 2)
        cols = max_cols_dual if self.show_depth_cb.isChecked() else max_cols_single
        
        for i, (alias, widget) in enumerate(self.active_displays.items()):
            row = i // cols
            col = i % cols
            self.display_layout.addWidget(widget, row, col)
    
    def _start_streaming(self):
        """Démarre le streaming de toutes les caméras actives"""
        if self.is_streaming:
            return
            
        if not self.active_displays:
            no_cameras_msg = self.config.get('ui', 'camera_tab.messages.no_cameras_streaming', 
                                           "⚠️ Aucune caméra ouverte pour le streaming")
            self._log(no_cameras_msg)
            return
        
        self.is_streaming = True
        self.frame_count = 0
        
        # Démarrage timers
        fps_target = self.fps_spinbox.value()
        update_interval = int(1000 / fps_target)  # Conversion en ms
        self.update_timer.start(update_interval)
        
        stats_interval = self.config.get('ui', 'camera_tab.timers.stats_interval_ms', 1000)
        self.stats_timer.start(stats_interval)
        
        streaming_msg = self.config.get('ui', 'camera_tab.messages.streaming_started', 
                                       "🎬 Streaming démarré à {fps} FPS")
        self._log(streaming_msg.format(fps=fps_target))
        
        # Émission signal pour les autres onglets
        if self.selected_camera:
            alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
            self.camera_started.emit(alias)
        
        self._update_controls_state()
    
    def _stop_streaming(self):
        """Arrête le streaming"""
        if not self.is_streaming:
            return
            
        self.is_streaming = False
        
        # Arrêt timers
        self.update_timer.stop()
        self.stats_timer.stop()
        
        streaming_stopped_msg = self.config.get('ui', 'camera_tab.messages.streaming_stopped', 
                                               "⏹️ Streaming arrêté")
        self._log(streaming_stopped_msg)
        
        self._update_controls_state()
    
    def _update_camera_frames(self):
        """Met à jour les frames des caméras"""
        if not self.is_streaming or not self.active_displays:
            return
        
        frames_updated = 0
        start_time = time.time()
        
        for alias, display_widget in self.active_displays.items():
            try:
                ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(alias)
                
                if ret and color_frame is not None:
                    # Ajout overlays si activé
                    if self.show_info_cb.isChecked():
                        color_frame = self._add_info_overlay(color_frame, alias)
                    
                    display_widget.update_frame(color_frame, depth_frame)
                    frames_updated += 1
                    
                    # Émission signal pour autres onglets
                    frame_data = {
                        'alias': alias,
                        'color': color_frame,
                        'depth': depth_frame,
                        'timestamp': time.time()
                    }
                    self.frame_captured.emit(alias, frame_data)
                    
            except Exception as e:
                logger.debug(f"Erreur mise à jour frame {alias}: {e}")
        
        self.frame_count += frames_updated
        
        # Calcul temps de traitement
        processing_time = (time.time() - start_time) * 1000  # en ms
        if processing_time > 50:  # Log si > 50ms
            logger.debug(f"Temps traitement frames: {processing_time:.1f}ms")
    
    def _add_info_overlay(self, frame: np.ndarray, alias: str) -> np.ndarray:
        """Ajoute des informations en overlay sur la frame"""
        if not self.show_fps_cb.isChecked():
            return frame
        
        # Informations à afficher
        info_text = f"FPS: {self.current_fps:.1f}"
        if self.show_info_cb.isChecked():
            info_text += f" | {alias}"
        
        # Style depuis config
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = self.config.get('ui', 'camera_tab.overlay.font_scale', 0.6)
        color = tuple(self.config.get('ui', 'camera_tab.overlay.text_color', [255, 255, 255]))
        thickness = self.config.get('ui', 'camera_tab.overlay.thickness', 1)
        
        # Position
        position = (10, 30)
        
        # Fond semi-transparent
        text_size = cv2.getTextSize(info_text, font, font_scale, thickness)[0]
        cv2.rectangle(frame, (5, 5), (text_size[0] + 15, text_size[1] + 15), (0, 0, 0), -1)
        cv2.rectangle(frame, (5, 5), (text_size[0] + 15, text_size[1] + 15), (255, 255, 255), 1)
        
        # Texte
        cv2.putText(frame, info_text, position, font, font_scale, color, thickness)
        
        return frame
    
    def _update_statistics(self):
        """Met à jour les statistiques d'affichage"""
        if self.is_streaming:
            # Calcul FPS basé sur l'intervalle de mise à jour
            fps_target = self.fps_spinbox.value()
            self.current_fps = fps_target if self.active_displays else 0.0
        else:
            self.current_fps = 0.0
        
        # Mise à jour labels
        self.fps_label.setText(f"FPS: {self.current_fps:.1f}")
        self.cameras_label.setText(f"Caméras: {len(self.active_displays)}/{len(self.available_cameras)}")
        self.frames_label.setText(f"Images: {self.frame_count}")
    
    def _on_fps_changed(self, value):
        """Gestion du changement de FPS cible"""
        self._log(f"🎬 FPS cible modifié: {value}")
        
        # Redémarrage avec nouveau FPS si streaming actif
        if self.is_streaming:
            self._stop_streaming()
            self._start_streaming()
    
    def _on_zoom_changed(self, value):
        """Gestion du changement de zoom"""
        zoom_factor = value / 100.0
        self.zoom_label.setText(f"{value}%")
        
        # Application zoom à tous les affichages
        for display_widget in self.active_displays.values():
            display_widget.set_zoom(zoom_factor)
        
        zoom_msg = self.config.get('ui', 'camera_tab.messages.zoom_changed', 
                                   "🔍 Zoom modifié: {zoom}%")
        self._log(zoom_msg.format(zoom=value))
    
    def _toggle_depth_view(self):
        """Bascule l'affichage profondeur"""
        show_depth = self.show_depth_cb.isChecked()
        
        for alias, display_widget in self.active_displays.items():
            # Vérification que la caméra supporte la profondeur
            cam_data = self.camera_combo.currentData()
            if cam_data and cam_data.camera_type == CameraType.REALSENSE:
                display_widget.set_depth_view(show_depth)
            else:
                display_widget.set_depth_view(False)
        
        # Réorganisation grille si nécessaire
        self._reorganize_display_grid()
        
        depth_msg = self.config.get('ui', 'camera_tab.messages.depth_toggled', 
                                   "👁️ Vue profondeur: {state}")
        enabled_text = self.config.get('ui', 'camera_tab.messages.depth_enabled', "Activée")
        disabled_text = self.config.get('ui', 'camera_tab.messages.depth_disabled', "Désactivée")
        state = enabled_text if show_depth else disabled_text
        self._log(depth_msg.format(state=state))
    
    def _toggle_info_overlay(self):
        """Bascule l'affichage des informations en overlay"""
        show_info = self.show_info_cb.isChecked()
        
        info_msg = self.config.get('ui', 'camera_tab.messages.info_overlay_toggled',
                                   "📊 Overlay informations: {state}")
        state = "Activé" if show_info else "Désactivé"
        self._log(info_msg.format(state=state))
    
    def _camera_display_clicked(self, alias: str):
        """Gestion clic sur affichage caméra"""
        click_msg = self.config.get('ui', 'camera_tab.messages.camera_clicked', 
                                   "🖱️ Clic sur caméra: {alias}")
        self._log(click_msg.format(alias=alias))
        self.camera_selected.emit(alias)
    
    def _capture_frame(self):
        """Capture une frame"""
        if not self.selected_camera:
            no_camera_msg = self.config.get('ui', 'camera_tab.messages.no_camera_capture', 
                                           "⚠️ Aucune caméra sélectionnée")
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
                                                    "❌ Impossible de capturer: {alias}")
                self._log(capture_failed_msg.format(alias=alias))
                
        except Exception as e:
            capture_error_msg = self.config.get('ui', 'camera_tab.messages.capture_error', 
                                               'Erreur capture: {error}')
            self._log(capture_error_msg.format(error=e))
    
    def _save_image(self):
        """Sauvegarde l'image courante"""
        if not self.selected_camera:
            no_camera_save_msg = self.config.get('ui', 'camera_tab.messages.no_camera_save', 
                                                "⚠️ Aucune caméra pour sauvegarde")
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
            
            try:
                # Tentative sauvegarde via camera_manager
                if hasattr(self.camera_manager, 'save_camera_frame'):
                    success = self.camera_manager.save_camera_frame(alias, filepath)
                else:
                    # Fallback: capture et sauvegarde manuelle
                    ret, color_frame, depth_frame = self.camera_manager.get_camera_frame(alias)
                    if ret and color_frame is not None:
                        success = cv2.imwrite(filepath, color_frame)
                    else:
                        success = False
                
                if success:
                    save_success_msg = self.config.get('ui', 'camera_tab.messages.save_success', 
                                                      "💾 Image sauvée: {filepath}")
                    self._log(save_success_msg.format(filepath=filepath))
                    
                    # Sauvegarde profondeur si disponible et activée
                    if (self.show_depth_cb.isChecked() and 
                        self.selected_camera.camera_type == CameraType.REALSENSE):
                        
                        depth_suffix = self.config.get('ui', 'camera_tab.save.depth_suffix', '_depth')
                        depth_ext = self.config.get('ui', 'camera_tab.save.depth_extension', '.png')
                        
                        # Génération nom fichier profondeur
                        base_name = filepath.rsplit('.', 1)[0]
                        depth_filepath = f"{base_name}{depth_suffix}{depth_ext}"
                        
                        ret, _, depth_frame = self.camera_manager.get_camera_frame(alias)
                        
                        if ret and depth_frame is not None:
                            cv2.imwrite(depth_filepath, depth_frame)
                            depth_save_msg = self.config.get('ui', 'camera_tab.messages.depth_save_success', 
                                                            "🗂️ Image profondeur sauvée: {filepath}")
                            self._log(depth_save_msg.format(filepath=depth_filepath))
                else:
                    save_failed_msg = self.config.get('ui', 'camera_tab.messages.save_failed', 
                                                     "❌ Échec sauvegarde: {filepath}")
                    self._log(save_failed_msg.format(filepath=filepath))
                    
            except Exception as e:
                save_error_msg = self.config.get('ui', 'camera_tab.messages.save_error',
                                                'Erreur sauvegarde: {error}')
                self._log(save_error_msg.format(error=e))
    
    def _log(self, message: str):
        """Affiche un message dans le log"""
        timestamp = time.strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}"
        
        self.log_text.append(formatted_msg)
        
        # Limitation du nombre de lignes
        max_lines = self.config.get('ui', 'camera_tab.log.max_lines', 100)
        
        # Nettoyage si trop de lignes
        document = self.log_text.document()
        if document.blockCount() > max_lines:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
        
        # Scroll vers le bas
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # Log aussi dans le système de logging Python
        logger.info(message)
    
    # Méthodes publiques pour intégration avec MainWindow
    
    def start_acquisition(self):
        """Démarre l'acquisition (alias pour _start_streaming)"""
        self._start_streaming()
    
    def stop_acquisition(self):
        """Arrête l'acquisition (alias pour _stop_streaming)"""
        self._stop_streaming()
    
    def get_active_cameras(self) -> list:
        """Retourne la liste des caméras actives"""
        return list(self.active_displays.keys())
    
    def get_current_fps(self) -> float:
        """Retourne le FPS actuel"""
        return self.current_fps
    
    def is_acquiring(self) -> bool:
        """Retourne True si acquisition en cours"""
        return self.is_streaming
    
    def get_camera_frame(self, alias: str = None):
        """Récupère une frame de caméra"""
        if alias is None and self.selected_camera:
            alias = f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
        
        if alias and alias in self.active_displays:
            return self.camera_manager.get_camera_frame(alias)
        
        return False, None, None
    
    # Méthodes de nettoyage
    
    def cleanup(self):
        """Nettoyage lors de la fermeture"""
        try:
            # Arrêt streaming
            self._stop_streaming()
            
            # Fermeture caméras seulement si on possède le camera_manager
            if self.owns_camera_manager and hasattr(self, 'camera_manager'):
                self.camera_manager.close_all_cameras()
                logger.info("📷 Caméras fermées par CameraTab")
            else:
                logger.info("📷 Camera_manager externe - pas de fermeture automatique")
                
            # Nettoyage widgets
            for alias in list(self.active_displays.keys()):
                self._remove_camera_display(alias)
                
        except Exception as e:
            logger.error(f"❌ Erreur cleanup CameraTab: {e}")
    
    def closeEvent(self, event):
        """Gestion de la fermeture de l'onglet"""
        self.cleanup()
        event.accept()
    
    # Propriétés pour compatibilité
    
    @property 
    def current_camera_alias(self) -> str:
        """Retourne l'alias de la caméra courante"""
        if self.selected_camera:
            return f"{self.selected_camera.camera_type.value}_{self.selected_camera.device_id}"
        return ""
    
    @property
    def has_active_cameras(self) -> bool:
        """Retourne True si des caméras sont actives"""
        return len(self.active_displays) > 0