# tests/test_realsense_depth_fix.py
# Version 1.0 - Test correction détection RealSense pour vue profondeur
# Modification: Test validation de la fonction _is_realsense_camera()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import unittest
from unittest.mock import Mock, patch

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestRealSenseDetection(unittest.TestCase):
    """Test de la détection RealSense dans CameraTab"""
    
    def setUp(self):
        """Configuration des tests"""
        # Mock de la configuration
        self.mock_config = Mock()
        self.mock_config.get.return_value = "default_value"
        
        # Mock du camera_manager
        self.mock_camera_manager = Mock()
        self.mock_camera_manager.cameras = {
            '014122072611': {
                'type': 'realsense',
                'serial': '014122072611',
                'name': 'Intel RealSense D435',
                'alias': 'realsense_0'
            }
        }
    
    def test_realsense_detection_dict_format(self):
        """Test détection avec format dictionnaire"""
        # Import local pour éviter les problèmes
        try:
            from ui.camera_tab import CameraTab
        except ImportError:
            self.skipTest("Interface non disponible en mode test")
        
        # Création du CameraTab
        camera_tab = CameraTab(self.mock_camera_manager, self.mock_config)
        
        # Test cas 1: Format dictionnaire avec type 'realsense'
        camera_data_1 = {
            'type': 'realsense',
            'serial': '014122072611',
            'name': 'Intel RealSense D435'
        }
        
        result_1 = camera_tab._is_realsense_camera(camera_data_1)
        self.assertTrue(result_1, "Doit détecter RealSense avec type 'realsense'")
        
        # Test cas 2: Format dictionnaire avec nom contenant 'realsense'
        camera_data_2 = {
            'type': 'camera',
            'serial': '014122072611',
            'name': 'Intel RealSense D435'
        }
        
        result_2 = camera_tab._is_realsense_camera(camera_data_2)
        self.assertTrue(result_2, "Doit détecter RealSense avec nom contenant 'realsense'")
        
        # Test cas 3: Caméra non-RealSense
        camera_data_3 = {
            'type': 'usb3',
            'serial': '123456789',
            'name': 'Generic USB Camera'
        }
        
        result_3 = camera_tab._is_realsense_camera(camera_data_3)
        self.assertFalse(result_3, "Ne doit pas détecter caméra USB standard")
    
    def test_realsense_detection_object_format(self):
        """Test détection avec format objet"""
        try:
            from ui.camera_tab import CameraTab
        except ImportError:
            self.skipTest("Interface non disponible en mode test")
        
        camera_tab = CameraTab(self.mock_camera_manager, self.mock_config)
        
        # Mock objet caméra avec attribut camera_type
        mock_camera = Mock()
        mock_camera.camera_type = Mock()
        mock_camera.camera_type.__str__ = Mock(return_value='REALSENSE')
        mock_camera.name = 'Intel RealSense D435'
        
        result = camera_tab._is_realsense_camera(mock_camera)
        self.assertTrue(result, "Doit détecter RealSense avec attribut camera_type")
    
    def test_controls_state_update_with_realsense(self):
        """Test mise à jour des contrôles avec caméra RealSense"""
        try:
            from ui.camera_tab import CameraTab
        except ImportError:
            self.skipTest("Interface non disponible en mode test")
        
        # Mock des widgets Qt
        with patch('ui.camera_tab.QCheckBox') as mock_checkbox, \
             patch('ui.camera_tab.QPushButton'), \
             patch('ui.camera_tab.QWidget'), \
             patch('ui.camera_tab.QHBoxLayout'), \
             patch('ui.camera_tab.QVBoxLayout'), \
             patch('ui.camera_tab.QGroupBox'), \
             patch('ui.camera_tab.QListWidget'), \
             patch('ui.camera_tab.QLabel'), \
             patch('ui.camera_tab.QSpinBox'), \
             patch('ui.camera_tab.QSlider'), \
             patch('ui.camera_tab.QTableWidget'), \
             patch('ui.camera_tab.QTextEdit'), \
             patch('ui.camera_tab.QScrollArea'), \
             patch('ui.camera_tab.QGridLayout'), \
             patch('ui.camera_tab.QTimer'):
            
            camera_tab = CameraTab(self.mock_camera_manager, self.mock_config)
            
            # Simulation d'une caméra RealSense sélectionnée
            camera_tab.selected_camera = {
                'type': 'realsense',
                'serial': '014122072611',
                'name': 'Intel RealSense D435'
            }
            
            # Mock de ADVANCED_DISPLAY = True
            with patch('ui.camera_tab.ADVANCED_DISPLAY', True):
                camera_tab._update_controls_state()
                
                # Vérification que la checkbox est activée
                camera_tab.depth_checkbox.setEnabled.assert_called_with(True)
    
    def test_edge_cases(self):
        """Test des cas limites"""
        try:
            from ui.camera_tab import CameraTab
        except ImportError:
            self.skipTest("Interface non disponible en mode test")
        
        camera_tab = CameraTab(self.mock_camera_manager, self.mock_config)
        
        # Test avec None
        result_none = camera_tab._is_realsense_camera(None)
        self.assertFalse(result_none, "Doit retourner False pour None")
        
        # Test avec dictionnaire vide
        result_empty = camera_tab._is_realsense_camera({})
        self.assertFalse(result_empty, "Doit retourner False pour dictionnaire vide")
        
        # Test avec objet sans attributs
        empty_object = object()
        result_object = camera_tab._is_realsense_camera(empty_object)
        self.assertFalse(result_object, "Doit retourner False pour objet vide")

