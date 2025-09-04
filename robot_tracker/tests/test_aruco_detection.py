# robot_tracker/tests/test_aruco_detection.py
# Test simple pour vérifier que la détection ArUco fonctionne

import cv2
import numpy as np
import sys
import os
from pathlib import Path

# Ajout du chemin parent pour imports
sys.path.append(str(Path(__file__).parent.parent))

from core.config_manager import ConfigManager
from core.target_detector import TargetDetector
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_aruco_detection():
    """Test de base de la détection ArUco"""
    
    try:
        # Initialisation
        config_manager = ConfigManager()
        detector = TargetDetector(config_manager)
        
        print("🎯 Détecteur initialisé")
        
        # Vérification que ArUco est activé
        from core.target_detector import TargetType
        is_enabled = detector.detection_enabled.get(TargetType.ARUCO, False)
        print(f"ArUco activé: {is_enabled}")
        
        # Affichage du dictionnaire actuel
        if hasattr(detector, 'aruco_config'):
            current_dict = detector.aruco_config.get('dictionary_type', 'Non défini')
            print(f"Dictionnaire actuel: {current_dict}")
        
        # Test avec une image test (créons un marqueur simple)
        test_frame = create_test_aruco_image()
        print("🖼️ Image test créée")
        
        # Test détection SANS ROI (cas normal)
        detector.set_roi(roi=None, enabled=False)
        results = detector.detect_all_targets(test_frame)
        
        print(f"✅ Détections trouvées: {len(results)}")
        
        for i, result in enumerate(results):
            print(f"  Marqueur {i}: ID={result.id}, Centre={result.center}, Confiance={result.confidence}")
        
        # Test de détection DIRECTE avec différents dictionnaires
        print("\n🔍 Test détection directe OpenCV...")
        test_direct_opencv_detection(test_frame)
        
        # Test avec vraie caméra si disponible
        print("\n🎥 Test avec caméra...")
        try:
            cap = cv2.VideoCapture(1)  # Index 1 au lieu de 0
            
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    results_camera = detector.detect_all_targets(frame)
                    print(f"📷 Détections sur caméra: {len(results_camera)}")
                    
                    # Sauvegarde frame caméra pour debug
                    cv2.imwrite("debug_camera_frame.png", frame)
                    print("💾 Frame caméra sauvegardée: debug_camera_frame.png")
                else:
                    print("⚠️ Impossible de lire frame caméra")
                cap.release()
            else:
                print("⚠️ Pas de caméra disponible sur index 1")
        except Exception as e:
            print(f"⚠️ Erreur test caméra: {e}")
        
        return len(results) > 0
        
    except Exception as e:
        print(f"❌ Erreur test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_direct_opencv_detection(image):
    """Test détection OpenCV directe pour comparaison"""
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Test avec différents dictionnaires
        dictionaries = [
            (cv2.aruco.DICT_4X4_50, "4X4_50"),
            (cv2.aruco.DICT_5X5_100, "5X5_100"),
            (cv2.aruco.DICT_6X6_250, "6X6_250")
        ]
        
        for dict_id, dict_name in dictionaries:
            try:
                aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
                detector_params = cv2.aruco.DetectorParameters()
                aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, detector_params)
                
                corners, ids, rejected = aruco_detector.detectMarkers(gray)
                
                detections = len(ids) if ids is not None else 0
                print(f"  {dict_name}: {detections} détections")
                
                if detections > 0:
                    print(f"    IDs détectés: {ids.flatten().tolist()}")
                    
            except Exception as e:
                print(f"  ❌ Erreur test {dict_name}: {e}")
                
    except Exception as e:
        print(f"❌ Erreur test OpenCV direct: {e}")

def create_test_aruco_image():
    """Crée une image test avec un marqueur ArUco"""
    try:
        # Création image blanche
        img = np.ones((400, 400, 3), dtype=np.uint8) * 255
        
        # Génération marqueur ArUco 4x4_50 ID=0
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        marker = cv2.aruco.generateImageMarker(aruco_dict, 0, 100)
        
        # Placement du marqueur au centre
        y_offset = (400 - 100) // 2
        x_offset = (400 - 100) // 2
        
        # Conversion marqueur en 3 canaux si nécessaire
        if len(marker.shape) == 2:
            marker = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
        
        img[y_offset:y_offset+100, x_offset:x_offset+100] = marker
        
        return img
        
    except Exception as e:
        print(f"❌ Erreur création image test: {e}")
        # Image vide en cas d'erreur
        return np.ones((400, 400, 3), dtype=np.uint8) * 255

if __name__ == "__main__":
    print("=== TEST DÉTECTION ARUCO ===")
    success = test_aruco_detection()
    
    if success:
        print("\n✅ TEST RÉUSSI - La détection ArUco fonctionne !")
    else:
        print("\n❌ TEST ÉCHEC - Problème avec la détection ArUco")
    
    print("=== FIN TEST ===")