# tests/quick_camera_test.py
# Version 1.0 - Test rapide des corrections d'ouverture de caméra
# Modification: Test unitaire pour valider les corrections

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# Ajout du chemin du projet
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_camera_manager_creation():
    """Test simple de création d'une instance CameraManager"""
    print("🧪 Test création CameraManager...")
    
    try:
        # Configuration de test simple
        class TestConfig:
            def get(self, section, key, default=None):
                return default
        
        from core.camera_manager import CameraManager
        
        config = TestConfig()
        manager = CameraManager(config)
        
        print("✅ CameraManager créé avec succès")
        
        # Test méthode _create_camera_instance avec format dictionnaire
        camera_info = {
            'type': 'realsense',
            'serial': '014122072611',
            'name': 'Intel RealSense D435',
            'device_index': 0
        }
        
        # Cette ligne aurait causé l'erreur "__init__() takes 2 positional arguments but 3 were given"
        instance = manager._create_camera_instance(camera_info)
        
        if instance is not None:
            print("✅ Instance RealSense créée sans erreur de signature")
            
            # Vérifier que l'attribut is_streaming existe
            if hasattr(instance, 'is_streaming'):
                print("✅ Attribut is_streaming présent")
            else:
                print("❌ Attribut is_streaming manquant")
                return False
                
            # Test configuration du serial
            if hasattr(instance, 'device_serial') and instance.device_serial == '014122072611':
                print("✅ Serial configuré correctement")
            else:
                print(f"⚠️ Serial: {getattr(instance, 'device_serial', 'Non défini')}")
                
        else:
            print("❌ Échec création instance")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_camera_open_formats():
    """Test ouverture avec différents formats de données"""
    print("\n🧪 Test formats de données caméra...")
    
    try:
        from core.camera_manager import CameraManager
        
        class TestConfig:
            def get(self, section, key, default=None):
                return default
        
        config = TestConfig()
        manager = CameraManager(config)
        
        # Format 1: Dictionnaire (nouveau)
        camera_dict = {
            'type': 'realsense',
            'serial': '014122072611',
            'name': 'Intel RealSense D435',
            'device_index': 0
        }
        
        print("Test format dictionnaire...")
        try:
            # Cette ligne ne devrait plus causer d'erreur
            result = manager.open_camera(camera_dict, "test_realsense")
            print("✅ Pas d'exception lors de l'appel open_camera (format dict)")
        except Exception as e:
            # Une erreur est attendue car pas de vraie caméra, mais pas l'erreur de signature
            if "__init__() takes 2 positional arguments but 3 were given" in str(e):
                print("❌ Erreur de signature toujours présente")
                return False
            else:
                print("✅ Erreur différente (attendu car pas de vraie caméra)")
        
        # Format 2: String
        print("Test format string...")
        try:
            result = manager.open_camera("014122072611", "test_realsense_str")
            print("✅ Pas d'exception lors de l'appel open_camera (format string)")
        except Exception as e:
            if "__init__() takes 2 positional arguments but 3 were given" in str(e):
                print("❌ Erreur de signature toujours présente")
                return False
            else:
                print("✅ Erreur différente (attendu car pas de vraie caméra)")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur test formats: {e}")
        return False

def main():
    """Test principal"""
    print("🚀 TEST RAPIDE DES CORRECTIONS CAMERA")
    print("=" * 45)
    
    tests = [
        ("Création CameraManager", test_camera_manager_creation),
        ("Formats de données", test_camera_open_formats)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
        
        if result:
            print(f"✅ {test_name}: PASSÉ\n")
        else:
            print(f"❌ {test_name}: ÉCHOUÉ\n")
    
    # Résumé
    print("=" * 45)
    print("📊 RÉSULTATS:")
    
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n📈 Score: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 CORRECTIONS VALIDÉES!")
        print("💡 Vous pouvez maintenant tester l'ouverture réelle de caméra")
    else:
        print("\n⚠️ Des corrections supplémentaires sont nécessaires")

if __name__ == '__main__':
    main()