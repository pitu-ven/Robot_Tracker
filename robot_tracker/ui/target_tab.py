# robot_tracker/ui/target_tab.py
# Version 2.5 - CORRECTION: ROI cassant la détection ArUco
# Modifications:
# - ROI appliquée seulement quand explicitement activée
# - Correction initialisation détecteur sans ROI forcée
# - Amélioration gestion états ROI/détection

import cv2
import numpy as np
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QSplitter,
    QGroupBox, QPushButton, QLabel, QComboBox, QSpinBox, QCheckBox,
    QLineEdit, QTextEdit, QProgressBar, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSlider, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QPixmap, QImage, QFont, QIcon, QPainter, QPen, QColor

# Import avec fallback pour éviter les erreurs d'import relatif
try:
    from core.aruco_config_loader import ArUcoConfigLoader
    from core.target_detector import TargetDetector, TargetType
    from core.roi_manager import ROIManager, ROIType
except ImportError:
    # Stubs temporaires pour éviter les erreurs lors du développement
    class ArUcoConfigLoader:
        def __init__(self, config): self.detected_markers = {}
        def scan_aruco_folder(self, folder_path): return {}
        def get_detector_params(self): return {}
        def get_latest_aruco_folder(self): return None
        def validate_markers(self): return 0, []
        def _detect_common_dictionary(self): return "DICT_4X4_50"
    
    class TargetDetector:
        def __init__(self, config): 
            self.detection_enabled = {'aruco': True, 'reflective': True, 'led': True}
        def detect_all_targets(self, frame): return []
        def set_roi(self, roi=None, enabled=False): pass
        def set_detection_enabled(self, target_type, enabled): pass
    
    class TargetType:
        ARUCO = "aruco"
        REFLECTIVE = "reflective"
        LED = "led"
    
    class ROIManager:
        def __init__(self, config_manager): 
            self.is_creating = False
            self.rois = []
            self.temp_points = []
            self.creation_type = None
            self.selected_roi_id = None
        def start_roi_creation(self, roi_type): 
            self.is_creating = True
            return True
        def add_creation_point(self, point): return False
        def cancel_roi_creation(self): self.is_creating = False
        def complete_polygon_creation(self): return False

    class ROIType:
        RECTANGLE = "rectangle"
        POLYGON = "polygon"
        CIRCLE = "circle"

logger = logging.getLogger(__name__)

