#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_realsense_import.py - Robot_Tracker/robot_tracker/test_realsense_import.py
Script de test pour vérifier l'import RealSense - Version 1.0
Modification: Diagnostic complet de l'installation RealSense
"""

import sys
import os

def test_pyrealsense2_import():
    """Test d'import du module pyrealsense2"""
    print("🧪 Test d'import pyrealsense2...")
    
    try:
        import pyrealsense2 as rs
        print("✅ pyrealsense2 importé avec succès")
        
        # Version du SDK
        try:
            version = rs.context().query_all_sensors()[0].get_info(rs.camera_info.firmware_version) if rs.context().query_devices() else "N/A"
            print(f"📟 Version SDK RealSense détectée")
        except:
            print("⚠️ Impossible de récupérer la version")
        
        # Test de contexte
        ctx = rs.context()
        devices = ctx.query_devices()
        print(f"🔍 {len(devices)} périphérique(s) RealSense détecté(s)")
        
        for i, device in enumerate(devices):
            try:
                name = device.get_info(rs.camera_info.name)
                serial = device.get_info(rs.camera_info.serial_number)
                firmware = device.get_info(rs.camera_info.firmware_version)
                print(f"  📷 Device {i}: {name} (S/N: {serial}, FW: {firmware})")
            except Exception as e:
                print(f"  ❌ Erreur lecture device {i}: {e}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Erreur import pyrealsense2: {e}")
        print("💡 Solutions possibles:")
        print("   1. pip install pyrealsense2")
        print("   2. Vérifier l'environnement virtuel actif")
        print("   3. Redémarrer le terminal après installation")
        return False
    except Exception as e:
        print(f"❌ Erreur test pyrealsense2: {e}")
        return False

def test_driver_import():
    """Test d'import du driver RealSense local"""
    print("\n🧪 Test d'import driver RealSense local...")
    
    try:
        # Ajout du chemin courant si nécessaire
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        from hardware.realsense_driver import RealSenseCamera, list_available_realsense
        print("✅ Driver RealSense local importé avec succès")
        
        # Test de détection
        cameras = list_available_realsense()
        print(f"🔍 {len(cameras)} caméra(s) détectée(s) par le driver local")
        
        for cam in cameras:
            print(f"  📷 {cam['name']} (S/N: {cam['serial']})")
        
        return True
        
    except ImportError as e:
        print(f"❌ Erreur import driver local: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur test driver local: {e}")
        return False

def test_camera_manager_import():
    """Test d'import du CameraManager"""
    print("\n🧪 Test d'import CameraManager...")
    
    try:
        from core.camera_manager import CameraManager
        print("✅ CameraManager importé avec succès")
        
        # Configuration dummy
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: default
        })()
        
        # Test d'initialisation
        manager = CameraManager(dummy_config)
        print("✅ CameraManager initialisé avec succès")
        
        # Test de détection
        cameras = manager.detect_all_cameras()
        print(f"🔍 {len(cameras)} caméra(s) détectée(s) par le manager")
        
        for cam in cameras:
            print(f"  📷 {cam.name} ({cam.camera_type.value})")
        
        return True
        
    except ImportError as e:
        print(f"❌ Erreur import CameraManager: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur test CameraManager: {e}")
        return False

def main():
    """Fonction principale de test"""
    print("🎥 Test complet RealSense - Robot Tracker")
    print("=" * 50)
    
    # Test 1: pyrealsense2
    test1_ok = test_pyrealsense2_import()
    
    # Test 2: Driver local
    test2_ok = test_driver_import()
    
    # Test 3: CameraManager
    test3_ok = test_camera_manager_import()
    
    # Résumé
    print("\n" + "=" * 50)
    print("📋 Résumé des tests:")
    print(f"   pyrealsense2:     {'✅ OK' if test1_ok else '❌ ÉCHEC'}")
    print(f"   Driver local:     {'✅ OK' if test2_ok else '❌ ÉCHEC'}")
    print(f"   CameraManager:    {'✅ OK' if test3_ok else '❌ ÉCHEC'}")
    
    if all([test1_ok, test2_ok, test3_ok]):
        print("\n🎉 Tous les tests sont passés!")
        print("💡 RealSense devrait fonctionner dans camera_demo.py")
    else:
        print("\n⚠️ Certains tests ont échoué")
        print("💡 Vérifiez les erreurs ci-dessus")
    
    return 0 if all([test1_ok, test2_ok, test3_ok]) else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)