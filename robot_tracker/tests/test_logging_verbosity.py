# tests/test_logging_verbosity.py
# Version 1.0 - Test système verbosité logging
# Modification: Test des différents niveaux de verbosité

import sys
import logging
import tempfile
import json
from pathlib import Path

# Ajout du chemin vers le module principal
sys.path.append(str(Path(__file__).parent.parent))

from core.config_manager import ConfigManager
from utils.logging_utils import VerbosityManager, setup_application_logging


def create_test_config(verbosity: str = "Moyenne") -> Path:
    """Crée une configuration de test temporaire"""
    config_data = {
        "logging": {
            "console_verbosity": verbosity,
            "available_levels": ["Faible", "Moyenne", "Debug"],
            "descriptions": {
                "Faible": "Erreurs et avertissements uniquement",
                "Moyenne": "Informations importantes + erreurs/avertissements", 
                "Debug": "Tous les messages de débogage détaillés"
            }
        },
        "window": {
            "title": "Test App",
            "width": 800,
            "height": 600
        }
    }
    
    # Création d'un fichier temporaire
    temp_dir = Path(tempfile.mkdtemp())
    config_file = temp_dir / "ui_config.json"
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2)
    
    return temp_dir


def test_verbosity_levels():
    """Test des différents niveaux de verbosité"""
    
    print("🧪 Test des niveaux de verbosité")
    print("=" * 50)
    
    levels_to_test = ["Faible", "Moyenne", "Debug"]
    
    for level in levels_to_test:
        print(f"\n📋 Test niveau: {level}")
        print("-" * 30)
        
        # Création d'une config de test
        config_dir = create_test_config(level)
        
        try:
            # Chargement de la configuration
            config = ConfigManager(config_dir)
            
            # Vérification de la récupération du niveau
            retrieved_level = config.get_logging_verbosity()
            assert retrieved_level == level, f"Niveau attendu: {level}, obtenu: {retrieved_level}"
            
            # Configuration du logging
            VerbosityManager.setup_logging(level, config)
            
            # Test des différents types de messages
            logger = logging.getLogger("test_logger")
            
            print(f"✅ Configuration niveau '{level}' réussie")
            
            # Messages de test selon le niveau configuré
            logger.debug(f"🔍 Message DEBUG - Niveau {level}")
            logger.info(f"ℹ️  Message INFO - Niveau {level}")
            logger.warning(f"⚠️  Message WARNING - Niveau {level}")
            logger.error(f"❌ Message ERROR - Niveau {level}")
            
        except Exception as e:
            print(f"❌ Erreur test niveau {level}: {e}")
        
        finally:
            # Nettoyage
            import shutil
            shutil.rmtree(config_dir, ignore_errors=True)


def test_dynamic_verbosity_change():
    """Test du changement dynamique de verbosité"""
    
    print("\n🔄 Test changement dynamique de verbosité")
    print("=" * 50)
    
    # Configuration initiale
    config_dir = create_test_config("Moyenne")
    
    try:
        config = ConfigManager(config_dir)
        logger = logging.getLogger("dynamic_test")
        
        # Test initial
        setup_application_logging(config)
        logger.info("📊 Configuration initiale: Moyenne")
        
        # Changement vers Debug
        success = VerbosityManager.change_verbosity("Debug", config)
        assert success, "Changement vers Debug échoué"
        logger.debug("🔍 Maintenant en mode Debug")
        
        # Changement vers Faible
        success = VerbosityManager.change_verbosity("Faible", config)
        assert success, "Changement vers Faible échoué"
        logger.warning("⚠️  Maintenant en mode Faible")
        logger.info("ℹ️  Ce message INFO ne devrait pas s'afficher en mode Faible")
        
        print("✅ Test changement dynamique réussi")
        
    except Exception as e:
        print(f"❌ Erreur test changement dynamique: {e}")
    
    finally:
        import shutil
        shutil.rmtree(config_dir, ignore_errors=True)


def test_config_manager_logging_methods():
    """Test des méthodes spécifiques au logging du ConfigManager"""
    
    print("\n⚙️  Test méthodes ConfigManager logging")
    print("=" * 50)
    
    config_dir = create_test_config("Debug")
    
    try:
        config = ConfigManager(config_dir)
        
        # Test récupération verbosité
        verbosity = config.get_logging_verbosity()
        assert verbosity == "Debug", f"Verbosité attendue: Debug, obtenue: {verbosity}"
        print(f"✅ get_logging_verbosity(): {verbosity}")
        
        # Test niveaux disponibles
        levels = config.get_available_verbosity_levels()
        expected_levels = ["Faible", "Moyenne", "Debug"]
        assert levels == expected_levels, f"Niveaux attendus: {expected_levels}, obtenus: {levels}"
        print(f"✅ get_available_verbosity_levels(): {levels}")
        
        # Test descriptions
        description = config.get_verbosity_description("Debug")
        assert description, "Description Debug vide"
        print(f"✅ get_verbosity_description('Debug'): {description}")
        
        # Test changement de verbosité
        success = config.set_logging_verbosity("Faible")
        assert success, "Changement verbosité échoué"
        new_verbosity = config.get_logging_verbosity()
        assert new_verbosity == "Faible", f"Nouvelle verbosité attendue: Faible, obtenue: {new_verbosity}"
        print(f"✅ set_logging_verbosity('Faible'): {new_verbosity}")
        
        # Test niveau invalide
        success = config.set_logging_verbosity("Inexistant")
        assert not success, "Changement vers niveau invalide devrait échouer"
        print("✅ Validation niveau invalide fonctionne")
        
        print("✅ Tous les tests ConfigManager réussis")
        
    except Exception as e:
        print(f"❌ Erreur test ConfigManager: {e}")
    
    finally:
        import shutil
        shutil.rmtree(config_dir, ignore_errors=True)


def main():
    """Point d'entrée principal des tests"""
    
    print("🧪 Tests du système de verbosité logging")
    print("=" * 70)
    
    try:
        # Tests individuels
        test_verbosity_levels()
        test_dynamic_verbosity_change()
        test_config_manager_logging_methods()
        
        print("\n" + "=" * 70)
        print("🎉 TOUS LES TESTS RÉUSSIS!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ ERREUR GLOBALE: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)