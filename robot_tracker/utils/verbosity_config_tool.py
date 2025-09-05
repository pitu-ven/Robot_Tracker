# robot_tracker/utils/verbosity_config_tool.py
# Version 1.0 - Outil de configuration verbosité
# Modification: Script utilitaire pour changer la verbosité des logs

import sys
import argparse
from pathlib import Path

# Ajout du chemin vers le module principal
sys.path.append(str(Path(__file__).parent.parent))

from core.config_manager import ConfigManager
from utils.logging_utils import VerbosityManager


def display_current_config(config: ConfigManager):
    """Affiche la configuration actuelle de verbosité"""
    print("\n📋 Configuration actuelle:")
    print("-" * 40)
    
    current_verbosity = config.get_logging_verbosity()
    available_levels = config.get_available_verbosity_levels()
    
    print(f"🔧 Verbosité actuelle: {current_verbosity}")
    print(f"📝 Description: {config.get_verbosity_description(current_verbosity)}")
    print(f"📋 Niveaux disponibles: {', '.join(available_levels)}")
    
    # Affichage des descriptions de tous les niveaux
    print("\n📚 Descriptions des niveaux:")
    for level in available_levels:
        description = config.get_verbosity_description(level)
        marker = "👉" if level == current_verbosity else "  "
        print(f"{marker} {level:8}: {description}")


def change_verbosity(config: ConfigManager, new_level: str) -> bool:
    """Change le niveau de verbosité"""
    
    # Validation du niveau
    available_levels = config.get_available_verbosity_levels()
    if new_level not in available_levels:
        print(f"❌ Niveau '{new_level}' invalide!")
        print(f"📋 Niveaux disponibles: {', '.join(available_levels)}")
        return False
    
    # Changement de la verbosité
    success = config.set_logging_verbosity(new_level)
    if not success:
        print(f"❌ Échec du changement vers '{new_level}'")
        return False
    
    # Sauvegarde de la configuration
    save_success = config.save_config('ui')
    if not save_success:
        print("⚠️  Configuration changée mais pas sauvegardée")
    
    print(f"✅ Verbosité changée vers: {new_level}")
    if save_success:
        print("💾 Configuration sauvegardée")
    
    return True


def interactive_mode(config: ConfigManager):
    """Mode interactif pour changer la verbosité"""
    print("\n🔄 Mode interactif de configuration verbosité")
    print("=" * 50)
    
    while True:
        display_current_config(config)
        
        print("\n🎯 Actions disponibles:")
        print("  1. Changer la verbosité")
        print("  2. Afficher la configuration actuelle")
        print("  3. Tester les messages de logging") 
        print("  0. Quitter")
        
        try:
            choice = input("\n👉 Votre choix (0-3): ").strip()
            
            if choice == "0":
                print("👋 Au revoir!")
                break
                
            elif choice == "1":
                available_levels = config.get_available_verbosity_levels()
                print(f"\n📋 Niveaux disponibles: {', '.join(available_levels)}")
                new_level = input("👉 Nouveau niveau: ").strip()
                
                if new_level:
                    change_verbosity(config, new_level)
                
            elif choice == "2":
                continue  # La configuration s'affiche déjà en haut de boucle
                
            elif choice == "3":
                test_logging_messages()
                
            else:
                print("⚠️  Choix invalide, veuillez entrer 0, 1, 2 ou 3")
                
        except KeyboardInterrupt:
            print("\n👋 Arrêt demandé, au revoir!")
            break
        except Exception as e:
            print(f"❌ Erreur: {e}")


def test_logging_messages():
    """Teste les messages de logging avec le niveau actuel"""
    import logging
    
    print("\n🧪 Test des messages de logging:")
    print("-" * 40)
    
    logger = logging.getLogger("verbosity_test")
    
    logger.debug("🔍 Message DEBUG - Très détaillé pour le débogage")
    logger.info("ℹ️  Message INFO - Information générale")
    logger.warning("⚠️  Message WARNING - Avertissement")
    logger.error("❌ Message ERROR - Erreur")
    
    print("📝 Seuls les messages correspondant au niveau configuré sont affichés")


def main():
    """Point d'entrée principal de l'outil"""
    
    parser = argparse.ArgumentParser(
        description="🔧 Outil de configuration de verbosité pour Robot Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  python verbosity_config_tool.py                    # Mode interactif
  python verbosity_config_tool.py --show             # Afficher config actuelle
  python verbosity_config_tool.py --set Debug        # Définir niveau Debug
  python verbosity_config_tool.py --set Faible       # Définir niveau Faible
  python verbosity_config_tool.py --test             # Tester messages logging
        """
    )
    
    parser.add_argument(
        '--set', 
        metavar='NIVEAU',
        help='Définir le niveau de verbosité (Faible, Moyenne, Debug)'
    )
    parser.add_argument(
        '--show', 
        action='store_true',
        help='Afficher la configuration actuelle'
    )
    parser.add_argument(
        '--test',
        action='store_true', 
        help='Tester les messages de logging'
    )
    parser.add_argument(
        '--config-dir',
        metavar='DOSSIER',
        help='Dossier de configuration personnalisé'
    )
    
    args = parser.parse_args()
    
    print("🔧 Robot Tracker - Outil de Configuration Verbosité")
    print("=" * 60)
    
    try:
        # Chargement de la configuration
        config_dir = Path(args.config_dir) if args.config_dir else None
        config = ConfigManager(config_dir)
        
        # Mode ligne de commande
        if args.show:
            display_current_config(config)
            
        elif args.set:
            change_verbosity(config, args.set)
            display_current_config(config)
            
        elif args.test:
            # Configuration du logging pour le test
            from utils.logging_utils import setup_application_logging
            setup_application_logging(config)
            test_logging_messages()
            
        else:
            # Mode interactif par défaut
            interactive_mode(config)
            
    except FileNotFoundError as e:
        print(f"❌ Fichier de configuration non trouvé: {e}")
        print("💡 Assurez-vous d'être dans le dossier robot_tracker")
        return 1
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)