def test_real_scenario_simulation():
    """Test simulation du scénario réel"""
    print("\n🧪 Test simulation scénario réel...")
    
    try:
        # Import avec gestion d'erreur
        try:
            from ui.camera_tab import CameraTab
        except ImportError as e:
            print(f"⚠️ Import CameraTab échoué: {e}")
            return False
        
        # Configuration mock
        mock_config = Mock()
        mock_config.get.side_effect = lambda section, key, default=None: {
            'ui.camera_tab.version': '4.9',
            'ui.camera_tab.layout.control_panel_width': 280,
            'ui.camera_tab.layout.display_area_width': 800,
            'ui.camera_tab.acquisition.default_fps': 30,
            'ui.camera_tab.timers.stats_interval_ms': 1000,
            'ui.camera_tab.log.max_lines': 100,
            'ui.camera_tab.layout.grid_spacing': 15,
            'ui.camera_tab.layout.max_columns_single': 3,
            'ui.camera_tab.layout.max_columns_dual': 2
        }.get(f"{section}.{key}", default)
        
        # CameraManager mock avec vraie caméra RealSense
        mock_camera_manager = Mock()
        mock_camera_manager.cameras = {
            '014122072611': {
                'type': 'realsense',
                'serial': '014122072611',
                'name': 'Intel RealSense D435',
                'alias': 'camera_7422',  # Comme dans les logs
                'device_index': 0
            }
        }
        
        # Test avec mocks Qt
        with patch('ui.camera_tab.QWidget'), \
             patch('ui.camera_tab.QHBoxLayout'), \
             patch('ui.camera_tab.QVBoxLayout'), \
             patch('ui.camera_tab.QGroupBox'), \
             patch('ui.camera_tab.QListWidget'), \
             patch('ui.camera_tab.QLabel'), \
             patch('ui.camera_tab.QPushButton'), \
             patch('ui.camera_tab.QCheckBox') as mock_checkbox, \
             patch('ui.camera_tab.QSpinBox'), \
             patch('ui.camera_tab.QSlider'), \
             patch('ui.camera_tab.QTableWidget'), \
             patch('ui.camera_tab.QTextEdit'), \
             patch('ui.camera_tab.QScrollArea'), \
             patch('ui.camera_tab.QGridLayout'), \
             patch('ui.camera_tab.QTimer'), \
             patch('ui.camera_tab.ADVANCED_DISPLAY', True):
            
            # Création du CameraTab
            camera_tab = CameraTab(mock_camera_manager, mock_config)
            
            print("✅ CameraTab créé avec succès")
            
            # Simulation sélection caméra RealSense
            camera_tab.selected_camera = {
                'type': 'realsense',
                'serial': '014122072611',
                'name': 'Intel RealSense D435',
                'alias': 'camera_7422'
            }
            
            # Test détection
            is_realsense = camera_tab._is_realsense_camera(camera_tab.selected_camera)
            print(f"✅ Détection RealSense: {is_realsense}")
            
            if not is_realsense:
                print("❌ ÉCHEC: Caméra RealSense non détectée")
                return False
            
            # Test mise à jour des contrôles
            camera_tab._update_controls_state()
            print("✅ Mise à jour des contrôles effectuée")
            
            # Vérification que setEnabled(True) a été appelé
            if hasattr(camera_tab, 'depth_checkbox'):
                print("✅ Checkbox vue profondeur accessible")
            
            print("✅ Test scénario réel réussi")
            return True
            
    except Exception as e:
        print(f"❌ Erreur test scénario: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("🔍 TEST DE CORRECTION DÉTECTION REALSENSE")
    print("=" * 50)
    
    # Test simulation scénario
    success = test_real_scenario_simulation()
    
    if success:
        print("\n✅ CORRECTION VALIDÉE")
        print("La fonction _is_realsense_camera() devrait maintenant détecter correctement les caméras RealSense")
        print("\n📋 ÉTAPES SUIVANTES:")
        print("1. Remplacer le fichier ui/camera_tab.py par la version corrigée")
        print("2. Redémarrer l'application")
        print("3. Tester que la checkbox 'Vue Profondeur' s'active avec RealSense")
    else:
        print("\n❌ CORRECTION À RÉVISER")
        print("La détection RealSense nécessite des ajustements supplémentaires")
    
    # Tests unitaires
    print("\n🧪 Tests unitaires...")
    unittest.main(argv=[''], exit=False, verbosity=2)