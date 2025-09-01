# core/aruco_config_loader.py
# Version 1.1 - Amélioration patterns détection et auto-ouverture dernier dossier
# Modification: Meilleurs patterns de détection + auto-sélection dernier dossier

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ArUcoConfigLoader:
    """Chargeur automatique de configuration ArUco depuis dossier généré"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        # Utilisation du tracking_config.json existant avec section target_detection
        self.aruco_config = self.config.get('tracking', 'target_detection.aruco', {})
        self.detected_markers = {}
        self.folder_path = None
        
        # Dossier racine ArUco pour auto-détection
        self.aruco_root_folder = self.aruco_config.get('default_markers_folder', './ArUco')
        
    def get_latest_aruco_folder(self) -> Optional[str]:
        """Retourne le dossier ArUco le plus récent en cherchant dans les chemins possibles"""
        try:
            # Liste des dossiers à tenter
            search_folders = [self.aruco_root_folder]
            
            # Ajout des dossiers de fallback depuis config
            fallback_folders = self.aruco_config.get('fallback_folders', [])
            search_folders.extend(fallback_folders)
            
            logger.debug(f"🔍 Recherche dans {len(search_folders)} dossiers potentiels")
            
            best_folder = None
            latest_time = 0
            
            for folder_path in search_folders:
                try:
                    root_path = Path(folder_path)
                    if not root_path.exists():
                        logger.debug(f"❌ Dossier inexistant: {root_path}")
                        continue
                    
                    logger.debug(f"✅ Dossier trouvé: {root_path}")
                    
                    # Recherche des sous-dossiers contenant des marqueurs
                    subfolders = []
                    for item in root_path.iterdir():
                        if item.is_dir():
                            # Vérifier s'il contient des images ArUco
                            has_markers = any(
                                file.suffix.lower() in ['.png', '.jpg', '.jpeg'] 
                                for file in item.iterdir() 
                                if file.is_file()
                            )
                            if has_markers:
                                subfolders.append(item)
                                logger.debug(f"📁 Sous-dossier avec marqueurs: {item.name}")
                    
                    # Trouver le plus récent dans ce dossier racine
                    if subfolders:
                        local_latest = max(subfolders, key=lambda x: x.stat().st_mtime)
                        local_time = local_latest.stat().st_mtime
                        
                        if local_time > latest_time:
                            latest_time = local_time
                            best_folder = local_latest
                            logger.debug(f"🎯 Nouveau meilleur dossier: {local_latest}")
                        
                except Exception as e:
                    logger.debug(f"⚠️ Erreur examen dossier {folder_path}: {e}")
                    continue
            
            if best_folder:
                logger.info(f"📁 Dossier ArUco le plus récent trouvé: {best_folder}")
                return str(best_folder)
            else:
                logger.info("ℹ️ Aucun dossier ArUco trouvé avec des marqueurs")
                return None
            
        except Exception as e:
            logger.error(f"❌ Erreur recherche dernier dossier ArUco: {e}")
            return None
    
    def scan_aruco_folder(self, folder_path: str) -> Dict:
        """Scanne un dossier pour détecter les marqueurs ArUco - Version améliorée"""
        self.folder_path = Path(folder_path)
        
        if not self.folder_path.exists():
            logger.warning(f"Dossier ArUco introuvable: {folder_path}")
            return {}
            
        logger.info(f"Scan du dossier ArUco: {folder_path}")
        
        # Extensions supportées depuis config
        extensions = self.aruco_config.get('supported_extensions', ['.png', '.jpg', '.jpeg'])
        
        markers_found = {}
        total_files = 0
        processed_files = 0
        
        # Scan de tous les fichiers avec extensions supportées
        all_files = []
        for ext in extensions:
            pattern = f"*{ext}"
            files = list(self.folder_path.glob(pattern))
            all_files.extend(files)
            
        total_files = len(all_files)
        logger.info(f"🔍 Analyse de {total_files} fichiers potentiels...")
        
        for file_path in all_files:
            processed_files += 1
            logger.debug(f"Analyse fichier {processed_files}/{total_files}: {file_path.name}")
            
            marker_info = self._extract_marker_info(file_path)
            if marker_info:
                marker_id = marker_info['id']
                if marker_id in markers_found:
                    logger.warning(f"⚠️ Marqueur {marker_id} dupliqué - gardé: {marker_info['filename']}")
                markers_found[marker_id] = marker_info
                logger.debug(f"✅ Marqueur {marker_id} détecté: {marker_info['filename']}")
            else:
                logger.debug(f"❌ Impossible d'extraire infos de: {file_path.name}")
                    
        logger.info(f"ArUco: {len(markers_found)} marqueurs détectés sur {total_files} fichiers")
        
        # Analyse du dossier pour détecter le type de dictionnaire
        if markers_found:
            detected_dict = self._detect_dictionary_from_folder_name()
            if detected_dict:
                logger.info(f"🎯 Dictionnaire détecté depuis nom dossier: {detected_dict}")
                # Mise à jour config temporaire
                for marker in markers_found.values():
                    marker['dictionary'] = detected_dict
        
        self.detected_markers = markers_found
        return markers_found
    
    def _extract_marker_info(self, file_path: Path) -> Optional[Dict]:
        """Extrait les informations d'un marqueur depuis le nom de fichier - Version étendue"""
        filename = file_path.stem
        
        # Patterns étendus pour extraction métadonnées
        patterns = [
            # Pattern spécifique pour le format du générateur ArUco
            r'aruco_DICT_(\w+)_(\d+)',              # aruco_DICT_4X4_50_0000 → dict=4X4_50, id=0000
            
            # Patterns générateur ArUco standard
            r'aruco_marker_(\d+)',                  # aruco_marker_0042.png
            r'marker_(\d+)',                        # marker_42.png
            
            # Patterns avec dictionnaire
            r'aruco_(\d+)_(\d+)x(\d+)_dict_(\w+)',  # aruco_5_100x100_dict_4X4_50
            r'marker_(\d+)_(\d+)_(\w+)',            # marker_5_100_4X4_50
            
            # Patterns avec taille
            r'id(\d+)_(\d+)x(\d+)',                 # id5_100x100
            r'(\d+)_(\d+)x(\d+)',                   # 5_100x100
            r'aruco_(\d+)_(\d+)px',                 # aruco_5_200px
            
            # Patterns simples
            r'id_?(\d+)',                           # id_42 ou id42
            r'^(\d+)$',                            # 42.png (juste le numéro)
            r'aruco_?(\d+)',                       # aruco_42 ou aruco42
            
            # Patterns complexes du générateur
            r'aruco_(\d+)_(\w+)_(\d+)px',          # aruco_5_5X5_100_200px
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                try:
                    # Traitement spécial pour le premier pattern (vos fichiers)
                    if i == 0:  # Pattern aruco_DICT_(\w+)_(\d+)
                        dict_type = groups[0].replace('_', 'X')  # 4X4_50 → 4X4_50
                        marker_id = int(groups[1])
                        size = self._extract_size_from_folder_name()  # Taille depuis nom dossier
                        
                        marker_info = {
                            'id': marker_id,
                            'file_path': str(file_path),
                            'size_mm': size,
                            'dictionary': dict_type,
                            'filename': filename,
                            'enabled': True,
                            'detection_params': self._get_optimized_params(marker_id, size),
                            'pattern_used': i,
                            'file_size_bytes': file_path.stat().st_size,
                            'modification_time': file_path.stat().st_mtime
                        }
                        
                        logger.debug(f"✅ Pattern {i} réussi pour {filename}: ID={marker_id}, Dict={dict_type}")
                        return marker_info
                    
                    else:
                        # Traitement normal pour les autres patterns
                        marker_id = int(groups[0])
                        size = self._extract_size_from_groups(groups, filename)
                        dict_type = self._extract_dictionary_from_groups(groups, filename)
                        
                        marker_info = {
                            'id': marker_id,
                            'file_path': str(file_path),
                            'size_mm': size,
                            'dictionary': dict_type,
                            'filename': filename,
                            'enabled': True,
                            'detection_params': self._get_optimized_params(marker_id, size),
                            'pattern_used': i,
                            'file_size_bytes': file_path.stat().st_size,
                            'modification_time': file_path.stat().st_mtime
                        }
                        
                        logger.debug(f"✅ Pattern {i} réussi pour {filename}: ID={marker_id}")
                        return marker_info
                        
                except (ValueError, IndexError) as e:
                    logger.debug(f"⚠️ Pattern {i} partiellement réussi mais erreur extraction: {e}")
                    continue
                
        logger.debug(f"❌ Aucun pattern ne correspond à: {filename}")
        return None
    
    def _extract_size_from_groups(self, groups: tuple, filename: str) -> int:
        """Extrait la taille depuis les groupes de regex"""
        # Recherche dans les groupes
        for group in groups:
            try:
                # Si le groupe ressemble à une taille (50-500)
                val = int(group)
                if 20 <= val <= 1000:  # Taille raisonnable pour un marqueur
                    return val
            except (ValueError, TypeError):
                continue
        
        # Recherche dans le nom de fichier
        size_match = re.search(r'(\d+)px', filename, re.IGNORECASE)
        if size_match:
            try:
                return int(size_match.group(1))
            except ValueError:
                pass
        
        # Recherche dans le nom du dossier parent
        parent_name = self.folder_path.name if self.folder_path else ""
        folder_size_match = re.search(r'(\d+)px', parent_name, re.IGNORECASE)
        if folder_size_match:
            try:
                return int(folder_size_match.group(1))
            except ValueError:
                pass
        
        # Valeur par défaut
        return 100
    
    def _extract_dictionary_from_groups(self, groups: tuple, filename: str) -> str:
        """Extrait le type de dictionnaire depuis les groupes ou contexte"""
        # Recherche dans les groupes
        for group in groups:
            if isinstance(group, str):
                # Patterns de dictionnaire
                if re.match(r'\d+X\d+_\d+', group, re.IGNORECASE):
                    return group.upper()
                if 'X' in group.upper() and any(char.isdigit() for char in group):
                    return group.upper()
        
        # Recherche dans le nom de fichier
        dict_match = re.search(r'(\d+X\d+_\d+)', filename, re.IGNORECASE)
        if dict_match:
            return dict_match.group(1).upper()
        
        # Recherche dans le nom du dossier
        return self._detect_dictionary_from_folder_name()
    
    def _detect_dictionary_from_folder_name(self) -> str:
        """Détecte le type de dictionnaire depuis le nom du dossier"""
        if not self.folder_path:
            return "4X4_50"  # Par défaut
        
        folder_name = self.folder_path.name
        
        # Patterns pour dictionnaires dans le nom de dossier
        dict_patterns = [
            r'(\d+X\d+_\d+)',           # 5X5_100
            r'(\d+x\d+_\d+)',           # 5x5_100 (minuscule)
            r'dict_(\d+X\d+_\d+)',      # dict_5X5_100
        ]
        
        for pattern in dict_patterns:
            match = re.search(pattern, folder_name, re.IGNORECASE)
            if match:
                detected = match.group(1).upper().replace('x', 'X')
                logger.debug(f"🎯 Dictionnaire détecté depuis dossier: {detected}")
                return detected
        
        # Analyse heuristique basée sur le nom
        if '5X5' in folder_name.upper() or '5x5' in folder_name:
            return "5X5_100"
        elif '6X6' in folder_name.upper() or '6x6' in folder_name:
            return "6X6_250"
        elif '7X7' in folder_name.upper() or '7x7' in folder_name:
            return "7X7_1000"
        
        # Par défaut
        return "4X4_50"
    
    def _get_optimized_params(self, marker_id: int, size_mm: int) -> Dict:
        """Génère des paramètres de détection optimisés selon la taille"""
        base_params = self.aruco_config.get('detection_params', {}).copy()
        
        # Ajustements selon la taille du marqueur
        if size_mm < 50:
            # Petits marqueurs: plus sensible
            base_params.update({
                'minMarkerPerimeterRate': 0.01,
                'maxMarkerPerimeterRate': 3.0,
                'adaptiveThreshWinSizeMin': 3,
                'adaptiveThreshWinSizeMax': 15
            })
        elif size_mm > 200:
            # Grands marqueurs: moins sensible mais plus stable
            base_params.update({
                'minMarkerPerimeterRate': 0.05,
                'maxMarkerPerimeterRate': 6.0,
                'adaptiveThreshWinSizeMin': 5,
                'adaptiveThreshWinSizeMax': 35
            })
        else:
            # Taille normale
            base_params.update({
                'minMarkerPerimeterRate': 0.03,
                'maxMarkerPerimeterRate': 4.0,
                'adaptiveThreshWinSizeMin': 3,
                'adaptiveThreshWinSizeMax': 23
            })
            
        return base_params
    
    def generate_config_file(self, save_path: Optional[str] = None) -> str:
        """Génère le fichier de configuration depuis les marqueurs détectés"""
        if not self.detected_markers:
            raise ValueError("Aucun marqueur détecté pour générer la configuration")
            
        config_data = {
            '_metadata': {
                'generated_at': datetime.now().isoformat(),
                'source_folder': str(self.folder_path),
                'total_markers': len(self.detected_markers),
                'version': '1.1',
                'generator': 'ArUcoConfigLoader'
            },
            'markers': self.detected_markers,
            'detection_settings': {
                'dictionary_type': self._detect_common_dictionary(),
                'detection_params': self._get_global_optimized_params(),
                'display_settings': self.config.get('tracking', 'target_tab_ui.display', {})
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
        """Détecte le type de dictionnaire le plus utilisé dans les marqueurs"""
        if not self.detected_markers:
            return self._detect_dictionary_from_folder_name()
        
        dict_counts = {}
        
        for marker in self.detected_markers.values():
            dict_type = marker.get('dictionary', '4X4_50')
            dict_counts[dict_type] = dict_counts.get(dict_type, 0) + 1
            
        if dict_counts:
            most_common = max(dict_counts.items(), key=lambda x: x[1])
            logger.info(f"📊 Dictionnaire majoritaire: {most_common[0]} ({most_common[1]} marqueurs)")
            return most_common[0]
            
        return self._detect_dictionary_from_folder_name()
    
    def _get_global_optimized_params(self) -> Dict:
        """Génère des paramètres globaux optimisés basés sur tous les marqueurs"""
        if not self.detected_markers:
            return self.aruco_config.get('detection_params', {})
        
        # Analyse des tailles
        sizes = [marker['size_mm'] for marker in self.detected_markers.values()]
        min_size = min(sizes)
        max_size = max(sizes)
        avg_size = sum(sizes) / len(sizes)
        
        logger.info(f"📏 Tailles marqueurs: min={min_size}, max={max_size}, moy={avg_size:.1f}")
        
        # Paramètres adaptés à la plage de tailles
        base_params = self.aruco_config.get('detection_params', {}).copy()
        
        if max_size - min_size > 100:
            # Grande variation de tailles: paramètres tolérants
            base_params.update({
                'minMarkerPerimeterRate': 0.01,
                'maxMarkerPerimeterRate': 8.0,
                'adaptiveThreshWinSizeMin': 3,
                'adaptiveThreshWinSizeMax': 45
            })
        elif avg_size < 100:
            # Marqueurs plutôt petits
            base_params.update({
                'minMarkerPerimeterRate': 0.02,
                'maxMarkerPerimeterRate': 4.0,
                'adaptiveThreshWinSizeMin': 3,
                'adaptiveThreshWinSizeMax': 20
            })
        else:
            # Marqueurs standards
            base_params.update({
                'minMarkerPerimeterRate': 0.03,
                'maxMarkerPerimeterRate': 5.0,
                'adaptiveThreshWinSizeMin': 3,
                'adaptiveThreshWinSizeMax': 30
            })
        
        return base_params
    
    def load_existing_config(self, config_path: str) -> Dict:
        """Charge une configuration existante"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info(f"✅ Configuration ArUco chargée: {config_path}")
                return config
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"❌ Erreur chargement config ArUco: {e}")
            return {}
    
    def validate_markers(self) -> Tuple[int, List[str]]:
        """Valide les marqueurs détectés et retourne les problèmes"""
        valid_count = 0
        issues = []
        
        for marker_id, marker_info in self.detected_markers.items():
            # Vérification fichier existe
            if not Path(marker_info['file_path']).exists():
                issues.append(f"Fichier manquant pour marqueur {marker_id}")
                continue
                
            # Vérification taille raisonnable
            size = marker_info.get('size_mm', 0)
            if size < 10 or size > 1000:
                issues.append(f"Marqueur {marker_id}: taille suspecte ({size}mm)")
            
            # Vérification unicité ID
            duplicate_ids = [mid for mid, minfo in self.detected_markers.items() 
                           if mid != marker_id and minfo.get('id') == marker_id]
            if duplicate_ids:
                issues.append(f"ID {marker_id} dupliqué")
                
            valid_count += 1
        
        return valid_count, issues
    
    def get_detector_params(self) -> Dict:
        """Retourne les paramètres pour le détecteur"""
        if self.detected_markers:
            return self._get_global_optimized_params()
        else:
            return self.aruco_config.get('detection_params', {})
        
    def _extract_size_from_folder_name(self) -> int:
        """Extrait la taille depuis le nom du dossier"""
        if not self.folder_path:
            return 100
        
        folder_name = self.folder_path.name
        
        # Recherche dans le nom du dossier : 4X4_50_500px
        size_match = re.search(r'(\d+)px', folder_name, re.IGNORECASE)
        if size_match:
            try:
                return int(size_match.group(1))
            except ValueError:
                pass
        
        # Fallback : recherche d'un nombre qui pourrait être une taille
        numbers = re.findall(r'\d+', folder_name)
        for num_str in reversed(numbers):  # Prendre le dernier nombre (souvent la taille)
            num = int(num_str)
            if 50 <= num <= 1000:  # Taille raisonnable
                return num
        
        return 100  # Par défaut