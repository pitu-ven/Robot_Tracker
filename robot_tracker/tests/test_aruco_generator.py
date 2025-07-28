#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/tests/test_aruco_generator.py
Tests pour le générateur de codes ArUco - Version 1.0
Modification: Validation complète du générateur ArUco
"""

import sys
import os
import cv2
import numpy as np
import tempfile
import shutil
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt, QTimer

# Ajout du chemin parent pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from robot_tracker.ui.aruco_generator import ArUcoGeneratorDialog, ArUcoGeneratorThread, MarkerWidget
except ImportError as e:
    print(f"❌ Erreur import: {e}")
    print("💡 Exécutez depuis le répertoire robot_tracker/")
    sys.exit(1)

class TestConfig:
    """Configuration de test pour le générateur ArUco"""
    
    def __init__(self):
        self.config_values = {
            'ui.aruco_generator.window_title': "Test ArUco Generator",
            'ui.aruco_generator.window_width': 800,
            'ui.aruco_generator.window_height': 600,
            'ui.aruco_generator.marker_display_size': 100,
            'ui.aruco_generator.dictionaries': ["DICT_4X4_50", "DICT_5X5_100"],
            'ui.aruco_generator.default_dictionary': "DICT_4X4_50",
            'ui.aruco_generator.marker_size_min': 50,
            'ui.aruco_generator.marker_size_max': 500,
            'ui.aruco_generator.marker_size_default': 100,
            'ui.aruco_generator.grid_spacing': 5,
            'ui.aruco_generator.markers_per_row': 4,
            'ui.aruco_generator.max_markers_warning': 20,
            'ui.aruco_generator.labels.config_group': "Configuration",
            'ui.aruco_generator.labels.dictionary': "Dictionnaire:",
            'ui.aruco_generator.labels.marker_size': "Taille:",
            'ui.aruco_generator.labels.generate_button': "Générer",
            'ui.aruco_generator.messages.ready': "Prêt",
            'ui.aruco_generator.messages.generating': "Génération...",
            'ui.aruco_generator.messages.completed': "Terminé",
            'ui.aruco_generator.default_save_dir': './test_markers'
        }
    
    def get(self, section, key, default=None):
        full_key = f"{section}.{key}"
        return self.config_values.get(full_key, default)

class TestArUcoGenerator:
    """Tests pour le générateur ArUco"""
    
    def __init__(self):
        self.app = None
        self.config = TestConfig()
        self.temp_dir = None
    
    def setup(self):
        """Configuration des tests"""
        print("🔧 Configuration des tests...")
        self.app = QApplication.instance() or QApplication([])
        self.temp_dir = Path(tempfile.mkdtemp())
        print(f"📁 Répertoire temporaire: {self.temp_dir}")
    
    def teardown(self):
        """Nettoyage après tests"""
        print("🔄 Nettoyage...")
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            print("✅ Répertoire temporaire supprimé")
    
    def test_aruco_generation_thread(self):
        """Test du thread de génération"""
        print("\n🧪 Test du thread de génération ArUco...")
        
        try:
            # Configuration du test
            dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            marker_ids = [0, 1, 2]
            marker_size = 100
            
            # Création du thread
            thread = ArUcoGeneratorThread(dictionary, marker_ids, marker_size)
            
            # Variables de test
            generated_markers = {}
            progress_values = []
            
            # Connexion des signaux
            def on_marker_generated(marker_id, marker_image):
                generated_markers[marker_id] = marker_image
                print(f"   ✅ Marqueur {marker_id} généré")
            
            def on_progress_updated(value):
                progress_values.append(value)
            
            thread.marker_generated.connect(on_marker_generated)
            thread.progress_updated.connect(on_progress_updated)
            
            # Démarrage et attente
            thread.start()
            thread.wait(5000)  # 5 secondes max
            
            # Vérifications
            assert len(generated_markers) == 3, f"Attendu 3 marqueurs, obtenu {len(generated_markers)}"
            assert all(id in generated_markers for id in marker_ids), "IDs de marqueurs manquants"
            assert len(progress_values) > 0, "Aucune mise à jour de progression"
            assert max(progress_values) == 100, "Progression incomplète"
            
            # Vérification des images
            for marker_id, image in generated_markers.items():
                assert image is not None, f"Image nulle pour marqueur {marker_id}"
                assert image.shape == (marker_size, marker_size), f"Taille incorrecte pour marqueur {marker_id}"
                assert image.dtype == np.uint8, f"Type incorrect pour marqueur {marker_id}"
            
            print("✅ Thread de génération: SUCCÈS")
            return True
            
        except Exception as e:
            print(f"❌ Thread de génération: ÉCHEC - {e}")
            return False
    
    def test_marker_widget(self):
        """Test du widget d'affichage de marqueur"""
        print("\n🧪 Test du widget de marqueur...")
        
        try:
            # Génération d'un marqueur de test
            dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            marker_image = np.zeros((100, 100), dtype=np.uint8)
            marker_image = cv2.aruco.generateImageMarker(dictionary, 42, 100, marker_image, 1)
            
            # Création du widget
            widget = MarkerWidget(42, marker_image, self.config)
            
            # Vérifications
            assert widget.marker_id == 42, "ID de marqueur incorrect"
            assert widget.marker_image is not None, "Image de marqueur nulle"
            assert widget.pixmap() is not None, "Pixmap non généré"
            
            widget.show()
            QTest.qWait(100)  # Attendre l'affichage
            
            # Vérification de la taille
            expected_size = self.config.get('ui', 'aruco_generator.marker_display_size', 100)
            assert widget.width() <= expected_size + 50, "Largeur du widget incorrecte"
            
            widget.close()
            print("✅ Widget de marqueur: SUCCÈS")
            return True
            
        except Exception as e:
            print(f"❌ Widget de marqueur: ÉCHEC - {e}")
            return False
    
    def test_aruco_dialog_creation(self):
        """Test de création du dialog"""
        print("\n🧪 Test de création du dialog...")
        
        try:
            # Création du dialog
            dialog = ArUcoGeneratorDialog(self.config)
            
            # Vérifications de l'interface
            assert dialog.dictionary_combo is not None, "ComboBox dictionnaire manquant"
            assert dialog.size_spinbox is not None, "SpinBox taille manquant"
            assert dialog.generate_btn is not None, "Bouton génération manquant"
            assert dialog.markers_layout is not None, "Layout marqueurs manquant"
            
            # Vérification des valeurs par défaut
            assert dialog.size_spinbox.value() == 100, "Taille par défaut incorrecte"
            assert dialog.start_id_spinbox.value() == 0, "ID début incorrect"
            assert dialog.end_id_spinbox.value() == 9, "ID fin incorrect"
            
            # Vérification de l'état initial
            assert dialog.generate_btn.isEnabled(), "Bouton génération désactivé"
            assert not dialog.stop_btn.isEnabled(), "Bouton arrêt activé"
            assert not dialog.save_btn.isEnabled(), "Bouton sauvegarde activé"
            
            dialog.close()
            print("✅ Création du dialog: SUCCÈS")
            return True
            
        except Exception as e:
            print(f"❌ Création du dialog: ÉCHEC - {e}")
            return False
    
    def test_marker_generation_process(self):
        """Test du processus complet de génération"""
        print("\n🧪 Test du processus de génération...")
        
        try:
            dialog = ArUcoGeneratorDialog(self.config)
            dialog.show()
            
            # Configuration pour un test rapide
            dialog.start_id_spinbox.setValue(0)
            dialog.end_id_spinbox.setValue(2)  # 3 marqueurs seulement
            dialog.size_spinbox.setValue(50)   # Petite taille pour la rapidité
            
            # Vérification avant génération
            assert len(dialog.generated_markers) == 0, "Marqueurs déjà présents"
            
            # Simulation du processus de génération
            generated_count = 0
            def count_generated_markers(marker_id, marker_image):
                nonlocal generated_count
                generated_count += 1
                print(f"   📋 Marqueur {marker_id} généré ({generated_count}/3)")
            
            # Génération manuelle pour le test (sans thread pour la simplicité)
            dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            for marker_id in range(3):
                marker_image = np.zeros((50, 50), dtype=np.uint8)
                marker_image = cv2.aruco.generateImageMarker(dictionary, marker_id, 50, marker_image, 1)
                dialog.add_marker_to_display(marker_id, marker_image)
            
            # Vérifications après génération
            assert len(dialog.generated_markers) == 3, f"Nombre incorrect de marqueurs: {len(dialog.generated_markers)}"
            assert all(id in dialog.generated_markers for id in range(3)), "IDs manquants"
            
            # Vérification de l'interface
            QTest.qWait(100)
            widget_count = dialog.markers_layout.count()
            assert widget_count >= 3, f"Widgets marqueurs insuffisants: {widget_count}"
            
            dialog.close()
            print("✅ Processus de génération: SUCCÈS")
            return True
            
        except Exception as e:
            print(f"❌ Processus de génération: ÉCHEC - {e}")
            return False
    
    def test_marker_export(self):
        """Test de l'export des marqueurs"""
        print("\n🧪 Test de l'export des marqueurs...")
        
        try:
            dialog = ArUcoGeneratorDialog(self.config)
            
            # Génération de marqueurs de test
            dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            test_markers = {}
            
            for marker_id in range(3):
                marker_image = np.zeros((100, 100), dtype=np.uint8)
                marker_image = cv2.aruco.generateImageMarker(dictionary, marker_id, 100, marker_image, 1)
                test_markers[marker_id] = marker_image
            
            dialog.generated_markers = test_markers
            
            # Test du traitement pour export
            processed_image = dialog.process_marker_for_export(test_markers[0], 0)
            assert processed_image is not None, "Image traitée nulle"
            assert processed_image.shape[0] >= 100, "Image traitée trop petite"
            
            # Test avec options activées
            dialog.add_border_cb.setChecked(True)
            dialog.add_id_text_cb.setChecked(True)
            
            processed_with_options = dialog.process_marker_for_export(test_markers[1], 1)
            assert processed_with_options.shape[0] > processed_image.shape[0], "Bordure non ajoutée"
            
            print("✅ Export des marqueurs: SUCCÈS")
            return True
            
        except Exception as e:
            print(f"❌ Export des marqueurs: ÉCHEC - {e}")
            return False
    
    def test_dictionary_validation(self):
        """Test de la validation des dictionnaires"""
        print("\n🧪 Test de validation des dictionnaires...")
        
        try:
            dialog = ArUcoGeneratorDialog(self.config)
            
            # Test avec DICT_4X4_50 (50 marqueurs max)
            dialog.dictionary_combo.setCurrentText("DICT_4X4_50")
            dialog.validate_dictionary_limits()
            
            assert dialog.start_id_spinbox.maximum() == 49, "Limite max incorrecte pour DICT_4X4_50"
            assert dialog.end_id_spinbox.maximum() == 49, "Limite max incorrecte pour DICT_4X4_50"
            
            # Test avec une plage invalide
            dialog.start_id_spinbox.setValue(60)  # Au-dessus de la limite
            dialog.validate_dictionary_limits()
            
            assert dialog.start_id_spinbox.value() == 0, "Valeur non réinitialisée"
            
            # Test de validation de plage
            dialog.start_id_spinbox.setValue(10)
            dialog.end_id_spinbox.setValue(5)  # Fin < Début
            dialog.validate_id_range()
            
            assert dialog.end_id_spinbox.value() == 10, "Plage non corrigée"
            
            print("✅ Validation des dictionnaires: SUCCÈS")
            return True
            
        except Exception as e:
            print(f"❌ Validation des dictionnaires: ÉCHEC - {e}")
            return False
    
    def run_all_tests(self):
        """Lance tous les tests"""
        print("🚀 Lancement des tests du générateur ArUco")
        print("=" * 60)
        
        self.setup()
        
        tests = [
            ("Thread de génération", self.test_aruco_generation_thread),
            ("Widget de marqueur", self.test_marker_widget),
            ("Création du dialog", self.test_aruco_dialog_creation),
            ("Processus de génération", self.test_marker_generation_process),
            ("Export des marqueurs", self.test_marker_export),
            ("Validation des dictionnaires", self.test_dictionary_validation)
        ]
        
        results = {}
        for test_name, test_func in tests:
            try:
                results[test_name] = test_func()
            except Exception as e:
                print(f"❌ {test_name}: ERREUR CRITIQUE - {e}")
                results[test_name] = False
        
        self.teardown()
        
        # Résumé
        print("\n" + "=" * 60)
        print("📊 RÉSUMÉ DES TESTS")
        print("=" * 60)
        
        passed = 0
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status:8} {test_name}")
            if result:
                passed += 1
        
        success_rate = passed / len(results)
        print(f"\nScore: {passed}/{len(results)} ({success_rate:.1%})")
        
        if success_rate == 1.0:
            print("\n🎉 TOUS LES TESTS RÉUSSIS!")
            print("✅ Le générateur ArUco est prêt à être intégré")
            return True
        else:
            print(f"\n⚠️ {len(results) - passed} test(s) échoué(s)")
            print("🔧 Vérifiez les erreurs ci-dessus")
            return False

def main():
    """Point d'entrée principal des tests"""
    print("🎯 Tests du Générateur ArUco - Robot Tracker")
    print("=" * 60)
    
    # Vérification des dépendances
    try:
        import cv2
        print(f"✅ OpenCV version: {cv2.__version__}")
        
        # Test de l'accès aux dictionnaires ArUco
        dict_test = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        print("✅ Dictionnaires ArUco accessibles")
        
    except Exception as e:
        print(f"❌ Problème dépendances: {e}")
        return 1
    
    # Lancement des tests
    tester = TestArUcoGenerator()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎯 RECOMMANDATIONS POUR L'INTÉGRATION:")
        print("1. Ajouter le menu dans main_window.py")
        print("2. Intégrer la configuration ArUco dans ui_config.json") 
        print("3. Tester l'impression avec une vraie imprimante")
        print("4. Valider les marqueurs générés avec un détecteur")
        
        return 0
    else:
        print("\n🔧 ACTIONS REQUISES:")
        print("1. Corriger les erreurs détectées")
        print("2. Relancer les tests")
        print("3. Vérifier l'environnement de développement")
        
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        print(f"\n👋 Tests terminés (code: {exit_code})")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrompus par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur générale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)