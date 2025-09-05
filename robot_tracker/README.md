# Robot Trajectory Controller

Système de contrôle de trajectoire robotique par vision industrielle pour tracking millimétrique d'objets en mouvement.

## 🎯 Vue d'ensemble

Le Robot Trajectory Controller est un système modulaire permettant le tracking précis de trajectoires robotiques via vision industrielle. L'application offre une interface PyQt6 à 5 onglets avec support multi-caméras, détection ArUco, marqueurs réfléchissants et génération de rapports automatiques.

### Objectifs techniques
- **Précision** : ±1mm de précision de tracking
- **Performance** : 20-30 FPS en temps réel
- **Flexibilité** : Support multi-caméras et multi-robots
- **Configuration** : Architecture JSON externalisée

## 🚀 Installation

### Prérequis
- Python 3.8+
- OpenCV 4.8+
- PyQt6
- Intel RealSense SDK (optionnel)

### Installation rapide
```bash
git clone https://github.com/user/robot-tracker.git
cd robot-tracker/robot_tracker
pip install -r requirements.txt
```

### Lancement
```bash
python main.py
```

## 📋 État d'implémentation

### 🏗️ Architecture de base
- ✅ **Structure modulaire** - Organisation en 5 onglets
- ✅ **Configuration JSON** - Système externalisé complet
- ✅ **Gestionnaire de configuration** - ConfigManager avec support multi-fichiers
- ✅ **Interface principale** - MainWindow avec onglets dynamiques
- ✅ **Système de logging** - 3 niveaux de verbosité configurables

### 🎥 Gestion caméras
- ✅ **CameraManager** - Gestion centralisée des caméras
- ✅ **Support RealSense** - Driver Intel RealSense D435
- ✅ **Support USB3** - Driver caméras USB3 standard
- ✅ **Détection automatique** - Scan des caméras disponibles
- ✅ **Interface caméra** - Onglet complet avec preview temps réel

### 🎯 Détection et tracking (Onglet Cible)
- ✅ **Interface TargetTab** - Interface complète de détection
- ✅ **ArUco auto-config** - Chargement automatique des configurations
- ✅ **ArUco ConfigLoader** - Scan de dossiers de marqueurs générés
- ✅ **Composants détection** - TargetDetector avec stubs fonctionnels
- ✅ **ROI Manager** - Gestion des régions d'intérêt
- 🔄 **Détection multi-types** - ArUco + marqueurs réfléchissants + LEDs (en cours)
- 🔄 **Tracking Kalman** - Filtrage et prédiction (planifié)

### 🤖 Communication robot
- 🔄 **Adaptateurs multi-robots** - VAL3, KRL, RAPID, G-Code (planifié)
- 🔄 **Interface trajectoire** - Onglet de gestion des trajectoires (planifié)
- 🔄 **Parseurs trajectoires** - Support multi-formats (planifié)

### 🔧 Calibration
- 🔄 **Calibration intrinsèque** - Paramètres caméra (planifié)
- 🔄 **Calibration extrinsèque** - Relation caméra-robot (planifié)
- 🔄 **Interface calibration** - Onglet dédié (planifié)

### 📊 Mesures et rapports
- 🔄 **Interface mesures** - Onglet de métriques (planifié)
- 🔄 **Génération PDF** - Rapports automatiques (planifié)
- 🔄 **Export données** - CSV, JSON, XML (planifié)

### 🧪 Tests et qualité
- ✅ **Tests logging** - Validation du système de verbosité
- ✅ **Tests suppression** - Validation mode silencieux
- ✅ **Tests ArUco** - Validation chargement configuration
- 🔄 **Tests intégration** - Tests bout-en-bout (en cours)
- 🔄 **Tests performance** - Benchmarks (planifié)

## 📁 Architecture du projet

