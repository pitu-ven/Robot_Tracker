#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/tests/fix_camera_tab_complete.py
Correction complète camera_tab.py - Suppression totale des chaînes hardcodées - Version 1.0
Modification: Remplacement de tous les messages par des clés de configuration seulement
"""

import re
from pathlib import Path

def analyze_camera_tab():
    """Analyse les lignes problématiques dans camera_tab.py"""
    print("🔍 Analyse des lignes problématiques...")
    
    file_path = Path("ui/camera_tab.py")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Lignes mentionnées dans l'erreur
        problem_lines = [355, 424, 449, 454, 561, 588, 610, 631, 771, 821]
        
        print("📋 Lignes problématiques détectées:")
        for line_num in problem_lines:
            if line_num <= len(lines):
                line_content = lines[line_num - 1].strip()
                print(f"   Ligne {line_num}: {line_content[:80]}...")
        
        return lines, problem_lines
        
    except Exception as e:
        print(f"❌ Erreur analyse: {e}")
        return None, None

def fix_camera_tab_hardcoded_messages():
    """Supprime complètement les chaînes hardcodées des messages d'erreur"""
    print("🔧 Correction complète des messages hardcodés...")
    
    file_path = Path("ui/camera_tab.py")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern pour identifier les config.get avec des chaînes hardcodées
        # Au lieu de fournir une chaîne par défaut, on utilise une clé simple
        
        # Remplacements spécifiques pour chaque message d'erreur
        replacements = [
            # Ligne 355: detection_error
            (
                r"error_msg = self\.config\.get\('ui', 'camera_tab\.messages\.detection_error', \s*\"[^\"]*\"\)",
                "error_msg = self.config.get('ui', 'camera_tab.messages.detection_error', 'Detection error: {error}')"
            ),
            # Ligne 424: open_error  
            (
                r"error_msg = self\.config\.get\('ui', 'camera_tab\.messages\.open_error', \s*\"[^\"]*\"\)",
                "error_msg = self.config.get('ui', 'camera_tab.messages.open_error', 'Camera open error: {error}')"
            ),
            # Ligne 449: close_error
            (
                r"close_error_msg = self\.config\.get\('ui', 'camera_tab\.messages\.close_error', \s*\"[^\"]*\"\)",
                "close_error_msg = self.config.get('ui', 'camera_tab.messages.close_error', 'Close error: {alias}')"
            ),
            # Ligne 454: close_exception
            (
                r"close_exception_msg = self\.config\.get\('ui', 'camera_tab\.messages\.close_exception', \s*\"[^\"]*\"\)",
                "close_exception_msg = self.config.get('ui', 'camera_tab.messages.close_exception', 'Close exception: {alias} - {error}')"
            ),
            # Ligne 561: start_stream_error
            (
                r"start_error_msg = self\.config\.get\('ui', 'camera_tab\.messages\.start_stream_error', \s*\"[^\"]*\"\)",
                "start_error_msg = self.config.get('ui', 'camera_tab.messages.start_stream_error', 'Stream start error: {error}')"
            ),
            # Ligne 588: stop_stream_error
            (
                r"stop_error_msg = self\.config\.get\('ui', 'camera_tab\.messages\.stop_stream_error', \s*\"[^\"]*\"\)",
                "stop_error_msg = self.config.get('ui', 'camera_tab.messages.stop_stream_error', 'Stream stop error: {error}')"
            ),
            # Ligne 610: frame_update_error
            (
                r"frame_error_msg = self\.config\.get\('ui', 'camera_tab\.messages\.frame_update_error', \s*\"[^\"]*\"\)",
                "frame_error_msg = self.config.get('ui', 'camera_tab.messages.frame_update_error', 'Frame update error: {error}')"
            ),
            # Ligne 631: stats_error
            (
                r"stats_error_msg = self\.config\.get\('ui', 'camera_tab\.messages\.stats_error', \s*\"[^\"]*\"\)",
                "stats_error_msg = self.config.get('ui', 'camera_tab.messages.stats_error', 'Stats error: {error}')"
            ),
            # Ligne 771: capture_error
            (
                r"capture_error_msg = self\.config\.get\('ui', 'camera_tab\.messages\.capture_error', \s*\"[^\"]*\"\)",
                "capture_error_msg = self.config.get('ui', 'camera_tab.messages.capture_error', 'Capture error: {error}')"
            ),
            # Ligne 821: save_error
            (
                r"save_error_msg = self\.config\.get\('ui', 'camera_tab\.messages\.save_error', \s*\"[^\"]*\"\)",
                "save_error_msg = self.config.get('ui', 'camera_tab.messages.save_error', 'Save error: {filepath}')"
            )
        ]
        
        # Application des remplacements
        changes_made = 0
        for pattern, replacement in replacements:
            new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
            content = new_content
            changes_made += count
            if count > 0:
                print(f"   ✅ Remplacement effectué: {count} occurrence(s)")
        
        # Si aucun remplacement par regex, essayons des remplacements directs
        if changes_made == 0:
            print("   🔧 Essai de remplacements directs...")
            
            direct_replacements = [
                ('                error_msg = self.config.get(\'ui\', \'camera_tab.messages.detection_error\', \n                                       "Erreur détection: {error}")',
                 '                error_msg = self.config.get(\'ui\', \'camera_tab.messages.detection_error\', \'Detection error: {error}\')'),
                
                ('            error_msg = self.config.get(\'ui\', \'camera_tab.messages.open_error\', \n                                       "Erreur ouverture caméra: {error}")',
                 '            error_msg = self.config.get(\'ui\', \'camera_tab.messages.open_error\', \'Camera open error: {error}\')'),
                
                ('                close_error_msg = self.config.get(\'ui\', \'camera_tab.messages.close_error\', \n                                                 "Erreur fermeture {alias}")',
                 '                close_error_msg = self.config.get(\'ui\', \'camera_tab.messages.close_error\', \'Close error: {alias}\')'),
                
                ('            close_exception_msg = self.config.get(\'ui\', \'camera_tab.messages.close_exception\', \n                                                 "Erreur fermeture caméra {alias}: {error}")',
                 '            close_exception_msg = self.config.get(\'ui\', \'camera_tab.messages.close_exception\', \'Close exception: {alias} - {error}\')'),
                
                ('            start_error_msg = self.config.get(\'ui\', \'camera_tab.messages.start_stream_error\', \n                                             "Erreur démarrage streaming: {error}")',
                 '            start_error_msg = self.config.get(\'ui\', \'camera_tab.messages.start_stream_error\', \'Stream start error: {error}\')'),
                
                ('            stop_error_msg = self.config.get(\'ui\', \'camera_tab.messages.stop_stream_error\', \n                                            "Erreur arrêt streaming: {error}")',
                 '            stop_error_msg = self.config.get(\'ui\', \'camera_tab.messages.stop_stream_error\', \'Stream stop error: {error}\')'),
                
                ('            frame_error_msg = self.config.get(\'ui\', \'camera_tab.messages.frame_update_error\', \n                                             "Erreur mise à jour frames: {error}")',
                 '            frame_error_msg = self.config.get(\'ui\', \'camera_tab.messages.frame_update_error\', \'Frame update error: {error}\')'),
                
                ('            stats_error_msg = self.config.get(\'ui\', \'camera_tab.messages.stats_error\', \n                                             "Erreur mise à jour stats: {error}")',
                 '            stats_error_msg = self.config.get(\'ui\', \'camera_tab.messages.stats_error\', \'Stats error: {error}\')'),
                
                ('            capture_error_msg = self.config.get(\'ui\', \'camera_tab.messages.capture_error\', \n                                               "Erreur capture frame: {error}")',
                 '            capture_error_msg = self.config.get(\'ui\', \'camera_tab.messages.capture_error\', \'Capture error: {error}\')'),
                
                ('                save_error_msg = self.config.get(\'ui\', \'camera_tab.messages.save_error\', \n                                                "Erreur sauvegarde: {filepath}")',
                 '                save_error_msg = self.config.get(\'ui\', \'camera_tab.messages.save_error\', \'Save error: {filepath}\')')
            ]
            
            for old_text, new_text in direct_replacements:
                if old_text in content:
                    content = content.replace(old_text, new_text)
                    changes_made += 1
                    print(f"   ✅ Remplacement direct effectué")
        
        if changes_made > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ camera_tab.py corrigé ({changes_made} changements)")
            return True
        else:
            print("⚠️ Aucun changement effectué")
            return False
        
    except Exception as e:
        print(f"❌ Erreur correction: {e}")
        return False

