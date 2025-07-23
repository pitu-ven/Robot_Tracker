#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/test_camera_fix.py
Script de test pour vérifier les corrections des drivers caméra - Version 1.0
Modification: Test des corrections apportées aux drivers RealSense et CameraManager
"""

import sys
import os
import time
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_realsense_driver():
    """Test du driver RealSense corrigé"""
    print("🎥 Test RealSense Driver")
    print("=" * 40)
    
    try:
        from hardware.realsense_driver import RealSenseCamera, list_available_realsense
        
        # Configuration dummy
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: {
                'camera.realsense.color_width': 640,
                'camera.realsense.color_height': 480,
                'camera.realsense.color_fps': 30,
                'camera.realsense.depth_width': 640,
                'camera.realsense.depth_height': 480,
                'camera.realsense.depth_fps': 30,
                'camera.realsense.enable_filters': True,
                'camera.realsense.enable_align': True
            }.get(f"{section}.{key}", default)
        })()
        
        # Test détection
        cameras = list_available_realsense()
        if not cameras:
            print("⚠️ Aucune caméra RealSense détectée")
            return False
        
        print(f"📷 {len(cameras)} caméra(s) détectée(s)")
        for cam in cameras:
            print(f"  - {cam['name']} (S/N: {cam['serial']})")
        
        # Test streaming avec la première caméra
        camera = RealSenseCamera(dummy_config)
        camera.device_serial = cameras[0]['serial']
        
        print(f"\n🎬 Test streaming avec {cameras[0]['name']}...")
        
        if not camera.start_streaming():
            print("❌ Échec démarrage streaming")
            return False
        
        print("✅ Streaming démarré")
        
        # Test acquisition frames
        frame_count = 0
        test_duration = 3.0
        start_time = time.time()
        
        while time.time() - start_time < test_duration:
            success, color_frame, depth_frame = camera.get_frames()
            
            if success and color_frame is not None:
                frame_count += 1
                if frame_count % 30 == 0:  # Log toutes les 30 frames
                    print(f"📸 Frame {frame_count}: {color_frame.shape}")
                    if depth_frame is not None:
                        print(f"📏 Depth: {depth_frame.shape}")
            
            time.sleep(0.033)  # ~30 FPS
        
        camera.stop_streaming()
        
        fps_measured = frame_count / test_duration
        print(f"✅ Test réussi: {frame_count} frames en {test_duration}s ({fps_measured:.1f} FPS)")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur test RealSense: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_camera_manager():
    """Test du CameraManager corrigé"""
    print("\n🎛️ Test CameraManager")
    print("=" * 40)
    
    try:
        from core.camera_manager import CameraManager
        
        # Configuration dummy
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: {
                'camera.realsense.color_width': 640,
                'camera.realsense.color_height': 480,
                'camera.realsense.color_fps': 30,
                'camera.realsense.depth_width': 640,
                'camera.realsense.depth_height': 480,
                'camera.realsense.depth_fps': 30,
                'camera.realsense.enable_filters': True,
                'camera.realsense.enable_align': True,
                'camera.usb3_camera.width': 640,
                'camera.usb3_camera.height': 480,
                'camera.usb3_camera.fps': 30
            }.get(f"{section}.{key}", default)
        })()
        
        manager = CameraManager(dummy_config)
        
        # Test détection
        cameras = manager.detect_all_cameras()
        if not cameras:
            print("⚠️ Aucune caméra détectée")
            return False
        
        print(f"📷 {len(cameras)} caméra(s) détectée(s)")
        for cam in cameras:
            print(f"  - {cam.name} ({cam.camera_type.value})")
        
        # Test ouverture première caméra
        first_camera = cameras[0]
        alias = f"test_{first_camera.camera_type.value}"
        
        print(f"\n📷 Ouverture caméra: {first_camera.name}")
        if not manager.open_camera(first_camera, alias):
            print("❌ Échec ouverture caméra")
            return False
        
        print("✅ Caméra ouverte")
        
        # Test streaming
        print("\n🎬 Test streaming...")
        if not manager.start_streaming():
            print("❌ Échec démarrage streaming")
            return False
        
        print("✅ Streaming démarré")
        
        # Test acquisition frames
        frame_count = 0
        test_duration = 3.0
        start_time = time.time()
        
        while time.time() - start_time < test_duration:
            ret, color_frame, depth_frame = manager.get_camera_frame(alias)
            
            if ret and color_frame is not None:
                frame_count += 1
                if frame_count % 30 == 0:  # Log toutes les 30 frames
                    print(f"📸 Frame {frame_count}: {color_frame.shape}")
                    if depth_frame is not None:
                        print(f"📏 Depth: {depth_frame.shape}")
            
            time.sleep(0.033)  # ~30 FPS
        
        # Test statistiques
        stats = manager.get_all_stats()
        if stats:
            print(f"\n📊 Statistiques:")
            for cam_alias, stat in stats.items():
                print(f"  - {cam_alias}: {stat.get('fps', 0):.1f} FPS, {stat.get('frame_count', 0)} frames")
        
        # Nettoyage
        manager.stop_streaming()
        manager.close_all_cameras()
        
        fps_measured = frame_count / test_duration
        print(f"✅ Test réussi: {frame_count} frames en {test_duration}s ({fps_measured:.1f} FPS)")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur test CameraManager: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Fonction principale de test"""
    print("🧪 Test des corrections caméras - Robot Tracker")
    print("=" * 60)
    
    # Vérification de l'environnement
    current_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"📍 Répertoire: {current_dir}")
    
    # Tests séquentiels
    test1_ok = test_realsense_driver()
    test2_ok = test_camera_manager()
    
    # Résumé
    print("\n" + "=" * 60)
    print("📋 Résumé des tests:")
    print(f"   RealSense Driver: {'✅ OK' if test1_ok else '❌ ÉCHEC'}")
    print(f"   CameraManager:    {'✅ OK' if test2_ok else '❌ ÉCHEC'}")
    
    if test1_ok and test2_ok:
        print("\n🎉 Tous les tests sont passés!")
        print("💡 Les corrections fonctionnent correctement")
        print("🚀 Vous pouvez maintenant relancer camera_demo.py")
    else:
        print("\n⚠️ Certains tests ont échoué")
        print("💡 Vérifiez les erreurs ci-dessus")
    
    return 0 if (test1_ok and test2_ok) else 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrompus par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur générale: {e}")
        sys.exit(1)