#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/debug_streaming.py
Test de diagnostic du problème de streaming - Version 1.0
Modification: Diagnostic approfondi du blocage dans la boucle de streaming
"""

import sys
import os
import time
import logging
import threading
from threading import Timer

# Configuration du logging détaillé
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_realsense_direct():
    """Test direct du driver RealSense"""
    print("🎥 Test Direct RealSense")
    print("=" * 40)
    
    try:
        from hardware.realsense_driver import RealSenseCamera
        
        # Configuration simple
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: {
                'camera.realsense.color_width': 640,
                'camera.realsense.color_height': 480,
                'camera.realsense.color_fps': 30,
                'camera.realsense.depth_width': 640,
                'camera.realsense.depth_height': 480,
                'camera.realsense.depth_fps': 30,
                'camera.realsense.enable_filters': False,  # Désactiver les filtres
                'camera.realsense.enable_align': False     # Désactiver l'alignement
            }.get(f"{section}.{key}", default)
        })()
        
        camera = RealSenseCamera(dummy_config)
        
        if not camera.start_streaming():
            print("❌ Échec démarrage direct")
            return False
        
        print("✅ Streaming direct démarré")
        
        # Test pendant 5 secondes
        start_time = time.time()
        frame_count = 0
        
        while time.time() - start_time < 5.0:
            success, color, depth = camera.get_frames()
            if success:
                frame_count += 1
                if frame_count % 50 == 0:
                    print(f"📸 Direct: {frame_count} frames")
            time.sleep(0.01)
        
        camera.stop_streaming()
        print(f"✅ Direct terminé: {frame_count} frames")
        return True
        
    except Exception as e:
        print(f"❌ Erreur direct: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_manager_with_timeout():
    """Test du CameraManager avec timeout de sécurité"""
    print("\n🎛️ Test CameraManager avec timeout")
    print("=" * 40)
    
    # Timeout de sécurité
    timeout_triggered = False
    
    def timeout_handler():
        nonlocal timeout_triggered
        timeout_triggered = True
        print("⏰ TIMEOUT! Le streaming est bloqué depuis 10 secondes")
        print("🔍 Threads actifs:")
        for thread in threading.enumerate():
            print(f"  - {thread.name}: {thread.is_alive()}")
        
        # Force exit
        os._exit(1)
    
    # Démarrer le timeout
    timeout_timer = Timer(10.0, timeout_handler)
    timeout_timer.start()
    
    try:
        from core.camera_manager import CameraManager
        
        # Configuration simple
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: {
                'camera.realsense.color_width': 640,
                'camera.realsense.color_height': 480,
                'camera.realsense.color_fps': 30,
                'camera.realsense.depth_width': 640,
                'camera.realsense.depth_height': 480,
                'camera.realsense.depth_fps': 30,
                'camera.realsense.enable_filters': False,
                'camera.realsense.enable_align': False
            }.get(f"{section}.{key}", default)
        })()
        
        print("🔧 Création CameraManager...")
        manager = CameraManager(dummy_config)
        
        print("🔍 Détection caméras...")
        cameras = manager.detect_all_cameras()
        if not cameras:
            print("❌ Aucune caméra")
            return False
        
        print(f"📷 {len(cameras)} caméra(s) trouvée(s)")
        
        print("📷 Ouverture caméra...")
        first_camera = cameras[0]
        if not manager.open_camera(first_camera, "test_debug"):
            print("❌ Échec ouverture")
            return False
        
        print("✅ Caméra ouverte")
        
        print("🎬 Démarrage streaming...")
        
        # Callback simple pour tracer les frames
        frame_callback_count = 0
        def debug_callback(frames_data):
            nonlocal frame_callback_count
            frame_callback_count += 1
            if frame_callback_count % 30 == 0:
                print(f"📸 Callback: {frame_callback_count} appels, {len(frames_data)} caméras")
        
        if not manager.start_streaming(debug_callback):
            print("❌ Échec démarrage streaming")
            return False
        
        print("✅ Streaming démarré, attente frames...")
        
        # Test pendant 5 secondes avec monitoring
        start_time = time.time()
        frame_count = 0
        last_log_time = start_time
        
        while time.time() - start_time < 5.0:
            current_time = time.time()
            
            # Log de monitoring toutes les secondes
            if current_time - last_log_time >= 1.0:
                print(f"⏱️ {current_time - start_time:.1f}s - {frame_count} frames, {frame_callback_count} callbacks")
                last_log_time = current_time
            
            # Test get_camera_frame (non-bloquant)
            ret, color, depth = manager.get_camera_frame("test_debug")
            if ret and color is not None:
                frame_count += 1
            
            time.sleep(0.050)  # 20 Hz
        
        print("🛑 Arrêt streaming...")
        manager.stop_streaming()
        
        print("🔒 Fermeture caméras...")
        manager.close_all_cameras()
        
        # Annuler le timeout
        timeout_timer.cancel()
        
        print(f"✅ Test terminé: {frame_count} frames, {frame_callback_count} callbacks")
        return True
        
    except Exception as e:
        timeout_timer.cancel()
        print(f"❌ Erreur manager: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_polling_performance():
    """Test des performances de polling RealSense"""
    print("\n⚡ Test Performance Polling")
    print("=" * 40)
    
    try:
        from hardware.realsense_driver import RealSenseCamera
        
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: {
                'camera.realsense.color_width': 640,
                'camera.realsense.color_height': 480,
                'camera.realsense.color_fps': 30,
                'camera.realsense.depth_width': 640,
                'camera.realsense.depth_height': 480,
                'camera.realsense.depth_fps': 30,
                'camera.realsense.enable_filters': False,
                'camera.realsense.enable_align': False
            }.get(f"{section}.{key}", default)
        })()
        
        camera = RealSenseCamera(dummy_config)
        
        if not camera.start_streaming():
            return False
        
        print("🔄 Test polling intensif (100 appels/seconde)...")
        
        start_time = time.time()
        poll_count = 0
        success_count = 0
        
        # Test pendant 3 secondes
        while time.time() - start_time < 3.0:
            success, color, depth = camera.get_frames()
            poll_count += 1
            if success:
                success_count += 1
            time.sleep(0.01)  # 100 Hz
        
        camera.stop_streaming()
        
        success_rate = (success_count / poll_count) * 100
        print(f"📊 Polling: {poll_count} appels, {success_count} succès ({success_rate:.1f}%)")
        
        return success_rate > 50  # Au moins 50% de succès
        
    except Exception as e:
        print(f"❌ Erreur polling: {e}")
        return False

def main():
    """Fonction principale de diagnostic"""
    print("🔬 Diagnostic Streaming - Robot Tracker")
    print("=" * 60)
    
    print(f"🔍 Thread principal: {threading.current_thread().name}")
    print(f"📍 PID: {os.getpid()}")
    
    # Tests progressifs
    results = {}
    
    # 1. Test direct RealSense
    results['direct'] = test_realsense_direct()
    
    if not results['direct']:
        print("\n❌ Le test direct a échoué, problème avec le driver RealSense")
        return 1
    
    # 2. Test performances polling
    results['polling'] = test_polling_performance()
    
    # 3. Test CameraManager avec timeout
    results['manager'] = test_manager_with_timeout()
    
    # Résumé
    print("\n" + "=" * 60)
    print("📋 Résultats du diagnostic:")
    print(f"   RealSense Direct:  {'✅ OK' if results['direct'] else '❌ ÉCHEC'}")
    print(f"   Polling Performance: {'✅ OK' if results['polling'] else '❌ ÉCHEC'}")
    print(f"   CameraManager:     {'✅ OK' if results['manager'] else '❌ ÉCHEC'}")
    
    if results['direct'] and not results['manager']:
        print("\n🔍 DIAGNOSTIC:")
        print("   - Le driver RealSense fonctionne correctement")
        print("   - Le problème vient du CameraManager")
        print("   - Probablement un problème de threading ou de polling")
        print("\n💡 Solutions à essayer:")
        print("   1. Réduire la fréquence de polling")
        print("   2. Simplifier la boucle de streaming")
        print("   3. Éliminer les verrous (locks) excessifs")
    
    return 0 if all(results.values()) else 1

if __name__ == "__main__":
    try:
        exit_code = main()
        print(f"\n👋 Diagnostic terminé (code: {exit_code})")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Diagnostic interrompu")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur diagnostic: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)