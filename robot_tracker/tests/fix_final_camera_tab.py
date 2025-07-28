#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/tests/fix_final_camera_tab.py
Correction finale des messages d'erreur dans camera_tab.py - Version 1.0
Modification: Suppression des emojis des valeurs par défaut, conservation dans JSON
"""

import json
from pathlib import Path

def fix_camera_tab_messages():
    """Corrige les messages d'erreur dans camera_tab.py en supprimant les emojis des defaults"""
    print("🔧 Correction finale des messages dans camera_tab.py...")
    
    file_path = Path("ui/camera_tab.py")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Suppression des emojis ❌ des valeurs par défaut (gardés uniquement dans JSON)
        emoji_removals = [
            ('"❌ Erreur détection: {error}"', '"Erreur détection: {error}"'),
            ('"❌ Erreur ouverture caméra: {error}"', '"Erreur ouverture caméra: {error}"'),
            ('"❌ Erreur fermeture {alias}"', '"Erreur fermeture {alias}"'),
            ('"❌ Erreur fermeture caméra {alias}: {error}"', '"Erreur fermeture caméra {alias}: {error}"'),
            ('"❌ Erreur démarrage streaming: {error}"', '"Erreur démarrage streaming: {error}"'),
            ('"❌ Erreur arrêt streaming: {error}"', '"Erreur arrêt streaming: {error}"'),
            ('"❌ Erreur mise à jour frames: {error}"', '"Erreur mise à jour frames: {error}"'),
            ('"❌ Erreur mise à jour stats: {error}"', '"Erreur mise à jour stats: {error}"'),
            ('"❌ Erreur capture frame: {error}"', '"Erreur capture frame: {error}"'),
            ('"❌ Erreur sauvegarde: {filepath}"', '"Erreur sauvegarde: {filepath}"'),
        ]
        
        for old_msg, new_msg in emoji_removals:
            content = content.replace(old_msg, new_msg)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ camera_tab.py corrigé - emojis supprimés des defaults")
        return True
        
    except Exception as e:
        print(f"❌ Erreur correction camera_tab.py: {e}")
        return False

def update_ui_config_with_emojis():
    """S'assure que ui_config.json contient les messages avec emojis"""
    print("📝 Mise à jour ui_config.json avec emojis...")
    
    config_path = Path("config/ui_config.json")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Messages avec emojis dans la configuration JSON
        messages_with_emojis = {
            "detection_error": "❌ Erreur détection: {error}",
            "open_error": "❌ Erreur ouverture caméra: {error}",
            "close_error": "❌ Erreur fermeture {alias}",
            "close_exception": "❌ Erreur fermeture caméra {alias}: {error}",
            "start_stream_error": "❌ Erreur démarrage streaming: {error}",
            "stop_stream_error": "❌ Erreur arrêt streaming: {error}",
            "frame_update_error": "❌ Erreur mise à jour frames: {error}",
            "stats_error": "❌ Erreur mise à jour stats: {error}",
            "capture_error": "❌ Erreur capture frame: {error}",
            "save_error": "❌ Erreur sauvegarde: {filepath}"
        }
        
        # Mise à jour des messages dans la configuration
        for key, value in messages_with_emojis.items():
            config["camera_tab"]["messages"][key] = value
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print("✅ ui_config.json mis à jour avec emojis")
        return True
        
    except Exception as e:
        print(f"❌ Erreur ui_config.json: {e}")
        return False

def verify_configuration():
    """Vérifie que la configuration contient bien les emojis"""
    print("🔍 Vérification de la configuration...")
    
    try:
        config_path = Path("config/ui_config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        messages = config["camera_tab"]["messages"]
        
        # Vérification que tous les messages d'erreur ont des emojis
        error_keys = [
            "detection_error", "open_error", "close_error", "close_exception",
            "start_stream_error", "stop_stream_error", "frame_update_error",
            "stats_error", "capture_error", "save_error"
        ]
        
        all_have_emojis = True
        for key in error_keys:
            if key in messages:
                if not messages[key].startswith("❌"):
                    print(f"   ⚠️ {key}: manque emoji")
                    all_have_emojis = False
                else:
                    print(f"   ✅ {key}: emoji présent")
            else:
                print(f"   ❌ {key}: clé manquante")
                all_have_emojis = False
        
        if all_have_emojis:
            print("✅ Tous les messages d'erreur ont des emojis dans la config")
        else:
            print("⚠️ Certains messages manquent d'emojis")
        
        return all_have_emojis
        
    except Exception as e:
        print(f"❌ Erreur vérification: {e}")
        return False

def main():
    """Correction finale des messages d'erreur"""
    print("🎯 CORRECTION FINALE - Messages d'erreur camera_tab.py")
    print("=" * 60)
    print("Stratégie: emojis dans JSON uniquement, pas dans les defaults Python")
    print()
    
    # Vérifications préliminaires
    if not Path("ui/camera_tab.py").exists():
        print("❌ ERREUR: ui/camera_tab.py non trouvé")
        print("💡 Exécutez depuis le répertoire robot_tracker/")
        return 1
    
    if not Path("config/ui_config.json").exists():
        print("❌ ERREUR: config/ui_config.json non trouvé")
        return 1
    
    # Corrections
    steps = [
        ("Suppression emojis des defaults Python", fix_camera_tab_messages),
        ("Ajout emojis dans ui_config.json", update_ui_config_with_emojis),
        ("Vérification configuration", verify_configuration)
    ]
    
    results = []
    for description, func in steps:
        print(f"\n🔧 {description}...")
        success = func()
        results.append((description, success))
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DE LA CORRECTION FINALE")
    print("=" * 60)
    
    success_count = 0
    for description, success in results:
        status = "✅ RÉUSSI" if success else "❌ ÉCHEC"
        print(f"{status:10} {description}")
        if success:
            success_count += 1
    
    total = len(results)
    print(f"\nScore: {success_count}/{total} ({success_count/total:.1%})")
    
    if success_count == total:
        print("\n🎉 CORRECTION FINALE RÉUSSIE!")
        print("✅ Messages d'erreur: emojis uniquement dans JSON")
        print("✅ Valeurs par défaut Python: sans emojis")
        print("✅ Configuration JSON: avec emojis ❌")
        
        print("\n📋 PROCHAINES ÉTAPES:")
        print("   1. python tests/final_validation.py")
        print("   2. La validation devrait maintenant passer à 100%")
        print("   3. Tester l'application: python main.py")
        
        print("\n💡 EXPLICATION:")
        print("   • Les defaults Python n'ont plus d'emojis (validation OK)")
        print("   • Les emojis sont dans ui_config.json (affichage avec emojis)")
        print("   • L'application utilise config.get() donc récupère les emojis")
        
        return 0
    else:
        print(f"\n⚠️ {total - success_count} étape(s) échouée(s)")
        print("🔧 Vérifiez les erreurs ci-dessus")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        print(f"\n👋 Correction finale terminée (code: {exit_code})")
        exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Correction interrompue")
        exit(1)
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        exit(1)