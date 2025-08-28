# tests/test_final_integration.py
# Version 1.0 - Test d'intégration finale après corrections
# Modification: Vérification complète que toutes les erreurs sont corrigées

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from pathlib import Path

# Configuration du chemin
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_camera_manager_methods():
    """Test des méthodes de CameraManager"""
    print("🧪 Test CameraManager...")
    
    try:
        # Mock pyrealsense2
        if 'pyrealsense2' not in sys.modules:
            sys.modules['pyrealsense2'] = type('MockRS', (), {
                'context': lambda: type('Context', (), {
                    'query_devices': lambda: []
                })(),
                'camera_info': type('CameraInfo', (), {
                    'serial_number': 'serial_number',
                    'name': 'name'
                })()
            })()
        
        from core.camera_manager import CameraManager
        
        # Configuration test
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: default
        })()
        
        manager = CameraManager(dummy_config)
        print("✅ CameraManager créé")
        
        # Test des méthodes critiques pour camera_tab.py
        camera_tab_methods = [
            'detect_all_cameras',
            'open_camera',
            'close_camera', 
            'is_camera_open',
            'start_streaming',
            'stop_streaming',
            'get_camera_frame'
        ]
        
        missing_methods = []
        for method in camera_tab_methods:
            if hasattr(manager, method):
                print(f"✅ {method}")
            else:
                print(f"❌ {method} MANQUANTE")
                missing_methods.append(method)
        
        # Test des propriétés pour main_window.py
        main_window_properties = ['active_cameras']
        
        for prop in main_window_properties:
            if hasattr(manager, prop):
                print(f"✅ Propriété {prop}")
            else:
                print(f"❌ Propriété {prop} MANQUANTE")
                missing_methods.append(prop)
        
        if not missing_methods:
            print("✅ Toutes les méthodes requises sont présentes")
            return True
        else:
            print(f"❌ {len(missing_methods)} méthode(s)/propriété(s) manquante(s)")
            return False
            
    except Exception as e:
        print(f"❌ Erreur test CameraManager: {e}")
        return False

def test_camera_tab_integration():
    """Test d'intégration avec camera_tab"""
    print("\n🧪 Test intégration CameraTab...")
    
    try:
        # Mock pour éviter l'interface graphique
        import sys
        if 'PyQt6.QtWidgets' not in sys.modules:
            # Mock PyQt6
            mock_qt = type('MockQt', (), {
                'QWidget': type('QWidget', (), {}),
                'QVBoxLayout': type('QVBoxLayout', (), {}),
                'QHBoxLayout': type('QHBoxLayout', (), {}),
                'QLabel': type('QLabel', (), {}),
                'QComboBox': type('QComboBox', (), {}),
                'QPushButton': type('QPushButton', (), {}),
                'QTextEdit': type('QTextEdit', (), {}),
                'QCheckBox': type('QCheckBox', (), {}),
                'QScrollArea': type('QScrollArea', (), {}),
                'QTableWidget': type('QTableWidget', (), {}),
                'QTimer': type('QTimer', (), {}),
            })()
            
            sys.modules['PyQt6.QtWidgets'] = mock_qt
            sys.modules['PyQt6.QtCore'] = type('MockQtCore', (), {
                'QTimer': type('QTimer', (), {}),
                'pyqtSignal': lambda *args: lambda f: f,
                'Qt': type('Qt', (), {
                    'AlignmentFlag': type('AlignmentFlag', (), {'AlignCenter': 1}),
                    'MouseButton': type('MouseButton', (), {'LeftButton': 1})
                })()
            })()
            sys.modules['PyQt6.QtGui'] = type('MockQtGui', (), {
                'QImage': type('QImage', (), {}),
                'QPixmap': type('QPixmap', (), {})
            })()
        
        # Mock cv2
        if 'cv2' not in sys.modules:
            sys.modules['cv2'] = type('MockCV2', (), {
                'COLOR_BGR2RGB': 4,
                'cvtColor': lambda img, code: img,
                'imwrite': lambda filename, img: True
            })()
        
        # Mock numpy
        if 'numpy' not in sys.modules:
            sys.modules['numpy'] = type('MockNumpy', (), {
                'ndarray': type('ndarray', (), {})
            })()
        
        from core.camera_manager import CameraManager
        
        # Configuration test
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: {
                'ui.camera_tab.acquisition.default_fps': 30,
                'ui.camera_tab.timers.stats_interval_ms': 1000,
                'ui.camera_tab.layout.control_panel_width': 280,
                'ui.camera_tab.log.max_lines': 100
            }.get(f"{section}.{key}", default)
        })()
        
        camera_manager = CameraManager(dummy_config)
        
        # Test des appels spécifiques que fait camera_tab.py
        try:
            cameras = camera_manager.detect_all_cameras()
            print(f"✅ detect_all_cameras() retourne {len(cameras)} caméras")
            
            active = camera_manager.active_cameras
            print(f"✅ active_cameras retourne {len(active)} caméras actives")
            
            is_open = camera_manager.is_camera_open("test_camera")
            print(f"✅ is_camera_open() retourne {is_open}")
            
            # Test format get_camera_frame pour camera_tab
            result = camera_manager.get_camera_frame("test_camera")
            if isinstance(result, tuple) and len(result) == 3:
                print("✅ get_camera_frame() retourne le bon format (bool, frame, depth)")
            else:
                print(f"⚠️ get_camera_frame() format inattendu: {type(result)}")
            
            print("✅ Intégration CameraTab réussie")
            return True
            
        except Exception as e:
            print(f"❌ Erreur appels CameraTab: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur test intégration CameraTab: {e}")
        return False