```
robot_tracker/
├── main.py                    # ✅ Point d'entrée principal
├── ui/                        # Interface utilisateur PyQt6
│   ├── main_window.py        # ✅ Fenêtre principale avec onglets
│   ├── camera_tab.py         # ✅ Onglet caméra (complet)
│   ├── target_tab.py         # ✅ Onglet cible (interface complète)
│   ├── trajectory_tab.py     # 🔄 Onglet trajectoire (planifié)
│   ├── calibration_tab.py    # 🔄 Onglet calibration (planifié)
│   ├── measures_tab.py       # 🔄 Onglet mesures (planifié)
│   └── aruco_generator.py    # ✅ Générateur de marqueurs ArUco
├── core/                      # Logique métier
│   ├── config_manager.py     # ✅ Gestion configurations JSON
│   ├── camera_manager.py     # ✅ Gestion multi-caméras
│   ├── aruco_config_loader.py # ✅ Chargement config ArUco auto
│   ├── target_detector.py    # ✅ Détection multi-types (stubs)
│   ├── roi_manager.py        # ✅ Gestion ROI (stubs)
│   ├── tracker.py            # 🔄 Algorithmes tracking (planifié)
│   ├── calibration.py        # 🔄 Calibration caméra-robot (planifié)
│   └── trajectory_parser.py  # 🔄 Parseurs trajectoires (planifié)
├── hardware/                  # Drivers hardware
│   ├── realsense_driver.py   # ✅ Driver RealSense complet
│   ├── usb3_camera_driver.py # ✅ Driver USB3 complet
│   └── robot_communication.py # 🔄 Communication robot (planifié)
├── utils/                     # Utilitaires
│   ├── logging_utils.py      # ✅ Gestionnaire verbosité
│   ├── system_logging_suppressor.py # ✅ Suppresseur logs système
│   ├── verbosity_config_tool.py # ✅ Outil config logging
│   ├── pdf_generator.py      # 🔄 Génération rapports (planifié)
│   └── data_export.py        # 🔄 Export données (planifié)
├── config/                    # Configuration JSON
│   ├── ui_config.json        # ✅ Configuration interface
│   ├── camera_config.json    # ✅ Paramètres caméras
│   ├── aruco_generator.json  # ✅ Configuration générateur ArUco
│   ├── tracking_config.json  # 🔄 Config algorithmes (planifié)
│   └── robot_config.json     # 🔄 Communication robot (planifié)
└── tests/                     # Tests et validation
    ├── test_logging_verbosity.py # ✅ Tests logging
    ├── test_suppression_complete.py # ✅ Tests suppression
    ├── test_final_validation.py # ✅ Tests validation finale
    └── aruco_demo.py         # ✅ Démonstration ArUco
```

## 🔧 Configuration des logs

Robot Tracker dispose d'un système de verbosité avancé avec 3 niveaux configurables.

### 🎯 Niveaux disponibles

| Niveau | Description | Messages affichés |
|--------|-------------|-------------------|
| **🔇 Faible** | Mode silencieux | Seulement les erreurs critiques |
| **📊 Moyenne** | Mode standard (défaut) | Informations importantes + erreurs |
| **🔍 Debug** | Mode développement | Tous les messages détaillés |

### 📋 Changement de verbosité

#### **Outil en ligne de commande (recommandé)**

```bash
# Mode interactif avec menu
python utils/verbosity_config_tool.py

# Commandes directes
python utils/verbosity_config_tool.py --set Debug     # Mode développement
python utils/verbosity_config_tool.py --set Moyenne  # Mode standard
python utils/verbosity_config_tool.py --set Faible   # Mode silencieux

# Afficher la configuration actuelle
python utils/verbosity_config_tool.py --show

# Tester les messages
python utils/verbosity_config_tool.py --test
```

#### **Modification directe du fichier**

Éditez `config/ui_config.json` :
```json
{
  "logging": {
    "console_verbosity": "Moyenne"
  }
}
```

### 🔇 Suppression automatique (Mode Faible)

En mode **Faible**, le système supprime automatiquement :
- Messages de chargement des configurations
- Messages OpenCV (MSMF, obsensor, etc.)
- Warnings Python des bibliothèques
- Messages de débogage internes

## 🎯 Générateur ArUco

L'application inclut un générateur de marqueurs ArUco intégré accessible via l'interface principale.

### Fonctionnalités
- ✅ **Génération batch** - Création de séries de marqueurs
- ✅ **Multi-dictionnaires** - Support de tous les dictionnaires ArUco
- ✅ **Haute qualité** - Images optimisées pour impression
- ✅ **Auto-nommage** - Convention de nommage automatique
- ✅ **Configuration persistante** - Sauvegarde des paramètres

