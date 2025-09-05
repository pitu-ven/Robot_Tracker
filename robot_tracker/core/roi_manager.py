# core/roi_manager.py
# Version 1.0 - Gestionnaire de ROI interactives
# Modification: Création initiale avec support rectangle et polygone

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ROIType(Enum):
    """Types de ROI supportées"""
    RECTANGLE = "rectangle"
    POLYGON = "polygon"
    CIRCLE = "circle"

@dataclass
class ROI:
    """Représentation d'une région d'intérêt"""
    roi_type: ROIType
    points: List[Tuple[int, int]]
    name: str
    active: bool = True
    color: Tuple[int, int, int] = (255, 255, 0)  # Jaune par défaut
    thickness: int = 2
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class ROIManager:
    """Gestionnaire de régions d'intérêt interactives"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.roi_config = self.config.get('tracking', 'target_detection.roi_management', {})
        
        # Liste des ROI actives
        self.rois: List[ROI] = []
        
        # État de création ROI
        self.is_creating = False
        self.current_roi_type = None
        self.creation_points = []
        self.temp_roi = None
        
        # Configuration couleurs et styles
        self.default_colors = self.roi_config.get('colors', {
            'active_roi': [255, 255, 0],
            'inactive_roi': [128, 128, 128],
            'creation_roi': [0, 255, 255]
        })
        
        self.line_thickness = self.roi_config.get('line_thickness', 2)
        
        # Statistiques
        self.roi_stats = {
            'total_created': 0,
            'active_count': 0,
            'detections_in_roi': 0
        }
        
        logger.info("📐 ROIManager v1.0 initialisé")
    
    def start_roi_creation(self, roi_type: ROIType, name: str = None):
        """Démarre la création d'une nouvelle ROI"""
        if self.is_creating:
            logger.warning("⚠️ Création ROI déjà en cours, abandon de la précédente")
            self.cancel_roi_creation()
        
        self.is_creating = True
        self.current_roi_type = roi_type
        self.creation_points = []
        
        if name is None:
            name = f"{roi_type.value}_{len(self.rois) + 1}"
        
        self.temp_roi_name = name
        
        logger.info(f"📐 Création ROI {roi_type.value} démarrée: {name}")
    
    def add_creation_point(self, point: Tuple[int, int]) -> bool:
        """Ajoute un point à la ROI en cours de création"""
        if not self.is_creating:
            logger.warning("⚠️ Aucune création ROI en cours")
            return False
        
        self.creation_points.append(point)
        logger.debug(f"📍 Point ajouté: {point} ({len(self.creation_points)} points)")
        
        # Logique spécifique par type de ROI
        if self.current_roi_type == ROIType.RECTANGLE:
            if len(self.creation_points) >= 2:
                # Rectangle défini par 2 points opposés
                self._finalize_rectangle_creation()
                return True
        
        elif self.current_roi_type == ROIType.CIRCLE:
            if len(self.creation_points) >= 2:
                # Cercle défini par centre + point sur périmètre
                self._finalize_circle_creation()
                return True
        
        # Pour polygone, continuer jusqu'à double-clic ou clic droit
        return False
    
    def finish_polygon_creation(self):
        """Finalise la création d'un polygone (appelé par double-clic)"""
        if not self.is_creating or self.current_roi_type != ROIType.POLYGON:
            return False
        
        if len(self.creation_points) >= 3:
            roi = ROI(
                roi_type=ROIType.POLYGON,
                points=self.creation_points.copy(),
                name=self.temp_roi_name,
                color=tuple(self.default_colors['active_roi'])
            )
            
            self.rois.append(roi)
            self._finalize_creation()
            logger.info(f"✅ Polygone créé: {roi.name} ({len(roi.points)} points)")
            return True
        else:
            logger.warning("⚠️ Polygone nécessite au moins 3 points")
            return False
    
    def _finalize_rectangle_creation(self):
        """Finalise la création d'un rectangle"""
        if len(self.creation_points) >= 2:
            p1, p2 = self.creation_points[0], self.creation_points[-1]
            
            # Conversion en 4 coins du rectangle
            x1, y1 = min(p1[0], p2[0]), min(p1[1], p2[1])
            x2, y2 = max(p1[0], p2[0]), max(p1[1], p2[1])
            
            rectangle_points = [
                (x1, y1), (x2, y1), (x2, y2), (x1, y2)
            ]
            
            roi = ROI(
                roi_type=ROIType.RECTANGLE,
                points=rectangle_points,
                name=self.temp_roi_name,
                color=tuple(self.default_colors['active_roi'])
            )
            
            self.rois.append(roi)
            self._finalize_creation()
            logger.info(f"✅ Rectangle créé: {roi.name} ({x2-x1}x{y2-y1})")
    
    def _finalize_circle_creation(self):
        """Finalise la création d'un cercle"""
        if len(self.creation_points) >= 2:
            center = self.creation_points[0]
            edge_point = self.creation_points[-1]
            
            # Calcul du rayon
            radius = int(np.sqrt((center[0] - edge_point[0])**2 + (center[1] - edge_point[1])**2))
            
            # Approximation du cercle par un polygone (16 points)
            circle_points = []
            for i in range(16):
                angle = 2 * np.pi * i / 16
                x = int(center[0] + radius * np.cos(angle))
                y = int(center[1] + radius * np.sin(angle))
                circle_points.append((x, y))
            
            roi = ROI(
                roi_type=ROIType.CIRCLE,
                points=circle_points,
                name=self.temp_roi_name,
                color=tuple(self.default_colors['active_roi']),
                metadata={'center': center, 'radius': radius}
            )
            
            self.rois.append(roi)
            self._finalize_creation()
            logger.info(f"✅ Cercle créé: {roi.name} (rayon {radius})")
    
    def _finalize_creation(self):
        """Finalise la création d'une ROI"""
        self.is_creating = False
        self.current_roi_type = None
        self.creation_points = []
        self.temp_roi = None
        self.roi_stats['total_created'] += 1
        self._update_active_count()
    
    def cancel_roi_creation(self):
        """Annule la création ROI en cours"""
        if self.is_creating:
            logger.info("🚫 Création ROI annulée")
            self.is_creating = False
            self.current_roi_type = None
            self.creation_points = []
            self.temp_roi = None
    
    def delete_roi(self, roi_index: int) -> bool:
        """Supprime une ROI par son index"""
        if 0 <= roi_index < len(self.rois):
            deleted_roi = self.rois.pop(roi_index)
            logger.info(f"🗑️ ROI supprimée: {deleted_roi.name}")
            self._update_active_count()
            return True
        return False
    
    def delete_roi_by_name(self, name: str) -> bool:
        """Supprime une ROI par son nom"""
        for i, roi in enumerate(self.rois):
            if roi.name == name:
                deleted_roi = self.rois.pop(i)
                logger.info(f"🗑️ ROI supprimée: {deleted_roi.name}")
                self._update_active_count()
                return True
        return False
    
    def clear_all_rois(self):
        """Supprime toutes les ROI"""
        count = len(self.rois)
        self.rois.clear()
        self._update_active_count()
        logger.info(f"🗑️ Toutes les ROI supprimées ({count})")
    
    def toggle_roi_active(self, roi_index: int) -> bool:
        """Active/désactive une ROI"""
        if 0 <= roi_index < len(self.rois):
            roi = self.rois[roi_index]
            roi.active = not roi.active
            self._update_active_count()
            logger.info(f"🔄 ROI {roi.name}: {'Activée' if roi.active else 'Désactivée'}")
            return True
        return False
    
    def point_in_roi(self, point: Tuple[int, int], roi: ROI) -> bool:
        """Teste si un point est à l'intérieur d'une ROI"""
        if not roi.active:
            return False
        
        x, y = point
        
        if roi.roi_type in [ROIType.RECTANGLE, ROIType.POLYGON, ROIType.CIRCLE]:
            # Utilisation de cv2.pointPolygonTest pour tous les types
            contour = np.array(roi.points, dtype=np.int32)
            result = cv2.pointPolygonTest(contour, (float(x), float(y)), False)
            return result >= 0
        
        return False
    
    def point_in_any_active_roi(self, point: Tuple[int, int]) -> Optional[ROI]:
        """Teste si un point est dans une ROI active, retourne la première trouvée"""
        for roi in self.rois:
            if roi.active and self.point_in_roi(point, roi):
                return roi
        return None
    
    def filter_points_by_rois(self, points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Filtre une liste de points selon les ROI actives"""
        if not self.has_active_rois():
            return points  # Pas de filtrage si aucune ROI active
        
        filtered_points = []
        for point in points:
            if self.point_in_any_active_roi(point):
                filtered_points.append(point)
        
        return filtered_points
    
    def has_active_rois(self) -> bool:
        """Vérifie s'il y a des ROI actives"""
        return any(roi.active for roi in self.rois)
    
    def get_active_rois(self) -> List[ROI]:
        """Retourne la liste des ROI actives"""
        return [roi for roi in self.rois if roi.active]
    
    def _update_active_count(self):
        """Met à jour le compteur de ROI actives"""
        self.roi_stats['active_count'] = sum(1 for roi in self.rois if roi.active)
    
    def draw_rois_on_frame(self, frame: np.ndarray) -> np.ndarray:
        """Dessine toutes les ROI sur un frame"""
        if not self.rois and not self.is_creating:
            return frame
        
        frame_copy = frame.copy()
        
        # Dessiner les ROI existantes
        for roi in self.rois:
            color = roi.color if roi.active else tuple(self.default_colors['inactive_roi'])
            thickness = self.line_thickness
            
            if roi.roi_type == ROIType.RECTANGLE:
                # Rectangle simple
                if len(roi.points) >= 4:
                    pt1 = roi.points[0]
                    pt2 = roi.points[2]  # Point diagonal opposé
                    cv2.rectangle(frame_copy, pt1, pt2, color, thickness)
            
            elif roi.roi_type in [ROIType.POLYGON, ROIType.CIRCLE]:
                # Polygone ou cercle (approximé en polygone)
                if len(roi.points) >= 3:
                    points = np.array(roi.points, dtype=np.int32)
                    cv2.polylines(frame_copy, [points], True, color, thickness)
            
            # Afficher le nom de la ROI
            if roi.points:
                text_pos = (roi.points[0][0], roi.points[0][1] - 10)
                cv2.putText(frame_copy, roi.name, text_pos, 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        # Dessiner la ROI en cours de création
        if self.is_creating and len(self.creation_points) > 0:
            creation_color = tuple(self.default_colors['creation_roi'])
            
            if self.current_roi_type == ROIType.RECTANGLE and len(self.creation_points) >= 1:
                # Preview rectangle en cours
                if len(self.creation_points) == 1:
                    # Juste le premier point
                    cv2.circle(frame_copy, self.creation_points[0], 3, creation_color, -1)
                else:
                    # Rectangle preview
                    p1, p2 = self.creation_points[0], self.creation_points[-1]
                    cv2.rectangle(frame_copy, p1, p2, creation_color, self.line_thickness)
            
            elif self.current_roi_type == ROIType.POLYGON:
                # Lignes du polygone en cours
                if len(self.creation_points) >= 2:
                    points = np.array(self.creation_points, dtype=np.int32)
                    cv2.polylines(frame_copy, [points], False, creation_color, self.line_thickness)
                
                # Points individuels
                for point in self.creation_points:
                    cv2.circle(frame_copy, point, 3, creation_color, -1)
            
            elif self.current_roi_type == ROIType.CIRCLE and len(self.creation_points) >= 1:
                center = self.creation_points[0]
                cv2.circle(frame_copy, center, 3, creation_color, -1)
                
                if len(self.creation_points) >= 2:
                    # Preview cercle
                    edge_point = self.creation_points[-1]
                    radius = int(np.sqrt((center[0] - edge_point[0])**2 + (center[1] - edge_point[1])**2))
                    cv2.circle(frame_copy, center, radius, creation_color, self.line_thickness)
        
        return frame_copy
    
    def save_rois_to_file(self, filepath: str) -> bool:
        """Sauvegarde les ROI dans un fichier JSON"""
        try:
            roi_data = {
                'rois': [],
                'stats': self.roi_stats,
                'config': {
                    'default_colors': self.default_colors,
                    'line_thickness': self.line_thickness
                }
            }
            
            for roi in self.rois:
                roi_dict = {
                    'type': roi.roi_type.value,
                    'points': roi.points,
                    'name': roi.name,
                    'active': roi.active,
                    'color': roi.color,
                    'thickness': roi.thickness,
                    'metadata': roi.metadata or {}
                }
                roi_data['rois'].append(roi_dict)
            
            with open(filepath, 'w') as f:
                json.dump(roi_data, f, indent=2)
            
            logger.info(f"💾 ROI sauvegardées: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde ROI: {e}")
            return False
    
    def load_rois_from_file(self, filepath: str) -> bool:
        """Charge les ROI depuis un fichier JSON"""
        try:
            if not Path(filepath).exists():
                logger.warning(f"⚠️ Fichier ROI inexistant: {filepath}")
                return False
            
            with open(filepath, 'r') as f:
                roi_data = json.load(f)
            
            self.rois.clear()
            
            for roi_dict in roi_data.get('rois', []):
                roi_type = ROIType(roi_dict['type'])
                
                roi = ROI(
                    roi_type=roi_type,
                    points=roi_dict['points'],
                    name=roi_dict['name'],
                    active=roi_dict.get('active', True),
                    color=tuple(roi_dict.get('color', [255, 255, 0])),
                    thickness=roi_dict.get('thickness', 2),
                    metadata=roi_dict.get('metadata', {})
                )
                
                self.rois.append(roi)
            
            # Charger les statistiques si disponibles
            if 'stats' in roi_data:
                self.roi_stats.update(roi_data['stats'])
            
            self._update_active_count()
            logger.info(f"📂 ROI chargées: {filepath} ({len(self.rois)} ROI)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement ROI: {e}")
            return False
    
    def get_roi_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques des ROI"""
        stats = self.roi_stats.copy()
        stats.update({
            'total_rois': len(self.rois),
            'rois_by_type': {
                roi_type.value: sum(1 for roi in self.rois if roi.roi_type == roi_type)
                for roi_type in ROIType
            }
        })
        return stats
    
    def export_rois_summary(self) -> Dict[str, Any]:
        """Exporte un résumé des ROI pour rapports"""
        summary = {
            'total_rois': len(self.rois),
            'active_rois': sum(1 for roi in self.rois if roi.active),
            'rois_by_type': {},
            'roi_details': []
        }
        
        for roi_type in ROIType:
            count = sum(1 for roi in self.rois if roi.roi_type == roi_type)
            if count > 0:
                summary['rois_by_type'][roi_type.value] = count
        
        for roi in self.rois:
            area = self._calculate_roi_area(roi)
            roi_detail = {
                'name': roi.name,
                'type': roi.roi_type.value,
                'active': roi.active,
                'area_pixels': area,
                'points_count': len(roi.points)
            }
            summary['roi_details'].append(roi_detail)
        
        return summary
    
    def _calculate_roi_area(self, roi: ROI) -> float:
        """Calcule l'aire d'une ROI en pixels"""
        if len(roi.points) < 3:
            return 0.0
        
        try:
            contour = np.array(roi.points, dtype=np.int32)
            area = cv2.contourArea(contour)
            return float(area)
        except:
            return 0.0