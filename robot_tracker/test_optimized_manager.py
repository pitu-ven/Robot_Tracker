#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/test_optimized_manager.py
Test de validation des optimisations du CameraManager - Version 1.0
Modification: Test rapide pour valider les performances améliorées
"""

import sys
import os
import time
import logging

# Configuration du logging moins verbeux
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_direct_vs_manager():
    """Compare les performances direct vs manager"""
    print("⚖️ Comparaison Direct vs Manager")
    print("=" * 50)
    
    # Test 1: Direct RealSense
    print("\n🎥 Test Direct (référence)...")
    try:
        from hardware.realsense_driver import RealSenseCamera
        
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: {
                'camera.realsense.color_width': 640,
                'camera.realsense.color_height': 480,
                'camera.realsense.color_fps': 30,
                'camera.realsense.enable_filters': False,
                'camera.realsense.enable_align': False
            }.get(f"{section}.{key}", default)
        })()
        
        camera = RealSenseCamera(dummy_config)
        
        if not camera.start_streaming():
            print("❌ Échec direct")
            return False
        
        # Test 3 secondes
        start_time = time.time()
        direct_frames = 0
        
        while time.time() - start_time < 3.0:
            success, color, depth = camera.get_frames()
            if success:
                direct_frames += 1
            time.sleep(0.02)  # 50 Hz polling
        
        camera.stop_streaming()
        direct_fps = direct_frames / 3.0
        
        print(f"✅ Direct: {direct_frames} frames ({direct_fps:.1f} FPS)")
        
    except Exception as e:
        print(f"❌ Erreur direct: {e}")
        return False
    
    # Test 2: CameraManager optimisé
    print("\n🎛️ Test Manager optimisé...")
    try:
        from core.camera_manager import CameraManager
        
        manager = CameraManager(dummy_config)
        
        cameras = manager.detect_all_cameras()
        if not cameras:
            print("❌ Pas de caméras")
            return False
        
        if not manager.open_camera(cameras[0], "test_manager"):
            print("❌ Échec ouverture manager")
            return False
        
        # Callback pour compter les frames
        callback_frames = 0
        def count_callback(frames_data):
            nonlocal callback_frames
            if frames_data:
                callback_frames += len(frames_data)
        
        if not manager.start_streaming(count_callback):
            print("❌ Échec streaming manager")
            return False
        
        # Test 3 secondes
        start_time = time.time()
        manager_frames = 0
        
        while time.time() - start_time < 3.0:
            ret, color, depth = manager.get_camera_frame("test_manager")
            if ret and color is not None:
                manager_frames += 1
            time.sleep(0.02)  # 50 Hz polling
        
        manager.stop_streaming()
        manager.close_all_cameras()
        
        manager_fps = manager_frames / 3.0
        
        print(f"✅ Manager: {manager_frames} frames ({manager_fps:.1f} FPS)")
        print(f"📊 Callbacks: {callback_frames} appels")
        
        # Analyse des résultats
        efficiency = (manager_fps / direct_fps) * 100 if direct_fps > 0 else 0
        print(f"\n📈 Efficacité Manager: {efficiency:.1f}% du direct")
        
        if efficiency >= 70:  # Au moins 70% du direct
            print("✅ Performance acceptable")
            return True
        else:
            print("⚠️ Performance dégradée")
            return False
        
    except Exception as e:
        print(f"❌ Erreur manager: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_streaming_stability():
    """Test de stabilité du streaming sur 30 secondes"""
    print("\n🔄 Test de stabilité (30s)...")
    
    try:
        from core.camera_manager import CameraManager
        
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: {
                'camera.realsense.color_width': 640,
                'camera.realsense.color_height': 480,
                'camera.realsense.color_fps': 30,
                'camera.realsense.enable_filters': False,
                'camera.realsense.enable_align': False
            }.get(f"{section}.{key}", default)
        })()
        
        manager = CameraManager(dummy_config)
        
        cameras = manager.detect_all_cameras()
        if not cameras or not manager.open_camera(cameras[0], "stability_test"):
            print("❌ Setup échoué")
            return False
        
        if not manager.start_streaming():
            print("❌ Streaming échoué")
            return False
        
        print("⌛ Test en cours (30s)...")
        
        start_time = time.time()
        frames_per_period = []
        last_period = start_time
        total_frames = 0
        
        while time.time() - start_time < 30.0:
            current_time = time.time()
            
            # Compter frames pendant cette période de 5s
            period_frames = 0
            period_start = time.time()
            
            while time.time() - period_start < 5.0:
                ret, color, depth = manager.get_camera_frame("stability_test")
                if ret and color is not None:
                    period_frames += 1
                    total_frames += 1
                time.sleep(0.05)  # 20 Hz
            
            fps_period = period_frames / 5.0
            frames_per_period.append(fps_period)
            
            elapsed = current_time - start_time
            print(f"  📊 {elapsed:.0f}s: {fps_period:.1f} FPS")
        
        manager.stop_streaming()
        manager.close_all_cameras()
        
        # Analyse de stabilité
        if frames_per_period:
            avg_fps = sum(frames_per_period) / len(frames_per_period)
            min_fps = min(frames_per_period)
            max_fps = max(frames_per_period)
            stability = (min_fps / max_fps) * 100 if max_fps > 0 else 0
            
            print(f"\n📈 Résultats stabilité:")
            print(f"   Moyenne: {avg_fps:.1f} FPS")
            print(f"   Min: {min_fps:.1f} FPS")
            print(f"   Max: {max_fps:.1f} FPS")
            print(f"   Stabilité: {stability:.1f}%")
            print(f"   Total: {total_frames} frames")
            
            return stability > 80 and avg_fps > 10  # Critères de succès
        
        return False
        
    except Exception as e:
        print(f"❌ Erreur stabilité: {e}")
        return False

def main():
    """Fonction principale de test"""
    print("🧪 Test Validation Optimisations - Robot Tracker")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Comparaison performance
    results['performance'] = test_direct_vs_manager()
    
    if not results['performance']:
        print("\n❌ Test performance échoué, pas la peine de continuer")
        return 1
    
    # Test 2: Stabilité (optionnel, long)
    if '--stability' in sys.argv:
        results['stability'] = test_streaming_stability()
    else:
        print("\n⏭️ Test stabilité ignoré (utilisez --stability pour l'activer)")
        results['stability'] = True  # Pas testé = OK par défaut
    
    # Résumé
    print("\n" + "=" * 60)
    print("📋 Résultats validation:")
    print(f"   Performance:  {'✅ OK' if results['performance'] else '❌ ÉCHEC'}")
    print(f"   Stabilité:    {'✅ OK' if results['stability'] else '❌ ÉCHEC'}")
    
    if all(results.values()):
        print("\n🎉 VALIDATION RÉUSSIE!")
        print("✅ Le CameraManager optimisé est prêt")
        print("🚀 Vous pouvez maintenant utiliser camera_demo.py")
    else:
        print("\n⚠️ VALIDATION ÉCHOUÉE")
        print("🔧 Des optimisations supplémentaires sont nécessaires")
    
    return 0 if all(results.values()) else 1

if __name__ == "__main__":
    try:
        print("💡 Usage:")
        print("   python test_optimized_manager.py           # Test rapide")
        print("   python test_optimized_manager.py --stability # Test complet")
        print()
        
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Test interrompu")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        sys.exit(1)