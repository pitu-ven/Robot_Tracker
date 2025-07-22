#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire centralisé des configurations JSON
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import shutil
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConfigManager:
    """Gestionnaire centralisé pour toutes les configurations"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.default_dir = self.config_dir / "default"
        self.configs = {}
        self._ensure_config_directory()
        self._load_all_configs()
    
    def _ensure_config_directory(self):
        """Assure que le répertoire de configuration existe"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.default_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Configuration directory: {self.config_dir}")
    
    def _load_all_configs(self):
        """Charge toutes les configurations au démarrage"""
        config_files = {
            'ui': 'ui_config.json',
            'camera': 'camera_config.json',
            'robot': 'robot_config.json',
            'tracking': 'tracking_config.json'
        }
        
        for config_name, filename in config_files.items():
            try:
                self.configs[config_name] = self._load_config(filename)
                logger.info(f"✅ Configuration '{config_name}' chargée avec succès")
            except Exception as e:
                logger.error(f"❌ Erreur lors du chargement de '{config_name}': {e}")
                # Créer une configuration vide en cas d'erreur
                self.configs[config_name] = {}
    
    def _load_config(self, filename: str) -> Dict[str, Any]:
        """Charge un fichier de configuration avec fallback vers default"""
        config_path = self.config_dir / filename
        default_filename = filename.replace('.json', '_default.json')
        default_path = self.default_dir / default_filename
        
        # Stratégie de chargement avec fallback
        if config_path.exists():
            # 1. Charger le fichier principal s'il existe
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"Configuration chargée: {config_path}")
                return config
            except json.JSONDecodeError as e:
                logger.warning(f"Fichier JSON invalide {config_path}: {e}")
                # Fallback vers default
                return self._load_default_config(default_path, config_path)
        else:
            # 2. Le fichier principal n'existe pas, utiliser le default
            logger.info(f"Fichier {config_path} non trouvé, utilisation du default")
            return self._load_default_config(default_path, config_path)
    
    def _load_default_config(self, default_path: Path, target_path: Path) -> Dict[str, Any]:
        """Charge la configuration par défaut et la copie si nécessaire"""
        if default_path.exists():
            try:
                with open(default_path, 'r', encoding='utf-8') as f:
                    default_config = json.load(f)
                
                # Copier le default vers le fichier principal s'il n'existe pas
                if not target_path.exists():
                    shutil.copy2(default_path, target_path)
                    logger.info(f"Configuration par défaut copiée: {default_path} -> {target_path}")
                
                return default_config
            except Exception as e:
                logger.error(f"Erreur lors du chargement du default {default_path}: {e}")
                return {}
        else:
            logger.warning(f"Fichier default {default_path} non trouvé")
            return {}
    
    def get(self, config_type: str, path: str = "", default: Any = None) -> Any:
        """Récupère une valeur de configuration avec notation pointée
        
        Args:
            config_type: Type de configuration ('ui', 'camera', 'robot', 'tracking')
            path: Chemin vers la valeur (ex: "window.width" ou "realsense.color_stream.fps")
            default: Valeur par défaut si non trouvée
            
        Returns:
            La valeur trouvée ou la valeur par défaut
            
        Examples:
            config.get('ui', 'window.width', 1200)
            config.get('camera', 'realsense.enabled', True)
            config.get('tracking', 'aruco.marker_size', 0.05)
        """
        if config_type not in self.configs:
            logger.warning(f"Type de configuration inconnu: {config_type}")
            return default
        
        config = self.configs[config_type]
        
        # Si pas de chemin, retourner toute la configuration
        if not path:
            return config
        
        # Naviguer dans la configuration avec la notation pointée
        try:
            current = config
            for key in path.split('.'):
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    logger.debug(f"Clé '{key}' non trouvée dans le chemin '{path}'")
                    return default
            return current
        except Exception as e:
            logger.debug(f"Erreur lors de la navigation dans '{path}': {e}")
            return default
    
    def set(self, config_type: str, path: str, value: Any):
        """Modifie une valeur de configuration
        
        Args:
            config_type: Type de configuration
            path: Chemin vers la valeur (notation pointée)
            value: Nouvelle valeur
            
        Examples:
            config.set('ui', 'window.width', 1400)
            config.set('camera', 'realsense.fps', 60)
        """
        if config_type not in self.configs:
            logger.warning(f"Type de configuration inconnu: {config_type}")
            self.configs[config_type] = {}
        
        config = self.configs[config_type]
        
        # Naviguer et créer la structure si nécessaire
        keys = path.split('.')
        current = config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                # Remplacer la valeur par un dictionnaire
                current[key] = {}
            current = current[key]
        
        # Définir la valeur finale
        current[keys[-1]] = value
        logger.info(f"Configuration mise à jour: {config_type}.{path} = {value}")
    
    def save_config(self, config_type: str):
        """Sauvegarde une configuration modifiée"""
        if config_type not in self.configs:
            logger.error(f"Impossible de sauvegarder: type '{config_type}' non trouvé")
            return False
        
        try:
            config_files = {
                'ui': 'ui_config.json',
                'camera': 'camera_config.json', 
                'robot': 'robot_config.json',
                'tracking': 'tracking_config.json'
            }
            
            if config_type not in config_files:
                logger.error(f"Nom de fichier inconnu pour le type: {config_type}")
                return False
            
            config_path = self.config_dir / config_files[config_type]
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.configs[config_type], f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration sauvegardée: {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de '{config_type}': {e}")
            return False
    
    def save_all_configs(self):
        """Sauvegarde toutes les configurations"""
        success_count = 0
        for config_type in self.configs.keys():
            if self.save_config(config_type):
                success_count += 1
        
        logger.info(f"Sauvegarde terminée: {success_count}/{len(self.configs)} configurations")
        return success_count == len(self.configs)
    
    def reload_config(self, config_type: str):
        """Recharge une configuration depuis le disque"""
        config_files = {
            'ui': 'ui_config.json',
            'camera': 'camera_config.json',
            'robot': 'robot_config.json', 
            'tracking': 'tracking_config.json'
        }
        
        if config_type in config_files:
            try:
                self.configs[config_type] = self._load_config(config_files[config_type])
                logger.info(f"Configuration '{config_type}' rechargée")
                return True
            except Exception as e:
                logger.error(f"Erreur lors du rechargement de '{config_type}': {e}")
                return False
        else:
            logger.error(f"Type de configuration inconnu: {config_type}")
            return False
    
    def get_all_config_types(self) -> list:
        """Retourne la liste de tous les types de configuration disponibles"""
        return list(self.configs.keys())
    
    def export_config(self, config_type: str, export_path: str):
        """Exporte une configuration vers un fichier spécifique"""
        if config_type not in self.configs:
            logger.error(f"Type de configuration inexistant: {config_type}")
            return False
        
        try:
            export_path = Path(export_path)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(self.configs[config_type], f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration '{config_type}' exportée vers: {export_path}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'export: {e}")
            return False
    
    def import_config(self, config_type: str, import_path: str):
        """Importe une configuration depuis un fichier"""
        try:
            import_path = Path(import_path)
            if not import_path.exists():
                logger.error(f"Fichier d'import inexistant: {import_path}")
                return False
            
            with open(import_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
            
            self.configs[config_type] = imported_config
            logger.info(f"Configuration '{config_type}' importée depuis: {import_path}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'import: {e}")
            return False
    
    def validate_config(self, config_type: str) -> bool:
        """Valide la structure d'une configuration"""
        if config_type not in self.configs:
            return False
        
        config = self.configs[config_type]
        
        # Validation basique : vérifier que c'est un dictionnaire
        if not isinstance(config, dict):
            logger.warning(f"Configuration '{config_type}' n'est pas un dictionnaire")
            return False
        
        # Validations spécifiques par type
        if config_type == 'ui':
            required_keys = ['window', 'tabs', 'theme']
            return all(key in config for key in required_keys)
        
        elif config_type == 'camera':
            return 'realsense' in config or 'usb3_camera' in config
        
        elif config_type == 'tracking':
            return 'aruco' in config or 'reflective_markers' in config
        
        elif config_type == 'robot':
            return 'communication' in config
        
        return True
    
    def __str__(self):
        """Représentation string du ConfigManager"""
        loaded_configs = list(self.configs.keys())
        return f"ConfigManager(configs={loaded_configs}, dir='{self.config_dir}')"
    
    def __repr__(self):
        return self.__str__()


# Fonction utilitaire pour créer une instance globale
_global_config_manager = None

def get_config_manager(config_dir: str = "config") -> ConfigManager:
    """Retourne l'instance globale du ConfigManager (singleton pattern)"""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigManager(config_dir)
    return _global_config_manager


if __name__ == "__main__":
    # Test du ConfigManager
    print("🧪 Test du ConfigManager")
    
    # Créer une instance
    config = ConfigManager()
    
    # Tester la récupération de valeurs
    print(f"Titre de l'application: {config.get('ui', 'window.title', 'Défaut')}")
    print(f"Largeur fenêtre: {config.get('ui', 'window.width', 800)}")
    print(f"FPS RealSense: {config.get('camera', 'realsense.color_stream.fps', 30)}")
    print(f"Taille marqueur ArUco: {config.get('tracking', 'aruco.marker_size', 0.05)}")
    
    # Tester la modification
    config.set('ui', 'window.width', 1600)
    print(f"Nouvelle largeur: {config.get('ui', 'window.width')}")
    
    # Tester la validation
    for config_type in config.get_all_config_types():
        is_valid = config.validate_config(config_type)
        print(f"Configuration '{config_type}': {'✅ Valide' if is_valid else '❌ Invalide'}")
    
    print("\n🎉 ConfigManager testé avec succès !")