# core/roi_manager.py
# Version 1.2 - Version complète corrigée avec debug
# Modification: Intégration complète des corrections et debug détaillé

import json
import numpy as np
import cv2
import time
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ROIType(Enum):
    """Types de ROI supportées"""
    RECTANGLE = "rectangle"
    POLYGON = "polygon"
    CIRCLE = "circle"

class ROIState(Enum):
    """États d'une ROI"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EDITING = "editing"
    SELECTED = "selected"

@dataclass
class ROI:
    """Région d'intérêt"""
    id: int
    name: str
    roi_type: ROIType
    points: List[Tuple[int, int]]
    state: ROIState = ROIState.ACTIVE
    color: Tuple[int, int, int] = (255, 255, 0)
    thickness: int = 2
    filled: bool = False
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class ROIManager:
    """Gestionnaire des Régions d'Intérêt"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        # Utilisation du tracking_config.json existant
        self.roi_config = self.config.get('tracking', 'target_tab_ui.roi', {})
        self.ui_config = self.config.get('tracking', 'target_tab_ui', {})
        
        # État du gestionnaire
        self.rois: List[ROI] = []
        self.selected_roi_id: Optional[int] = None
        self.next_roi_id = 1
        self.is_creating = False
        self.creation_type = ROIType.RECTANGLE
        self.temp_points: List[Tuple[int, int]] = []
        
        # Configuration d'affichage depuis tracking_config.json
        display_config = self.ui_config.get('display', {})
        self.colors = display_config.get('colors', {})
        self.default_thickness = self.roi_config.get('line_thickness', 2)
        self.handle_size = self.roi_config.get('selection_handles_size', 8)
        self.snap_distance = self.roi_config.get('snap_distance', 10)
        self.max_roi_count = self.roi_config.get('max_roi_count', 10)
        
        logger.info("ROIManager initialisé")

    def _convert_roi_type_from_string(self, roi_type_str: str) -> Optional[ROIType]:
        """Convertit une chaîne en ROIType enum avec gestion d'erreurs"""
        if not isinstance(roi_type_str, str):
            logger.error(f"❌ _convert_roi_type_from_string: Paramètre n'est pas string: {type(roi_type_str)}")
            return None
            
        mapping = {
            'rectangle': ROIType.RECTANGLE,
            'polygon': ROIType.POLYGON,
            'circle': ROIType.CIRCLE,
            # Ajout variantes possibles
            'rect': ROIType.RECTANGLE,
            'poly': ROIType.POLYGON,
            'octagon': ROIType.POLYGON,  # Si utilisé ailleurs
        }
        
        key = roi_type_str.lower().strip()
        result = mapping.get(key)
        
        if result is None:
            logger.error(f"❌ Type ROI non reconnu: '{roi_type_str}' - Types supportés: {list(mapping.keys())}")
            
        return result
    
    def start_roi_creation(self, roi_type) -> bool:
        """Démarre la création d'une nouvelle ROI"""
        logger.info(f"🔍 DEBUG ROIManager: Demande création type='{roi_type}' (type Python: {type(roi_type)})")
        
        if len(self.rois) >= self.max_roi_count:
            logger.warning(f"Limite de {self.max_roi_count} ROI atteinte")
            return False
            
        if self.is_creating:
            logger.info("🔍 DEBUG: Annulation création précédente en cours")
            self.cancel_roi_creation()
        
        # Support string et enum avec debug détaillé
        original_roi_type = roi_type
        if isinstance(roi_type, str):
            logger.info(f"🔍 DEBUG: Conversion string '{roi_type}' vers enum")
            roi_type = self._convert_roi_type_from_string(roi_type)
            logger.info(f"🔍 DEBUG: Résultat conversion: {roi_type}")
        elif isinstance(roi_type, ROIType):
            logger.info(f"🔍 DEBUG: Type déjà enum ROIType: {roi_type}")
        else:
            logger.error(f"❌ Type ROI invalide: {type(roi_type)} - Valeur: {roi_type}")
            return False
            
        if roi_type is None:
            logger.error(f"❌ Conversion ROI échouée pour: '{original_roi_type}'")
            return False
            
        # Mise à jour état
        self.is_creating = True
        self.creation_type = roi_type
        self.temp_points = []
        
        logger.info(f"✅ Création ROI {roi_type.value} démarrée (is_creating={self.is_creating})")
        return True
    
    def add_creation_point(self, point: Tuple[int, int]) -> bool:
        """Ajoute un point lors de la création avec debug"""
        logger.info(f"🔍 DEBUG: add_creation_point appelée - is_creating={self.is_creating}, point={point}")
        
        if not self.is_creating:
            logger.warning("⚠️ add_creation_point: Mode création non actif")
            return False
            
        if not isinstance(point, tuple) or len(point) != 2:
            logger.error(f"❌ Point invalide: {point} (type: {type(point)})")
            return False
            
        try:
            snapped_point = self._snap_to_grid(point)
            logger.info(f"🔍 DEBUG: Point snappé: {point} -> {snapped_point}")
            
            if self.creation_type == ROIType.RECTANGLE:
                if len(self.temp_points) == 0:
                    self.temp_points.append(snapped_point)
                    logger.info(f"🔍 DEBUG: Premier point rectangle ajouté: {snapped_point}")
                    return False  # Continuer
                elif len(self.temp_points) == 1:
                    # Completion rectangle avec deux points diagonaux
                    self.temp_points.append(snapped_point)
                    logger.info(f"🔍 DEBUG: Second point rectangle, finalisation: {snapped_point}")
                    self._complete_rectangle_creation()
                    return True  # ROI terminée
                    
            elif self.creation_type == ROIType.POLYGON:
                self.temp_points.append(snapped_point)
                logger.info(f"🔍 DEBUG: Point polygone ajouté: {snapped_point} (total: {len(self.temp_points)})")
                return False  # Continuer
                
            elif self.creation_type == ROIType.CIRCLE:
                if len(self.temp_points) == 0:
                    self.temp_points.append(snapped_point)  # Centre
                    logger.info(f"🔍 DEBUG: Centre cercle défini: {snapped_point}")
                    return False  # Continuer
                elif len(self.temp_points) == 1:
                    self.temp_points.append(snapped_point)  # Point sur le cercle
                    logger.info(f"🔍 DEBUG: Rayon cercle défini: {snapped_point}")
                    self._complete_circle_creation()
                    return True  # ROI terminée
                    
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur add_creation_point: {e}")
            return False
    
    def complete_polygon_creation(self) -> bool:
        """Termine la création d'un polygone"""
        if not self.is_creating or self.creation_type != ROIType.POLYGON:
            return False
            
        if len(self.temp_points) < 3:
            logger.warning("Polygone: minimum 3 points requis")
            return False
            
        self._create_roi_from_temp_points()
        return True
    
    def cancel_roi_creation(self):
        """Annule la création en cours"""
        self.is_creating = False
        self.temp_points = []
        logger.info("Création ROI annulée")
    
    def _complete_rectangle_creation(self):
        """Termine la création d'un rectangle avec debug"""
        logger.info(f"🔍 DEBUG: _complete_rectangle_creation - temp_points={self.temp_points}")
        
        if len(self.temp_points) != 2:
            logger.error(f"❌ Rectangle: Nombre de points invalide: {len(self.temp_points)}")
            return
            
        try:
            # Conversion en 4 points rectangle
            p1, p2 = self.temp_points
            rect_points = [
                (min(p1[0], p2[0]), min(p1[1], p2[1])),  # Top-left
                (max(p1[0], p2[0]), min(p1[1], p2[1])),  # Top-right
                (max(p1[0], p2[0]), max(p1[1], p2[1])),  # Bottom-right
                (min(p1[0], p2[0]), max(p1[1], p2[1]))   # Bottom-left
            ]
            
            self.temp_points = rect_points
            logger.info(f"🔍 DEBUG: Rectangle converti en 4 points: {rect_points}")
            
            self._create_roi_from_temp_points()
            
        except Exception as e:
            logger.error(f"❌ Erreur completion rectangle: {e}")
    
    def _complete_circle_creation(self):
        """Termine la création d'un cercle"""
        if len(self.temp_points) == 2:
            center, edge = self.temp_points
            radius = int(np.linalg.norm(np.array(edge) - np.array(center)))
            
            # Génération points cercle (approximation polygonale)
            angles = np.linspace(0, 2*np.pi, 32, endpoint=False)
            circle_points = []
            
            for angle in angles:
                x = int(center[0] + radius * np.cos(angle))
                y = int(center[1] + radius * np.sin(angle))
                circle_points.append((x, y))
                
            self.temp_points = circle_points
            self._create_roi_from_temp_points()
    
    def _create_roi_from_temp_points(self):
        """Crée une ROI depuis les points temporaires avec debug"""
        logger.info(f"🔍 DEBUG: _create_roi_from_temp_points - {len(self.temp_points)} points")
        
        if not self.temp_points:
            logger.error("❌ Aucun point temporaire pour créer ROI")
            return
            
        try:
            roi_name = f"ROI_{self.next_roi_id}"
            
            # Couleur par défaut selon le type
            color_key = f"roi_{self.creation_type.value}"
            default_color = [255, 255, 0]  # Jaune par défaut
            roi_color = tuple(self.colors.get(color_key, default_color))
            
            roi = ROI(
                id=self.next_roi_id,
                name=roi_name,
                roi_type=self.creation_type,
                points=self.temp_points.copy(),
                color=roi_color,
                thickness=self.default_thickness,
                metadata={
                    'created_at': time.time(),
                    'area': self._calculate_area(self.temp_points)
                }
            )
            
            self.rois.append(roi)
            logger.info(f"✅ ROI créée: {roi.name} (type={roi.roi_type.value}, points={len(roi.points)})")
            
            self.next_roi_id += 1
            
            # Nettoyage
            self.is_creating = False
            self.temp_points = []
            
            logger.info(f"🔍 DEBUG: État après création: is_creating={self.is_creating}, total_rois={len(self.rois)}")
            
        except Exception as e:
            logger.error(f"❌ Erreur création ROI: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _snap_to_grid(self, point: Tuple[int, int], grid_size: int = 1) -> Tuple[int, int]:
        """Aligne un point sur une grille virtuelle (désactivé par défaut)"""
        if self.snap_distance <= 0 or grid_size <= 1:
            return point
            
        x, y = point
        snapped_x = round(x / grid_size) * grid_size
        snapped_y = round(y / grid_size) * grid_size
        
        return (snapped_x, snapped_y)
    
    def _calculate_area(self, points: List[Tuple[int, int]]) -> float:
        """Calcule l'aire d'un polygone"""
        if len(points) < 3:
            return 0.0
            
        try:
            points_array = np.array(points, dtype=np.float32)
            area = cv2.contourArea(points_array)
            return abs(area)
        except:
            return 0.0
    
    def _deselect_all(self):
        """Désélectionne toutes les ROI"""
        for roi in self.rois:
            if roi.state == ROIState.SELECTED:
                roi.state = ROIState.ACTIVE
        self.selected_roi_id = None
    
    def _draw_selection_handles(self, frame: np.ndarray, roi: ROI):
        """Dessine les poignées de sélection d'une ROI"""
        handle_color = (255, 255, 255)  # Blanc
        handle_border = (0, 0, 0)       # Noir
        
        for point in roi.points:
            # Poignée avec bordure
            cv2.circle(frame, point, self.handle_size, handle_border, -1)
            cv2.circle(frame, point, self.handle_size - 1, handle_color, -1)
    
    def select_roi(self, point: Tuple[int, int]) -> Optional[int]:
        """Sélectionne la ROI contenant le point"""
        for roi in reversed(self.rois):  # Dernière créée en premier
            if self.point_in_roi(point, roi):
                self.selected_roi_id = roi.id
                roi.state = ROIState.SELECTED
                logger.info(f"ROI {roi.name} sélectionnée")
                return roi.id
                
        # Désélection si aucune ROI trouvée
        self._deselect_all()
        return None
    
    def delete_roi(self, roi_id: int) -> bool:
        """Supprime une ROI"""
        roi = self.get_roi_by_id(roi_id)
        if not roi:
            return False
            
        self.rois.remove(roi)
        if self.selected_roi_id == roi_id:
            self.selected_roi_id = None
            
        logger.info(f"ROI {roi.name} supprimée")
        return True
    
    def get_roi_by_id(self, roi_id: int) -> Optional[ROI]:
        """Récupère une ROI par son ID"""
        for roi in self.rois:
            if roi.id == roi_id:
                return roi
        return None
    
    def point_in_roi(self, point: Tuple[int, int], roi: ROI) -> bool:
        """Teste si un point est dans une ROI"""
        if not roi.points:
            return False
            
        try:
            points_array = np.array(roi.points, dtype=np.int32)
            result = cv2.pointPolygonTest(points_array, point, False)
            return result >= 0
        except:
            return False
    
    def get_detections_in_roi(self, detections: List, roi: ROI) -> List:
        """Filtre les détections dans une ROI"""
        filtered = []
        for detection in detections:
            if hasattr(detection, 'center') and self.point_in_roi(detection.center, roi):
                filtered.append(detection)
        return filtered
    
    def update_roi_points(self, roi_id: int, new_points: List[Tuple[int, int]]) -> bool:
        """Met à jour les points d'une ROI"""
        roi = self.get_roi_by_id(roi_id)
        if not roi:
            return False
            
        roi.points = new_points
        roi.metadata['area'] = self._calculate_area(new_points)
        roi.metadata['modified_at'] = time.time()
        
        return True
    
    def set_roi_active(self, roi_id: int, active: bool):
        """Active/désactive une ROI"""
        roi = self.get_roi_by_id(roi_id)
        if roi:
            roi.state = ROIState.ACTIVE if active else ROIState.INACTIVE
            color_key = 'roi_active' if active else 'roi_inactive'
            roi.color = tuple(self.colors.get(color_key, [255, 255, 0] if active else [128, 128, 128]))
    
    def draw_rois(self, frame: np.ndarray) -> np.ndarray:
        """Dessine toutes les ROI sur l'image"""
        result = frame.copy()
        
        # ROI existantes
        for roi in self.rois:
            if roi.points:
                self._draw_single_roi(result, roi)
        
        # ROI en cours de création
        if self.is_creating and self.temp_points:
            self._draw_creation_preview(result)
            
        return result
    
    def _draw_single_roi(self, frame: np.ndarray, roi: ROI):
        """Dessine une ROI individuelle"""
        if not roi.points:
            return
            
        points = np.array(roi.points, dtype=np.int32)
        
        # Remplissage si demandé
        if roi.filled:
            overlay = frame.copy()
            cv2.fillPoly(overlay, [points], roi.color)
            cv2.addWeighted(frame, 0.7, overlay, 0.3, 0, frame)
        
        # Contour
        cv2.polylines(frame, [points], True, roi.color, roi.thickness)
        
        # Nom de la ROI
        if roi.points:
            text_pos = (roi.points[0][0], roi.points[0][1] - 10)
            cv2.putText(frame, roi.name, text_pos, 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, roi.color, 1)
        
        # Poignées de sélection si sélectionnée
        if roi.state == ROIState.SELECTED:
            self._draw_selection_handles(frame, roi)
    
    def _draw_creation_preview(self, frame: np.ndarray):
        """Dessine l'aperçu lors de la création"""
        preview_color = tuple(self.colors.get('roi_active', [255, 255, 0]))
        
        if self.creation_type == ROIType.RECTANGLE and len(self.temp_points) == 1:
            # Preview rectangle avec souris
            cv2.circle(frame, self.temp_points[0], 3, preview_color, -1)
            
        elif self.creation_type == ROIType.POLYGON and len(self.temp_points) >= 2:
            # Preview polygone
            points = np.array(self.temp_points, dtype=np.int32)
            cv2.polylines(frame, [points], False, preview_color, 2)
            
            # Points individuels
            for point in self.temp_points:
                cv2.circle(frame, point, 3, preview_color, -1)
                
        elif self.creation_type == ROIType.CIRCLE and len(self.temp_points) == 1:
            # Preview centre cercle
            cv2.circle(frame, self.temp_points[0], 3, preview_color, -1)
    
    def save_rois_to_file(self, file_path: str) -> bool:
        """Sauvegarde les ROI dans un fichier JSON"""
        try:
            roi_data = {
                'version': '1.0',
                'created_at': time.time(),
                'rois': []
            }
            
            for roi in self.rois:
                roi_dict = asdict(roi)
                roi_dict['roi_type'] = roi.roi_type.value
                roi_dict['state'] = roi.state.value
                roi_data['rois'].append(roi_dict)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(roi_data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"ROI sauvées: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde ROI: {e}")
            return False
    
    def load_rois_from_file(self, file_path: str) -> bool:
        """Charge les ROI depuis un fichier JSON"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.rois = []
            max_id = 0
            
            for roi_data in data.get('rois', []):
                roi = ROI(
                    id=roi_data['id'],
                    name=roi_data['name'],
                    roi_type=ROIType(roi_data['roi_type']),
                    points=[tuple(p) for p in roi_data['points']],
                    state=ROIState(roi_data.get('state', 'active')),
                    color=tuple(roi_data.get('color', [255, 255, 0])),
                    thickness=roi_data.get('thickness', 2),
                    filled=roi_data.get('filled', False),
                    metadata=roi_data.get('metadata', {})
                )
                self.rois.append(roi)
                max_id = max(max_id, roi.id)
            
            self.next_roi_id = max_id + 1
            logger.info(f"ROI chargées: {len(self.rois)} éléments")
            return True
            
        except Exception as e:
            logger.error(f"Erreur chargement ROI: {e}")
            return False
    
    def get_roi_summary(self) -> Dict:
        """Retourne un résumé des ROI"""
        active_count = sum(1 for roi in self.rois if roi.state == ROIState.ACTIVE)
        
        return {
            'total_rois': len(self.rois),
            'active_rois': active_count,
            'selected_roi': self.selected_roi_id,
            'is_creating': self.is_creating,
            'creation_type': self.creation_type.value if self.is_creating else None,
            'types_count': {
                roi_type.value: sum(1 for roi in self.rois if roi.roi_type == roi_type)
                for roi_type in ROIType
            }
        }