### Utilisation
```bash
# Lancement direct
python ui/aruco_generator.py

# Via l'interface principale : Outils → Générateur ArUco
```

## 🚀 Roadmap de développement

### 📅 Phase 1 : Fondations (✅ Terminée)
- ✅ Architecture modulaire complète
- ✅ Système de configuration JSON
- ✅ Interface principale avec onglets
- ✅ Gestion multi-caméras
- ✅ Système de logging avancé

### 📅 Phase 2 : Détection avancée (🔄 En cours)
- 🔄 Algorithmes de détection ArUco optimisés
- 🔄 Support marqueurs réfléchissants
- 🔄 Détection LEDs colorées
- 🔄 Filtrage Kalman pour stabilité
- 🔄 ROI interactives complètes

### 📅 Phase 3 : Communication robot (🔄 Planifiée)
- 🔄 Adaptateurs multi-robots (Stäubli, KUKA, ABB, UR)
- 🔄 Parseurs de trajectoires (VAL3, KRL, RAPID, G-Code)
- 🔄 Interface de gestion des trajectoires
- 🔄 Validation et sécurité des commandes

### 📅 Phase 4 : Calibration (🔄 Planifiée)
- 🔄 Calibration intrinsèque automatique
- 🔄 Calibration extrinsèque caméra-robot
- 🔄 Interface de calibration guidée
- 🔄 Validation métrologique

### 📅 Phase 5 : Rapports et mesures (🔄 Planifiée)
- 🔄 Interface de métriques temps réel
- 🔄 Génération automatique de rapports PDF
- 🔄 Export multi-formats (CSV, JSON, XML)
- 🔄 Analyses statistiques avancées

## 🧪 Tests et validation

### Lancement des tests
```bash
# Test complet du système de logging
python tests/test_logging_verbosity.py

# Test de suppression des messages
python tests/test_suppression_complete.py

# Validation finale du système
python tests/test_final_validation.py

# Démonstration ArUco
python tests/aruco_demo.py
```

### Métriques de qualité
- ✅ **Tests logging** : 100% passés
- ✅ **Suppression OpenCV** : Fonctionnelle
- ✅ **Configuration JSON** : Validée
- 🔄 **Tests intégration** : En développement

## 🔧 Configuration système recommandée

### Hardware minimum
- **OS** : Windows 10+ / Ubuntu 20.04+
- **CPU** : Intel i5-8400 / AMD Ryzen 5 3600
- **RAM** : 16GB minimum
- **GPU** : NVIDIA GTX 1060 (pour traitement avancé)
- **USB** : Contrôleurs USB3.0 dédiés

### Performance cible
- **Latence** : <20ms acquisition
- **Fréquence** : 20-30 FPS tracking
- **Précision 2D** : ±0.5 pixel
- **Précision 3D** : ±1mm à 1 mètre

## 📚 Documentation et support

### Guides utilisateur
- [Guide de démarrage rapide](docs/quick-start.md) (🔄 planifié)
- [Manuel utilisateur complet](docs/user-manual.md) (🔄 planifié)
- [Guide d'administration](docs/admin-guide.md) (🔄 planifié)

### Documentation technique
- [Architecture du système](docs/architecture.md) (🔄 planifié)
- [API de développement](docs/api-reference.md) (🔄 planifié)
- [Guide de contribution](docs/contributing.md) (🔄 planifié)

### Standards et références
- **ISO 9283:1998** : Tests de performance robots
- **ISO 17025:2017** : Traçabilité métrologique
- **OpenCV ArUco** : Documentation officielle
- **Intel RealSense** : SDK Python

## 🤝 Contribution

Le projet suit une architecture modulaire permettant l'extension facile. Les contributions sont les bienvenues pour :
- Nouveaux drivers de caméras
- Adaptateurs de robots supplémentaires
- Algorithmes de détection avancés
- Améliorations d'interface

## 📄 Licence

Robot Trajectory Controller est distribué sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

---

**Version actuelle** : 1.0-dev  
**Dernière mise à jour** : Janvier 2025  
**Statut** : Développement actif - Phase 2