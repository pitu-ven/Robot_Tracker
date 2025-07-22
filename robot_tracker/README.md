# Robot Trajectory Controller

Système de contrôle de trajectoire robotique par vision industrielle.

## Installation

```bash
cd robot_tracker
pip install -r requirements.txt
```

## Utilisation

```bash
python main.py
```

## Configuration

Les fichiers de configuration se trouvent dans le dossier `config/`.
Modifiez les paramètres selon vos besoins spécifiques.

## Structure

- `ui/` - Interface utilisateur PyQt6
- `core/` - Logique métier et algorithmes
- `hardware/` - Drivers caméras et communication robot
- `utils/` - Utilitaires et génération de rapports
- `config/` - Fichiers de configuration JSON
