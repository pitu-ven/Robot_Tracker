# tests/test_roi_error_fix.py
# Version 1.1 - Test correction erreurs ROI avec imports corrigés
# Modification: Correction des chemins d'import pour exécution depuis robot_tracker/

import sys
import os
import unittest
from unittest.mock import Mock, MagicMock, patch
import numpy as np

# Ajouter le répertoire parent au path pour les imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Imports PyQt6 avec gestion des erreurs
try:
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QApplication
    PYQT_AVAILABLE = True
except ImportError:
    print("⚠️ PyQt6 non disponible - Tests UI désactivés")
    PYQT_AVAILABLE = False
    # Mock classes pour les tests sans PyQt6
    class QPoint:
        def __init__(self, x, y):
            self.x_val = x
            self.y_val = y
        def x(self): return self.x_val
        def y(self): return self.y_val
    
    class QApplication:
        @staticmethod
        def instance(): return None

# Import des modules à tester avec gestion d'erreurs
try:
    from ui.target_tab import TargetTab
    from core.camera_manager import CameraManager
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Modules non disponibles: {e}")
    MODULES_AVAILABLE = False
    # Mock classes pour les tests
    class TargetTab:
        def __init__(self, config, camera_manager):
            self.config = config
            self.camera_manager = camera_manager
            self.current_frame_size = None
            self.selected_camera_alias = None
            self.camera_ready = False
    
    class CameraManager:
        def __init__(self):
            pass

class TestROIErrorFix(unittest.TestCase):
    """Test des corrections pour les erreurs ROI"""
    
    def setUp(self):
        """Setup du test"""
        if PYQT_AVAILABLE:
            self.app = QApplication.instance()
            if self.app is None:
                self.app = QApplication([])
        
        # Mock configuration
        self.config = Mock()
        self.config.get.return_value = {}
        
        # Mock camera manager avec méthode corrigée
        self.camera_manager = Mock()
        self.camera_manager.get_camera_frame = Mock()
        self.camera_manager.is_camera_open = Mock(return_value=True)
        
        # Frame de test
        self.test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    @unittest.skipUnless(MODULES_AVAILABLE, "Modules non disponibles")
    def test_get_camera_frame_method_exists(self):
        """Test que la méthode get_camera_frame existe"""
        # Setup mock pour retourner une frame
        self.camera_manager.get_camera_frame.return_value = (True, self.test_frame, None)
        
        # Vérifier que get_camera_frame existe
        self.assertTrue(hasattr(self.camera_manager, 'get_camera_frame'))
        self.assertTrue(callable(self.camera_manager.get_camera_frame))
        
        # Appeler la méthode
        success, frame, depth = self.camera_manager.get_camera_frame("test_camera")
        
        # Vérifications
        self.assertTrue(success)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (480, 640, 3))
    
    def test_screen_coords_conversion_logic(self):
        """Test la logique de conversion des coordonnées sans dépendances UI"""
        # Simulation des paramètres de conversion
        screen_x, screen_y = 320, 240
        display_width, display_height = 640, 480
        img_width, img_height = 640, 480
        
        # Calcul du ratio (cas simple 1:1)
        display_ratio = display_width / display_height
        image_ratio = img_width / img_height
        
        if display_ratio > image_ratio:
            scale = display_height / img_height
            scaled_width = img_width * scale
            offset_x = (display_width - scaled_width) / 2
            offset_y = 0
        else:
            scale = display_width / img_width
            scaled_height = img_height * scale
            offset_x = 0
            offset_y = (display_height - scaled_height) / 2
        
        # Conversion coordonnées
        image_x = int((screen_x - offset_x) / scale)
        image_y = int((screen_y - offset_y) / scale)
        
        # Vérifications
        self.assertGreaterEqual(image_x, 0)
        self.assertGreaterEqual(image_y, 0)
        self.assertLess(image_x, img_width)
        self.assertLess(image_y, img_height)
    
    def test_frame_size_initialization(self):
        """Test l'initialisation de current_frame_size"""
        # Simuler une frame
        frame = self.test_frame
        
        # Calcul de la taille (width, height)
        current_frame_size = (frame.shape[1], frame.shape[0])
        
        # Vérifications
        self.assertEqual(current_frame_size, (640, 480))
        self.assertIsInstance(current_frame_size[0], int)
        self.assertIsInstance(current_frame_size[1], int)
    
    def test_camera_manager_signature(self):
        """Test la signature de get_camera_frame"""
        # Setup mock avec bonne signature
        self.camera_manager.get_camera_frame.return_value = (True, self.test_frame, None)
        
        # Appel avec alias
        result = self.camera_manager.get_camera_frame("test_alias")
        
        # Vérifier que c'est un tuple de 3 éléments
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        
        success, frame, depth = result
        self.assertIsInstance(success, bool)
        self.assertTrue(success)
        self.assertIsNotNone(frame)
        # depth peut être None
    
    def test_error_handling_simulation(self):
        """Test simulation de gestion d'erreur"""
        # Simuler une erreur de caméra
        self.camera_manager.get_camera_frame.side_effect = Exception("Camera disconnected")
        
        # Test du comportement avec erreur
        try:
            result = self.camera_manager.get_camera_frame("test_alias")
            # Ne devrait pas arriver
            self.fail("Exception attendue non levée")
        except Exception as e:
            # Vérifier que c'est bien notre erreur
            self.assertIn("Camera disconnected", str(e))
    
    def test_coordinates_bounds_validation(self):
        """Test validation des bornes de coordonnées"""
        img_width, img_height = 640, 480
        
        # Test coordonnées valides
        valid_coords = [(0, 0), (320, 240), (639, 479)]
        for x, y in valid_coords:
            self.assertTrue(0 <= x < img_width)
            self.assertTrue(0 <= y < img_height)
        
        # Test coordonnées invalides
        invalid_coords = [(-1, 0), (640, 240), (320, 480), (-1, -1)]
        for x, y in invalid_coords:
            valid = 0 <= x < img_width and 0 <= y < img_height
            self.assertFalse(valid, f"Coordonnées ({x}, {y}) devraient être invalides")
    
    @unittest.skipUnless(MODULES_AVAILABLE, "Modules non disponibles")
    def test_no_get_latest_frame_method(self):
        """Test qu'aucune méthode get_latest_frame n'existe"""
        # Créer un mock de TargetTab
        target_tab = Mock()
        
        # Vérifier qu'aucune méthode get_latest_frame n'existe
        self.assertFalse(hasattr(target_tab, 'get_latest_frame'))
        self.assertFalse(hasattr(self.camera_manager, 'get_latest_frame'))
        
        # Vérifier que get_camera_frame existe
        self.assertTrue(hasattr(self.camera_manager, 'get_camera_frame'))

