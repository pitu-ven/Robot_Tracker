# tests/test_camera_fix.py
# Version 2.0 - Test des corrections camera_manager et camera_tab avec corrections imports
# Modification: Correction des erreurs d'import relatif et dépendances manquantes

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import logging

# Ajout du chemin parent pour les imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def check_pyrealsense_availability():
    """Vérifie la disponibilité de pyrealsense2"""
    try:
        import pyrealsense2 as rs
        return True, "Disponible"
    except ImportError as e:
        return False, f"Non disponible: {e}"

def test_camera_manager_import():
    """Test d'import et de la méthode is_camera_open avec gestion pyrealsense2"""
    print("🧪 Test import CameraManager...")
    
    # Vérification préalable pyrealsense2
    has_realsense, rs_msg = check_pyrealsense_availability()
    if not has_realsense:
        print(f"⚠️ RealSense non disponible: {rs_msg.split(':')[-1].strip()}")
    
    try:
        # Mock temporaire pour pyrealsense2 si nécessaire
        if not has_realsense:
            sys.modules['pyrealsense2'] = type('MockRS', (), {
                'pipeline': type('Pipeline', (), {}),
                'config': type('Config', (), {}),
                'align': type('Align', (), {}),
                'stream': type('Stream', (), {'color': 1, 'depth': 2}),
                'format': type('Format', (), {'bgr8': 1, 'z16': 2}),
                'colorizer': type('Colorizer', (), {})
            })()
        
        from core.camera_manager import CameraManager
        
        # Configuration dummy
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: default
        })()
        
        # Création instance
        manager = CameraManager(dummy_config)
        print(f"✅ CameraManager créé: {type(manager).__name__}")
        
        # Test méthode is_camera_open
        if hasattr(manager, 'is_camera_open'):
            result = manager.is_camera_open("test_alias")
            print(f"✅ Méthode is_camera_open disponible, retour: {result}")
        else:
            print("❌ Méthode is_camera_open manquante")
            return False
            
        # Test autres méthodes critiques
        methods_to_check = ['detect_cameras', 'open_camera', 'close_camera', 'get_camera_frame']
        
        for method_name in methods_to_check:
            if hasattr(manager, method_name):
                print(f"✅ Méthode {method_name} disponible")
            else:
                print(f"❌ Méthode {method_name} manquante")
                return False
        
        return True
        
    except ImportError as e:
        if "pyrealsense2" in str(e):
            print(f"❌ Erreur import USB3CameraDriver: {e}")
        else:
            print(f"❌ Erreur import CameraManager: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur test CameraManager: {e}")
        return False

def test_camera_tab_import():
    """Test d'import du CameraTab avec correction imports relatifs"""
    print("\n🧪 Test import CameraTab...")
    
    try:
        # Configuration dummy étendue
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
        
        # Mock des dépendances pyrealsense2 si nécessaire 
        has_realsense, _ = check_pyrealsense_availability()
        if not has_realsense:
            sys.modules['pyrealsense2'] = type('MockRS', (), {
                'pipeline': type('Pipeline', (), {}),
                'config': type('Config', (), {}),
                'align': type('Align', (), {}),
                'stream': type('Stream', (), {'color': 1, 'depth': 2}),
                'format': type('Format', (), {'bgr8': 1, 'z16': 2}),
                'colorizer': type('Colorizer', (), {})
            })()
        
        # Import direct sans relatifs
        from ui.camera_tab import CameraTab
        print(f"✅ CameraTab importé: {CameraTab.__name__}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Erreur import CameraTab: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur test CameraTab: {e}")
        return False

def test_integration():
    """Test d'intégration CameraManager + CameraTab"""
    print("\n🧪 Test intégration CameraManager + CameraTab...")
    
    # Vérification préalable
    has_realsense, rs_msg = check_pyrealsense_availability()
    if not has_realsense:
        print(f"⚠️ RealSense non disponible: {rs_msg.split(':')[-1].strip()}")
        # Mock pour permettre l'intégration
        sys.modules['pyrealsense2'] = type('MockRS', (), {
            'pipeline': type('Pipeline', (), {}),
            'config': type('Config', (), {}),
            'align': type('Align', (), {}),
            'stream': type('Stream', (), {'color': 1, 'depth': 2}),
            'format': type('Format', (), {'bgr8': 1, 'z16': 2}),
            'colorizer': type('Colorizer', (), {})
        })()
    
    try:
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
                'camera.manager.target_fps': 30,
                'camera.manager.auto_detect_interval': 5.0,
                'camera.manager.max_frame_buffer': 5,
                'camera.realsense.color_width': 640,
                'camera.realsense.color_height': 480,
                'camera.realsense.color_fps': 30,
                'camera.realsense.depth_width': 640,
                'camera.realsense.depth_height': 480,
                'camera.realsense.depth_fps': 30,
                'camera.usb3_camera.width': 640,
                'camera.usb3_camera.height': 480,
                'camera.usb3_camera.fps': 30
            }.get(f"{section}.{key}", default)
        })()
        
        # Création CameraManager
        camera_manager = CameraManager(dummy_config)
        print("✅ CameraManager créé pour intégration")
        
        # Test méthode is_camera_open
        test_alias = "test_camera"
        is_open_before = camera_manager.is_camera_open(test_alias)
        print(f"✅ Test is_camera_open('{test_alias}'): {is_open_before}")
        
        print("✅ Intégration basique réussie")
        return True
        
    except Exception as e:
        print(f"❌ Erreur intégration: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Fonction principale de test"""
    print("🚀 Tests des corrections Camera Manager et Camera Tab")
    print("=" * 60)
    
    # Configuration logging pour réduire le bruit
    logging.getLogger().setLevel(logging.WARNING)
    
    tests = [
        ("Import CameraManager", test_camera_manager_import),
        ("Import CameraTab", test_camera_tab_import), 
        ("Intégration", test_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Échec critique {test_name}: {e}")
            results.append((test_name, False))
    
    # Résultats finaux
    print("\n" + "=" * 60)
    print("📊 RÉSULTATS DES TESTS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASSÉ" if result else "❌ ÉCHEC"
        print(f"{test_name:<25} : {status}")
        
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📈 Total: {passed} réussis, {failed} échoués")
    
    if failed == 0:
        print("🎉 TOUS LES TESTS SONT PASSÉS - Les corrections fonctionnent !")
        return True
    else:
        print(f"⚠️ {failed} test(s) échoué(s) - Des corrections supplémentaires sont nécessaires")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)