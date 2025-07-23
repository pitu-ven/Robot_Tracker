#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/tests/test_camera_diagnostics.py
Test de diagnostic avancé pour caméra USB avec validation flux vidéo - Version 1.0
Modification: Diagnostic complet du flux vidéo et validation des données caméra
"""

import cv2
import numpy as np
import time
import sys
import os
from pathlib import Path

# Ajout du chemin parent pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

class CameraDiagnostics:
    """Classe de diagnostic avancé pour caméra USB"""
    
    def __init__(self, device_id=0):
        self.device_id = device_id
        self.cap = None
        self.test_results = {}
    
    def run_full_diagnostics(self):
        """Lance tous les tests de diagnostic"""
        print(f"🔍 Diagnostic Caméra USB {self.device_id}")
        print("=" * 50)
        
        tests = [
            ("Détection caméra", self.test_camera_detection),
            ("Propriétés par défaut", self.test_default_properties),
            ("Backends disponibles", self.test_backends),
            ("Capture basique", self.test_basic_capture),
            ("Analyse flux vidéo", self.test_video_stream_analysis),
            ("Ajustement paramètres", self.test_parameter_adjustment),
            ("Test streaming continu", self.test_continuous_streaming),
            ("Validation données", self.test_data_validation)
        ]
        
        for test_name, test_func in tests:
            print(f"\n📋 {test_name}...")
            try:
                result = test_func()
                self.test_results[test_name] = result
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"   {status}")
            except Exception as e:
                print(f"   ❌ ERREUR: {e}")
                self.test_results[test_name] = False
        
        self.print_summary()
        self.generate_recommendations()
    
    def test_camera_detection(self):
        """Test de détection de la caméra"""
        try:
            # Test ouverture simple
            cap = cv2.VideoCapture(self.device_id)
            is_opened = cap.isOpened()
            
            if is_opened:
                print(f"   📷 Caméra {self.device_id} détectée")
                cap.release()
                return True
            else:
                print(f"   ❌ Caméra {self.device_id} non accessible")
                return False
                
        except Exception as e:
            print(f"   ❌ Erreur détection: {e}")
            return False
    
    def test_default_properties(self):
        """Test des propriétés par défaut"""
        try:
            cap = cv2.VideoCapture(self.device_id)
            if not cap.isOpened():
                return False
            
            properties = {
                'FRAME_WIDTH': cv2.CAP_PROP_FRAME_WIDTH,
                'FRAME_HEIGHT': cv2.CAP_PROP_FRAME_HEIGHT,
                'FPS': cv2.CAP_PROP_FPS,
                'BRIGHTNESS': cv2.CAP_PROP_BRIGHTNESS,
                'CONTRAST': cv2.CAP_PROP_CONTRAST,
                'SATURATION': cv2.CAP_PROP_SATURATION,
                'GAIN': cv2.CAP_PROP_GAIN,
                'EXPOSURE': cv2.CAP_PROP_EXPOSURE,
                'AUTO_EXPOSURE': cv2.CAP_PROP_AUTO_EXPOSURE
            }
            
            print("   📊 Propriétés par défaut:")
            for name, prop in properties.items():
                value = cap.get(prop)
                print(f"     {name}: {value}")
            
            cap.release()
            return True
            
        except Exception as e:
            print(f"   ❌ Erreur lecture propriétés: {e}")
            return False
    
    def test_backends(self):
        """Test des différents backends OpenCV"""
        backends = [
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_MSMF, "Media Foundation"),
            (cv2.CAP_V4L2, "Video4Linux2"),
            (-1, "Auto")
        ]
        
        working_backends = []
        
        for backend_id, backend_name in backends:
            try:
                if backend_id == -1:
                    cap = cv2.VideoCapture(self.device_id)
                else:
                    cap = cv2.VideoCapture(self.device_id, backend_id)
                
                if cap.isOpened():
                    # Test rapide de capture
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        working_backends.append(backend_name)
                        intensity = np.mean(frame)
                        print(f"   ✅ {backend_name}: intensité {intensity:.1f}")
                    else:
                        print(f"   ⚠️ {backend_name}: ouvert mais pas de frame")
                else:
                    print(f"   ❌ {backend_name}: échec ouverture")
                
                cap.release()
                
            except Exception as e:
                print(f"   ❌ {backend_name}: {e}")
        
        return len(working_backends) > 0
    
    def test_basic_capture(self):
        """Test de capture basique avec analyse détaillée"""
        try:
            cap = cv2.VideoCapture(self.device_id)
            if not cap.isOpened():
                return False
            
            print("   🎬 Test capture multiple...")
            
            capture_results = []
            for i in range(10):
                ret, frame = cap.read()
                
                if ret and frame is not None:
                    intensity = np.mean(frame)
                    min_val = np.min(frame)
                    max_val = np.max(frame)
                    
                    result = {
                        'frame_num': i + 1,
                        'intensity': intensity,
                        'min': min_val,
                        'max': max_val,
                        'shape': frame.shape,
                        'dtype': frame.dtype
                    }
                    capture_results.append(result)
                    
                    if i < 3:  # Afficher les 3 premières
                        print(f"     Frame {i+1}: {frame.shape}, intensité={intensity:.1f}, min/max={min_val}/{max_val}")
                else:
                    print(f"     Frame {i+1}: ÉCHEC")
                
                time.sleep(0.1)
            
            cap.release()
            
            if capture_results:
                avg_intensity = np.mean([r['intensity'] for r in capture_results])
                print(f"   📊 Intensité moyenne sur {len(capture_results)} frames: {avg_intensity:.1f}")
                return avg_intensity > 0.1  # Au moins quelque chose
            else:
                return False
                
        except Exception as e:
            print(f"   ❌ Erreur capture: {e}")
            return False
    
    def test_video_stream_analysis(self):
        """Analyse approfondie du flux vidéo"""
        try:
            cap = cv2.VideoCapture(self.device_id)
            if not cap.isOpened():
                return False
            
            print("   🔬 Analyse flux vidéo (5 secondes)...")
            
            # Configuration pour analyse
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            start_time = time.time()
            frame_count = 0
            total_intensity = 0
            intensity_history = []
            
            while time.time() - start_time < 5.0:
                ret, frame = cap.read()
                
                if ret and frame is not None:
                    frame_count += 1
                    intensity = np.mean(frame)
                    total_intensity += intensity
                    intensity_history.append(intensity)
                    
                    # Log détaillé toutes les 50 frames
                    if frame_count % 50 == 0:
                        print(f"     Frame {frame_count}: intensité {intensity:.1f}")
                
                time.sleep(0.02)  # ~50 FPS max
            
            cap.release()
            
            if frame_count > 0:
                avg_intensity = total_intensity / frame_count
                fps_measured = frame_count / 5.0
                
                print(f"   📈 Résultats analyse:")
                print(f"     Frames capturées: {frame_count}")
                print(f"     FPS mesuré: {fps_measured:.1f}")
                print(f"     Intensité moyenne: {avg_intensity:.1f}")
                
                if intensity_history:
                    min_intensity = min(intensity_history)
                    max_intensity = max(intensity_history)
                    print(f"     Range intensité: {min_intensity:.1f} - {max_intensity:.1f}")
                    
                    # Détection de variation
                    variation = max_intensity - min_intensity
                    if variation > 5:
                        print(f"     ✅ Variation détectée: {variation:.1f}")
                    else:
                        print(f"     ⚠️ Peu de variation: {variation:.1f}")
                
                return avg_intensity > 0.1 and frame_count > 100
            else:
                return False
                
        except Exception as e:
            print(f"   ❌ Erreur analyse: {e}")
            return False
    
    def test_parameter_adjustment(self):
        """Test d'ajustement automatique des paramètres"""
        try:
            cap = cv2.VideoCapture(self.device_id)
            if not cap.isOpened():
                return False
            
            print("   🔧 Test ajustements automatiques...")
            
            # Configuration aggressive pour image noire
            adjustments = [
                ("Auto-exposition", {cv2.CAP_PROP_AUTO_EXPOSURE: 1}),
                ("Luminosité max", {cv2.CAP_PROP_BRIGHTNESS: 1.0}),
                ("Contraste max", {cv2.CAP_PROP_CONTRAST: 1.0}),
                ("Gain élevé", {cv2.CAP_PROP_GAIN: 100}),
                ("Exposition forcée", {
                    cv2.CAP_PROP_AUTO_EXPOSURE: 0,
                    cv2.CAP_PROP_EXPOSURE: -1
                })
            ]
            
            best_intensity = 0
            best_config = None
            
            for config_name, params in adjustments:
                # Application des paramètres
                for prop, value in params.items():
                    cap.set(prop, value)
                
                # Attente stabilisation
                time.sleep(1.0)
                
                # Test plusieurs captures
                intensities = []
                for _ in range(5):
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        intensity = np.mean(frame)
                        intensities.append(intensity)
                    time.sleep(0.1)
                
                if intensities:
                    avg_intensity = np.mean(intensities)
                    print(f"     {config_name}: {avg_intensity:.1f}")
                    
                    if avg_intensity > best_intensity:
                        best_intensity = avg_intensity
                        best_config = config_name
            
            cap.release()
            
            if best_config:
                print(f"   ✅ Meilleure config: {best_config} (intensité: {best_intensity:.1f})")
                return best_intensity > 10
            else:
                print("   ❌ Aucune amélioration détectée")
                return False
                
        except Exception as e:
            print(f"   ❌ Erreur ajustement: {e}")
            return False
    
    def test_continuous_streaming(self):
        """Test de streaming continu pour détecter des problèmes de buffer"""
        try:
            cap = cv2.VideoCapture(self.device_id)
            if not cap.isOpened():
                return False
            
            print("   🔄 Test streaming continu (10 secondes)...")
            
            # Configuration optimale
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
            cap.set(cv2.CAP_PROP_BRIGHTNESS, 0.7)
            cap.set(cv2.CAP_PROP_CONTRAST, 0.8)
            
            start_time = time.time()
            frame_count = 0
            black_frames = 0
            good_frames = 0
            
            while time.time() - start_time < 10.0:
                ret, frame = cap.read()
                
                if ret and frame is not None:
                    frame_count += 1
                    intensity = np.mean(frame)
                    
                    if intensity < 1.0:
                        black_frames += 1
                    elif intensity > 10.0:
                        good_frames += 1
                    
                    # Log toutes les 2 secondes
                    if frame_count % 100 == 0:
                        elapsed = time.time() - start_time
                        print(f"     {elapsed:.1f}s: {frame_count} frames, intensité actuelle: {intensity:.1f}")
                
                time.sleep(0.02)
            
            cap.release()
            
            print(f"   📊 Résultats streaming:")
            print(f"     Total frames: {frame_count}")
            print(f"     Frames noires: {black_frames}")
            print(f"     Frames correctes: {good_frames}")
            
            if frame_count > 0:
                black_ratio = black_frames / frame_count
                good_ratio = good_frames / frame_count
                print(f"     Ratio frames noires: {black_ratio:.1%}")
                print(f"     Ratio frames correctes: {good_ratio:.1%}")
                
                return good_ratio > 0.1  # Au moins 10% de frames correctes
            
            return False
            
        except Exception as e:
            print(f"   ❌ Erreur streaming: {e}")
            return False
    
    def test_data_validation(self):
        """Validation approfondie des données de la caméra"""
        try:
            cap = cv2.VideoCapture(self.device_id)
            if not cap.isOpened():
                return False
            
            print("   🔬 Validation données approfondies...")
            
            # Configuration pour test
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
            time.sleep(2)  # Attente longue pour auto-exposition
            
            # Test avec différentes résolutions
            resolutions = [(640, 480), (320, 240), (1280, 720)]
            
            for width, height in resolutions:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                time.sleep(0.5)
                
                ret, frame = cap.read()
                if ret and frame is not None:
                    actual_shape = frame.shape
                    intensity = np.mean(frame)
                    
                    print(f"     {width}x{height}: shape={actual_shape}, intensité={intensity:.1f}")
                    
                    # Analyse des canaux couleur
                    if len(frame.shape) == 3:
                        b_mean = np.mean(frame[:, :, 0])
                        g_mean = np.mean(frame[:, :, 1])
                        r_mean = np.mean(frame[:, :, 2])
                        print(f"       BGR: {b_mean:.1f}, {g_mean:.1f}, {r_mean:.1f}")
                    
                    # Test de patterns
                    std_dev = np.std(frame)
                    print(f"       Écart-type: {std_dev:.1f}")
                    
                    if intensity > 0.1:
                        cap.release()
                        return True
            
            cap.release()
            return False
            
        except Exception as e:
            print(f"   ❌ Erreur validation: {e}")
            return False
    
    def print_summary(self):
        """Affiche le résumé des tests"""
        print("\n" + "=" * 50)
        print("📋 RÉSUMÉ DES TESTS")
        print("=" * 50)
        
        passed = 0
        total = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status:8} {test_name}")
            if result:
                passed += 1
        
        print(f"\nScore: {passed}/{total} ({passed/total:.1%})")
    
    def generate_recommendations(self):
        """Génère des recommandations basées sur les résultats"""
        print("\n💡 RECOMMANDATIONS")
        print("=" * 50)
        
        if not self.test_results.get("Détection caméra", False):
            print("❌ CRITIQUE: Caméra non détectée")
            print("   - Vérifier la connexion USB")
            print("   - Tester avec une autre application")
            print("   - Vérifier les pilotes Windows")
            return
        
        if not self.test_results.get("Capture basique", False):
            print("❌ CRITIQUE: Impossible de capturer des frames")
            print("   - Problème de driver ou de permissions")
            print("   - Caméra utilisée par une autre application")
            return
        
        if not self.test_results.get("Analyse flux vidéo", False):
            print("⚠️ PROBLÈME: Flux vidéo défaillant")
            print("   - Images complètement noires")
            print("   - Problème d'exposition ou de paramètres")
            print("   - Possibles solutions:")
            print("     1. Forcer l'auto-exposition")
            print("     2. Augmenter manuellement l'exposition")
            print("     3. Vérifier l'éclairage de la scène")
            print("     4. Tester le driver USB3CameraDriver modifié")
        
        if not self.test_results.get("Ajustement paramètres", False):
            print("⚠️ PROBLÈME: Ajustement automatique échoue")
            print("   - Les paramètres OpenCV ne s'appliquent pas")
            print("   - Utiliser des valeurs plus agressives")
            print("   - Essayer différents backends")
        
        # Génération de code de correction
        self.generate_fix_code()
    
    def generate_fix_code(self):
        """Génère le code de correction pour le driver"""
        print("\n🔧 CODE DE CORRECTION SUGGÉRÉ")
        print("=" * 50)
        
        fix_code = '''
# À ajouter dans robot_tracker/hardware/usb3_camera_driver.py
# Dans la méthode _configure_camera_from_json():

def _configure_camera_from_json(self):
    """Configuration AGRESSIVE pour corriger l'image noire"""
    if not self.cap:
        return
    
    logger.info("🔧 Configuration AGGRESSIVE anti-image-noire...")
    
    # Résolution de base
    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
    self.cap.set(cv2.CAP_PROP_FPS, self.fps)
    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    # CORRECTION AGRESSIVE IMAGE NOIRE
    # 1. Forcer auto-exposition d'abord
    self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    logger.debug("📸 Auto-exposition forcée")
    
    # 2. Paramètres au maximum
    self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 1.0)    # 100%
    self.cap.set(cv2.CAP_PROP_CONTRAST, 1.0)      # 100%
    self.cap.set(cv2.CAP_PROP_SATURATION, 1.0)    # 100%
    self.cap.set(cv2.CAP_PROP_GAIN, 100)          # Gain max
    
    # 3. Attente longue pour stabilisation
    time.sleep(2.0)
    
    # 4. Test et correction si nécessaire
    ret, test_frame = self.cap.read()
    if ret and test_frame is not None:
        test_intensity = np.mean(test_frame)
        logger.debug(f"🧪 Intensité après config: {test_intensity:.1f}")
        
        if test_intensity < 5.0:
            logger.warning("⚠️ Toujours sombre, exposition manuelle")
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, -1)  # Exposition très élevée
            time.sleep(1.0)
    
    self._log_applied_parameters()
        '''
        
        print(fix_code)
        
        # Sauvegarder le code
        try:
            fix_path = Path(__file__).parent / "camera_fix_code.txt"
            with open(fix_path, 'w') as f:
                f.write(fix_code)
            print(f"\n💾 Code sauvegardé dans: {fix_path}")
        except Exception as e:
            print(f"⚠️ Impossible de sauvegarder: {e}")

def main():
    """Point d'entrée principal"""
    print("🎥 Diagnostic Avancé Caméra USB")
    print("Résolution du problème d'image noire")
    print("=" * 60)
    
    device_id = 0
    if len(sys.argv) > 1:
        try:
            device_id = int(sys.argv[1])
        except ValueError:
            print("⚠️ ID de caméra invalide, utilisation de 0")
    
    diagnostics = CameraDiagnostics(device_id)
    diagnostics.run_full_diagnostics()
    
    print("\n🎯 PROCHAINES ÉTAPES:")
    print("1. Appliquer le code de correction généré")
    print("2. Tester avec l'éclairage de la scène")
    print("3. Vérifier les permissions caméra Windows")
    print("4. Relancer camera_demo.py après correction")
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        print(f"\n👋 Diagnostic terminé (code: {exit_code})")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Diagnostic interrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur générale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)