class TargetTab(QWidget):
    """Onglet Cible - Focus détection/suivi avec détection automatique caméra"""
    
    # Signaux pour communication inter-onglets
    target_detected = pyqtSignal(dict)
    tracking_started = pyqtSignal()
    tracking_stopped = pyqtSignal()
    status_changed = pyqtSignal(dict)
    
    def __init__(self, config_manager, camera_manager):
        super().__init__()
        
        # Managers principaux
        self.config = config_manager
        self.camera_manager = camera_manager
        
        # États internes
        self.current_frame = None
        self.detected_targets = []
        self.is_tracking_active = False
        self.roi_detection_enabled = False  # CORRECTION: ROI désactivée par défaut
        
        # Statistiques
        self.detection_stats = {
            'total_detections': 0,
            'fps': 0.0,
            'last_update': time.time()
        }
        
        # Configuration interface
        self.setup_detection_components()
        self._setup_ui()
        self._setup_timers()
        self._auto_load_latest_aruco_folder()
        
        # CORRECTION: Configuration initiale du détecteur SANS ROI
        self._configure_detector_without_roi()
        
        logger.info("✅ TargetTab initialisé avec détection ArUco libre")
    
    def setup_detection_components(self):
        """Configure les composants de détection"""
        try:
            # Chargement des composants réels
            self.aruco_loader = ArUcoConfigLoader(self.config)
            self.target_detector = TargetDetector(self.config)
            self.roi_manager = ROIManager(self.config)
            
        except Exception as e:
            logger.warning(f"⚠️ Composants détection non disponibles: {e}")
            # Fallback avec stubs
            self.aruco_loader = ArUcoConfigLoader(self.config)
            self.target_detector = TargetDetector(self.config)
            self.roi_manager = ROIManager(self.config)

    def _configure_detector_without_roi(self):
        """CORRECTION: Configure le détecteur sans ROI au démarrage"""
        if hasattr(self.target_detector, 'set_roi'):
            self.target_detector.set_roi(roi=None, enabled=False)
            logger.info("🎯 Détecteur configuré SANS ROI - détection libre")
        else:
            logger.warning("⚠️ Méthode set_roi non disponible sur le détecteur")

    # === MÉTHODES ROI CORRIGÉES ===
    
    def _start_roi_creation(self, roi_type):
        """Démarre la création d'une ROI"""
        try:
            # Conversion string → ROIType enum
            from core.roi_manager import ROIType
            
            if roi_type == 'rectangle':
                roi_enum = ROIType.RECTANGLE
            elif roi_type == 'polygon':
                roi_enum = ROIType.POLYGON
            else:
                logger.warning(f"Type ROI non supporté: {roi_type}")
                return
            
            success = self.roi_manager.start_roi_creation(roi_enum)
            if success:
                logger.info(f"📐 Création ROI {roi_type} démarrée")
                # NOTE: La détection continue NORMALEMENT pendant la création
            else:
                logger.warning("⚠️ Impossible de démarrer création ROI")
            
        except Exception as e:
            logger.error(f"❌ Erreur création ROI: {e}")
    
    def _clear_all_rois(self):
        """Efface toutes les ROI et désactive le filtrage ROI"""
        try:
            roi_count = len(self.roi_manager.rois)
            self.roi_manager.rois.clear()
            
            # CORRECTION: Désactiver explicitement le filtrage ROI
            self.roi_detection_enabled = False
            if hasattr(self.target_detector, 'set_roi'):
                self.target_detector.set_roi(roi=None, enabled=False)
            
            logger.info(f"🗑️ {roi_count} ROI supprimées - détection libre rétablie")
            
        except Exception as e:
            logger.error(f"❌ Erreur suppression ROI: {e}")

    def _toggle_roi_detection(self):
        """Active/désactive le filtrage de détection par ROI"""
        if not self.roi_manager.rois:
            QMessageBox.information(self, "ROI", "Aucune ROI définie pour filtrer la détection")
            return
        
        self.roi_detection_enabled = not self.roi_detection_enabled
        
        if self.roi_detection_enabled:
            # Appliquer la première ROI active comme filtre
            active_rois = [roi for roi in self.roi_manager.rois if hasattr(roi, 'state') and roi.state.value != 'INACTIVE']
            if active_rois:
                selected_roi = active_rois[0]
                if hasattr(self.target_detector, 'set_roi'):
                    self.target_detector.set_roi(roi=selected_roi, enabled=True)
                logger.info(f"🔍 Détection limitée à ROI: {selected_roi}")
            else:
                self.roi_detection_enabled = False
                logger.warning("⚠️ Aucune ROI active - filtrage désactivé")
        else:
            # Désactiver filtrage ROI
            if hasattr(self.target_detector, 'set_roi'):
                self.target_detector.set_roi(roi=None, enabled=False)
            logger.info("🔍 Détection libre - ROI désactivée")

    def _detect_targets_in_frame(self):
        """Effectue la détection des cibles dans la frame courante"""
        if self.current_frame is None:
            return
        
        # Protection contre traitement concurrent
        if hasattr(self, '_processing_detection') and self._processing_detection:
            return
        
        self._processing_detection = True

        try:
            # CORRECTION: Utilisation directe sans modification de ROI
            detected_results = self.target_detector.detect_all_targets(self.current_frame)
            
            # Conversion des résultats pour compatibilité
            self.detected_targets = detected_results
            
            # Création des infos de détection
            detection_info = {
                'frame_size': self.current_frame.shape[:2],
                'detection_count': len(detected_results),
                'detection_time': time.time(),
                'target_types': [result.target_type.value for result in detected_results] if detected_results else [],
                'roi_enabled': self.roi_detection_enabled
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

    def _update_detection_stats(self, detection_info):
        """Met à jour les statistiques de détection"""
        try:
            current_time = time.time()
            time_diff = current_time - self.detection_stats['last_update']
            
            if time_diff > 0:
                self.detection_stats['fps'] = 1.0 / time_diff
            
            self.detection_stats['total_detections'] += detection_info['detection_count']
            self.detection_stats['last_update'] = current_time
            
            # Log périodique
            if self.detection_stats['total_detections'] % 100 == 0 and detection_info['detection_count'] > 0:
                fps_str = f"{self.detection_stats['fps']:.1f}"
                roi_status = "avec ROI" if detection_info.get('roi_enabled', False) else "libre"
                logger.info(f"📊 Détection {roi_status}: {detection_info['detection_count']} cibles, {fps_str} FPS")
                
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour stats: {e}")

    # === CRÉATION UI SIMPLIFIÉE ===
    
    def _setup_ui(self):
        """Configure l'interface utilisateur simplifiée"""
        main_layout = QHBoxLayout(self)
        
        # Panneau de contrôle (gauche)
        control_panel = self._create_control_panel()
        control_width = self._safe_get_config('ui', 'target_tab.layout.control_panel_width', 320)
        control_panel.setMaximumWidth(control_width)
        
        # Zone d'affichage (droite)
        display_area = self._create_display_area()
        
        main_layout.addWidget(control_panel)
        main_layout.addWidget(display_area, 1)

    def _create_control_panel(self):
        """Crée le panneau de contrôle focalisé sur la détection"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 1. État de la caméra
        camera_status_group = self._create_camera_status_group()
        layout.addWidget(camera_status_group)
        
        # 2. Configuration ArUco
        aruco_group = self._create_aruco_config_group()
        layout.addWidget(aruco_group)
        
        # 3. Types de détection
        detection_types_group = self._create_detection_types_group()
        layout.addWidget(detection_types_group)
        
        # 4. CORRECTION: Outils ROI avec état clair
        roi_tools_group = self._create_roi_tools_group_corrected()
        layout.addWidget(roi_tools_group)
        
        # 5. Statistiques
        stats_group = self._create_stats_group()
        layout.addWidget(stats_group)
        
        layout.addStretch()
        return panel

    def _create_roi_tools_group_corrected(self):
        """CORRECTION: Groupe ROI avec état de filtrage clair"""
        group = QGroupBox("🔍 Régions d'Intérêt (ROI)")
        layout = QVBoxLayout(group)
        
        # État du filtrage ROI
        status_layout = QHBoxLayout()
        self.roi_status_label = QLabel("Détection: Libre (sans ROI)")
        self.roi_status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
        status_layout.addWidget(self.roi_status_label)
        layout.addLayout(status_layout)
        
        # Boutons de création ROI
        creation_layout = QHBoxLayout()
        
        self.create_rect_btn = QPushButton("Rectangle")
        self.create_rect_btn.clicked.connect(lambda: self._start_roi_creation('rectangle'))
        
        self.create_poly_btn = QPushButton("Polygone")
        self.create_poly_btn.clicked.connect(lambda: self._start_roi_creation('polygon'))
        
        creation_layout.addWidget(self.create_rect_btn)
        creation_layout.addWidget(self.create_poly_btn)
        layout.addLayout(creation_layout)
        
        # Contrôles ROI
        controls_layout = QHBoxLayout()
        
        self.toggle_roi_detection_btn = QPushButton("Activer filtrage ROI")
        self.toggle_roi_detection_btn.clicked.connect(self._toggle_roi_detection)
        self.toggle_roi_detection_btn.setEnabled(False)  # Désactivé au départ
        
        self.clear_rois_btn = QPushButton("Effacer tout")
        self.clear_rois_btn.clicked.connect(self._clear_all_rois)
        
        controls_layout.addWidget(self.toggle_roi_detection_btn)
        controls_layout.addWidget(self.clear_rois_btn)
        layout.addLayout(controls_layout)
        
        return group

    def _create_camera_status_group(self):
        """Groupe état caméra avec détection automatique"""
        group = QGroupBox("📹 État Caméra")
        layout = QVBoxLayout(group)
        
        # Status caméra
        self.camera_status_label = QLabel("État: Détection...")
        layout.addWidget(self.camera_status_label)
        
        # Bouton refresh manuel
        self.refresh_camera_btn = QPushButton("🔄 Actualiser")
        self.refresh_camera_btn.clicked.connect(self._refresh_camera_status)
        layout.addWidget(self.refresh_camera_btn)
        
        return group

    def _create_aruco_config_group(self):
        """Groupe configuration ArUco"""
        group = QGroupBox("🎯 Configuration ArUco")
        layout = QVBoxLayout(group)
        
        # Sélection dossier
        folder_layout = QHBoxLayout()
        self.select_aruco_btn = QPushButton("📁 Dossier")
        self.select_aruco_btn.clicked.connect(self._select_aruco_folder)
        self.aruco_folder_label = QLabel("Aucun dossier")
        
        folder_layout.addWidget(self.select_aruco_btn)
        folder_layout.addWidget(self.aruco_folder_label, 1)
        layout.addLayout(folder_layout)
        
        # Statistiques marqueurs
        self.aruco_stats_label = QLabel("Marqueurs: 0 détecté")
        layout.addWidget(self.aruco_stats_label)
        
        # Boutons d'action
        actions_layout = QHBoxLayout()
        self.rescan_btn = QPushButton("🔄 Re-scan")
        self.rescan_btn.clicked.connect(self._rescan_aruco_folder)
        self.rescan_btn.setEnabled(False)
        
        self.debug_btn = QPushButton("🔍 Debug")
        self.debug_btn.clicked.connect(self._show_aruco_debug_info)
        self.debug_btn.setEnabled(False)
        
        actions_layout.addWidget(self.rescan_btn)
        actions_layout.addWidget(self.debug_btn)
        layout.addLayout(actions_layout)
        
        return group

    def _create_detection_types_group(self):
        """Groupe types de détection"""
        group = QGroupBox("🔍 Types de Détection")
        layout = QVBoxLayout(group)
        
        # Checkboxes pour chaque type
        self.aruco_check = QCheckBox("Marqueurs ArUco")
        self.aruco_check.setChecked(True)
        self.aruco_check.toggled.connect(self._on_detection_type_changed)
        
        self.reflective_check = QCheckBox("Marqueurs Réfléchissants")
        self.reflective_check.setChecked(False)
        self.reflective_check.toggled.connect(self._on_detection_type_changed)
        
        self.led_check = QCheckBox("Marqueurs LED")
        self.led_check.setChecked(False)
        self.led_check.toggled.connect(self._on_detection_type_changed)
        
        layout.addWidget(self.aruco_check)
        layout.addWidget(self.reflective_check)
        layout.addWidget(self.led_check)
        
        return group

    def _create_stats_group(self):
        """Groupe statistiques"""
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
        display_widget = QLabel("Flux vidéo avec détections")
        display_widget.setStyleSheet("QLabel { border: 1px solid gray; background: black; color: white; }")
        display_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        display_widget.setMinimumSize(640, 480)
        
        return display_widget

    # === MÉTHODES UTILITAIRES ===
    
    def _safe_get_config(self, section: str, key: str, default=None):
        """Accès sécurisé à la configuration"""
        try:
            return self.config.get(section, key, default) if hasattr(self.config, 'get') else default
        except Exception:
            return default

    def _setup_timers(self):
        """Configure les timers pour les mises à jour"""
        # Timer de détection
        self.detection_timer = QTimer()
        self.detection_timer.timeout.connect(self._detect_targets_in_frame)
        self.detection_timer.start(50)  # 20 FPS
        
        # Timer de mise à jour UI
        self.ui_update_timer = QTimer()
        self.ui_update_timer.timeout.connect(self._update_ui_stats)
        self.ui_update_timer.start(1000)  # 1 Hz

    def _update_ui_stats(self):
        """Met à jour les statistiques dans l'interface"""
        try:
            self.detections_count_label.setText(f"Détections: {self.detection_stats['total_detections']}")
            self.fps_label.setText(f"FPS: {self.detection_stats['fps']:.1f}")
            
            # Mise à jour statut ROI
            if self.roi_detection_enabled:
                self.roi_status_label.setText("Détection: Filtrée par ROI")
                self.roi_status_label.setStyleSheet("QLabel { color: orange; font-weight: bold; }")
                self.toggle_roi_detection_btn.setText("Désactiver filtrage ROI")
            else:
                self.roi_status_label.setText("Détection: Libre (sans ROI)")
                self.roi_status_label.setStyleSheet("QLabel { color: green; font-weight: bold; }")
                self.toggle_roi_detection_btn.setText("Activer filtrage ROI")
            
            # Activation bouton ROI selon disponibilité
            self.toggle_roi_detection_btn.setEnabled(len(self.roi_manager.rois) > 0)
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour UI stats: {e}")

    # === MÉTHODES ARUCO (simplifiées) ===
    
    def _auto_load_latest_aruco_folder(self):
        """Charge automatiquement le dernier dossier ArUco disponible"""
        try:
            latest_folder = self.aruco_loader.get_latest_aruco_folder()
            if latest_folder:
                logger.info(f"🎯 Auto-chargement dossier ArUco: {latest_folder}")
                self._scan_aruco_folder(latest_folder)
            else:
                logger.info("ℹ️ Aucun dossier ArUco trouvé pour auto-chargement")
        except Exception as e:
            logger.warning(f"⚠️ Erreur auto-chargement ArUco: {e}")

    def _select_aruco_folder(self):
        """Sélection du dossier ArUco"""
        current_folder = self._safe_get_config('aruco', 'markers_folder', '.')
        
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Sélectionner le dossier des marqueurs ArUco",
            current_folder
        )
        
        if folder:
            self._scan_aruco_folder(folder)

    def _scan_aruco_folder(self, folder_path):
        """Scan du dossier ArUco sélectionné"""
        try:
            folder_path = Path(folder_path)
            detected_markers = self.aruco_loader.scan_aruco_folder(folder_path)
            valid_count, issues = self.aruco_loader.validate_markers()
            
            # Mise à jour affichage
            self.aruco_folder_label.setText(f"📁 {folder_path.name}")
            self.aruco_folder_label.setStyleSheet("QLabel { color: green; }")
            
            if detected_markers:
                dict_type = self.aruco_loader._detect_common_dictionary()
                self.aruco_stats_label.setText(f"Marqueurs: {len(detected_markers)} détectés ({dict_type})")
                
                # CORRECTION: Mise à jour du détecteur avec le bon dictionnaire
                if hasattr(self.target_detector, 'aruco_config'):
                    self.target_detector.aruco_config['dictionary_type'] = dict_type
                    logger.info(f"🎯 Dictionnaire mis à jour: {dict_type}")
                    # Réinitialiser le détecteur ArUco avec le bon dictionnaire
                    self.target_detector._init_aruco_detector()
            else:
                self.aruco_stats_label.setText("Marqueurs: 0 détecté")
                self.aruco_stats_label.setStyleSheet("QLabel { color: orange; }")
            
            if issues:
                logger.warning(f"⚠️ Problèmes détectés: {'; '.join(issues[:3])}")
            
            # Activation boutons
            self.rescan_btn.setEnabled(True)
            self.debug_btn.setEnabled(True)
            
            logger.info(f"✅ ArUco: {len(detected_markers)} marqueurs détectés ({valid_count} valides)")
            
        except Exception as e:
            logger.error(f"❌ Erreur scan ArUco: {e}")
            self.aruco_folder_label.setText("❌ Erreur de scan")
            self.aruco_folder_label.setStyleSheet("QLabel { color: red; }")

    def _rescan_aruco_folder(self):
        """Re-scan du dossier ArUco"""
        try:
            if hasattr(self.aruco_loader, 'folder_path') and self.aruco_loader.folder_path:
                folder_path = str(self.aruco_loader.folder_path)
                logger.info(f"🔄 Re-scan ArUco: {folder_path}")
                self._scan_aruco_folder(folder_path)
            else:
                logger.warning("⚠️ Aucun dossier ArUco à rescanner")
                QMessageBox.information(self, "Re-scan", "Aucun dossier ArUco sélectionné à rescanner")
        except Exception as e:
            logger.error(f"❌ Erreur re-scan ArUco: {e}")
            QMessageBox.warning(self, "Erreur", f"Erreur lors du re-scan:\n{e}")

    def _show_aruco_debug_info(self):
        """Affiche les informations de débogage ArUco"""
        if not hasattr(self.aruco_loader, 'detected_markers') or not self.aruco_loader.detected_markers:
            QMessageBox.information(self, "Debug ArUco", "Aucun marqueur détecté à analyser")
            return
        
        debug_info = []
        debug_info.append("=== INFORMATIONS DEBUG ARUCO ===\n")
        
        # Informations générales
        debug_info.append(f"Dossier: {self.aruco_loader.folder_path}")
        debug_info.append(f"Marqueurs détectés: {len(self.aruco_loader.detected_markers)}")
        debug_info.append(f"Dictionnaire détecté: {self.aruco_loader._detect_common_dictionary()}\n")
        
        # État détection
        debug_info.append(f"ROI activée: {self.roi_detection_enabled}")
        debug_info.append(f"Détections totales: {self.detection_stats['total_detections']}")
        debug_info.append(f"FPS: {self.detection_stats['fps']:.1f}\n")
        
        # Validation
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

    def _refresh_camera_status(self):
        """Actualise le statut de la caméra"""
        if self.camera_manager and hasattr(self.camera_manager, 'is_camera_active'):
            is_active = self.camera_manager.is_camera_active()
            if is_active:
                self.camera_status_label.setText("État: ✅ Caméra active")
                self.camera_status_label.setStyleSheet("QLabel { color: green; }")
            else:
                self.camera_status_label.setText("État: ❌ Caméra inactive")
                self.camera_status_label.setStyleSheet("QLabel { color: red; }")
        else:
            self.camera_status_label.setText("État: ⚠️ Manager non disponible")
            self.camera_status_label.setStyleSheet("QLabel { color: orange; }")

    # === SLOTS POUR INTÉGRATION ===
    
    def on_camera_ready(self):
        """Callback quand la caméra est prête"""
        logger.info("📹 Caméra prête - démarrage détection")
        self.camera_status_label.setText("État: ✅ Caméra active")
        self.camera_status_label.setStyleSheet("QLabel { color: green; }")
        
    def on_frame_received(self, frame):
        """Callback réception nouvelle frame de la caméra"""
        self.current_frame = frame

    def closeEvent(self, event):
        """Nettoyage à la fermeture"""
        try:
            if hasattr(self, 'detection_timer'):
                self.detection_timer.stop()
            if hasattr(self, 'ui_update_timer'):
                self.ui_update_timer.stop()
            logger.info("🛑 TargetTab fermé proprement")
        except Exception as e:
            logger.error(f"❌ Erreur fermeture TargetTab: {e}")
        finally:
            event.accept()