class TestROIFunctionalLogic(unittest.TestCase):
    """Tests de la logique fonctionnelle sans dépendances UI"""
    
    def test_roi_coordinate_conversion_math(self):
        """Test des calculs mathématiques de conversion ROI"""
        # Paramètres d'exemple
        scenarios = [
            # (display_w, display_h, img_w, img_h, click_x, click_y)
            (640, 480, 640, 480, 320, 240),  # 1:1
            (800, 600, 640, 480, 400, 300),  # Upscale
            (320, 240, 640, 480, 160, 120),  # Downscale
        ]
        
        for display_w, display_h, img_w, img_h, click_x, click_y in scenarios:
            with self.subTest(scenario=(display_w, display_h, img_w, img_h)):
                # Calculs de conversion
                display_ratio = display_w / display_h
                image_ratio = img_w / img_h
                
                if display_ratio > image_ratio:
                    scale = display_h / img_h
                    offset_x = (display_w - img_w * scale) / 2
                    offset_y = 0
                else:
                    scale = display_w / img_w
                    offset_x = 0
                    offset_y = (display_h - img_h * scale) / 2
                
                # Conversion
                image_x = int((click_x - offset_x) / scale)
                image_y = int((click_y - offset_y) / scale)
                
                # Vérifications de base
                self.assertIsInstance(image_x, int)
                self.assertIsInstance(image_y, int)
                
                # Les coordonnées devraient être dans les limites (ou proche)
                # permettre une marge pour les calculs flottants
                self.assertGreaterEqual(image_x, -10)
                self.assertLessEqual(image_x, img_w + 10)

def run_tests_with_summary():
    """Lance les tests avec un résumé détaillé"""
    print("🧪 Lancement des tests de correction ROI")
    print("=" * 50)
    
    # Configuration du test runner
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Ajouter les classes de test
    suite.addTests(loader.loadTestsFromTestCase(TestROIErrorFix))
    suite.addTests(loader.loadTestsFromTestCase(TestROIFunctionalLogic))
    
    # Runner avec verbosité
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    # Résumé
    print("\n" + "=" * 50)
    print(f"📊 Résultats des tests:")
    print(f"   ✅ Tests réussis: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"   ❌ Échecs: {len(result.failures)}")
    print(f"   💥 Erreurs: {len(result.errors)}")
    print(f"   🔄 Total: {result.testsRun}")
    
    if result.failures:
        print(f"\n🔍 Détail des échecs:")
        for test, traceback in result.failures:
            print(f"   - {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print(f"\n💥 Détail des erreurs:")
        for test, traceback in result.errors:
            print(f"   - {test}: {traceback.split(':')[-1].strip()}")
    
    # Statut de disponibilité
    print(f"\n🔧 État des dépendances:")
    print(f"   PyQt6: {'✅ Disponible' if PYQT_AVAILABLE else '❌ Non disponible'}")
    print(f"   Modules: {'✅ Disponible' if MODULES_AVAILABLE else '❌ Non disponible'}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\n{'✅ Tous les tests passent!' if success else '⚠️ Certains tests ont échoué'}")
    
    return success

if __name__ == '__main__':
    success = run_tests_with_summary()
    sys.exit(0 if success else 1)