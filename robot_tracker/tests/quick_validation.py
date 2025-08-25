# tests/quick_validation.py
# Version 1.0 - Validation rapide des corrections d'imports
# Modification: Test rapide sans interface graphique

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# Configuration paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_basic_imports():
    """Test des imports de base"""
    print("🧪 Test imports de base...")
    
    try:
        # Test import logging et os
        import logging
        import os
        import time
        print("✅ Modules système OK")
        
        # Test PyQt6 minimal
        from PyQt6.QtWidgets import QApplication, QWidget, QLabel
        from PyQt6.QtCore import QTimer
        print("✅ PyQt6 minimal OK")
        
        return True
    except ImportError as e:
        print(f"❌ Erreur imports de base: {e}")
        return False

def test_camera_manager_import():
    """Test import camera_manager avec mock pyrealsense2"""
    print("\n🧪 Test CameraManager...")
    
    try:
        # Mock pyrealsense2 pour éviter l'erreur
        sys.modules['pyrealsense2'] = type('MockRS', (), {
            'pipeline': type('Pipeline', (), {}),
            'config': type('Config', (), {}),
            'align': type('Align', (), {}),
            'stream': type('Stream', (), {'color': 1, 'depth': 2}),
            'format': type('Format', (), {'bgr8': 1, 'z16': 2}),
            'colorizer': type('Colorizer', (), {})
        })()
        
        from core.camera_manager import CameraManager
        print("✅ CameraManager importé")
        
        # Test création avec config dummy
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: default
        })()
        
        manager = CameraManager(dummy_config)
        print("✅ CameraManager instancié")
        
        # Test méthode is_camera_open
        if hasattr(manager, 'is_camera_open'):
            result = manager.is_camera_open("test")
            print(f"✅ is_camera_open disponible: {result}")
        
        return True
    except Exception as e:
        print(f"❌ Erreur CameraManager: {e}")
        return False

def test_camera_tab_import():
    """Test import camera_tab"""
    print("\n🧪 Test CameraTab...")
    
    try:
        # Configuration dummy
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: {
                'ui.camera_tab.version': '4.5',
                'ui.camera_tab.layout.control_panel_width': 280,
                'ui.camera_tab.acquisition.default_fps': 30,
                'ui.camera_tab.log.max_lines': 100
            }.get(f"{section}.{key}", default)
        })()
        
        from ui.camera_tab import CameraTab
        print("✅ CameraTab importé")
        
        return True
    except Exception as e:
        print(f"❌ Erreur CameraTab: {e}")
        return False

def test_integration_basic():
    """Test intégration basique sans interface"""
    print("\n🧪 Test intégration basique...")
    
    try:
        # Mock pyrealsense2
        sys.modules['pyrealsense2'] = type('MockRS', (), {
            'pipeline': type('Pipeline', (), {}),
            'config': type('Config', (), {}),
            'align': type('Align', (), {}),
            'stream': type('Stream', (), {'color': 1, 'depth': 2}),
            'format': type('Format', (), {'bgr8': 1, 'z16': 2}),
            'colorizer': type('Colorizer', (), {})
        })()
        
        from core.camera_manager import CameraManager
        from ui.camera_tab import CameraTab
        
        # Configuration dummy complète
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: {
                'ui.camera_tab.version': '4.5',
                'ui.camera_tab.layout.control_panel_width': 280,
                'ui.camera_tab.layout.display_area_width': 800,
                'ui.camera_tab.acquisition.default_fps': 30,
                'ui.camera_tab.timers.stats_interval_ms': 1000,
                'ui.camera_tab.layout.max_columns_single': 3,
                'ui.camera_tab.layout.max_columns_dual': 2,
                'ui.camera_tab.overlay.font_scale': 0.6,
                'ui.camera_tab.overlay.text_color': [255, 255, 255],
                'ui.camera_tab.overlay.thickness': 1,
                'ui.camera_tab.log.max_lines': 100,
                'camera.manager.target_fps': 30
            }.get(f"{section}.{key}", default)
        })()
        
        # Création instances
        camera_manager = CameraManager(dummy_config)
        print("✅ CameraManager créé")
        
        # Test is_camera_open
        is_open = camera_manager.is_camera_open("test_camera")
        print(f"✅ is_camera_open('test_camera'): {is_open}")
        
        print("✅ Intégration basique réussie")
        return True
        
    except Exception as e:
        print(f"❌ Erreur intégration: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_file_structure():
    """Vérifie la structure des fichiers"""
    print("\n🧪 Test structure fichiers...")
    
    files_to_check = [
        "core/camera_manager.py",
        "ui/camera_tab.py", 
        "ui/__init__.py",
        "hardware/usb3_camera_driver.py",
        "tests/test_camera_fix.py"
    ]
    
    missing = []
    for file_path in files_to_check:
        full_path = os.path.join(project_root, file_path)
        if os.path.exists(full_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} MANQUANT")
            missing.append(file_path)
    
    if not missing:
        print("✅ Structure fichiers OK")
        return True
    else:
        print(f"❌ {len(missing)} fichier(s) manquant(s)")
        return False

def main():
    """Fonction principale de validation"""
    print("🚀 Validation rapide des corrections d'imports")
    print("=" * 50)
    
    tests = [
        ("Imports de base", test_basic_imports),
        ("CameraManager", test_camera_manager_import),
        ("CameraTab", test_camera_tab_import),
        ("Intégration", test_integration_basic),
        ("Structure fichiers", test_file_structure)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Échec critique {test_name}: {e}")
            results.append((test_name, False))
    
    # Résultats
    print("\n" + "=" * 50)
    print("📊 RÉSULTATS VALIDATION")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSÉ" if result else "❌ ÉCHEC"
        print(f"{test_name:<20} : {status}")
        if result:
            passed += 1
    
    success_rate = passed / total
    print(f"\nScore: {passed}/{total} ({success_rate:.1%})")
    
    if success_rate == 1.0:
        print("\n🎉 VALIDATION COMPLÈTE RÉUSSIE!")
        print("✅ Les corrections d'imports fonctionnent")
        print("✅ Vous pouvez maintenant lancer test_camera_fix.py")
        return True
    else:
        failed = total - passed
        print(f"\n⚠️ {failed} test(s) échoué(s)")
        print("❌ Des corrections supplémentaires sont nécessaires")
        return False

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n💡 Étapes suivantes:")
        print("1. Lancez: python tests/test_camera_fix.py")
        print("2. Vérifiez que tous les tests passent")
        print("3. Si OK, les corrections sont opérationnelles")
    
    sys.exit(0 if success else 1)