# tests/quick_fix_validation.py
# Version 1.0 - Validation rapide des corrections d'ouverture RealSense
# Modification: Test minimal sans interface graphique

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import logging

# Configuration paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def validate_camera_manager_fix():
    """Valide la correction du CameraManager"""
    print("🔧 Validation CameraManager...")
    
    try:
        # Mock pyrealsense2 si nécessaire
        try:
            import pyrealsense2 as rs
            print("✅ RealSense SDK disponible")
        except ImportError:
            print("⚠️ RealSense SDK non disponible, utilisation du mock")
            sys.modules['pyrealsense2'] = type('MockRS', (), {
                'pipeline': type('Pipeline', (), {}),
                'config': type('Config', (), {}),
                'align': type('Align', (), {}),
                'stream': type('Stream', (), {'color': 1, 'depth': 2}),
                'format': type('Format', (), {'bgr8': 1, 'z16': 2}),
                'context': lambda: type('Context', (), {
                    'query_devices': lambda: []
                })()
            })()
        
        from core.camera_manager import CameraManager
        from hardware.realsense_driver import RealSenseCamera
        
        # Configuration de test
        class TestConfig:
            def get(self, section: str, key: str, default=None):
                return default
        
        config = TestConfig()
        manager = CameraManager(config)
        
        # Test création instance RealSense avec config
        from core.camera_manager import CameraInfo, CameraType
        
        test_camera_info = CameraInfo(
            camera_type=CameraType.REALSENSE,
            device_id="test_serial",
            name="Test RealSense",
            details={}
        )
        
        # VÉRIFICATION CRITIQUE: RealSenseCamera reçoit-elle la config ?
        instance = manager._create_camera_instance(test_camera_info)
        
        if instance is None:
            print("❌ Instance RealSense non créée")
            return False
        
        if hasattr(instance, 'config'):
            print("✅ Configuration transmise à RealSenseCamera")
        else:
            print("❌ Configuration NON transmise à RealSenseCamera")
            return False
        
        print("✅ CameraManager corrigé")
        return True
        
    except Exception as e:
        print(f"❌ Erreur validation CameraManager: {e}")
        return False

def validate_camera_tab_fix():
    """Valide la correction du CameraTab"""
    print("\n🔧 Validation CameraTab...")
    
    try:
        # Mock PyQt6 si nécessaire (pour éviter l'interface graphique)
        try:
            from PyQt6.QtWidgets import QWidget
        except ImportError:
            print("⚠️ PyQt6 non disponible, test des imports uniquement")
        
        # Test import du module
        import ui.camera_tab
        
        # Vérification que les méthodes stub sont remplacées
        import inspect
        
        stub_methods = [
            '_open_selected_camera',
            '_close_selected_camera',
            '_start_streaming',
            '_stop_streaming'
        ]
        
        for method_name in stub_methods:
            if hasattr(ui.camera_tab.CameraTab, method_name):
                method = getattr(ui.camera_tab.CameraTab, method_name)
                source = inspect.getsource(method)
                
                if "stub" in source.lower():
                    print(f"❌ {method_name} contient encore du code stub")
                    return False
                else:
                    print(f"✅ {method_name} implémentée")
        
        print("✅ CameraTab corrigé")
        return True
        
    except Exception as e:
        print(f"❌ Erreur validation CameraTab: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_file_structure():
    """Vérifie la structure des fichiers"""
    print("📁 Vérification structure fichiers...")
    
    required_files = [
        'core/camera_manager.py',
        'hardware/realsense_driver.py', 
        'ui/camera_tab.py'
    ]
    
    all_present = True
    for file_path in required_files:
        full_path = os.path.join(project_root, file_path)
        if os.path.exists(full_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} manquant")
            all_present = False
    
    return all_present

def main():
    """Validation rapide complète"""
    print("🚀 VALIDATION RAPIDE DES CORRECTIONS")
    print("=" * 50)
    
    # Réduction du logging
    logging.getLogger().setLevel(logging.ERROR)
    
    # Tests
    tests = [
        ("Structure fichiers", check_file_structure),
        ("CameraManager fix", validate_camera_manager_fix),
        ("CameraTab fix", validate_camera_tab_fix)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
    
    # Résultats
    print("\n" + "=" * 50)
    print("📊 RÉSULTATS")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ OK" if result else "❌ ÉCHEC"
        print(f"{test_name:<20} : {status}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\nScore: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 CORRECTIONS VALIDÉES!")
        print("\n💡 Pour tester avec votre RealSense:")
        print("   1. Remplacez le contenu des fichiers:")
        print("      - core/camera_manager.py")
        print("      - ui/camera_tab.py")  
        print("   2. Relancez python main.py")
        print("   3. L'ouverture de la caméra devrait maintenant fonctionner")
        return True
    else:
        print(f"\n⚠️ {total - passed} validation(s) échouée(s)")
        return False

if __name__ == "__main__":
    success = main()
    print(f"\n🔚 Validation {'réussie' if success else 'échouée'}")
    sys.exit(0 if success else 1)