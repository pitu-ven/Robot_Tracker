# robot_tracker/tests/check_environment.py
# Version 1.0 - Vérification et installation automatique de l'environnement

import sys
import subprocess
import os
from pathlib import Path

def check_python_version():
    """Vérifie la version Python"""
    print("🐍 Vérification Python...")
    version = sys.version_info
    print(f"   Version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ requis")
        return False
    
    print("✅ Version Python OK")
    return True

def install_package(package_name):
    """Installe un package via pip"""
    try:
        print(f"📦 Installation de {package_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"✅ {package_name} installé")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur installation {package_name}: {e}")
        return False

def check_and_install_dependencies():
    """Vérifie et installe les dépendances"""
    dependencies = [
        ("PyQt6", "PyQt6>=6.4.2"),
        ("OpenCV", "opencv-python>=4.8.1"),
        ("NumPy", "numpy>=1.24.3"),
        ("ReportLab", "reportlab>=4.0.8"),
    ]
    
    optional_dependencies = [
        ("RealSense", "pyrealsense2>=2.55.1"),
        ("Open3D", "open3d>=0.19.0"),
    ]
    
    print("🔍 Vérification des dépendances...")
    
    all_ok = True
    
    # Dépendances critiques
    for name, package in dependencies:
        try:
            if name == "PyQt6":
                import PyQt6
            elif name == "OpenCV":
                import cv2
            elif name == "NumPy":
                import numpy
            elif name == "ReportLab":
                import reportlab
            
            print(f"✅ {name} disponible")
        except ImportError:
            print(f"❌ {name} manquant")
            if not install_package(package):
                all_ok = False
    
    # Dépendances optionnelles
    print("\n🔍 Vérification dépendances optionnelles...")
    for name, package in optional_dependencies:
        try:
            if name == "RealSense":
                import pyrealsense2
            elif name == "Open3D":
                import open3d
            
            print(f"✅ {name} disponible")
        except ImportError:
            print(f"⚠️ {name} manquant (optionnel)")
            response = input(f"Installer {name}? (o/N): ")
            if response.lower() in ['o', 'oui', 'y', 'yes']:
                install_package(package)
    
    return all_ok

def test_pyqt6():
    """Test rapide PyQt6"""
    try:
        print("\n🧪 Test PyQt6...")
        from PyQt6.QtWidgets import QApplication, QLabel
        from PyQt6.QtCore import Qt
        
        # Test création application (sans affichage)
        app = QApplication([])
        label = QLabel("Test PyQt6")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        print("✅ PyQt6 fonctionne correctement")
        app.quit()
        return True
        
    except Exception as e:
        print(f"❌ Erreur PyQt6: {e}")
        return False

def test_project_structure():
    """Vérifie la structure du projet"""
    print("\n🔍 Vérification structure projet...")
    
    project_root = Path(__file__).parent.parent
    required_files = [
        "main.py",
        "ui/main_window.py",
        "ui/camera_tab.py",
        "core/config_manager.py",
        "config/ui_config.json",
        "config/camera_config.json"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not (project_root / file_path).exists():
            missing_files.append(file_path)
            print(f"❌ Manquant: {file_path}")
        else:
            print(f"✅ Trouvé: {file_path}")
    
    if missing_files:
        print(f"\n⚠️ {len(missing_files)} fichier(s) manquant(s)")
        return False
    
    print("✅ Structure projet OK")
    return True

def main():
    """Point d'entrée principal"""
    print("🔧 Robot Tracker - Vérification Environnement")
    print("=" * 50)
    
    # Vérifications
    checks = [
        ("Version Python", check_python_version),
        ("Dépendances", check_and_install_dependencies),
        ("Test PyQt6", test_pyqt6),
        ("Structure projet", test_project_structure)
    ]
    
    results = {}
    for check_name, check_func in checks:
        print(f"\n📋 {check_name}...")
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"❌ Erreur {check_name}: {e}")
            results[check_name] = False
    
    # Résumé
    print("\n" + "=" * 50)
    print("📊 RÉSUMÉ")
    print("=" * 50)
    
    passed = 0
    for check_name, result in results.items():
        status = "✅ OK" if result else "❌ ÉCHEC"
        print(f"{status:8} {check_name}")
        if result:
            passed += 1
    
    success_rate = passed / len(results)
    print(f"\nScore: {passed}/{len(results)} ({success_rate:.1%})")
    
    if success_rate == 1.0:
        print("\n🎉 ENVIRONNEMENT PRÊT!")
        print("✅ Vous pouvez lancer: python main.py")
        return 0
    elif success_rate >= 0.75:
        print("\n⚠️ ENVIRONNEMENT PARTIELLEMENT PRÊT")
        print("🔧 Corrigez les problèmes et relancez ce script")
        return 1
    else:
        print("\n❌ ENVIRONNEMENT NON PRÊT")
        print("🔧 Plusieurs problèmes à corriger")
        return 2

if __name__ == "__main__":
    exit_code = main()
    print(f"\n👋 Vérification terminée (code: {exit_code})")
    sys.exit(exit_code)