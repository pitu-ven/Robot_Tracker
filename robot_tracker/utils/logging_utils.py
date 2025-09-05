# robot_tracker/utils/logging_utils.py
# Version 1.0 - Utilitaire de logging centralisé avec contrôle de verbosité
# Modification: Création du module pour gérer les niveaux de verbosité

import logging
import sys
from typing import Dict, Optional


class VerbosityManager:
    """Gestionnaire de verbosité des logs pour Robot Tracker"""
    
    # Mapping des niveaux de verbosité
    VERBOSITY_LEVELS: Dict[str, int] = {
        "Faible": logging.WARNING,    # Erreurs et avertissements uniquement
        "Moyenne": logging.INFO,      # Informations importantes + erreurs/avertissements
        "Debug": logging.DEBUG        # Tous les messages de débogage
    }
    
    @classmethod
    def setup_logging(cls, verbosity: str = "Moyenne", config_manager=None) -> None:
        """Configure le système de logging selon le niveau de verbosité choisi
        
        Args:
            verbosity: Niveau de verbosité ("Faible", "Moyenne", "Debug")
            config_manager: Gestionnaire de configuration optionnel
        """
        # Récupération du niveau de logging
        log_level = cls.VERBOSITY_LEVELS.get(verbosity, logging.INFO)
        
        # Configuration du logging principal
        logging.basicConfig(
            level=log_level,
            format='[%(levelname)s] %(name)s: %(message)s',
            stream=sys.stdout,
            force=True  # Force la reconfiguration si déjà configuré
        )
        
        # Application de filtres spécifiques selon la verbosité
        cls._apply_verbosity_filters(verbosity, config_manager)
        
        # Message de confirmation (seulement si niveau Info ou Debug)
        if log_level <= logging.INFO:
            logger = logging.getLogger(__name__)
            logger.info(f"🔧 Logging configuré en mode '{verbosity}'")
    
    @classmethod
    def _apply_verbosity_filters(cls, verbosity: str, config_manager=None) -> None:
        """Applique des filtres spécifiques selon le niveau de verbosité"""
        
        # Configuration pour verbosité "Faible"
        if verbosity == "Faible":
            # Suppression des logs de débogage des bibliothèques externes
            logging.getLogger('matplotlib').setLevel(logging.WARNING)
            logging.getLogger('PIL').setLevel(logging.WARNING)
            logging.getLogger('urllib3').setLevel(logging.WARNING)
            
        # Configuration pour verbosité "Moyenne"  
        elif verbosity == "Moyenne":
            # Réduction des logs PyQt et OpenCV
            logging.getLogger('PyQt6').setLevel(logging.WARNING)
            logging.getLogger('cv2').setLevel(logging.INFO)
            
        # Configuration pour verbosité "Debug"
        elif verbosity == "Debug":
            # Tous les logs activés, y compris ceux des bibliothèques
            logging.getLogger().setLevel(logging.DEBUG)
    
    @classmethod
    def get_verbosity_from_config(cls, config_manager) -> str:
        """Récupère le niveau de verbosité depuis la configuration
        
        Args:
            config_manager: Instance du ConfigManager
            
        Returns:
            Niveau de verbosité configuré ou "Moyenne" par défaut
        """
        if not config_manager:
            return "Moyenne"
        
        verbosity = config_manager.get('ui', 'logging.console_verbosity', 'Moyenne')
        
        # Validation du niveau
        if verbosity not in cls.VERBOSITY_LEVELS:
            logging.warning(f"⚠️ Niveau de verbosité '{verbosity}' invalide, utilisation de 'Moyenne'")
            return "Moyenne"
            
        return verbosity
    
    @classmethod
    def get_available_levels(cls) -> list:
        """Retourne la liste des niveaux de verbosité disponibles"""
        return list(cls.VERBOSITY_LEVELS.keys())
    
    @classmethod
    def change_verbosity(cls, new_verbosity: str, config_manager=None) -> bool:
        """Change dynamiquement le niveau de verbosité
        
        Args:
            new_verbosity: Nouveau niveau de verbosité
            config_manager: Gestionnaire de configuration optionnel
            
        Returns:
            True si le changement a réussi, False sinon
        """
        if new_verbosity not in cls.VERBOSITY_LEVELS:
            return False
        
        # Reconfiguration du logging
        cls.setup_logging(new_verbosity, config_manager)
        
        # Sauvegarde en configuration si possible
        if config_manager:
            config_manager.set('ui', 'logging.console_verbosity', new_verbosity)
            config_manager.save_config('ui')
        
        return True


def setup_application_logging(config_manager=None) -> None:
    """Point d'entrée principal pour configurer le logging de l'application
    
    Args:
        config_manager: Instance du ConfigManager pour récupérer la configuration
    """
    verbosity = VerbosityManager.get_verbosity_from_config(config_manager)
    VerbosityManager.setup_logging(verbosity, config_manager)


# Fonction utilitaire pour l'affichage des niveaux disponibles
def display_verbosity_info() -> None:
    """Affiche les informations sur les niveaux de verbosité disponibles"""
    print("📋 Niveaux de verbosité disponibles :")
    for level, log_level in VerbosityManager.VERBOSITY_LEVELS.items():
        level_name = logging.getLevelName(log_level)
        print(f"  • {level:8} → {level_name} ({log_level})")