# robot_tracker/ui/target_tab.py
# Version: v4.4 - Correction méthode _update_video_display

import time
import logging
from typing import Optional

from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                            QLabel, QPushButton, QCheckBox, QSpinBox, 
                            QSlider, QMessageBox, QFileDialog)
from PyQt6.QtGui import QImage, QPixmap

from pathlib import Path

from core.aruco_config_loader import ArUcoConfigLoader
from core.target_detector import TargetDetector
from core.roi_manager import ROIManager

logger = logging.getLogger(__name__)

class TargetTab(QWidget):
    """
    Onglet Cible - Architecture Maître-Esclave
    
    Responsabilités:
    - Configuration ArUco et détection
    - Gestion ROI et tracking
    - Affichage flux avec overlays
    - Réception signaux de CameraTab (maître)
    
    Signaux reçus (CameraTab → TargetTab):
    - camera_opened → _on_camera_changed()
    - streaming_started → _on_streaming_started()
    - streaming_stopped → _on_streaming_stopped()
    
    Signaux émis (TargetTab → MainWindow):
    - tracking_started
    - tracking_stopped
    - target_detected
    - status_changed
    """
    
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
        
        version = self._safe_get_config('ui', 'target_tab.version', '4.4')
        logger.info(f"🎯 TargetTab v{version} initialisé avec corrections signaux")
        
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
        """Charge automatiquement le dernier dossier ArUco - CORRECTION COMPLÈTE"""
        try:
            # CORRECTION: Vérification que l'UI est initialisée
            if not hasattr(self, 'aruco_status_label') or not hasattr(self, 'markers_count_label'):
                logger.debug("⚠️ UI ArUco pas encore créée, auto-chargement reporté")
                # Programmer un retry
                QTimer.singleShot(500, self._auto_load_latest_aruco_folder)
                return
                
            # CORRECTION: Vérification méthode disponible
            if not hasattr(self.aruco_loader, 'get_latest_aruco_folder'):
                logger.warning("⚠️ Méthode get_latest_aruco_folder non disponible")
                self.aruco_status_label.setText("⚠️ Auto-chargement non disponible")
                self.aruco_status_label.setStyleSheet("QLabel { color: orange; }")
                return
                
            # Recherche du dernier dossier
            latest_folder = self.aruco_loader.get_latest_aruco_folder()
            
            if latest_folder:
                logger.info(f"🎯 Auto-chargement ArUco: {latest_folder}")
                self._scan_aruco_folder(latest_folder)
            else:
                logger.info("ℹ️ Aucun dossier ArUco trouvé pour auto-chargement")
                
                # Interface mise à jour même sans dossier
                self.aruco_status_label.setText("⚠️ Aucun dossier ArUco trouvé")
                self.aruco_status_label.setStyleSheet("QLabel { color: orange; }")
                self.markers_count_label.setText("Marqueurs: 0 détectés")
                self.markers_count_label.setStyleSheet("QLabel { color: orange; }")
                
        except Exception as e:
            logger.warning(f"⚠️ Erreur auto-chargement ArUco: {e}")
            
            try:
                self.aruco_status_label.setText("❌ Erreur auto-chargement")
                self.aruco_status_label.setStyleSheet("QLabel { color: red; }")
            except:
                pass
    
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
        
        layout.addStretch()  # Push vers le haut
        
        return panel
    
    def _create_camera_status_group(self):
        """Groupe d'état de la caméra (lecture seule)"""
        group = QGroupBox("📷 État Caméra")
        layout = QVBoxLayout(group)
        
        self.camera_status_label = QLabel("❌ Aucune caméra active")
        self.camera_status_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
        
        self.camera_alias_label = QLabel("Alias: N/A")
        self.camera_alias_label.setStyleSheet("QLabel { color: gray; }")
        
        info_label = QLabel("ℹ️ Géré par l'onglet Caméra")
        info_label.setStyleSheet("QLabel { color: blue; font-style: italic; }")
        
        layout.addWidget(self.camera_status_label)
        layout.addWidget(self.camera_alias_label)
        layout.addWidget(info_label)
        
        return group
    
    def _create_aruco_config_group(self):
        """Groupe de configuration ArUco"""
        group = QGroupBox("🎯 Configuration ArUco")
        layout = QVBoxLayout(group)
        
        # Sélection dossier
        folder_layout = QHBoxLayout()
        self.select_folder_btn = QPushButton("📁 Sélectionner Dossier")
        self.select_folder_btn.clicked.connect(self._select_aruco_folder)
        self.rescan_btn = QPushButton("🔄")
        self.rescan_btn.setMaximumWidth(30)
        self.rescan_btn.clicked.connect(self._rescan_current_folder)
        
        folder_layout.addWidget(self.select_folder_btn)
        folder_layout.addWidget(self.rescan_btn)
        
        # Status
        self.aruco_status_label = QLabel("Dossier: Non sélectionné")
        self.markers_count_label = QLabel("Marqueurs: 0 détectés")
        
        layout.addLayout(folder_layout)
        layout.addWidget(self.aruco_status_label)
        layout.addWidget(self.markers_count_label)
        
        return group
    
    def _create_detection_types_group(self):
        """Groupe des types de détection"""
        group = QGroupBox("🔍 Types de Détection")
        layout = QVBoxLayout(group)
        
        self.aruco_check = QCheckBox("ArUco Markers")
        self.aruco_check.setChecked(True)
        self.aruco_check.toggled.connect(self._on_detection_type_changed)
        
        self.reflective_check = QCheckBox("Marqueurs Réfléchissants")
        self.reflective_check.setChecked(False)
        self.reflective_check.toggled.connect(self._on_detection_type_changed)
        
        self.led_check = QCheckBox("LEDs Colorées")
        self.led_check.setChecked(False)
        self.led_check.toggled.connect(self._on_detection_type_changed)
        
        layout.addWidget(self.aruco_check)
        layout.addWidget(self.reflective_check)
        layout.addWidget(self.led_check)
        
        return group
    
    def _create_roi_tools_group(self):
        """Groupe des outils ROI"""
        group = QGroupBox("📐 Outils ROI")
        layout = QVBoxLayout(group)
        
        roi_buttons_layout = QHBoxLayout()
        
        self.roi_rect_btn = QPushButton("⬜")
        self.roi_rect_btn.setToolTip("Rectangle")
        self.roi_polygon_btn = QPushButton("⬟")
        self.roi_polygon_btn.setToolTip("Polygone")
        self.clear_roi_btn = QPushButton("🗑️")
        self.clear_roi_btn.setToolTip("Effacer ROI")
        
        roi_buttons_layout.addWidget(self.roi_rect_btn)
        roi_buttons_layout.addWidget(self.roi_polygon_btn)
        roi_buttons_layout.addWidget(self.clear_roi_btn)
        
        self.roi_status_label = QLabel("ROI: Aucune")
        
        layout.addLayout(roi_buttons_layout)
        layout.addWidget(self.roi_status_label)
        
        return group
    
    def _create_tracking_controls_group(self):
        """Groupe des contrôles de tracking"""
        group = QGroupBox("🎬 Contrôles Tracking")
        layout = QVBoxLayout(group)
        
        # Boutons start/stop
        buttons_layout = QHBoxLayout()
        self.start_tracking_btn = QPushButton("▶️ Démarrer")
        self.start_tracking_btn.clicked.connect(self._start_tracking)
        self.start_tracking_btn.setEnabled(False)
        
        self.stop_tracking_btn = QPushButton("⏹️ Arrêter")
        self.stop_tracking_btn.clicked.connect(self._stop_tracking)
        self.stop_tracking_btn.setEnabled(False)
        
        buttons_layout.addWidget(self.start_tracking_btn)
        buttons_layout.addWidget(self.stop_tracking_btn)
        
        # Paramètres
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("FPS Cible:"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(30)
        fps_layout.addWidget(self.fps_spin)
        fps_layout.addWidget(QLabel("fps"))
        
        confidence_layout = QHBoxLayout()
        confidence_layout.addWidget(QLabel("Confiance:"))
        self.confidence_spin = QSpinBox()
        self.confidence_spin.setRange(1, 100)
        self.confidence_spin.setValue(80)
        self.confidence_spin.setSuffix("%")
        confidence_layout.addWidget(self.confidence_spin)
        
        # Zoom
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(50, 200)
        self.zoom_slider.setValue(100)
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(QLabel("100%"))
        
        layout.addLayout(buttons_layout)
        layout.addLayout(fps_layout)
        layout.addLayout(confidence_layout)
        layout.addLayout(zoom_layout)
        
        return group
    
    def _create_statistics_group(self):
        """Groupe des statistiques"""
        group = QGroupBox("📊 Statistiques")
        layout = QVBoxLayout(group)
        
        self.detections_count_label = QLabel("Détections: 0")
        self.fps_label = QLabel("FPS: 0.0")
        self.processing_time_label = QLabel("Temps: 0ms")
        
        layout.addWidget(self.detections_count_label)
        layout.addWidget(self.fps_label)
        layout.addWidget(self.processing_time_label)
        
        return group
    
    def _create_display_area(self):
        """Zone d'affichage vidéo avec overlays"""
        self.camera_display = QLabel("En attente du flux caméra...")
        self.camera_display.setStyleSheet("QLabel { border: 1px solid gray; background: black; color: white; }")
        self.camera_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_display.setMinimumSize(640, 480)
        
        return self.camera_display
    
    # === MÉTHODES DE CONNEXION SIGNAUX ===
    
    def _connect_internal_signals(self):
        """Connecte les signaux internes de l'onglet"""
        # Connexions déjà établies dans _create_*_group()
        pass
    
    # === SLOTS POUR SIGNAUX EXTERNES (CameraTab → TargetTab) ===
    
    def _on_camera_changed(self, camera_alias: str):
        """Slot appelé quand une caméra est sélectionnée/ouverte"""
        logger.info(f"🎥 Signal caméra changée reçu: {camera_alias}")
        
        # Validation caméra disponible
        if not self.camera_manager.is_camera_open(camera_alias):
            logger.warning(f"⚠️ Caméra {camera_alias} non disponible")
            self.camera_ready = False
            self.selected_camera_alias = None
            self._update_camera_status()
            return
        
        # Mise à jour état
        self.selected_camera_alias = camera_alias
        self.camera_ready = True
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
        """MÉTHODE CORRIGÉE - Traite la frame courante avec optimisations performance"""
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
                
                # CORRECTION: Appel correct de la méthode d'affichage
                self._update_display()  # Au lieu de self._update_video_display()
                
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
            # Utilisation de detect_all_targets
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
        """MÉTHODE CORRIGÉE - Met à jour l'affichage avec la frame et les overlays"""
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
            # Code de dessin ROI à implémenter
        
        # Détections ArUco
        if hasattr(self, 'detected_targets') and self.detected_targets:
            for target in self.detected_targets:
                # Code de dessin des détections à implémenter
                pass
    
    # === MÉTHODES D'INTERFACE ===
    
    def _select_aruco_folder(self):
        """Sélectionne un dossier ArUco"""
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner dossier ArUco")
        if folder:
            self._scan_aruco_folder(folder)
    
    def _scan_aruco_folder(self, folder_path):
        """Scanne un dossier ArUco - CORRECTION COMPLÈTE"""
        try:
            logger.info(f"🔍 Scan dossier ArUco: {folder_path}")
            
            # CORRECTION 1: Utilisation de scan_aruco_folder (nom correct)
            detected_markers = self.aruco_loader.scan_aruco_folder(folder_path)
            markers_count = len(detected_markers) if detected_markers else 0
            
            logger.info(f"📊 Marqueurs détectés: {markers_count}")
            
            # CORRECTION 2: Mise à jour de l'interface avec gestion d'erreurs
            try:
                folder_name = Path(folder_path).name
                self.aruco_status_label.setText(f"📁 {folder_name}")
                self.markers_count_label.setText(f"Marqueurs: {markers_count} détectés")
                
                if markers_count > 0:
                    self.aruco_status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
                    self.markers_count_label.setStyleSheet("QLabel { color: green; }")
                    
                    # CORRECTION 3: Détection du dictionnaire si disponible
                    try:
                        if hasattr(self.aruco_loader, '_detect_common_dictionary'):
                            dict_name = self.aruco_loader._detect_common_dictionary()
                            logger.info(f"🎯 Dictionnaire détecté: {dict_name}")
                            
                            # CORRECTION 4: Mise à jour du détecteur avec méthodes disponibles
                            if hasattr(self.target_detector, 'update_aruco_dictionary'):
                                self.target_detector.update_aruco_dictionary(dict_name)
                                logger.info(f"✅ Détecteur mis à jour: {dict_name}")
                            elif hasattr(self.target_detector, 'set_aruco_dictionary'):
                                self.target_detector.set_aruco_dictionary(dict_name)
                                logger.info(f"✅ Dictionnaire configuré: {dict_name}")
                            else:
                                logger.warning(f"⚠️ Impossible de configurer le dictionnaire: {dict_name}")
                                
                    except Exception as dict_error:
                        logger.warning(f"⚠️ Erreur détection dictionnaire: {dict_error}")
                        
                else:
                    self.aruco_status_label.setStyleSheet("QLabel { color: orange; }")
                    self.markers_count_label.setStyleSheet("QLabel { color: orange; }")
                    logger.warning(f"⚠️ Aucun marqueur trouvé dans {folder_path}")
                    
            except Exception as ui_error:
                logger.error(f"❌ Erreur mise à jour interface: {ui_error}")
                
        except Exception as e:
            logger.error(f"❌ Erreur scan ArUco: {e}")
            
            # Mise à jour interface en cas d'erreur
            try:
                self.aruco_status_label.setText("❌ Erreur scan")
                self.aruco_status_label.setStyleSheet("QLabel { color: red; }")
                self.markers_count_label.setText("Marqueurs: Erreur")
                self.markers_count_label.setStyleSheet("QLabel { color: red; }")
            except:
                pass  # Ignore les erreurs d'interface si l'UI n'est pas initialisée
                
            # Message utilisateur
            QMessageBox.warning(self, "Erreur Scan ArUco", 
                              f"Erreur lors du scan du dossier ArUco:\n\n{str(e)}\n\n"
                              f"Vérifiez que le dossier contient des fichiers de marqueurs ArUco.")
    
    def _rescan_current_folder(self):
        """Rescanne le dossier ArUco actuel - CORRECTION"""
        try:
            # CORRECTION: Vérification robuste du dossier actuel
            current_folder = None
            
            if hasattr(self.aruco_loader, 'folder_path') and self.aruco_loader.folder_path:
                current_folder = str(self.aruco_loader.folder_path)
            elif hasattr(self.aruco_loader, 'current_folder') and self.aruco_loader.current_folder:
                current_folder = self.aruco_loader.current_folder
                
            if current_folder:
                logger.info(f"🔄 Rescan ArUco: {current_folder}")
                self._scan_aruco_folder(current_folder)
            else:
                logger.warning("⚠️ Aucun dossier ArUco à rescanner")
                QMessageBox.information(self, "Rescan", 
                                      "Aucun dossier ArUco sélectionné.\n"
                                      "Veuillez d'abord sélectionner un dossier avec le bouton '📁'.")
                                      
        except Exception as e:
            logger.error(f"❌ Erreur rescan ArUco: {e}")
            QMessageBox.warning(self, "Erreur", f"Erreur lors du rescan:\n{e}")
    
    def _on_detection_type_changed(self):
        """Callback changement types de détection"""
        if hasattr(self, 'target_detector'):
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
    
    def _start_tracking(self):
        """Démarre le tracking"""
        if not self.camera_ready:
            QMessageBox.warning(self, "Erreur", "Aucune caméra active")
            return
        
        self.is_tracking = True
        self.start_tracking_btn.setEnabled(False)
        self.stop_tracking_btn.setEnabled(True)
        
        # Émission du signal
        self.tracking_started.emit()
        
        logger.info("🎯 Tracking démarré")
    
    def _stop_tracking(self):
        """Arrête le tracking"""
        self.is_tracking = False
        self.start_tracking_btn.setEnabled(self.camera_ready)
        self.stop_tracking_btn.setEnabled(False)
        
        # Émission du signal
        self.tracking_stopped.emit()
        
        logger.info("🛑 Tracking arrêté")
    
    def _update_detection_stats(self, detection_info):
        """Met à jour les statistiques de détection"""
        try:
            self.detection_stats['total_detections'] += detection_info.get('detection_count', 0)
            
            # Calcul FPS
            current_time = time.time()
            if self.detection_stats['last_detection_time'] > 0:
                time_diff = current_time - self.detection_stats['last_detection_time']
                if time_diff > 0:
                    self.detection_stats['fps'] = 1.0 / time_diff
            
            self.detection_stats['last_detection_time'] = current_time
            
            # Mise à jour de l'affichage
            self.detections_count_label.setText(f"Détections: {self.detection_stats['total_detections']}")
            self.fps_label.setText(f"FPS: {self.detection_stats['fps']:.1f}")
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour stats: {e}")
    
    def _check_camera_status(self):
        """Vérifie périodiquement l'état de la caméra"""
        try:
            if self.selected_camera_alias:
                # Vérification si caméra toujours active
                if self.camera_manager and hasattr(self.camera_manager, 'is_camera_open'):
                    if self.camera_manager.is_camera_open(self.selected_camera_alias):
                        # Caméra OK
                        if hasattr(self.camera_manager, '_is_streaming') and self.camera_manager._is_streaming:
                            status_text = f"État: ✅ {self.selected_camera_alias} streaming"
                            color = "green"
                        else:
                            status_text = f"État: ✅ {self.selected_camera_alias} prête"
                            color = "green"
                    else:
                        # Caméra fermée
                        status_text = "État: ❌ Caméra fermée"
                        color = "red"
                        self.camera_ready = False
                else:
                    status_text = "État: ⚠️ Manager non disponible"
                    color = "orange"
                    self.camera_ready = False
            else:
                # Aucune caméra sélectionnée
                status_text = "État: Aucune caméra"
                color = "orange"
                self.camera_ready = False
            
            # Mise à jour interface
            if hasattr(self, 'camera_status_label'):
                self.camera_status_label.setText(status_text)
                self.camera_status_label.setStyleSheet(f"QLabel {{ color: {color}; }}")
                
        except Exception as e:
            logger.error(f"❌ Erreur vérification statut caméra: {e}")

    # === MÉTHODES UTILITAIRES ===
    
    def get_current_detection_results(self):
        """Retourne les résultats de détection actuels"""
        return getattr(self, 'detected_targets', [])
    
    def get_tracking_statistics(self):
        """Retourne les statistiques de tracking"""
        return self.detection_stats.copy()
    
    def is_camera_ready(self):
        """Vérifie si une caméra est prête"""
        return self.camera_ready and self.selected_camera_alias is not None
    
    def force_camera_refresh(self):
        """Force une actualisation de l'état caméra"""
        self._check_camera_status()
    
    # === MÉTHODES DE DEBUGGING ===
    
    def _debug_aruco_info(self):
        """Affiche les informations de débogage ArUco"""
        debug_info = []
        debug_info.append(f"Dossier ArUco: {getattr(self.aruco_loader, 'current_folder', 'Non défini')}")
        debug_info.append(f"Marqueurs chargés: {len(getattr(self.aruco_loader, 'markers', []))}")
        
        if hasattr(self.target_detector, 'aruco_detector'):
            debug_info.append(f"Détecteur initialisé: Oui")
        else:
            debug_info.append(f"Détecteur initialisé: Non")
        
        debug_info.append(f"Types détection actifs:")
        debug_info.append(f"  - ArUco: {self.aruco_check.isChecked()}")
        debug_info.append(f"  - Réfléchissants: {self.reflective_check.isChecked()}")
        debug_info.append(f"  - LEDs: {self.led_check.isChecked()}")
        
        debug_info.append(f"ROI activée: {getattr(self, 'roi_detection_enabled', False)}")
        debug_info.append(f"Détections totales: {self.detection_stats['total_detections']}")
        debug_info.append(f"FPS: {self.detection_stats['fps']:.1f}\n")
        
        # Validation
        if hasattr(self.aruco_loader, 'validate_markers'):
            valid_count, issues = self.aruco_loader.validate_markers()
            debug_info.append(f"Marqueurs valides: {valid_count}")
            if issues:
                debug_info.append("Problèmes détectés:")
                for issue in issues[:10]:
                    debug_info.append(f"  - {issue}")
                if len(issues) > 10:
                    debug_info.append(f"  ... et {len(issues) - 10} autres problèmes")
        
        # Affichage dans une fenêtre de dialogue
        msg = QMessageBox(self)
        msg.setWindowTitle("Debug ArUco")
        msg.setText("Informations de débogage ArUco:")
        msg.setDetailedText('\n'.join(debug_info))
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
    
    # === MÉTHODES DE CLEANUP ===
    
    def closeEvent(self, event):
        """Nettoyage à la fermeture"""
        try:
            if hasattr(self, 'processing_timer'):
                self.processing_timer.stop()
            if hasattr(self, 'camera_check_timer'):
                self.camera_check_timer.stop()
            if self.is_tracking:
                self._stop_tracking()
                
            logger.info("🛑 TargetTab fermé proprement")
        except Exception as e:
            logger.error(f"❌ Erreur fermeture TargetTab: {e}")
        finally:
            event.accept()
    
    def __del__(self):
        """Destructeur - nettoyage final"""
        try:
            if hasattr(self, 'processing_timer') and self.processing_timer.isActive():
                self.processing_timer.stop()
            if hasattr(self, 'camera_check_timer') and self.camera_check_timer.isActive():
                self.camera_check_timer.stop()
        except:
            pass  # Ignore les erreurs à la destruction