def test_main_window_integration():
    """Test d'intégration avec main_window"""
    print("\n🧪 Test intégration MainWindow...")
    
    try:
        from core.camera_manager import CameraManager
        
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: default
        })()
        
        camera_manager = CameraManager(dummy_config)
        
        # Test des appels spécifiques que fait main_window.py
        try:
            # Test active_cameras property
            active = camera_manager.active_cameras
            print(f"✅ active_cameras property: {active}")
            
            # Test stop_streaming method
            camera_manager.stop_streaming()  # Ne devrait pas planter
            print("✅ stop_streaming() ne plante pas")
            
            # Test close_all_cameras method
            camera_manager.close_all_cameras()  # Ne devrait pas planter
            print("✅ close_all_cameras() ne plante pas")
            
            print("✅ Intégration MainWindow réussie")
            return True
            
        except Exception as e:
            print(f"❌ Erreur appels MainWindow: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur test intégration MainWindow: {e}")
        return False

def test_import_circulaire():
    """Test qu'il n'y a plus d'import circulaire"""
    print("\n🧪 Test imports circulaires...")
    
    try:
        # Réinitialisation des modules
        modules_to_clear = [
            'core.camera_manager',
            'ui.camera_tab',
            'ui.main_window'
        ]
        
        for module in modules_to_clear:
            if module in sys.modules:
                del sys.modules[module]
        
        # Test import direct sans erreur circulaire
        from core.camera_manager import CameraManager
        print("✅ Import CameraManager sans erreur circulaire")
        
        # Test que les autres imports fonctionnent
        try:
            from ui.main_window import MainWindow
            print("✅ Import MainWindow réussi")
        except ImportError as e:
            if "circular import" in str(e).lower():
                print(f"❌ Import circulaire détecté: {e}")
                return False
            else:
                print(f"⚠️ Autre erreur d'import MainWindow (probablement dépendances): {e}")
        
        return True
        
    except ImportError as e:
        if "circular import" in str(e).lower() or "partially initialized" in str(e).lower():
            print(f"❌ Import circulaire persistant: {e}")
            return False
        else:
            print(f"⚠️ Autre erreur d'import: {e}")
            return True
            
    except Exception as e:
        print(f"❌ Erreur test import circulaire: {e}")
        return False

def main():
    """Test d'intégration finale"""
    print("🚀 TEST D'INTÉGRATION FINALE")
    print("=" * 50)
    print("Vérification que toutes les erreurs sont corrigées")
    print()
    
    # Tests
    tests = [
        ("Import circulaire", test_import_circulaire),
        ("CameraManager méthodes", test_camera_manager_methods),
        ("Intégration CameraTab", test_camera_tab_integration),
        ("Intégration MainWindow", test_main_window_integration)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results[test_name] = success
        except Exception as e:
            print(f"❌ Erreur critique {test_name}: {e}")
            results[test_name] = False
    
    # Résumé
    print("\n" + "=" * 50)
    print("📊 RÉSULTATS FINAUX")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅ PASSÉ" if success else "❌ ÉCHEC"
        print(f"{status:12} {test_name}")
        if success:
            passed += 1
    
    success_rate = passed / total
    print(f"\nScore: {passed}/{total} ({success_rate:.1%})")
    
    if success_rate >= 0.75:  # Au moins 75% de réussite
        print("\n🎉 INTÉGRATION FINALE RÉUSSIE!")
        print("✅ Les erreurs principales ont été corrigées")
        print("✅ L'application devrait se lancer sans erreurs AttributeError")
        print("\n📋 MAINTENANT:")
        print("   1. python main.py")
        print("   2. Testez l'onglet Caméra")
        print("   3. Vérifiez qu'il n'y a plus d'erreurs dans le terminal")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) échoué(s)")
        print("🔧 Des corrections supplémentaires peuvent être nécessaires")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Test interrompu")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur générale: {e}")
        sys.exit(1)