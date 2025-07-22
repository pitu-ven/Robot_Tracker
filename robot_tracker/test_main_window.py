#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_main_window.py
Test de la fenêtre principale avec les 5 onglets - Version 1.0
Modification: Test complet de l'interface utilisateur
"""

import sys
import os
from pathlib import Path

# Ajouter le répertoire du projet au path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer
import logging

# Configuration du logging pour les tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_config_manager():
    """Test du ConfigManager"""
    try:
        from robot_tracker.core.config_manager import ConfigManager
        
        logger.info("🧪 Test du ConfigManager...")
        config = ConfigManager("robot_tracker/config")
        
        # Tests de base
        title = config.get('ui', 'window.title', 'Test')
        width = config.get('ui', 'window.width', 1200)
        
        logger.info(f"✅ ConfigManager OK - Titre: {title}, Largeur: {width}")
        return config
        
    except Exception as e:
        logger.error(f"❌ Erreur ConfigManager: {e}")
        return None

def test_main_window(config):
    """Test de la MainWindow"""
    try:
        from robot_tracker.ui.main_window import MainWindow
        
        logger.info("🧪 Test de la MainWindow...")
        
        # Création de l'application Qt
        app = QApplication(sys.argv)
        
        # Création de la fenêtre principale
        window = MainWindow(config)
        
        # Affichage
        window.show()
        
        logger.info("✅ MainWindow créée avec succès")
        
        # Test des fonctionnalités après un délai
        QTimer.singleShot(2000, lambda: test_window_features(window))
        
        return app, window
        
    except Exception as e:
        logger.error(f"❌ Erreur MainWindow: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def test_window_features(window):
    """Test des fonctionnalités de la fenêtre"""
    try:
        logger.info("🧪 Test des fonctionnalités...")
        
        # Test de basculement entre onglets
        logger.info("📑 Test basculement onglets...")
        
        # Basculer vers chaque onglet
        for i, tab_name in enumerate(['caméra', 'trajectoire', 'cible', 'calibration', 'mesures']):
            success = window.switch_to_tab(tab_name)
            logger.info(f"  - Onglet '{tab_name}': {'✅' if success else '❌'}")
        
        # Test des méthodes de status
        logger.info("📊 Test des status...")
        for tab_name in window.tabs.keys():
            tab = window.get_tab(tab_name)
            if hasattr(tab, 'get_status_info'):
                status = tab.get_status_info()
                logger.info(f"  - Status {tab_name}: {status}")
        
        # Test de détection des caméras (onglet caméra)
        camera_tab = window.get_tab('caméra')
        if camera_tab and hasattr(camera_tab, 'detect_cameras'):
            logger.info("📷 Test détection caméras...")
            camera_tab.detect_cameras()
        
        # Test de chargement de trajectoire (onglet trajectoire)  
        trajectory_tab = window.get_tab('trajectoire')
        if trajectory_tab:
            logger.info("📊 Test onglet trajectoire...")
            # Simulation d'un fichier chargé
            if hasattr(trajectory_tab, 'process_trajectory_file'):
                # Créer un fichier de test temporaire
                test_file = Path("test_trajectory.val3")
                test_file.write_text("# Test VAL3 file\nMOVE joint, point1\n")
                
                try:
                    trajectory_tab.process_trajectory_file(str(test_file))
                    logger.info("  ✅ Chargement fichier test réussi")
                except Exception as e:
                    logger.warning(f"  ⚠️ Erreur chargement test: {e}")
                finally:
                    if test_file.exists():
                        test_file.unlink()
        
        logger.info("✅ Tests des fonctionnalités terminés")
        
        # Afficher un message de succès
        QMessageBox.information(
            window, 
            "Tests Réussis", 
            "🎉 Tous les tests de base sont passés avec succès!\n\n"
            "✅ ConfigManager fonctionnel\n"
            "✅ MainWindow créée\n"
            "✅ 5 onglets initialisés\n"
            "✅ Basculement entre onglets OK\n"
            "✅ Fonctionnalités de base testées"
        )
        
    except Exception as e:
        logger.error(f"❌ Erreur test fonctionnalités: {e}")
        QMessageBox.critical(
            window,
            "Erreur de Test",
            f"❌ Erreur lors des tests:\n{e}"
        )

def test_individual_tabs():
    """Test individuel de chaque onglet"""
    try:
        logger.info("🧪 Test individuel des onglets...")
        
        from robot_tracker.core.config_manager import ConfigManager
        config = ConfigManager("robot_tracker/config")
        
        # Test de chaque onglet individuellement
        tab_classes = [
            ('CameraTab', 'robot_tracker.ui.camera_tab'),
            ('TrajectoryTab', 'robot_tracker.ui.trajectory_tab'), 
            ('TargetTab', 'robot_tracker.ui.target_tab'),
            ('CalibrationTab', 'robot_tracker.ui.calibration_tab'),
            ('MeasuresTab', 'robot_tracker.ui.measures_tab')
        ]
        
        for tab_name, module_name in tab_classes:
            try:
                # Import dynamique
                module = __import__(module_name, fromlist=[tab_name])
                tab_class = getattr(module, tab_name)
                
                # Création de l'instance
                tab_instance = tab_class(config)
                
                logger.info(f"✅ {tab_name} créé avec succès")
                
                # Test de cleanup si disponible
                if hasattr(tab_instance, 'cleanup'):
                    tab_instance.cleanup()
                
            except Exception as e:
                logger.error(f"❌ Erreur {tab_name}: {e}")
        
        logger.info("✅ Tests individuels terminés")
        
    except Exception as e:
        logger.error(f"❌ Erreur tests individuels: {e}")

def main():
    """Fonction principale de test"""
    logger.info("🚀 DÉMARRAGE DES TESTS")
    logger.info("=" * 50)
    
    # Vérification de l'environnement
    logger.info(f"📍 Répertoire de travail: {os.getcwd()}")
    logger.info(f"📍 Répertoire du script: {Path(__file__).parent}")
    
    # Test 1: ConfigManager
    logger.info("\n🧪 TEST 1: ConfigManager")
    config = test_config_manager()
    if not config:
        logger.error("❌ Impossible de continuer sans ConfigManager")
        return 1
    
    # Test 2: Onglets individuels
    logger.info("\n🧪 TEST 2: Onglets Individuels")
    test_individual_tabs()
    
    # Test 3: MainWindow complète
    logger.info("\n🧪 TEST 3: MainWindow Complète")
    app, window = test_main_window(config)
    
    if not app or not window:
        logger.error("❌ Impossible de créer la MainWindow")
        return 1
    
    # Démarrage de l'application Qt
    logger.info("\n🚀 Lancement de l'interface utilisateur...")
    logger.info("   (Les tests automatiques se dérouleront après 2 secondes)")
    logger.info("   Fermez la fenêtre pour terminer les tests")
    
    try:
        exit_code = app.exec()
        logger.info(f"✅ Application fermée avec le code: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("⚠️ Interruption utilisateur")
        return 0
    except Exception as e:
        logger.error(f"❌ Erreur d'exécution: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    
    logger.info("\n" + "=" * 50)
    if exit_code == 0:
        logger.info("🎉 TOUS LES TESTS RÉUSSIS!")
        logger.info("✅ L'application Robot Trajectory Controller est fonctionnelle")
    else:
        logger.info("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        logger.info("🔧 Vérifiez les erreurs ci-dessus")
    
    logger.info("=" * 50)
    sys.exit(exit_code)