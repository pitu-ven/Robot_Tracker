# tests/test_target_tab.py
# Version 1.0 - Création tests unitaires onglet Cible
# Modification: Implémentation tests intégration et fonctionnalités principales

import pytest
import numpy as np
import cv2
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

import sys
import os
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_manager import ConfigManager
from core.aruco_config_loader import ArUcoConfigLoader
from core.target_detector import TargetDetector, TargetType
from core.roi_manager import ROIManager, ROIType
from ui.target_tab import TargetTab

class TestArUcoConfigLoader:
    """Tests du chargeur de configuration ArUco"""
    
    @pytest.fixture
    def config_manager(self):
        """Config manager pour tests"""
        return Mock(spec=ConfigManager)
    
    @pytest.fixture
    def loader(self, config_manager):
        """Instance du loader"""
        config_manager.get.return_value = {
            'supported_extensions': ['.png', '.jpg'],
            'detection_params': {'minMarkerPerimeterRate': 0.03}
        }
        return ArUcoConfigLoader(config_manager)
    
    @pytest.fixture
    def temp_aruco_folder(self):
        """Dossier temporaire avec marqueurs de test"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Création fichiers test
            test_files = [
                'aruco_5_100x100_dict_4X4_50.png',
                'aruco_10_200x200_dict_6X6_250.png', 
                'marker_15_150_4X4_50.jpg',
                'invalid_filename.png'
            ]
            
            for filename in test_files:
                (temp_path / filename).touch()
                
            yield temp_path
    
    def test_scan_valid_folder(self, loader, temp_aruco_folder):
        """Test scan dossier valide avec marqueurs"""
        markers = loader.scan_aruco_folder(str(temp_aruco_folder))
        
        assert len(markers) == 3  # 3 fichiers valides sur 4
        assert 5 in markers
        assert 10 in markers
        assert 15 in markers
        
        # Vérification structure des données
        marker_5 = markers[5]
        assert marker_5['id'] == 5
        assert marker_5['size_mm'] == 100
        assert marker_5['dictionary'] == '4X4_50'
        assert marker_5['enabled'] == True
        assert 'detection_params' in marker_5
    
    def test_scan_empty_folder(self, loader):
        """Test scan dossier vide"""
        with tempfile.TemporaryDirectory() as temp_dir:
            markers = loader.scan_aruco_folder(temp_dir)
            assert len(markers) == 0
    
    def test_scan_nonexistent_folder(self, loader):
        """Test scan dossier inexistant"""
        markers = loader.scan_aruco_folder('/nonexistent/folder')
        assert len(markers) == 0
    
    def test_extract_metadata_from_filename(self, loader):
        """Test extraction métadonnées depuis nom fichier"""
        test_cases = [
            ('aruco_5_100x100_dict_4X4_50.png', {'id': 5, 'size': 100, 'dict': '4X4_50'}),
            ('marker_10_200_6X6_250.jpg', {'id': 10, 'size': 200}),
            ('id15_150x150.png', {'id': 15, 'size': 150}),
            ('25_300x300.jpeg', {'id': 25, 'size': 300}),
            ('invalid_name.png', None)
        ]
        
        for filename, expected in test_cases:
            file_path = Path(filename)
            result = loader._extract_marker_info(file_path)
            
            if expected is None:
                assert result is None
            else:
                assert result is not None
                assert result['id'] == expected['id']
                if 'size' in expected:
                    assert result['size_mm'] == expected['size']
    
    def test_generate_config_file(self, loader, temp_aruco_folder):
        """Test génération fichier de configuration"""
        # Scan d'abord
        markers = loader.scan_aruco_folder(str(temp_aruco_folder))
        assert len(markers) > 0
        
        # Génération config
        config_path = loader.generate_config_file()
        assert Path(config_path).exists()
        
        # Vérification contenu
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        assert '_metadata' in config_data
        assert 'markers' in config_data 
        assert 'detection_settings' in config_data
        assert len(config_data['markers']) == len(markers)
    
    def test_validate_markers(self, loader, temp_aruco_folder):
        """Test validation des marqueurs"""
        loader.scan_aruco_folder(str(temp_aruco_folder))
        
        valid_count, issues = loader.validate_markers()
        
        assert valid_count == 3  # 3 marqueurs valides
        assert len(issues) == 0   # Aucun problème

class TestTargetDetector:
    """Tests des algorithmes de détection"""
    
    @pytest.fixture
    def config_manager(self):
        """Config manager mockée"""
        config = Mock(spec=ConfigManager)
        config.get.return_value = {
            'aruco': {
                'enabled': True,
                'dictionary_type': '4X4_50',
                'detection_params': {}
            },
            'reflective_markers': {
                'enabled': True,
                'hsv_ranges': {'lower': [0, 0, 200], 'upper': [180, 30, 255]},
                'morphology': {'kernel_size': 5, 'iterations': 2},
                'contour_filters': {'min_area': 50, 'max_area': 5000, 'min_circularity': 0.7}
            },
            'led_markers': {
                'enabled': True,
                'color_presets': {
                    'red': {'h': [0, 10], 's': [50, 255], 'v': [50, 255]}
                },
                'detection_params': {
                    'gaussian_blur_size': 5,
                    'morphology_kernel': 3,
                    'min_contour_area': 30
                }
            },
            'display': {'colors': {}, 'fonts': {}, 'overlays': {}}
        }
        return config
    
    @pytest.fixture
    def detector(self, config_manager):
        """Instance du détecteur"""
        return TargetDetector(config_manager)
    
    @pytest.fixture
    def test_frame(self):
        """Frame de test"""
        # Création image 640x480 avec fond gris
        frame = np.full((480, 640, 3), 128, dtype=np.uint8)
        
        # Ajout marqueur blanc (simulé réfléchissant)
        cv2.circle(frame, (100, 100), 20, (255, 255, 255), -1)
        
        # Ajout zone rouge (simulé LED)
        cv2.circle(frame, (200, 200), 15, (0, 0, 255), -1)
        
        return frame
    
    def test_detect_all_targets(self, detector, test_frame):
        """Test détection tous types de cibles"""
        detections = detector.detect_all_targets(test_frame)
        
        # Au moins une détection attendue (marqueur réfléchissant)
        assert len(detections) >= 1
        
        # Vérification structure
        for detection in detections:
            assert hasattr(detection, 'target_type')
            assert hasattr(detection, 'center')
            assert hasattr(detection, 'confidence')
            assert hasattr(detection, 'timestamp')
    
    def test_reflective_marker_detection(self, detector, test_frame):
        """Test détection marqueurs réfléchissants"""
        # Configuration pour détecter seulement les réfléchissants
        detector.set_detection_enabled(TargetType.ARUCO, False)
        detector.set_detection_enabled(TargetType.LED, False)
        
        detections = detector._detect_reflective_markers(test_frame)
        
        # Doit détecter le cercle blanc 
        assert len(detections) >= 1
        
        detection = detections[0]
        assert detection.target_type == TargetType.REFLECTIVE
        assert detection.center[0] == pytest.approx(100, abs=10)
        assert detection.center[1] == pytest.approx(100, abs=10)
    
    def test_led_tracking_stability(self, detector):
        """Test stabilité tracking LEDs"""
        # Séquence de frames avec LED qui bouge
        centers = [(200, 200), (202, 201), (204, 202), (203, 200)]
        
        detections_sequence = []
        for center in centers:
            frame = np.full((480, 640, 3), 128, dtype=np.uint8)
            cv2.circle(frame, center, 15, (0, 0, 255), -1)
            
            detections = detector._detect_led_markers(frame)
            detections_sequence.append(detections)
        
        # Vérification détection continue  
        for detections in detections_sequence:
            assert len(detections) >= 1
            assert detections[0].target_type == TargetType.LED
    
    def test_detection_stats_update(self, detector, test_frame):
        """Test mise à jour statistiques"""
        initial_stats = detector.get_detection_stats()
        assert initial_stats['total_detections'] == 0
        
        # Détection
        detector.detect_all_targets(test_frame)
        
        updated_stats = detector.get_detection_stats()
        assert updated_stats['total_detections'] > initial_stats['total_detections']
        assert updated_stats['last_detection_time'] > 0

class TestROIManager:
    """Tests gestion des ROI"""
    
    @pytest.fixture
    def config_manager(self):
        """Config manager mockée"""
        config = Mock(spec=ConfigManager)
        config.get.return_value = {
            'line_thickness': 2,
            'selection_handles_size': 8,
            'snap_distance': 10,
            'max_roi_count': 10
        }
        return config
    
    @pytest.fixture
    def roi_manager(self, config_manager):
        """Instance du gestionnaire ROI"""
        return ROIManager(config_manager)
    
    def test_rectangle_roi_creation(self, roi_manager):
        """Test création ROI rectangulaire"""
        # Démarrage création
        success = roi_manager.start_roi_creation(ROIType.RECTANGLE)
        assert success == True
        assert roi_manager.is_creating == True
        assert roi_manager.creation_type == ROIType.RECTANGLE
        
        # Premier point
        roi_manager.add_creation_point((100, 100))
        assert len(roi_manager.temp_points) == 1
        
        # Deuxième point - termine le rectangle
        completed = roi_manager.add_creation_point((200, 150))
        assert completed == True
        assert roi_manager.is_creating == False
        assert len(roi_manager.rois) == 1
        
        # Vérification ROI créée
        roi = roi_manager.rois[0]
        assert roi.roi_type == ROIType.RECTANGLE
        assert len(roi.points) == 4  # Rectangle = 4 points
    
    def test_polygon_roi_creation(self, roi_manager):
        """Test création ROI polygonale"""
        roi_manager.start_roi_creation(ROIType.POLYGON)
        
        # Ajout des points
        points = [(100, 100), (200, 100), (150, 200)]
        for point in points:
            roi_manager.add_creation_point(point)
        
        assert len(roi_manager.temp_points) == 3
        
        # Completion manuelle pour polygone
        completed = roi_manager.complete_polygon_creation()
        assert completed == True
        assert len(roi_manager.rois) == 1
        
        roi = roi_manager.rois[0]
        assert roi.roi_type == ROIType.POLYGON
        assert len(roi.points) == 3
    
    def test_point_in_roi_detection(self, roi_manager):
        """Test détection point dans ROI"""
        # Création ROI rectangulaire
        roi_manager.start_roi_creation(ROIType.RECTANGLE)
        roi_manager.add_creation_point((100, 100))
        roi_manager.add_creation_point((200, 200))
        
        roi = roi_manager.rois[0]
        
        # Tests points
        assert roi_manager.point_in_roi((150, 150), roi) == True   # Intérieur
        assert roi_manager.point_in_roi((50, 50), roi) == False    # Extérieur
        assert roi_manager.point_in_roi((100, 100), roi) == True   # Coin
    
    def test_roi_serialization(self, roi_manager):
        """Test sauvegarde/chargement ROI"""
        # Création ROI
        roi_manager.start_roi_creation(ROIType.RECTANGLE)
        roi_manager.add_creation_point((100, 100))
        roi_manager.add_creation_point((200, 200))
        
        original_count = len(roi_manager.rois)
        
        # Sauvegarde temporaire
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Sauvegarde
            success = roi_manager.save_rois_to_file(temp_path)
            assert success == True
            
            # Réinitialisation
            roi_manager.rois.clear()
            assert len(roi_manager.rois) == 0
            
            # Chargement
            success = roi_manager.load_rois_from_file(temp_path)
            assert success == True
            assert len(roi_manager.rois) == original_count
            
            # Vérification données
            roi = roi_manager.rois[0]
            assert roi.roi_type == ROIType.RECTANGLE
            assert len(roi.points) == 4
            
        finally:
            os.unlink(temp_path)
    
    def test_max_roi_limit(self, roi_manager):
        """Test limite maximum de ROI"""
        # Configuration limite basse pour test
        roi_manager.max_roi_count = 2
        
        # Création première ROI
        assert roi_manager.start_roi_creation(ROIType.RECTANGLE) == True
        roi_manager.add_creation_point((0, 0))
        roi_manager.add_creation_point((50, 50))
        
        # Création deuxième ROI
        assert roi_manager.start_roi_creation(ROIType.RECTANGLE) == True
        roi_manager.add_creation_point((100, 100))
        roi_manager.add_creation_point((150, 150))
        
        # Tentative troisième ROI - doit échouer
        assert roi_manager.start_roi_creation(ROIType.RECTANGLE) == False

class TestTargetTabIntegration:
    """Tests d'intégration de l'onglet cible"""
    
    @pytest.fixture
    def app(self):
        """Application Qt pour tests GUI"""
        return QApplication.instance() or QApplication([])
    
    @pytest.fixture
    def config_manager(self):
        """Config manager complète"""
        config = Mock(spec=ConfigManager)
        config.get.side_effect = lambda *args: self._get_config_value(args)
        return config
    
    def _get_config_value(self, keys):
        """Valeurs de configuration pour tests - Structure tracking_config.json"""
        config_values = {
            ('tracking',): {
                'target_detection': {
                    'aruco': {'enabled': True, 'default_markers_folder': './ArUco'},
                    'reflective_markers': {'enabled': True},
                    'led_markers': {'enabled': True}
                },
                'target_tab_ui': {
                    'window': {'control_panel_width': 320, 'update_interval_ms': 33},
                    'roi': {'max_roi_count': 10},
                    'display': {'colors': {}, 'fonts': {}, 'overlays': {}},
                    'export': {'formats': ['csv', 'json']}
                },
                # Config tracking existante (préservée)
                'kalman_filter': {'enabled': True},
                'prediction': {'enabled': True}
            }
        }
        
        current = config_values
        for key in keys:
            current = current.get(key, {})
        return current
    
    @pytest.fixture
    def camera_manager(self):
        """Camera manager mockée"""
        return Mock()
    
    @pytest.fixture
    def target_tab(self, app, config_manager, camera_manager):
        """Instance de l'onglet cible"""
        return TargetTab(config_manager, camera_manager)
    
    def test_target_tab_initialization(self, target_tab):
        """Test initialisation de l'onglet"""
        assert target_tab is not None
        assert hasattr(target_tab, 'aruco_loader')
        assert hasattr(target_tab, 'target_detector')
        assert hasattr(target_tab, 'roi_manager')
        assert hasattr(target_tab, 'camera_display')
    
    def test_aruco_folder_selection(self, target_tab):
        """Test sélection dossier ArUco avec nouvelle structure"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Création fichiers test
            (Path(temp_dir) / 'aruco_5_100x100_dict_4X4_50.png').touch()
            
            # Simulation sélection dossier
            target_tab._scan_aruco_folder(temp_dir)
            
            # Vérifications avec nouvelle structure de config
            assert len(target_tab.aruco_loader.detected_markers) == 1
            assert target_tab.rescan_btn.isEnabled() == True
            assert target_tab.config_btn.isEnabled() == True
    
    def test_roi_creation_workflow(self, target_tab):
        """Test workflow création ROI"""
        # Démarrage création rectangle
        target_tab._start_roi_creation(ROIType.RECTANGLE)
        assert target_tab.roi_manager.is_creating == True
        
        # Simulation clics
        target_tab._on_display_clicked((100, 100))  # Premier point
        target_tab._on_display_clicked((200, 200))  # Deuxième point
        
        # Vérification ROI créée
        assert len(target_tab.roi_manager.rois) == 1
        assert target_tab.roi_manager.is_creating == False
    
    def test_tracking_start_stop(self, target_tab):
        """Test démarrage/arrêt tracking"""
        # État initial
        assert target_tab.is_tracking == False
        assert target_tab.start_tracking_btn.isEnabled() == True
        assert target_tab.stop_tracking_btn.isEnabled() == False
        
        # Démarrage tracking
        target_tab._start_tracking()
        assert target_tab.is_tracking == True
        assert target_tab.start_tracking_btn.isEnabled() == False
        assert target_tab.stop_tracking_btn.isEnabled() == True
        
        # Arrêt tracking
        target_tab._stop_tracking()
        assert target_tab.is_tracking == False
        assert target_tab.start_tracking_btn.isEnabled() == True
        assert target_tab.stop_tracking_btn.isEnabled() == False
    
    def test_detection_type_toggles(self, target_tab):
        """Test activation/désactivation types de détection"""
        # Test ArUco
        target_tab.aruco_check.setChecked(False)
        assert target_tab.target_detector.detection_enabled[TargetType.ARUCO] == False
        
        target_tab.aruco_check.setChecked(True)
        assert target_tab.target_detector.detection_enabled[TargetType.ARUCO] == True
        
        # Test réfléchissants
        target_tab.reflective_check.setChecked(False)
        assert target_tab.target_detector.detection_enabled[TargetType.REFLECTIVE] == False
    
    def test_stats_update(self, target_tab):
        """Test mise à jour statistiques"""
        # Simulation détections
        target_tab.detected_targets = [Mock(), Mock(), Mock()]
        
        # Mise à jour stats
        target_tab._update_stats()
        
        # Vérification affichage
        assert "3" in target_tab.targets_label.text()
    
    @pytest.mark.parametrize("zoom_value,expected_percent", [
        (50, "50%"),
        (100, "100%"), 
        (200, "200%"),
        (500, "500%")
    ])
    def test_zoom_functionality(self, target_tab, zoom_value, expected_percent):
        """Test fonctionnalité zoom"""
        target_tab.zoom_slider.setValue(zoom_value)
        assert target_tab.zoom_label.text() == expected_percent

if __name__ == '__main__':
    # Exécution des tests avec verbosité réduite
    pytest.main([__file__, '-v', '--tb=short'])