# robot_tracker/tests/test_dictionary_change.py
# Test spécifique du changement de dictionnaire

import cv2
import numpy as np
import sys
from pathlib import Path

# Ajout du chemin parent pour imports
sys.path.append(str(Path(__file__).parent.parent))

from core.config_manager import ConfigManager
from core.target_detector import TargetDetector
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_aruco_image(dict_type, marker_id=0):
    """Crée une image avec un marqueur ArUco spécifique"""
    try:
        # Mapping dictionnaire
        dict_map = {
            'DICT_4X4_50': cv2.aruco.DICT_4X4_50,
            '4X4_50': cv2.aruco.DICT_4X4_50,
            'DICT_5X5_100': cv2.aruco.DICT_5X5_100,
            '5X5_100': cv2.aruco.DICT_5X5_100,
        }
        
        dict_id = dict_map.get(dict_type, cv2.aruco.DICT_4X4_50)
        
        # Création image blanche
        img = np.ones((300, 300, 3), dtype=np.uint8) * 255
        
        # Génération marqueur
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        marker = cv2.aruco.generateImageMarker(aruco_dict, marker_id, 100)
        
        # Placement au centre
        y_offset = (300 - 100) // 2
        x_offset = (300 - 100) // 2
        
        if len(marker.shape) == 2:
            marker = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
        
        img[y_offset:y_offset+100, x_offset:x_offset+100] = marker
        
        return img
        
    except Exception as e:
        print(f"❌ Erreur création image {dict_type}: {e}")
        return None

def test_dictionary_update():
    """Test du changement de dictionnaire"""
    
    print("=== TEST CHANGEMENT DICTIONNAIRE ===\n")
    
    try:
        # Initialisation
        config_manager = ConfigManager()
        detector = TargetDetector(config_manager)
        
        print(f"🎯 Détecteur initialisé")
        print(f"📖 Dictionnaire initial: {detector.aruco_config.get('dictionary_type', 'Non défini')}\n")
        
        # Test 1: Image 4X4_50
        print("--- TEST 1: Image 4X4_50 ---")
        img_4x4 = create_aruco_image('4X4_50', 0)
        if img_4x4 is not None:
            cv2.imwrite('test_4x4_marker.png', img_4x4)
            
            # Détection AVANT mise à jour dictionnaire
            results_before = detector.detect_all_targets(img_4x4)
            print(f"Détections AVANT maj dictionnaire: {len(results_before)}")
            
            # Mise à jour vers 4X4_50
            if hasattr(detector, 'update_aruco_config'):
                detector.update_aruco_config('4X4_50')
            else:
                detector.aruco_config['dictionary_type'] = '4X4_50'
                detector._init_aruco_detector()
            
            print(f"📖 Dictionnaire après maj: {detector.aruco_config.get('dictionary_type', 'Non défini')}")
            
            # Détection APRÈS mise à jour dictionnaire
            results_after = detector.detect_all_targets(img_4x4)
            print(f"Détections APRÈS maj dictionnaire: {len(results_after)}")
            
            if len(results_after) > 0:
                print("✅ SUCCESS: Détection fonctionne après mise à jour dictionnaire")
                for result in results_after:
                    print(f"  - Marqueur ID: {result.id}, Centre: {result.center}")
                return True
            else:
                print("❌ FAIL: Toujours pas de détection après mise à jour")
        
        # Test 2: Image 5X5_100
        print("\n--- TEST 2: Image 5X5_100 ---")
        img_5x5 = create_aruco_image('5X5_100', 0)
        if img_5x5 is not None:
            cv2.imwrite('test_5x5_marker.png', img_5x5)
            
            # Mise à jour vers 5X5_100
            if hasattr(detector, 'update_aruco_config'):
                detector.update_aruco_config('5X5_100')
            else:
                detector.aruco_config['dictionary_type'] = '5X5_100'
                detector._init_aruco_detector()
            
            print(f"📖 Dictionnaire après maj: {detector.aruco_config.get('dictionary_type', 'Non défini')}")
            
            results = detector.detect_all_targets(img_5x5)
            print(f"Détections 5X5_100: {len(results)}")
            
            if len(results) > 0:
                print("✅ Détection 5X5_100 fonctionne aussi")
                for result in results:
                    print(f"  - Marqueur ID: {result.id}, Centre: {result.center}")
        
        return False
        
    except Exception as e:
        print(f"❌ Erreur test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_dictionary_update()
    
    print(f"\n=== RÉSULTAT FINAL ===")
    if success:
        print("✅ Le changement de dictionnaire fonctionne !")
    else:
        print("❌ Problème avec le changement de dictionnaire")
    print("="*30)