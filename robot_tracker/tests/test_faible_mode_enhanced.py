# tests/test_faible_mode_enhanced.py
# Version 1.0 - Test du mode Faible amélioré
# Modification: Test de la suppression complète des logs externes

import sys
import logging
import tempfile
import json
from pathlib import Path

# Ajout du chemin vers le module principal
sys.path.append(str(Path(__file__).parent.parent))

from core.config_manager import ConfigManager
from utils.logging_utils import VerbosityManager


def create_test_config_faible() -> Path:
    """Crée une configuration de test en mode Faible"""
    config_data = {
        "logging": {
            "console_verbosity": "Faible",
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


def test_faible_mode_silence():
    """Test du mode Faible avec suppression complète"""
    
    print("🔇 Test mode Faible - Suppression complète des logs")
    print("=" * 60)
    
    config_dir = create_test_config_faible()
    
    try:
        print("📋 Avant configuration mode Faible:")
        print("   (vous devriez voir ce message)")
        
        # Chargement de la configuration
        config = ConfigManager(config_dir)
        
        # Configuration du logging en mode Faible
        VerbosityManager.setup_logging("Faible", config)
        
        print("\n📋 Après configuration mode Faible:")
        print("   (vous ne devriez voir QUE les erreurs ci-dessous)")
        
        # Test des différents types de messages
        logger = logging.getLogger("test_faible")
        
        logger.debug("🔍 Message DEBUG - NE DOIT PAS apparaître")
        logger.info("ℹ️  Message INFO - NE DOIT PAS apparaître") 
        logger.warning("⚠️  Message WARNING - NE DOIT PAS apparaître")
        logger.error("❌ Message ERROR - DOIT apparaître")
        
        # Test des modules système
        config_logger = logging.getLogger("core.config_manager")
        config_logger.info("Configuration test - NE DOIT PAS apparaître")
        config_logger.error("Erreur config test - DOIT apparaître")
        
        print("\n✅ Test mode Faible terminé")
        print("💡 Si vous voyez seulement les 2 messages ERROR ci-dessus, le test est réussi!")
        
    except Exception as e:
        print(f"❌ Erreur test mode Faible: {e}")
    
    finally:
        import shutil
        shutil.rmtree(config_dir, ignore_errors=True)


def test_opencv_suppression():
    """Test de la suppression des messages OpenCV"""
    
    print("\n🎥 Test suppression messages OpenCV")
    print("=" * 50)
    
    try:
        import cv2
        import os
        
        print("📋 Test avant suppression OpenCV:")
        
        # Configuration du mode Faible
        config_dir = create_test_config_faible()
        config = ConfigManager(config_dir)
        VerbosityManager.setup_logging("Faible", config)
        
        print("📋 Test après suppression OpenCV:")
        print("   (Les messages OpenCV suivants ne devraient PAS apparaître)")
        
        # Tentative d'ouverture d'une caméra inexistante pour générer des erreurs
        cap = cv2.VideoCapture(999)  # Index inexistant
        
        if not cap.isOpened():
            print("✅ Caméra inexistante (comportement attendu)")
        
        cap.release()
        
        print("✅ Test OpenCV terminé")
        
        # Nettoyage
        import shutil
        shutil.rmtree(config_dir, ignore_errors=True)
        
    except ImportError:
        print("⚠️  OpenCV non disponible pour le test")
    except Exception as e:
        print(f"❌ Erreur test OpenCV: {e}")


def test_comparison_modes():
    """Comparaison des 3 modes de verbosité"""
    
    print("\n📊 Comparaison des modes de verbosité")
    print("=" * 60)
    
    modes = ["Debug", "Moyenne", "Faible"]
    
    for mode in modes:
        print(f"\n🔧 Mode: {mode}")
        print("-" * 20)
        
        config_dir = create_test_config_faible()
        
        # Modification de la config pour le mode testé
        config_file = config_dir / "ui_config.json"
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        config_data["logging"]["console_verbosity"] = mode
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        try:
            config = ConfigManager(config_dir)
            VerbosityManager.setup_logging(mode, config)
            
            logger = logging.getLogger(f"test_{mode.lower()}")
            logger.debug(f"DEBUG - Mode {mode}")
            logger.info(f"INFO - Mode {mode}")
            logger.warning(f"WARNING - Mode {mode}")
            logger.error(f"ERROR - Mode {mode}")
            
        except Exception as e:
            print(f"❌ Erreur mode {mode}: {e}")
        
        finally:
            import shutil
            shutil.rmtree(config_dir, ignore_errors=True)


def main():
    """Point d'entrée principal des tests"""
    
    print("🧪 Tests du mode Faible amélioré")
    print("=" * 70)
    
    try:
        test_faible_mode_silence()
        test_opencv_suppression()
        test_comparison_modes()
        
        print("\n" + "=" * 70)
        print("🎉 TESTS TERMINÉS!")
        print("💡 En mode Faible, vous ne devriez voir que les messages ERROR")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ ERREUR GLOBALE: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)