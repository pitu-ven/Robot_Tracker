# robot_tracker/core/config_manager.py
# Version 1.1 - Intégration support ArUco
# Modification: Ajout support fichiers de configuration multiples

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

class ConfigManager:
    """Gestionnaire de configuration principal avec support ArUco"""
    
    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent.parent / "config"
        self.configs = {}
        self.aruco_config = None
        
        # Chargement des configurations
        self.load_all_configs()
    
    def load_all_configs(self):
        """Charge toutes les configurations disponibles"""
        config_files = {
            'ui': 'ui_config.json',
            'camera': 'camera_config.json', 
            'tracking': 'tracking_config.json',
            'robot': 'robot_config.json',
            'aruco': 'aruco_generator.json'  # Nouveau
        }
        
        for config_type, filename in config_files.items():
            config_path = self.config_dir / filename
            
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        self.configs[config_type] = json.load(f)
                    logger.info(f"Configuration {config_type} chargée")
                except Exception as e:
                    logger.error(f"Erreur chargement {config_type}: {e}")
                    self.configs[config_type] = {}
            else:
                logger.warning(f"Fichier manquant: {filename}")
                self.configs[config_type] = {}
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Récupère une valeur de configuration avec support ArUco"""
        try:
            # Support spécial ArUco
            if section == 'ui' and key.startswith('aruco_generator.'):
                return self._get_aruco_config(key, default)
            
            # Configuration standard
            if section in self.configs:
                config = self.configs[section]
                key_parts = key.split('.')
                
                value = config
                for part in key_parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        return default
                return value
            
            return default
            
        except Exception as e:
            logger.debug(f"Clé non trouvée {section}.{key}: {e}")
            return default
    
    def _get_aruco_config(self, key: str, default: Any = None) -> Any:
        """Récupère une configuration ArUco spécifique"""
        if 'aruco' not in self.configs:
            return default
        
        # Conversion du format ui.aruco_generator.xxx vers aruco_generator.xxx
        aruco_key = key.replace('aruco_generator.', '')
        key_parts = aruco_key.split('.')
        
        value = self.configs['aruco'].get('aruco_generator', {})
        for part in key_parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        
        return value
    
    def get_aruco_config(self) -> Dict[str, Any]:
        """Retourne la configuration ArUco complète"""
        return self.configs.get('aruco', {}).get('aruco_generator', {})
    
    def save_config(self, config_type: str) -> bool:
        """Sauvegarde une configuration spécifique"""
        if config_type not in self.configs:
            logger.error(f"Type de configuration inconnu: {config_type}")
            return False
        
        filename_map = {
            'ui': 'ui_config.json',
            'camera': 'camera_config.json',
            'tracking': 'tracking_config.json', 
            'robot': 'robot_config.json',
            'aruco': 'aruco_generator.json'
        }
        
        filename = filename_map.get(config_type)
        if not filename:
            logger.error(f"Pas de fichier défini pour: {config_type}")
            return False
        
        try:
            config_path = self.config_dir / filename
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.configs[config_type], f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration {config_type} sauvegardée")
            return True
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde {config_type}: {e}")
            return False
    
    def reload_config(self, config_type: str) -> bool:
        """Recharge une configuration spécifique"""
        filename_map = {
            'ui': 'ui_config.json',
            'camera': 'camera_config.json',
            'tracking': 'tracking_config.json',
            'robot': 'robot_config.json', 
            'aruco': 'aruco_generator.json'
        }
        
        filename = filename_map.get(config_type)
        if not filename:
            return False
        
        config_path = self.config_dir / filename
        if not config_path.exists():
            return False
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.configs[config_type] = json.load(f)
            logger.info(f"Configuration {config_type} rechargée")
            return True
        except Exception as e:
            logger.error(f"Erreur rechargement {config_type}: {e}")
            return False