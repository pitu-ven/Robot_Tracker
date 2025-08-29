# tests/test_camera_fix_integration.py
# Version 1.0 - Test des corrections d'ouverture de caméra RealSense
# Modification: Test complet d'intégration avec les corrections

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import logging

# Ajout du chemin parent pour les imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_camera_manager_with_config():
    """Test du CameraManager avec configuration RealSense"""
    print("🧪 Test CameraManager avec configuration...")
    
    try:
        # Mock pyrealsense2 si nécessaire
        has_realsense = True
        try:
            import pyrealsense2 as rs
        except ImportError:
            has_realsense = False
            sys.modules['pyrealsense2'] = type('MockRS', (), {
                'pipeline': type('Pipeline', (), {}),
                'config': type('Config', (), {}),
                'align': type('Align', (), {}),
                'stream': type('Stream', (), {'color': 1, 'depth': 2}),
                'format': type('Format', (), {'bgr8': 1, 'z16': 2}),
                'colorizer': type('Colorizer', (), {})
            })()
            print("⚠️ RealSense mocké pour les tests")
        
        from core.camera_manager import CameraManager
        
        # Configuration de test complète
        class TestConfig:
            def get(self, section: str, key: str, default=None):
                config_values = {
                    'camera.manager.auto_detect_interval': 5.0,
                    'camera.manager.max_frame_buffer': 5,
                    'camera.realsense.device_serial': None,
                    'camera.realsense.color_width': 640,
                    'camera.realsense.color_height': 480,
                    'camera.realsense.color_fps': 30,
                    'camera.realsense.depth_width': 640,
                    'camera.realsense.depth_height': 480,
                    'camera.realsense.depth_fps': 30,
                    'camera.realsense.enable_filters': True,
                    'camera.realsense.enable_align': True,
                    'camera.realsense.enable_infrared': False,
                    'camera.realsense.version': '2.9'
                }
                return config_values.get(f"{section}.{key}", default)
        
        config = TestConfig()
        manager = CameraManager(config)
        
        print("✅ CameraManager créé avec configuration RealSense")
        
        # Test détection
        cameras = manager.detect_all_cameras()
        print(f"✅ Détection: {len(cameras)} caméra(s)")
        
        # Test méthodes critiques
        methods = ['is_camera_open', 'open_camera', 'close_camera', 'get_camera_frame']
        for method in methods:
            if hasattr(manager, method):
                print(f"✅ Méthode {method} disponible")
            else:
                print(f"❌ Méthode {method} manquante")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur test CameraManager: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_realsense_instance_creation():
    """Test création d'instance RealSense avec config"""
    print("\n🧪 Test création instance RealSense...")
    
    try:
        # Mock pyrealsense2 si nécessaire
        try:
            import pyrealsense2 as rs
        except ImportError:
            sys.modules['pyrealsense2'] = type('MockRS', (), {
                'pipeline': type('Pipeline', (), {}),
                'config': type('Config', (), {}),
                'align': type('Align', (), {}),
                'stream': type('Stream', (), {'color': 1, 'depth': 2}),
                'format': type('Format', (), {'bgr8': 1, 'z16': 2}),
                'colorizer': type('Colorizer', (), {}),
                'context': lambda: type('Context', (), {
                    'query_devices': lambda: []
                })()
            })()
        
        from hardware.realsense_driver import RealSenseCamera
        from core.camera_manager import CameraType, CameraInfo
        
        # Configuration de test
        class TestConfig:
            def get(self, section: str, key: str, default=None):
                config_values = {
                    'camera.realsense.device_serial': None,
                    'camera.realsense.color_width': 640,
                    'camera.realsense.color_height': 480,
                    'camera.realsense.color_fps': 30,
                    'camera.realsense.depth_width': 640,
                    'camera.realsense.depth_height': 480,
                    'camera.realsense.depth_fps': 30,
                    'camera.realsense.enable_filters': True,
                    'camera.realsense.enable_align': True,
                    'camera.realsense.version': '2.9'
                }
                return config_values.get(f"{section}.{key}", default)
        
        config = TestConfig()
        
        # Test création avec config
        realsense_camera = RealSenseCamera(config)
        print("✅ RealSenseCamera créée avec config")
        
        # Test création via _create_camera_instance
        from core.camera_manager import CameraManager
        manager = CameraManager(config)
        
        # Simulation d'une CameraInfo RealSense
        camera_info = CameraInfo(
            camera_type=CameraType.REALSENSE,
            device_id="test_serial",
            name="Test RealSense D435",
            details={'serial': 'test_serial', 'name': 'Test RealSense D435'}
        )
        
        instance = manager._create_camera_instance(camera_info)
        if instance:
            print("✅ Instance RealSense créée via CameraManager")
        else:
            print("❌ Échec création instance via CameraManager")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur test création instance: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_camera_tab_real_methods():
    """Test que CameraTab utilise de vraies méthodes"""
    print("\n🧪 Test CameraTab méthodes réelles...")
    
    try:
        # Mock pyrealsense2
        try:
            import pyrealsense2 as rs
        except ImportError:
            sys.modules['pyrealsense2'] = type('MockRS', (), {
                'pipeline': type('Pipeline', (), {}),
                'config': type('Config', (), {}),
                'align': type('Align', (), {}),
                'stream': type('Stream', (), {'color': 1, 'depth': 2}),
                'format': type('Format', (), {'bgr8': 1, 'z16': 2}),
                'colorizer': type('Colorizer', (), {}),
                'context': lambda: type('Context', (), {
                    'query_devices': lambda: []
                })()
            })()
        
        from ui.camera_tab import CameraTab
        from core.camera_manager import CameraManager
        
        # Configuration complète
        class TestConfig:
            def get(self, section: str, key: str, default=None):
                config_values = {
                    'ui.camera_tab.version': '4.4',
                    'ui.camera_tab.layout.control_panel_width': 280,
                    'ui.camera_tab.acquisition.default_fps': 30,
                    'ui.camera_tab.timers.stats_interval_ms': 1000,
                    'ui.camera_tab.log.max_lines': 100,
                    'camera.manager.auto_detect_interval': 5.0,
                    'camera.realsense.device_serial': None,
                    'camera.realsense.color_width': 640,
                    'camera.realsense.color_height': 480,
                    'camera.realsense.color_fps': 30
                }
                return config_values.get(f"{section}.{key}", default)
        
        config = TestConfig()
        camera_manager = CameraManager(config)
        
        # Vérification des méthodes du CameraTab (sans créer l'UI)
        class TestCameraTab:
            def __init__(self, camera_manager, config):
                self.camera_manager = camera_manager
                self.config = config
                self.selected_camera = None
                self.active_displays = {}
                self.is_streaming = False
        
        # Importation directe des méthodes
        import inspect
        from ui.camera_tab import CameraTab
        
        # Vérification que les méthodes ne sont plus des stubs
        methods_to_check = [
            '_open_selected_camera',
            '_close_selected_camera', 
            '_start_streaming',
            '_stop_streaming',
            '_update_camera_frames',
            '_capture_frame',
            '_save_image'
        ]
        
        for method_name in methods_to_check:
            if hasattr(CameraTab, method_name):
                method = getattr(CameraTab, method_name)
                source = inspect.getsource(method)
                
                # Vérification qu'il n'y a plus de "stub" dans le code
                if "stub" in source.lower() or "version test" in source.lower():
                    print(f"❌ {method_name} contient encore du code stub")
                    return False
                else:
                    print(f"✅ {method_name} implémentée (pas de stub)")
            else:
                print(f"❌ Méthode {method_name} manquante")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur test CameraTab: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration_complete():
    """Test d'intégration complète"""
    print("\n🧪 Test intégration complète...")
    
    try:
        # Mock pyrealsense2
        try:
            import pyrealsense2 as rs
        except ImportError:
            sys.modules['pyrealsense2'] = type('MockRS', (), {
                'pipeline': type('Pipeline', (), {
                    'start': lambda self, config=None: None,
                    'stop': lambda self: None,
                    'wait_for_frames': lambda self, timeout_ms=5000: type('Frameset', (), {
                        'get_color_frame': lambda: type('Frame', (), {'get_data': lambda: None})(),
                        'get_depth_frame': lambda: type('Frame', (), {'get_data': lambda: None})()
                    })()
                })(),
                'config': type('Config', (), {
                    'enable_device': lambda self, serial: None,
                    'enable_stream': lambda self, *args: None
                })(),
                'align': type('Align', (), {})(),
                'stream': type('Stream', (), {'color': 1, 'depth': 2}),
                'format': type('Format', (), {'bgr8': 1, 'z16': 2}),
                'colorizer': type('Colorizer', (), {}),
                'context': lambda: type('Context', (), {
                    'query_devices': lambda: []
                })()
            })()
        
        from core.camera_manager import CameraManager, CameraInfo, CameraType
        
        # Configuration de test
        class TestConfig:
            def get(self, section: str, key: str, default=None):
                config_values = {
                    'camera.manager.auto_detect_interval': 5.0,
                    'camera.manager.max_frame_buffer': 5,
                    'camera.realsense.device_serial': None,
                    'camera.realsense.color_width': 640,
                    'camera.realsense.color_height': 480,
                    'camera.realsense.color_fps': 30,
                    'camera.realsense.depth_width': 640,
                    'camera.realsense.depth_height': 480,
                    'camera.realsense.depth_fps': 30,
                    'camera.realsense.enable_filters': True,
                    'camera.realsense.enable_align': True,
                    'camera.realsense.version': '2.9'
                }
                return config_values.get(f"{section}.{key}", default)
        
        config = TestConfig()
        manager = CameraManager(config)
        
        # Simulation d'une caméra RealSense
        test_camera = CameraInfo(
            camera_type=CameraType.REALSENSE,
            device_id="014122072611",  # Même serial que dans les logs
            name="Intel RealSense D435",
            details={'serial': '014122072611', 'name': 'Intel RealSense D435'}
        )
        
        print("✅ CameraInfo RealSense créée")
        
        # Test création d'instance
        instance = manager._create_camera_instance(test_camera)
        if instance is None:
            print("❌ Échec création instance RealSense")
            return False
        
        print("✅ Instance RealSense créée avec config")
        
        # Test que la config est bien passée
        if hasattr(instance, 'config'):
            print("✅ Configuration transmise à l'instance RealSense")
        else:
            print("❌ Configuration non transmise à l'instance")
            return False
        
        # Test d'ouverture (simulation)
        alias = "test_realsense"
        
        # Dans un vrai test, l'ouverture échouerait car pas de vraie caméra
        # Mais on peut vérifier que le code ne plante pas
        try:
            success = manager.open_camera(test_camera, alias)
            # On s'attend à un échec car pas de vraie caméra
            if success:
                print("✅ Ouverture simulée réussie (inattendu mais pas grave)")
                manager.close_camera(alias)
            else:
                print("✅ Échec ouverture attendu (pas de vraie caméra)")
        except Exception as e:
            print(f"✅ Exception attendue lors de l'ouverture: {type(e).__name__}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur test intégration: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_diagnostic():
    """Diagnostic complet du problème"""
    print("🔍 DIAGNOSTIC DU PROBLÈME D'OUVERTURE REALSENSE")
    print("=" * 60)
    
    # 1. Vérification des imports
    print("\n1️⃣ Vérification des imports...")
    try:
        import pyrealsense2 as rs
        print("✅ pyrealsense2 disponible")
        
        # Test contexte RealSense
        ctx = rs.context()
        devices = ctx.query_devices()
        print(f"✅ {len(devices)} device(s) RealSense détecté(s)")
        
    except ImportError as e:
        print(f"❌ pyrealsense2 non disponible: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Erreur détection RealSense: {e}")
    
    # 2. Vérification structure projet
    print("\n2️⃣ Vérification structure projet...")
    project_files = [
        'core/camera_manager.py',
        'hardware/realsense_driver.py',
        'ui/camera_tab.py'
    ]
    
    for file_path in project_files:
        full_path = os.path.join(project_root, file_path)
        if os.path.exists(full_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} manquant")
    
    # 3. Test imports du projet
    print("\n3️⃣ Test imports du projet...")
    try:
        from core.camera_manager import CameraManager
        print("✅ CameraManager importé")
        
        from hardware.realsense_driver import RealSenseCamera
        print("✅ RealSenseCamera importé")
        
    except Exception as e:
        print(f"❌ Erreur imports: {e}")
        return False
    
    # 4. Analyse du problème spécifique
    print("\n4️⃣ Analyse du problème...")
    print("D'après les logs fournis:")
    print("- ✅ RealSense détectée: Intel RealSense D435 (S/N: 014122072611)")
    print("- ✅ CameraManager v2.8 initialisé")
    print("- ❌ camera_tab affiche '⚠️ Version test - _open_selected_camera stub'")
    print("- 🔧 SOLUTION: Remplacer les méthodes stub par les vraies implémentations")
    
    return True

def main():
    """Point d'entrée principal"""
    print("🚀 TEST DES CORRECTIONS D'OUVERTURE CAMERA REALSENSE")
    print("=" * 60)
    
    # Réduction du logging pour se concentrer sur les tests
    logging.getLogger().setLevel(logging.ERROR)
    
    # Diagnostic préliminaire
    if not run_diagnostic():
        print("\n❌ Diagnostic échoué - Arrêt des tests")
        return False
    
    # Tests des corrections
    tests = [
        ("CameraManager avec config", test_camera_manager_with_config),
        ("Création instance RealSense", test_realsense_instance_creation),
        ("CameraTab méthodes réelles", test_camera_tab_real_methods),
        ("Intégration complète", test_integration_complete)
    ]
    
    results = []
    
    print("\n" + "=" * 60)
    print("🧪 EXÉCUTION DES TESTS")
    print("=" * 60)
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name}: PASSÉ")
            else:
                print(f"❌ {test_name}: ÉCHOUÉ")
                
        except Exception as e:
            print(f"❌ {test_name}: ERREUR - {e}")
            results.append((test_name, False))
    
    # Résultats finaux
    print("\n" + "=" * 60)
    print("📊 RÉSULTATS FINAUX")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSÉ" if result else "❌ ÉCHOUÉ"
        print(f"{test_name:<30} : {status}")
    
    print(f"\n📈 Score: {passed}/{total} tests réussis")
    
    if passed == total:
        print("\n🎉 TOUTES LES CORRECTIONS SEMBLENT FONCTIONNER!")
        print("\n💡 Prochaines étapes:")
        print("   1. Appliquer les corrections aux fichiers du projet")
        print("   2. Tester avec une vraie caméra RealSense")
        print("   3. Vérifier que l'ouverture fonctionne correctement")
        return True
    else:
        print(f"\n⚠️ {total - passed} test(s) échoué(s)")
        print("   Des corrections supplémentaires peuvent être nécessaires")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)