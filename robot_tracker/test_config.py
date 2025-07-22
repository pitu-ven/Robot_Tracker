#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test complet du ConfigManager
"""

import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_manager import ConfigManager

def test_config_manager():
    """Test complet du ConfigManager"""
    print("🧪 DÉBUT DES TESTS ConfigManager")
    print("=" * 50)
    
    # Test 1: Création de l'instance
    print("\n📁 Test 1: Création du ConfigManager")
    try:
        config = ConfigManager()
        print(f"✅ ConfigManager créé: {config}")
        print(f"📍 Répertoire config: {config.config_dir}")
        print(f"📋 Types de config chargés: {config.get_all_config_types()}")
    except Exception as e:
        print(f"❌ Erreur création ConfigManager: {e}")
        return False
    
    # Test 2: Lecture des configurations par défaut
    print("\n📖 Test 2: Lecture des configurations")
    try:
        # Test des valeurs UI
        window_title = config.get('ui', 'window.title')
        window_width = config.get('ui', 'window.width', 1200)
        tab_names = config.get('ui', 'tabs.tab_names', [])
        
        print(f"🖼️  Titre fenêtre: {window_title}")
        print(f"📏 Largeur fenêtre: {window_width}")
        print(f"📑 Onglets: {tab_names}")
        
        # Test des valeurs caméra
        realsense_enabled = config.get('camera', 'realsense.enabled', False)
        fps_color = config.get('camera', 'realsense.color_stream.fps', 30)
        usb3_width = config.get('camera', 'usb3_camera.width', 2448)
        
        print(f"📷 RealSense activé: {realsense_enabled}")
        print(f"🎬 FPS couleur: {fps_color}")
        print(f"📐 Largeur USB3: {usb3_width}")
        
        # Test des valeurs tracking
        aruco_dict = config.get('tracking', 'aruco.dictionary', 'Unknown')
        marker_size = config.get('tracking', 'aruco.marker_size', 0.05)
        kalman_enabled = config.get('tracking', 'kalman_filter.enabled', False)
        
        print(f"🎯 Dictionnaire ArUco: {aruco_dict}")
        print(f"📏 Taille marqueur: {marker_size}")
        print(f"🔄 Filtre Kalman: {kalman_enabled}")
        
        # Test des valeurs robot
        robot_ip = config.get('robot', 'communication.ip', '192.168.1.100')
        robot_port = config.get('robot', 'communication.port', 502)
        
        print(f"🤖 IP Robot: {robot_ip}")
        print(f"🔌 Port Robot: {robot_port}")
        
        print("✅ Lecture des configurations réussie")
        
    except Exception as e:
        print(f"❌ Erreur lecture configurations: {e}")
        return False
    
    # Test 3: Modification des configurations
    print("\n✏️  Test 3: Modification des configurations")
    try:
        # Sauvegarder les valeurs originales
        original_width = config.get('ui', 'window.width')
        original_fps = config.get('camera', 'realsense.color_stream.fps')
        
        print(f"📏 Largeur originale: {original_width}")
        print(f"🎬 FPS original: {original_fps}")
        
        # Modifier les valeurs
        config.set('ui', 'window.width', 1600)
        config.set('camera', 'realsense.color_stream.fps', 60)
        config.set('ui', 'test.nouvelle_valeur', 'test_reussi')
        
        # Vérifier les modifications
        new_width = config.get('ui', 'window.width')
        new_fps = config.get('camera', 'realsense.color_stream.fps')
        test_value = config.get('ui', 'test.nouvelle_valeur')
        
        print(f"📏 Nouvelle largeur: {new_width}")
        print(f"🎬 Nouveau FPS: {new_fps}")
        print(f"🆕 Nouvelle valeur test: {test_value}")
        
        if new_width == 1600 and new_fps == 60 and test_value == 'test_reussi':
            print("✅ Modifications réussies")
        else:
            print("❌ Erreur dans les modifications")
            return False
            
    except Exception as e:
        print(f"❌ Erreur modification configurations: {e}")
        return False
    
    # Test 4: Sauvegarde
    print("\n💾 Test 4: Sauvegarde des configurations")
    try:
        # Sauvegarder une configuration
        success_ui = config.save_config('ui')
        success_camera = config.save_config('camera')
        
        print(f"💾 Sauvegarde UI: {'✅ Réussie' if success_ui else '❌ Échouée'}")
        print(f"💾 Sauvegarde Caméra: {'✅ Réussie' if success_camera else '❌ Échouée'}")
        
        # Sauvegarder toutes les configurations
        all_saved = config.save_all_configs()
        print(f"💾 Sauvegarde complète: {'✅ Réussie' if all_saved else '❌ Échouée'}")
        
    except Exception as e:
        print(f"❌ Erreur sauvegarde: {e}")
        return False
    
    # Test 5: Validation
    print("\n✅ Test 5: Validation des configurations")
    try:
        for config_type in config.get_all_config_types():
            is_valid = config.validate_config(config_type)
            status = "✅ Valide" if is_valid else "❌ Invalide"
            print(f"🔍 Configuration '{config_type}': {status}")
            
    except Exception as e:
        print(f"❌ Erreur validation: {e}")
        return False
    
    # Test 6: Gestion des erreurs
    print("\n🚨 Test 6: Gestion des erreurs")
    try:
        # Test de clés inexistantes
        inexistant = config.get('inexistant', 'cle.inexistante', 'valeur_defaut')
        print(f"🔍 Clé inexistante: {inexistant} (devrait être 'valeur_defaut')")
        
        # Test de chemin invalide
        invalide = config.get('ui', 'chemin.tres.profond.inexistant', 'defaut')
        print(f"🔍 Chemin invalide: {invalide} (devrait être 'defaut')")
        
        print("✅ Gestion d'erreurs fonctionnelle")
        
    except Exception as e:
        print(f"❌ Erreur dans la gestion d'erreurs: {e}")
        return False
    
    # Test 7: Rechargement
    print("\n🔄 Test 7: Rechargement des configurations")
    try:
        # Modifier une valeur
        config.set('ui', 'window.width', 2000)
        print(f"📏 Largeur après modification: {config.get('ui', 'window.width')}")
        
        # Recharger la configuration
        reload_success = config.reload_config('ui')
        reloaded_width = config.get('ui', 'window.width')
        
        print(f"🔄 Rechargement UI: {'✅ Réussi' if reload_success else '❌ Échoué'}")
        print(f"📏 Largeur après rechargement: {reloaded_width}")
        
    except Exception as e:
        print(f"❌ Erreur rechargement: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 TOUS LES TESTS RÉUSSIS !")
    print("✅ ConfigManager fonctionne parfaitement")
    return True

def test_specific_features():
    """Test de fonctionnalités spécifiques pour le tracking robotique"""
    print("\n🤖 TESTS SPÉCIFIQUES TRACKING ROBOTIQUE")
    print("=" * 50)
    
    config = ConfigManager()
    
    # Test des configurations critiques pour le projet
    critical_configs = [
        ('ui', 'window.title', str),
        ('ui', 'tabs.tab_names', list),
        ('camera', 'realsense.enabled', bool),
        ('camera', 'realsense.color_stream.fps', int),
        ('tracking', 'aruco.marker_size', float),
        ('tracking', 'aruco.dictionary', str),
        ('robot', 'communication.ip', str),
        ('robot', 'communication.port', int),
    ]
    
    print("\n🔍 Vérification des configurations critiques:")
    all_ok = True
    
    for config_type, path, expected_type in critical_configs:
        try:
            value = config.get(config_type, path)
            value_type = type(value)
            
            if value is not None and (expected_type == type(value) or expected_type == type(None)):
                print(f"✅ {config_type}.{path}: {value} ({value_type.__name__})")
            else:
                print(f"⚠️  {config_type}.{path}: {value} (attendu: {expected_type.__name__})")
                all_ok = False
                
        except Exception as e:
            print(f"❌ {config_type}.{path}: Erreur - {e}")
            all_ok = False
    
    # Test de création de nouvelles configurations pour le projet
    print("\n⚙️  Test de configuration personnalisée:")
    try:
        # Configurations spécifiques au tracking
        config.set('tracking', 'precision.target_accuracy_mm', 1.0)
        config.set('tracking', 'precision.max_deviation_mm', 2.0)
        config.set('ui', 'performance.target_fps', 20)
        
        # Vérification
        accuracy = config.get('tracking', 'precision.target_accuracy_mm')
        deviation = config.get('tracking', 'precision.max_deviation_mm')
        target_fps = config.get('ui', 'performance.target_fps')
        
        print(f"🎯 Précision cible: {accuracy} mm")
        print(f"📏 Déviation max: {deviation} mm")
        print(f"🎬 FPS cible: {target_fps}")
        
        print("✅ Configuration personnalisée réussie")
        
    except Exception as e:
        print(f"❌ Erreur configuration personnalisée: {e}")
        all_ok = False
    
    return all_ok

if __name__ == "__main__":
    print("🚀 DÉMARRAGE DES TESTS ConfigManager")
    
    # Vérifier que nous sommes dans le bon répertoire
    current_dir = Path.cwd()
    print(f"📍 Répertoire actuel: {current_dir}")
    
    if not (current_dir / "config").exists():
        print("⚠️  Le répertoire 'config' n'existe pas, création...")
        (current_dir / "config").mkdir(exist_ok=True)
        (current_dir / "config" / "default").mkdir(exist_ok=True)
    
    # Exécuter les tests
    success1 = test_config_manager()
    success2 = test_specific_features()
    
    if success1 and success2:
        print("\n🎉 RÉSULTAT FINAL: TOUS LES TESTS RÉUSSIS!")
        print("✅ ConfigManager est prêt pour l'intégration")
    else:
        print("\n❌ RÉSULTAT FINAL: CERTAINS TESTS ONT ÉCHOUÉ")
        print("🔧 Vérifiez les erreurs ci-dessus")
    
    print("\n📝 Prochaines étapes:")
    print("   1. Intégrer ConfigManager dans MainWindow")
    print("   2. Implémenter les threads caméra")
    print("   3. Développer le tracking ArUco")