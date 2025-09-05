# robot_tracker/core/config_manager.py
# Version 1.3 - Ajout support verbosité logging
# Modification: Ajout méthodes pour gestion verbosité logging et validation

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union, List

logger = logging.getLogger(__name__)

class ConfigManager:
    """Gestionnaire de configuration principal avec support ArUco et logging"""
    
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
            'aruco': 'aruco_generator.json'
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
    
    def set(self, section: str, key: str, value: Any) -> bool:
        """Définit une valeur de configuration"""
        try:
            # Support spécial ArUco
            if section == 'ui' and key.startswith('aruco_generator.'):
                return self._set_aruco_config(key, value)
            
            # Configuration standard
            if section not in self.configs:
                self.configs[section] = {}
            
            config = self.configs[section]
            key_parts = key.split('.')
            
            # Navigation dans la structure
            current = config
            for part in key_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Définition de la valeur finale
            current[key_parts[-1]] = value
            
            logger.debug(f"Configuration {section}.{key} définie: {value}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur définition {section}.{key}: {e}")
            return False
    
    # === MÉTHODES SPÉCIFIQUES AU LOGGING ===
    
    def get_logging_verbosity(self) -> str:
        """Récupère le niveau de verbosité des logs depuis la configuration
        
        Returns:
            Niveau de verbosité configuré ou "Moyenne" par défaut
        """
        verbosity = self.get('ui', 'logging.console_verbosity', 'Moyenne')
        
        # Validation du niveau
        available_levels = self.get('ui', 'logging.available_levels', ['Faible', 'Moyenne', 'Debug'])
        if verbosity not in available_levels:
            logger.warning(f"Niveau verbosité '{verbosity}' invalide, utilisation de 'Moyenne'")
            return 'Moyenne'
            
        return verbosity
    
    def set_logging_verbosity(self, verbosity: str) -> bool:
        """Définit le niveau de verbosité des logs
        
        Args:
            verbosity: Nouveau niveau de verbosité
            
        Returns:
            True si la définition a réussi, False sinon
        """
        # Validation du niveau
        available_levels = self.get('ui', 'logging.available_levels', ['Faible', 'Moyenne', 'Debug'])
        if verbosity not in available_levels:
            logger.error(f"Niveau verbosité '{verbosity}' invalide. Niveaux disponibles: {available_levels}")
            return False
        
        # Définition de la valeur
        success = self.set('ui', 'logging.console_verbosity', verbosity)
        if success:
            logger.info(f"Niveau de verbosité défini à: {verbosity}")
        
        return success
    
    def get_available_verbosity_levels(self) -> List[str]:
        """Retourne la liste des niveaux de verbosité disponibles"""
        return self.get('ui', 'logging.available_levels', ['Faible', 'Moyenne', 'Debug'])
    
    def get_verbosity_description(self, verbosity: str) -> str:
        """Récupère la description d'un niveau de verbosité
        
        Args:
            verbosity: Niveau de verbosité
            
        Returns:
            Description du niveau ou chaîne vide si non trouvé
        """
        descriptions = self.get('ui', 'logging.descriptions', {})
        return descriptions.get(verbosity, '')
    
    def is_file_logging_enabled(self) -> bool:
        """Vérifie si le logging vers fichier est activé"""
        return self.get('ui', 'logging.file_logging.enabled', True)
    
    def get_log_file_path(self) -> str:
        """Récupère le chemin du fichier de log"""
        return self.get('ui', 'logging.file_logging.log_file', './logs/robot_tracker.log')
    
    # === MÉTHODES ARUCO (inchangées) ===
    
    def _get_aruco_config(self, key: str, default: Any = None) -> Any:
        """Récupère une configuration ArUco spécifique"""
        try:
            if 'aruco' not in self.configs:
                return default
                
            aruco_key = key.replace('aruco_generator.', '')
            key_parts = aruco_key.split('.')
            
            current = self.configs['aruco']['aruco_generator']
            for part in key_parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            
            return current
            
        except Exception as e:
            logger.debug(f"Clé ArUco non trouvée {key}: {e}")
            return default
    
    def _set_aruco_config(self, key: str, value: Any) -> bool:
        """Définit une configuration ArUco spécifique"""
        try:
            if 'aruco' not in self.configs:
                self.configs['aruco'] = {'aruco_generator': {}}
            if 'aruco_generator' not in self.configs['aruco']:
                self.configs['aruco']['aruco_generator'] = {}
            
            aruco_key = key.replace('aruco_generator.', '')
            key_parts = aruco_key.split('.')
            
            # Navigation dans la structure ArUco
            current = self.configs['aruco']['aruco_generator']
            for part in key_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Définition de la valeur finale
            current[key_parts[-1]] = value
            
            logger.debug(f"Configuration ArUco définie {key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur définition ArUco {key}: {e}")
            return False
    
    def get_aruco_config(self) -> Dict[str, Any]:
        """Retourne la configuration ArUco complète"""
        return self.configs.get('aruco', {}).get('aruco_generator', {})
    
    # === MÉTHODES DE SAUVEGARDE ===
    
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
    
    def save_all_configs(self) -> bool:
        """Sauvegarde toutes les configurations"""
        success = True
        for config_type in self.configs.keys():
            if not self.save_config(config_type):
                success = False
        return success
    
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
    
    # === MÉTHODES UTILITAIRES ===
    
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
            required_keys = ['window']
            return all(key in config for key in required_keys)
        
        elif config_type == 'camera':
            return 'realsense' in config or 'usb3_camera' in config
        
        elif config_type == 'tracking':
            return 'aruco' in config or 'reflective_markers' in config
        
        elif config_type == 'robot':
            return 'communication' in config
        
        elif config_type == 'aruco':
            return 'aruco_generator' in config
        
        return True
    
    def get_config_info(self) -> Dict[str, Any]:
        """Retourne des informations sur les configurations chargées"""
        info = {
            'config_dir': str(self.config_dir),
            'loaded_configs': list(self.configs.keys()),
            'config_sizes': {k: len(v) if isinstance(v, dict) else 0 for k, v in self.configs.items()},
            'valid_configs': {k: self.validate_config(k) for k in self.configs.keys()},
            'logging_verbosity': self.get_logging_verbosity(),
            'available_verbosity_levels': self.get_available_verbosity_levels()
        }
        return info
    
    def export_config(self, config_type: str, export_path: str) -> bool:
        """Exporte une configuration vers un fichier"""
        try:
            export_path = Path(export_path)
            if config_type not in self.configs:
                logger.error(f"Type de configuration inconnu: {config_type}")
                return False
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(self.configs[config_type], f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration '{config_type}' exportée vers: {export_path}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'export: {e}")
            return False
    
    def import_config(self, config_type: str, import_path: str) -> bool:
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