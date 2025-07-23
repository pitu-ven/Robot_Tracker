#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/debug_usb_camera.py
Script de diagnostic pour caméra USB avec image noire - Version 1.0
Modification: Diagnostic complet des problèmes d'image noire USB
"""

import cv2
import numpy as np
import time
import sys
import os

def test_opencv_direct():
    """Test direct OpenCV pour diagnostiquer l'image noire"""
    print("🔍 Test Direct OpenCV")
    print("=" * 40)
    
    try:
        # Test de différents backends
        backends = [
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_MSMF, "Media Foundation"),
            (cv2.CAP_V4L2, "Video4Linux2"),
            (-1, "Auto")
        ]
        
        device_id = 0
        
        for backend_id, backend_name in backends:
            print(f"\n📷 Test {backend_name} (device {device_id})...")
            
            try:
                if backend_id == -1:
                    cap = cv2.VideoCapture(device_id)
                else:
                    cap = cv2.VideoCapture(device_id, backend_id)
                
                if not cap.isOpened():
                    print(f"❌ Impossible d'ouvrir avec {backend_name}")
                    continue
                
                # Lecture des propriétés actuelles
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                brightness = cap.get(cv2.CAP_PROP_BRIGHTNESS)
                contrast = cap.get(cv2.CAP_PROP_CONTRAST)
                exposure = cap.get(cv2.CAP_PROP_EXPOSURE)
                gain = cap.get(cv2.CAP_PROP_GAIN)
                
                print(f"   📐 Résolution: {width}x{height}")
                print(f"   🎬 FPS: {fps}")
                print(f"   💡 Luminosité: {brightness}")
                print(f"   📊 Contraste: {contrast}")
                print(f"   📸 Exposition: {exposure}")
                print(f"   📈 Gain: {gain}")
                
                # Test de capture
                ret, frame = cap.read()
                
                if ret and frame is not None:
                    # Analyse de l'image
                    mean_intensity = np.mean(frame)
                    min_val = np.min(frame)
                    max_val = np.max(frame)
                    
                    print(f"   ✅ Frame capturée: {frame.shape}")
                    print(f"   📊 Intensité moyenne: {mean_intensity:.1f}")
                    print(f"   📏 Min/Max: {min_val}/{max_val}")
                    
                    # Diagnostic basé sur l'intensité
                    if mean_intensity < 5:
                        print(f"   ⚠️ IMAGE TRÈS SOMBRE (moyenne: {mean_intensity:.1f})")
                        print(f"      Causes possibles:")
                        print(f"      - Exposition trop faible")
                        print(f"      - Objectif fermé/couvert")
                        print(f"      - Paramètres automatiques défaillants")
                    elif mean_intensity < 20:
                        print(f"   ⚠️ IMAGE SOMBRE (moyenne: {mean_intensity:.1f})")
                    else:
                        print(f"   ✅ Intensité correcte")
                    
                    # Test d'ajustement automatique des paramètres
                    if mean_intensity < 20:
                        print(f"   🔧 Test ajustement paramètres...")
                        
                        # Forcer l'exposition automatique
                        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
                        time.sleep(1)  # Attendre l'ajustement
                        
                        # Test plusieurs captures
                        for i in range(5):
                            ret, frame = cap.read()
                            if ret:
                                mean_intensity = np.mean(frame)
                                print(f"      Frame {i+1}: {mean_intensity:.1f}")
                                if mean_intensity > 20:
                                    print(f"   ✅ Amélioration détectée!")
                                    break
                            time.sleep(0.2)
                    
                    cap.release()
                    return True, backend_name
                else:
                    print(f"   ❌ Impossible de capturer une frame")
                
                cap.release()
                
            except Exception as e:
                print(f"   ❌ Erreur {backend_name}: {e}")
        
        return False, None
        
    except Exception as e:
        print(f"❌ Erreur test OpenCV: {e}")
        return False, None

