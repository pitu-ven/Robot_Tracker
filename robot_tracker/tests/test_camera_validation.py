#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/tests/test_camera_validation.py
Script de validation des corrections du driver USB3 - Version 1.0
Modification: Test complet des corrections appliquées au driver USB3CameraDriver
"""

import sys
import os
import time
import cv2
import numpy as np
from pathlib import Path

# Ajout du chemin parent pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_opencv_baseline():
    """Test baseline OpenCV pour comparaison"""
    print("🔍 Test Baseline OpenCV")
    print("-" * 30)
    
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Impossible d'ouvrir la caméra")
            return False
        
        # Configuration basique
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
        cap.set(cv2.CAP_PROP_BRIGHTNESS, 0.5)
        cap.set(cv2.CAP_PROP_CONTRAST, 0.5)
        
        time.sleep(1)  # Stabilisation
        
        # Test capture
        intensities = []
        for i in range(5):
            ret, frame = cap.read()
            if ret and frame is not None:
                intensity = np.mean(frame)
                intensities.append(intensity)
                print(f"   Frame {i+1}: intensité {intensity:.1f}")
            time.sleep(0.2)
        
        cap.release()
        
        if intensities:
            avg_intensity = np.mean(intensities)
            print(f"   📊 Moyenne: {avg_intensity:.1f}")
            return avg_intensity > 5.0
        
        return False
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_corrected_driver():
    """Test du driver corrigé"""
    print("\n🔧 Test Driver Corrigé")
    print("-" * 30)
    
    try:
        from hardware.usb3_camera_driver import USB3CameraDriver
        
        # Configuration optimisée
        config = {
            'width': 640,
            'height': 480,
            'fps': 30,
            'auto_exposure': True,
            'exposure': -1,
            'gain': 100,
            'brightness': 255,
            'contrast': 100,
            'intensity_target': 30.0,
            'stabilization_delay': 2.0,
            'max_correction_attempts': 3,
            'force_manual_exposure': True
        }
        
        camera = USB3CameraDriver(0, config)
        
        if not camera.open():
            print("❌ Impossible d'ouvrir la caméra")
            return False
        
        print("✅ Caméra ouverte avec driver corrigé")
        
        # Validation du flux
        validation = camera.validate_current_stream()
        print(f"📊 Validation flux: {validation.get('status', 'unknown')}")
        print(f"   Intensité moyenne: {validation.get('avg_intensity', 0):.1f}")
        print(f"   Range: {validation.get('intensity_range', 0):.1f}")
        
        # Test streaming
        print("🎬 Test streaming...")
        success = camera.start_streaming()
        if success:
            print("✅ Streaming démarré")
            
            # Test captures
            good_frames = 0
            total_frames = 0
            
            for i in range(20):
                frame = camera.get_latest_frame()
                if frame is not None:
                    total_frames += 1
                    intensity = np.mean(frame)
                    if intensity > 10:
                        good_frames += 1
                    
                    if i % 5 == 0:
                        print(f"   Frame {i+1}: intensité {intensity:.1f}")
                
                time.sleep(0.2)
            
            camera.stop_streaming()
            
            if total_frames > 0:
                success_rate = good_frames / total_frames
                print(f"📊 Résultat: {good_frames}/{total_frames} frames correctes ({success_rate:.1%})")
                camera.close()
                return success_rate > 0.5
        
        camera.close()
        return False
        
    except Exception as e:
        print(f"❌ Erreur driver: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_camera_manager_integration():
    """Test d'intégration avec CameraManager"""
    print("\n🎛️ Test Intégration CameraManager")
    print("-" * 30)
    
    try:
        from core.camera_manager import CameraManager
        
        # Configuration avec driver corrigé
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: {
                'camera.usb3_camera.width': 640,
                'camera.usb3_camera.height': 480,
                'camera.usb3_camera.fps': 30,
                'camera.usb3_camera.auto_exposure': True,
                'camera.usb3_camera.exposure': -1,
                'camera.usb3_camera.gain': 100,
                'camera.usb3_camera.brightness': 255,
                'camera.usb3_camera.contrast': 100
            }.get(f"{section}.{key}", default)
        })()
        
        manager = CameraManager(dummy_config)
        
        # Détection
        cameras = manager.detect_all_cameras()
        if not cameras:
            print("❌ Aucune caméra détectée")
            return False
        
        print(f"📷 {len(cameras)} caméra(s) détectée(s)")
        
        # Test avec première caméra USB
        usb_cameras = [cam for cam in cameras if cam.camera_type.value == 'usb3']
        if not usb_cameras:
            print("❌ Aucune caméra USB3 détectée")
            return False
        
        first_usb = usb_cameras[0]
        print(f"🔧 Test avec: {first_usb.name}")
        
        # Ouverture
        if not manager.open_camera(first_usb, "test_validation"):
            print("❌ Échec ouverture via manager")
            return False
        
        print("✅ Caméra ouverte via CameraManager")
        
        # Test streaming
        if not manager.start_streaming():
            print("❌ Échec streaming via manager")
            return False
        
        print("🎬 Streaming démarré via CameraManager")
        
        # Test captures via manager
        good_frames = 0
        total_attempts = 0
        
        for i in range(15):
            ret, color_frame, depth_frame = manager.get_camera_frame("test_validation")
            total_attempts += 1
            
            if ret and color_frame is not None:
                intensity = np.mean(color_frame)
                if intensity > 10:
                    good_frames += 1
                
                if i % 5 == 0:
                    print(f"   Manager frame {i+1}: intensité {intensity:.1f}")
            else:
                print(f"   Manager frame {i+1}: ÉCHEC")
            
            time.sleep(0.3)
        
        # Nettoyage
        manager.stop_streaming()
        manager.close_all_cameras()
        
        if total_attempts > 0:
            success_rate = good_frames / total_attempts
            print(f"📊 Manager: {good_frames}/{total_attempts} frames correctes ({success_rate:.1%})")
            return success_rate > 0.4
        
        return False
        
    except Exception as e:
        print(f"❌ Erreur intégration: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_validation_report(results):
    """Génère un rapport de validation"""
    print("\n" + "=" * 60)
    print("📋 RAPPORT DE VALIDATION")
    print("=" * 60)
    
    tests = [
        ("OpenCV Baseline", results.get('baseline', False)),
        ("Driver Corrigé", results.get('driver', False)),
        ("Intégration Manager", results.get('integration', False))
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for test_name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:8} {test_name}")
    
    print(f"\nScore global: {passed}/{total} ({passed/total:.1%})")
    
    print("\n💡 RECOMMANDATIONS:")
    
    if not results.get('baseline', False):
        print("❌ CRITIQUE: Problème fondamental OpenCV")
        print("   - Vérifier pilotes caméra Windows")
        print("   - Tester avec autre application (VLC, etc.)")
        print("   - Vérifier permissions caméra")
    
    elif not results.get('driver', False):
        print("⚠️ Driver corrigé ne fonctionne pas")
        print("   - Problème hardware possible")
        print("   - Essayer avec éclairage de la scène")
        print("   - Vérifier configuration JSON")
    
    elif not results.get('integration', False):
        print("⚠️ Problème d'intégration CameraManager")
        print("   - Driver fonctionne mais pas l'intégration")
        print("   - Vérifier configuration CameraManager")
    
    else:
        print("🎉 TOUTES LES VALIDATIONS SONT PASSÉES!")
        print("✅ Le système est prêt pour camera_demo.py")
        print("🚀 Les corrections d'image noire fonctionnent")
    
    return passed == total

def main():
    """Point d'entrée principal"""
    print("🔬 Validation des Corrections Caméra USB")
    print("Résolution du problème d'image noire")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Baseline OpenCV
    print("Phase 1/3: Test baseline...")
    results['baseline'] = test_opencv_baseline()
    
    # Test 2: Driver corrigé
    print("Phase 2/3: Test driver corrigé...")
    results['driver'] = test_corrected_driver()
    
    # Test 3: Intégration
    print("Phase 3/3: Test intégration...")
    results['integration'] = test_camera_manager_integration()
    
    # Rapport final
    success = generate_validation_report(results)
    
    if success:
        print("\n🎯 PROCHAINES ÉTAPES:")
        print("1. ✅ Corrections validées")
        print("2. 🚀 Relancer main.py ou camera_demo.py")
        print("3. 📸 Tester capture d'images dans l'interface")
        return 0
    else:
        print("\n🔧 ACTIONS CORRECTIVES NÉCESSAIRES:")
        print("1. 🔍 Lancer test_camera_diagnostics.py pour diagnostic approfondi")
        print("2. 🔧 Appliquer les corrections supplémentaires suggérées")
        print("3. 💡 Vérifier l'éclairage physique de la scène")
        print("4. 🔄 Relancer ce script de validation")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        print(f"\n👋 Validation terminée (code: {exit_code})")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Validation interrompue par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur générale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)