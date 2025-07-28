#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/tests/validate_configuration.py
Script de validation de la suppression des valeurs statiques - Version 1.0
Modification: Vérification que toutes les valeurs sont configurables via JSON
"""

import sys
import os
import re
import json
from pathlib import Path

# Ajout du chemin parent pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

class ConfigurationValidator:
    """Validateur de configuration pour s'assurer qu'aucune valeur n'est statique"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.issues_found = []
        
        # Patterns à détecter (valeurs potentiellement statiques)
        self.static_patterns = {
            'hardcoded_sizes': r'(setMinimumSize|setMaximumSize|resize)\s*\(\s*\d+\s*,\s*\d+\s*\)',
            'hardcoded_colors': r'["\']#[0-9a-fA-F]{6}["\']',
            'hardcoded_numbers': r'(?<!\.get\()["\']?\b\d{2,4}\b["\']?(?!\s*[,\)])',
            'hardcoded_strings': r'["\'][^"\']*(?:Erreur|Error|Success|Info)[^"\']*["\']',
            'magic_numbers': r'(?<!=\s)\b(?:50|100|200|255|300|400|500|600|800|1000|1200|1400|1600)\b(?!\s*[,\)\.])',
        }
        
        # Exceptions (valeurs légitimes)
        self.exceptions = {
            'legitimate_numbers': [0, 1, 2, 3, 4, 5, -1, 16, 255],  # Valeurs systémiques
            'legitimate_patterns': [
                r'time\.sleep\(\d+\)',  # Délais temporels
                r'range\(\d+\)',       # Boucles
                r'\.format\(',         # Formatage
                r'f["\'].*{.*}.*["\']' # f-strings
            ]
        }
    
    def validate_project(self):
        """Valide l'ensemble du projet"""
        print("🔍 Validation Configuration - Suppression Valeurs Statiques")
        print("=" * 65)
        
        # Fichiers à analyser
        files_to_check = [
            'ui/camera_display_widget.py',
            'ui/camera_tab.py',
            'ui/main_window.py',
            'core/camera_manager.py',
            'hardware/usb3_camera_driver.py',
            'hardware/realsense_driver.py'
        ]
        
        total_issues = 0
        
        for file_path in files_to_check:
            full_path = self.project_root / file_path
            if full_path.exists():
                print(f"\n📁 Analyse: {file_path}")
                issues = self.analyze_file(full_path)
                total_issues += len(issues)
                
                if issues:
                    print(f"   ⚠️ {len(issues)} problème(s) détecté(s)")
                    for issue in issues:
                        print(f"     - Ligne {issue['line']}: {issue['type']} - {issue['content'][:50]}...")
                else:
                    print("   ✅ Aucun problème détecté")
            else:
                print(f"   ❌ Fichier non trouvé: {file_path}")
        
        # Validation des fichiers de configuration
        self.validate_config_files()
        
        # Résumé final
        self.print_summary(total_issues)
        
        return total_issues == 0
    
    def analyze_file(self, file_path: Path):
        """Analyse un fichier pour détecter les valeurs statiques"""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line_issues = self.analyze_line(line, line_num)
                issues.extend(line_issues)
        
        except Exception as e:
            print(f"   ❌ Erreur lecture fichier: {e}")
        
        return issues
    
    def analyze_line(self, line: str, line_num: int):
        """Analyse une ligne pour détecter les problèmes"""
        issues = []
        
        # Ignorer les commentaires et les lignes avec .get(
        if line.strip().startswith('#') or '.get(' in line or 'config.get(' in line:
            return issues
        
        for pattern_name, pattern in self.static_patterns.items():
            matches = re.finditer(pattern, line)
            for match in matches:
                # Vérifier si c'est une exception légitime
                if not self.is_legitimate(line, match.group()):
                    issues.append({
                        'line': line_num,
                        'type': pattern_name,
                        'content': line.strip(),
                        'match': match.group()
                    })
        
        return issues
    
    def is_legitimate(self, line: str, match: str):
        """Vérifie si une correspondance est légitime"""
        # Vérifier les patterns légitimes
        for pattern in self.exceptions['legitimate_patterns']:
            if re.search(pattern, line):
                return True
        
        # Vérifier les nombres légitimes
        try:
            if match.isdigit() and int(match) in self.exceptions['legitimate_numbers']:
                return True
        except ValueError:
            pass
        
        return False
    
    def validate_config_files(self):
        """Valide la présence et la structure des fichiers de configuration"""
        print(f"\n📋 Validation des fichiers de configuration")
        
        config_files = [
            'config/ui_config.json',
            'config/camera_config.json',
            'config/tracking_config.json',
            'config/robot_config.json'
        ]
        
        for config_file in config_files:
            config_path = self.project_root / config_file
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    
                    if self.validate_config_structure(config_data, config_file):
                        print(f"   ✅ {config_file}: Structure valide")
                    else:
                        print(f"   ⚠️ {config_file}: Structure incomplète")
                        
                except json.JSONDecodeError as e:
                    print(f"   ❌ {config_file}: JSON invalide - {e}")
            else:
                print(f"   ❌ {config_file}: Fichier manquant")
    
    def validate_config_structure(self, config_data: dict, filename: str):
        """Valide la structure d'un fichier de configuration"""
        required_sections = {
            'ui_config.json': ['window', 'camera_display', 'camera_tab'],
            'camera_config.json': ['realsense', 'usb3_camera', 'general'],
            'tracking_config.json': ['aruco', 'precision'],
            'robot_config.json': ['communication']
        }
        
        file_basename = Path(filename).name
        if file_basename in required_sections:
            required = required_sections[file_basename]
            missing = [section for section in required if section not in config_data]
            
            if missing:
                print(f"     ⚠️ Sections manquantes: {', '.join(missing)}")
                return False
        
        return True
    
    def print_summary(self, total_issues: int):
        """Affiche le résumé de la validation"""
        print(f"\n" + "=" * 65)
        print("📊 RÉSUMÉ DE LA VALIDATION")
        print("=" * 65)
        
        if total_issues == 0:
            print("🎉 EXCELLENT ! Aucune valeur statique détectée")
            print("✅ Toutes les valeurs sont configurables via JSON")
            print("🚀 Le code respecte les principes de configuration externalisée")
        else:
            print(f"⚠️ {total_issues} problème(s) détecté(s)")
            print("🔧 Actions recommandées:")
            print("   1. Remplacer les valeurs statiques par config.get()")
            print("   2. Ajouter les nouvelles clés dans les fichiers JSON")
            print("   3. Tester que les valeurs par défaut fonctionnent")
            print("   4. Relancer cette validation")
        
        print(f"\n💡 BONNES PRATIQUES :")
        print("   ✅ Utilisez: config.get('section', 'key', default_value)")
        print("   ✅ Externalisez: tailles, couleurs, messages, délais")
        print("   ✅ Organisez: groupez par fonctionnalité dans JSON")
        print("   ❌ Évitez: valeurs hardcodées directement dans le code")
    
    def generate_config_template(self):
        """Génère un template de configuration pour les valeurs manquantes"""
        print(f"\n🔧 Génération template configuration...")
        
        template = {
            "ui": {
                "camera_display": {
                    "single_view": {
                        "min_width": 320,
                        "min_height": 240,
                        "max_width": 800,
                        "max_height": 600,
                        "default_zoom": 1.0
                    },
                    "dual_view": {
                        "min_width": 240,
                        "min_height": 180,
                        "max_width": 600,
                        "max_height": 450,
                        "spacing": 10
                    },
                    "colors": {
                        "rgb_border": "#007acc",
                        "depth_border": "#ff6600",
                        "default_border": "#ccc"
                    }
                }
            }
        }
        
        template_path = self.project_root / "config" / "template_generated.json"
        
        try:
            with open(template_path, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Template généré: {template_path}")
            print("💡 Fusionnez ce template avec vos fichiers de configuration existants")
            
        except Exception as e:
            print(f"❌ Erreur génération template: {e}")

def main():
    """Point d'entrée principal"""
    print("🎯 Robot Tracker - Validation Configuration")
    print("Vérification suppression valeurs statiques")
    print()
    
    validator = ConfigurationValidator()
    
    # Validation principale
    success = validator.validate_project()
    
    # Génération template si nécessaire
    if not success:
        response = input("\nGénérer un template de configuration ? (o/N): ")
        if response.lower() in ['o', 'oui', 'y', 'yes']:
            validator.generate_config_template()
    
    print(f"\n🎯 RÉSULTAT FINAL:")
    if success:
        print("✅ VALIDATION RÉUSSIE - Code prêt pour production")
        print("🚀 Toutes les valeurs sont externalisées en JSON")
        return 0
    else:
        print("❌ VALIDATION ÉCHOUÉE - Corrections nécessaires")
        print("🔧 Appliquez les recommandations ci-dessus")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        print(f"\n👋 Validation terminée (code: {exit_code})")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Validation interrompue par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur générale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)