def test_parameter_adjustment():
    """Test d'ajustement des paramètres pour corriger l'image noire"""
    print("\n🔧 Test Ajustement Paramètres")
    print("=" * 40)
    
    try:
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("❌ Impossible d'ouvrir la caméra")
            return False
        
        print("📋 Paramètres par défaut:")
        params = {
            'BRIGHTNESS': cv2.CAP_PROP_BRIGHTNESS,
            'CONTRAST': cv2.CAP_PROP_CONTRAST,
            'SATURATION': cv2.CAP_PROP_SATURATION,
            'GAIN': cv2.CAP_PROP_GAIN,
            'EXPOSURE': cv2.CAP_PROP_EXPOSURE,
            'AUTO_EXPOSURE': cv2.CAP_PROP_AUTO_EXPOSURE
        }
        
        original_values = {}
        for name, prop in params.items():
            value = cap.get(prop)
            original_values[name] = value
            print(f"   {name}: {value}")
        
        # Test différents réglages pour corriger l'image noire
        adjustments = [
            ("Auto-exposition ON", {cv2.CAP_PROP_AUTO_EXPOSURE: 1}),
            ("Luminosité +", {cv2.CAP_PROP_BRIGHTNESS: 0.6}),
            ("Contraste +", {cv2.CAP_PROP_CONTRAST: 0.8}),
            ("Gain +", {cv2.CAP_PROP_GAIN: 50}),
            ("Exposition manuelle", {cv2.CAP_PROP_AUTO_EXPOSURE: 0, cv2.CAP_PROP_EXPOSURE: -4})
        ]
        
        best_intensity = 0
        best_settings = None
        
        for adjustment_name, settings in adjustments:
            print(f"\n🔧 Test: {adjustment_name}")
            
            # Application des réglages
            for prop, value in settings.items():
                cap.set(prop, value)
            
            # Attendre stabilisation
            time.sleep(1)
            
            # Test plusieurs captures
            intensities = []
            for i in range(3):
                ret, frame = cap.read()
                if ret:
                    intensity = np.mean(frame)
                    intensities.append(intensity)
                time.sleep(0.1)
            
            if intensities:
                avg_intensity = np.mean(intensities)
                print(f"   📊 Intensité moyenne: {avg_intensity:.1f}")
                
                if avg_intensity > best_intensity:
                    best_intensity = avg_intensity
                    best_settings = (adjustment_name, settings)
                    print(f"   ✅ Nouveau meilleur réglage!")
            else:
                print(f"   ❌ Pas de capture")
        
        cap.release()
        
        print(f"\n📈 Résultats:")
        print(f"   Meilleure intensité: {best_intensity:.1f}")
        if best_settings:
            print(f"   Meilleur réglage: {best_settings[0]}")
            print(f"   Paramètres: {best_settings[1]}")
            
            # Générer le code de correction
            print(f"\n💡 Code de correction pour USB3CameraDriver:")
            print(f"   # Ajout dans _configure_camera():")
            for prop, value in best_settings[1].items():
                prop_name = [k for k, v in params.items() if v == prop]
                if prop_name:
                    print(f"   self.cap.set(cv2.CAP_PROP_{prop_name[0]}, {value})")
        
        return best_intensity > 20
        
    except Exception as e:
        print(f"❌ Erreur ajustement: {e}")
        return False

