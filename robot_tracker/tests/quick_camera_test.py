#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/tests/quick_camera_test.py
Test rapide avec aperçu visuel de la caméra - Version 1.0
Modification: Test visuel rapide pour vérifier si l'objectif est couvert
"""

import cv2
import numpy as np
import sys
from pathlib import Path

# Ajout du chemin parent pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_visual_camera():
    """Test avec aperçu visuel de la caméra"""
    print("🎥 Test Visuel Caméra USB")
    print("=" * 40)
    print("INSTRUCTIONS:")
    print("- Vérifiez que l'objectif de la caméra N'EST PAS couvert")
    print("- Pointez la caméra vers différents objets/éclairages")
    print("- Appuyez sur 'q' pour quitter")
    print("- Appuyez sur 's' pour sauvegarder une image")
    print()
    
    input("Appuyez sur Entrée pour commencer...")
    
    # Ouverture de la caméra
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ Impossible d'ouvrir la caméra")
        return False
    
    # Configuration optimisée
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # Auto-exposition
    cap.set(cv2.CAP_PROP_BRIGHTNESS, 0.7)
    cap.set(cv2.CAP_PROP_CONTRAST, 0.8)
    
    print("⏳ Stabilisation de l'auto-exposition...")
    import time
    time.sleep(2)
    
    print("🎬 Aperçu vidéo ouvert - Vérifiez l'image!")
    print("   📊 Statistiques en temps réel affichées")
    
    frame_count = 0
    intensities = []
    
    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("❌ Erreur capture frame")
            break
        
        frame_count += 1
        
        # Analyse de l'image
        intensity = np.mean(frame)
        min_val = np.min(frame)
        max_val = np.max(frame)
        std_dev = np.std(frame)
        
        intensities.append(intensity)
        
        # Diagnostic visuel sur l'image
        display_frame = frame.copy()
        
        # Overlay avec statistiques
        stats_text = [
            f"Frame: {frame_count}",
            f"Intensite: {intensity:.1f}",
            f"Min/Max: {min_val}/{max_val}",
            f"Ecart-type: {std_dev:.1f}",
            f"Moy. 10f: {np.mean(intensities[-10:]):.1f}" if len(intensities) >= 10 else ""
        ]
        
        # Diagnostic couleur
        if intensity < 5:
            status_color = (0, 0, 255)  # Rouge - Très sombre
            status_text = "TRES SOMBRE - Objectif couvert?"
        elif intensity < 20:
            status_color = (0, 165, 255)  # Orange - Sombre
            status_text = "SOMBRE - Eclairage faible"
        elif std_dev < 5:
            status_color = (0, 255, 255)  # Jaune - Uniforme
            status_text = "UNIFORME - Pointez vers objet varie"
        else:
            status_color = (0, 255, 0)  # Vert - Normal
            status_text = "NORMAL - Image correcte"
        
        # Affichage des infos
        y_offset = 25
        for i, text in enumerate(stats_text):
            if text:  # Éviter les chaînes vides
                cv2.putText(display_frame, text, (10, y_offset + i * 25), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Status principal
        cv2.putText(display_frame, status_text, (10, display_frame.shape[0] - 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        # Crosshair central
        h, w = display_frame.shape[:2]
        cv2.line(display_frame, (w//2 - 20, h//2), (w//2 + 20, h//2), (0, 255, 0), 2)
        cv2.line(display_frame, (w//2, h//2 - 20), (w//2, h//2 + 20), (0, 255, 0), 2)
        
        # Affichage
        cv2.imshow('Robot Tracker - Test Camera', display_frame)
        
        # Gestion clavier
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("🛑 Arrêt demandé par utilisateur")
            break
        elif key == ord('s'):
            # Sauvegarde
            filename = f"camera_test_frame_{frame_count}.jpg"
            cv2.imwrite(filename, frame)
            print(f"💾 Image sauvegardée: {filename}")
        
        # Log périodique console
        if frame_count % 60 == 0:  # Toutes les 2 secondes environ
            print(f"📊 Frame {frame_count}: intensité {intensity:.1f}, écart-type {std_dev:.1f}")
    
    # Nettoyage
    cap.release()
    cv2.destroyAllWindows()
    
    # Analyse finale
    if intensities:
        avg_intensity = np.mean(intensities)
        min_intensity = min(intensities)
        max_intensity = max(intensities)
        variation = max_intensity - min_intensity
        
        print(f"\n📊 ANALYSE FINALE:")
        print(f"   Frames totales: {frame_count}")
        print(f"   Intensité moyenne: {avg_intensity:.1f}")
        print(f"   Range intensité: {min_intensity:.1f} - {max_intensity:.1f}")
        print(f"   Variation totale: {variation:.1f}")
        
        print(f"\n💡 DIAGNOSTIC:")
        if avg_intensity < 5:
            print("❌ PROBLÈME: Image très sombre")
            print("   - Vérifiez que l'objectif n'est pas couvert")
            print("   - Augmentez l'éclairage de la scène")
            print("   - L'auto-exposition n'arrive pas à compenser")
            return False
        elif variation < 10:
            print("⚠️ ATTENTION: Image très uniforme")
            print("   - La caméra fonctionne mais pointe vers surface unie")
            print("   - Pointez vers un objet avec plus de détails")
            print("   - Ajoutez de la variation d'éclairage")
            return True
        else:
            print("✅ EXCELLENT: Image normale avec variation")
            print("   - La caméra fonctionne parfaitement")
            print("   - Prêt pour utilisation dans Robot Tracker")
            return True
    
    return False

def test_driver_corrected():
    """Test rapide du driver corrigé"""
    print(f"\n🔧 Test Driver Corrigé")
    print("-" * 30)
    
    try:
        from hardware.usb3_camera_driver import USB3CameraDriver
        
        config = {
            'width': 640,
            'height': 480,
            'auto_exposure': True,
            'gain': 50,
            'brightness': 200,
            'contrast': 80,
            'intensity_target': 30.0
        }
        
        camera = USB3CameraDriver(0, config)
        
        if camera.open():
            print("✅ Driver corrigé fonctionne")
            
            # Test validation
            validation = camera.validate_current_stream()
            print(f"📊 Status: {validation.get('status')}")
            print(f"   Intensité: {validation.get('avg_intensity', 0):.1f}")
            
            camera.close()
            return True
        else:
            print("❌ Driver corrigé ne fonctionne pas")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def main():
    """Point d'entrée principal"""
    print("🚀 Test Rapide Caméra Robot Tracker")
    print("Vérification visuelle et fonctionnelle")
    print("=" * 50)
    
    print("Ce test va:")
    print("1. 🎥 Ouvrir un aperçu visuel de la caméra")
    print("2. 📊 Afficher les statistiques en temps réel")
    print("3. 🔧 Tester le driver corrigé")
    print()
    
    # Test 1: Aperçu visuel
    visual_ok = test_visual_camera()
    
    # Test 2: Driver corrigé
    driver_ok = test_driver_corrected()
    
    # Conclusion
    print(f"\n" + "=" * 50)
    print("📋 RÉSULTATS:")
    print(f"   Test visuel:     {'✅ OK' if visual_ok else '❌ PROBLÈME'}")
    print(f"   Driver corrigé:  {'✅ OK' if driver_ok else '❌ PROBLÈME'}")
    
    if visual_ok and driver_ok:
        print(f"\n🎉 SUCCÈS COMPLET!")
        print("✅ La caméra fonctionne parfaitement")
        print("🚀 Vous pouvez utiliser Robot Tracker normalement")
        print("\n📋 Prochaines étapes:")
        print("1. Relancer main.py")
        print("2. Tester l'onglet Caméra")
        print("3. Vérifier le streaming temps réel")
        return 0
    elif visual_ok:
        print(f"\n⚠️ SUCCÈS PARTIEL")
        print("✅ Caméra fonctionne mais problème driver")
        print("🔧 Appliquer les corrections du driver")
        return 1
    else:
        print(f"\n❌ PROBLÈME PHYSIQUE")
        print("⚠️ Vérifiez l'objectif et l'éclairage")
        print("💡 La caméra fonctionne mais image uniforme")
        return 2

if __name__ == "__main__":
    try:
        exit_code = main()
        print(f"\n👋 Test terminé (code: {exit_code})")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Test interrompu par l'utilisateur")
        cv2.destroyAllWindows()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        cv2.destroyAllWindows()
        sys.exit(1)