# core/aruco_config_loader.py
# Version 1.0 - Création du chargeur de configuration ArUco automatique
# Modification: Implémentation scanner dossier ArUco et extraction métadonnées

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import logging

logger = logging.getLogger(__name__)

class ArUcoConfigLoader:
    """Chargeur automatique de configuration ArUco depuis dossier généré"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        # Utilisation du tracking_config.json existant avec section target_detection
        self.aruco_config = self.config.get('tracking', 'target_detection.aruco', {})
        self.detected_markers = {}
        self.folder_path = None
        
    def scan_aruco_folder(self, folder_path: str) -> Dict:
        """Scanne un dossier pour détecter les marqueurs ArUco"""
        self.folder_path = Path(folder_path)
        
        if not self.folder_path.exists():
            logger.warning(f"Dossier ArUco introuvable: {folder_path}")
            return {}
            
        logger.info(f"Scan du dossier ArUco: {folder_path}")
        
        # Extensions supportées depuis config
        extensions = self.aruco_config.get('supported_extensions', ['.png', '.jpg', '.jpeg'])
        
        markers_found = {}
        total_files = 0
        
        for ext in extensions:
            pattern = f"*{ext}"
            files = list(self.folder_path.glob(pattern))
            total_files += len(files)
            
            for file_path in files:
                marker_info = self._extract_marker_info(file_path)
                if marker_info:
                    markers_found[marker_info['id']] = marker_info
                    
        logger.info(f"ArUco: {len(markers_found)} marqueurs détectés sur {total_files} fichiers")
        self.detected_markers = markers_found
        return markers_found
    
    def _extract_marker_info(self, file_path: Path) -> Optional[Dict]:
        """Extrait les informations d'un marqueur depuis le nom de fichier"""
        filename = file_path.stem
        
        # Patterns communs pour extraction métadonnées
        patterns = [
            r'aruco_(\d+)_(\d+)x(\d+)_dict_(\w+)',  # aruco_5_100x100_dict_4X4_50
            r'marker_(\d+)_(\d+)_(\w+)',            # marker_5_100_4X4_50
            r'id(\d+)_(\d+)x(\d+)',                 # id5_100x100
            r'(\d+)_(\d+)x(\d+)',                   # 5_100x100
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                # Extraction basique: ID + taille
                marker_id = int(groups[0])
                
                # Taille (si disponible)
                size = 100  # Par défaut
                if len(groups) >= 3:
                    try:
                        size = int(groups[1])
                    except (ValueError, IndexError):
                        pass
                
                # Dictionnaire (si disponible)
                dict_type = "4X4_50"  # Par défaut
                if len(groups) >= 4:
                    dict_type = groups[-1]
                
                marker_info = {
                    'id': marker_id,
                    'file_path': str(file_path),
                    'size_mm': size,
                    'dictionary': dict_type,
                    'filename': filename,
                    'enabled': True,
                    'detection_params': self._get_optimized_params(marker_id, size)
                }
                
                return marker_info
                
        logger.debug(f"Impossible d'extraire les infos de: {filename}")
        return None
    
    def _get_optimized_params(self, marker_id: int, size_mm: int) -> Dict:
        """Génère des paramètres de détection optimisés"""
        base_params = self.aruco_config.get('detection_params', {})
        
        # Ajustements selon la taille
        if size_mm < 50:
            # Petits marqueurs: plus sensible
            base_params['minMarkerPerimeterRate'] = 0.01
            base_params['maxMarkerPerimeterRate'] = 3.0
        elif size_mm > 200:
            # Grands marqueurs: moins sensible
            base_params['minMarkerPerimeterRate'] = 0.05
            base_params['maxMarkerPerimeterRate'] = 5.0
            
        return base_params
    
    def generate_config_file(self, save_path: Optional[str] = None) -> str:
        """Génère le fichier de configuration depuis les marqueurs détectés"""
        if not self.detected_markers:
            raise ValueError("Aucun marqueur détecté pour générer la configuration")
            
        config_data = {
            '_metadata': {
                'generated_at': pd.Timestamp.now() if hasattr(pd, 'Timestamp') else pd.now(),
                'source_folder': str(self.folder_path),
                'total_markers': len(self.detected_markers),
                'version': '1.0'
            },
            'markers': self.detected_markers,
            'detection_settings': {
                'dictionary_type': self._detect_common_dictionary(),
                'detection_params': self.aruco_config.get('detection_params', {}),
                'display_settings': self.config.get('target_tab', 'display', {})
            }
        }
        
        # Chemin de sauvegarde
        if not save_path:
            config_filename = self.aruco_config.get('config_file_name', 'markers_config.json')
            save_path = self.folder_path / config_filename
            
        # Sauvegarde
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Configuration ArUco sauvée: {save_path}")
        return str(save_path)
    
    def _detect_common_dictionary(self) -> str:
        """Détecte le type de dictionnaire le plus utilisé"""
        dict_counts = {}
        
        for marker in self.detected_markers.values():
            dict_type = marker.get('dictionary', '4X4_50')
            dict_counts[dict_type] = dict_counts.get(dict_type, 0) + 1
            
        if dict_counts:
            most_common = max(dict_counts.items(), key=lambda x: x[1])
            return most_common[0]
            
        return "4X4_50"  # Par défaut
    
    def load_existing_config(self, config_path: str) -> Dict:
        """Charge une configuration existante"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Erreur chargement config ArUco: {e}")
            return {}
    
    def validate_markers(self) -> Tuple[int, List[str]]:
        """Valide les marqueurs détectés"""
        valid_count = 0
        issues = []
        
        for marker_id, marker_info in self.detected_markers.items():
            # Vérification fichier
            if not Path(marker_info['file_path']).exists():
                issues.append(f"Fichier manquant pour marqueur {marker_id}")
                continue
                
            # Vérification ID unique
            if list(self.detected_markers.keys()).count(marker_id) > 1:
                issues.append(f"ID {marker_id} dupliqué")
                continue
                
            valid_count += 1
            
        return valid_count, issues
    
    def get_summary(self) -> Dict:
        """Retourne un résumé des marqueurs détectés"""
        if not self.detected_markers:
            return {'status': 'empty', 'message': 'Aucun marqueur détecté'}
            
        valid_count, issues = self.validate_markers()
        
        return {
            'status': 'ready' if not issues else 'warning',
            'total_markers': len(self.detected_markers),
            'valid_markers': valid_count,
            'issues': issues,
            'folder_path': str(self.folder_path),
            'dictionary_type': self._detect_common_dictionary(),
            'size_range': self._get_size_range()
        }
    
    def _get_size_range(self) -> Tuple[int, int]:
        """Retourne la plage de tailles des marqueurs"""
        if not self.detected_markers:
            return (0, 0)
            
        sizes = [m.get('size_mm', 100) for m in self.detected_markers.values()]
        return (min(sizes), max(sizes))

# Import conditionnel pour éviter erreur si pandas pas installé
try:
    import pandas as pd
except ImportError:
    # Fallback si pandas non disponible
    from datetime import datetime
    
    class MockPandas:
        """Mock de pandas.Timestamp pour éviter la dépendance"""
        @staticmethod
        def now():
            return datetime.now().isoformat()
    
    class MockTimestamp:
        """Mock de pandas.Timestamp"""
        @staticmethod
        def now():
            return datetime.now().isoformat()
    
    pd = MockPandas()
    pd.Timestamp = MockTimestamp