def test_driver_integration():
    """Test du driver USB3 avec diagnostic"""
    print("\n🎛️ Test Driver USB3")
    print("=" * 40)
    
    try:
        # Import avec chemin relatif
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, current_dir)
        
        from hardware.usb3_camera_driver import USB3CameraDriver
        
        # Configuration avec paramètres optimisés
        config = {
            'width': 640,
            'height': 480,
            'fps': 30,
            'buffer_size': 1,
            'auto_exposure': True,  # Forcer auto-exposition
            'exposure': -4,
            'gain': 20,  # Gain plus élevé
            'brightness': 0.5,
            'contrast': 0.7
        }
        
        print("📷 Test avec configuration optimisée...")
        
        camera = USB3CameraDriver(0, config)
        
        if not camera.open():
            print("❌ Impossible d'ouvrir la caméra")
            return False
        
        print("✅ Caméra ouverte")
        
        # Test capture directe
        for i in range(5):
            frame = camera.get_frame()
            if frame is not None:
                intensity = np.mean(frame)
                print(f"   Frame {i+1}: intensité {intensity:.1f}")
                
                if intensity > 20:
                    print("✅ Image correcte détectée!")
                    camera.close()
                    return True
            else:
                print(f"   Frame {i+1}: None")
            
            time.sleep(0.2)
        
        print("⚠️ Images toujours sombres avec le driver")
        
        camera.close()
        return False
        
    except Exception as e:
        print(f"❌ Erreur driver: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_fix():
    """Génère un patch pour corriger le problème"""
    print("\n🔧 Génération du correctif")
    print("=" * 40)
    
    fix_code = '''
# Correctif pour robot_tracker/hardware/usb3_camera_driver.py
# Ajouter dans la méthode _configure_camera():

def _configure_camera(self):
    """Configure les paramètres de la caméra avec correction image noire"""
    if not self.cap:
        return
    
    # Résolution
    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
    
    # FPS
    self.cap.set(cv2.CAP_PROP_FPS, self.fps)
    
    # Buffer
    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
    
    # CORRECTION IMAGE NOIRE - PARAMÈTRES OPTIMISÉS
    # Auto-exposition activée en priorité
    self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    
    # Paramètres de luminosité améliorés
    self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 0.5)  # 50%
    self.cap.set(cv2.CAP_PROP_CONTRAST, 0.7)    # 70%
    self.cap.set(cv2.CAP_PROP_SATURATION, 0.6)  # 60%
    
    # Gain adapté
    self.cap.set(cv2.CAP_PROP_GAIN, 20)
    
    # Si auto-exposition échoue, exposition manuelle
    if not self.auto_exposure:
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
        self.cap.set(cv2.CAP_PROP_EXPOSURE, -4)  # Exposition plus élevée
    
    # Attendre stabilisation des paramètres automatiques
    import time
    time.sleep(0.5)
'''
    
    print(fix_code)
    
    # Sauvegarder le correctif
    try:
        with open('usb_camera_fix.txt', 'w') as f:
            f.write(fix_code)
        print("💾 Correctif sauvegardé dans 'usb_camera_fix.txt'")
    except:
        pass

def main():
    """Fonction principale de diagnostic"""
    print("🔍 Diagnostic Caméra USB - Image Noire")
    print("=" * 50)
    
    results = {}
    
    # Test 1: OpenCV direct
    results['opencv'], best_backend = test_opencv_direct()
    
    # Test 2: Ajustement paramètres
    results['params'] = test_parameter_adjustment()
    
    # Test 3: Driver intégré
    results['driver'] = test_driver_integration()
    
    # Résumé et recommandations
    print("\n" + "=" * 50)
    print("📋 Résumé du diagnostic:")
    print(f"   OpenCV Direct:     {'✅ OK' if results['opencv'] else '❌ PROBLÈME'}")
    print(f"   Ajust. Paramètres: {'✅ OK' if results['params'] else '❌ PROBLÈME'}")
    print(f"   Driver USB3:       {'✅ OK' if results['driver'] else '❌ PROBLÈME'}")
    
    if best_backend:
        print(f"   Meilleur backend: {best_backend}")
    
    print("\n💡 Recommandations:")
    
    if not results['opencv']:
        print("   1. ❌ Problème fondamental OpenCV")
        print("      - Vérifier les pilotes de la caméra")
        print("      - Tester avec une autre application (VLC, etc.)")
        print("      - Vérifier les permissions caméra Windows")
    
    elif not results['params']:
        print("   2. ⚠️ Problème de paramètres")
        print("      - Auto-exposition défaillante")
        print("      - Réglages manuels nécessaires")
    
    elif not results['driver']:
        print("   3. 🔧 Problème dans le driver USB3")
        print("      - Configuration insuffisante")
        print("      - Paramètres par défaut inadaptés")
        
        # Générer le correctif
        generate_fix()
        print("      - Appliquer le correctif généré")
    
    else:
        print("   ✅ Tout fonctionne correctement!")
    
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