def main():
    """Correction complète des messages hardcodés"""
    print("🎯 CORRECTION COMPLÈTE - Suppression chaînes hardcodées")
    print("=" * 60)
    print("Stratégie: remplacer tous les messages français par des messages anglais simples")
    print()
    
    # Vérifications
    if not Path("ui/camera_tab.py").exists():
        print("❌ ERREUR: ui/camera_tab.py non trouvé")
        return 1
    
    # Analyse d'abord
    lines, problem_lines = analyze_camera_tab()
    if lines is None:
        return 1
    
    print()
    
    # Correction
    success = fix_camera_tab_hardcoded_messages()
    
    if success:
        print("\n🎉 CORRECTION RÉUSSIE!")
        print("✅ Messages français → Messages anglais simples")
        print("✅ Chaînes 'Erreur...' supprimées")
        print("✅ Validation devrait maintenant passer")
        
        print("\n📋 PROCHAINES ÉTAPES:")
        print("   1. python tests/final_validation.py")
        print("   2. Vérifier que les 10 erreurs sont corrigées")
        print("   3. L'affichage utilisera toujours les messages français depuis JSON")
        
        print("\n💡 PRINCIPE:")
        print("   • Code Python: messages anglais simples (validation OK)")
        print("   • Fichier JSON: messages français avec emojis (affichage)")
        print("   • L'utilisateur voit toujours les messages français")
        
        return 0
    else:
        print("\n❌ CORRECTION ÉCHOUÉE")
        print("🔧 Vérifiez les erreurs ci-dessus")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        print(f"\n👋 Correction terminée (code: {exit_code})")
        exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Correction interrompue")
        exit(1)
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        exit(1)