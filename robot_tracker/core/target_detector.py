# core/target_detector.py
# Version 1.2 - Finalisation pour intégration TargetTab
# Modification: Ajout des méthodes manquantes pour intégration complète

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)

class TargetType(Enum):
    """Types de cibles supportées"""
    ARUCO = "aruco"
    REFLECTIVE = "reflective" 
    LED = "led"

@dataclass
class DetectionResult:
    """Résultat de détection d'une cible"""
    target_type: TargetType
    id: int
    center: Tuple[int, int]
    corners: List[Tuple[int, int]]
    confidence: float
    size: float
    rotation: float
    timestamp: float
    additional_data: Dict[str, Any] = None

class TargetDetector:
    """Détecteur unifié pour tous types de cibles"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        # Utilisation du tracking_config.json existant
        self.target_config = self.config.get('tracking', 'target_detection', {})
        self.ui_config = self.config.get('tracking', 'target_tab_ui', {})
        
        # Configuration des détecteurs depuis tracking_config.json
        self.aruco_config = self.target_config.get('aruco', {})
        self.reflective_config = self.target_config.get('reflective_markers', {})
        self.led_config = self.target_config.get('led_markers', {})
        
        self.detection_enabled = {
            TargetType.ARUCO: self.aruco_config.get('enabled', True),
            TargetType.REFLECTIVE: self.reflective_config.get('enabled', True),
            TargetType.LED: self.led_config.get('enabled', True)
        }
        
        # ROI active (définie par ROIManager)
        self.active_roi = None
        
        # Initialisation détecteurs
        self._init_aruco_detector()
        self._init_morphology_kernels()
        self._init_kalman_filters()
        
        # Cache pour performances
        self._detection_cache = {}
        self._cache_timeout = 0.1  # 100ms
        
        # Statistiques
        self.stats = {
            'total_detections': 0,
            'detections_by_type': {t: 0 for t in TargetType},
            'avg_detection_time': 0.0,
            'last_detection_time': 0.0
        }
        
        logger.info("🎯 TargetDetector v1.2 initialisé (intégration complète)")
    
    def _init_aruco_detector(self):
        """Initialise le détecteur ArUco avec compatibilité multi-versions OpenCV"""
        try:
            # Dictionnaire ArUco depuis config
            dict_name = self.aruco_config.get('dictionary_type', '4X4_50')
            
            # Support des différentes versions d'OpenCV
            if hasattr(cv2.aruco, 'getPredefinedDictionary'):
                # OpenCV 4.6+
                dict_attr = getattr(cv2.aruco, f'DICT_{dict_name}', cv2.aruco.DICT_4X4_50)
                self.aruco_dict = cv2.aruco.getPredefinedDictionary(dict_attr)
                
                # Paramètres de détection
                self.aruco_params = cv2.aruco.DetectorParameters()
                self._configure_aruco_params()
                
                # Nouveau détecteur (OpenCV 4.7+)
                if hasattr(cv2.aruco, 'ArucoDetector'):
                    self.aruco_detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
                    self.use_new_api = True
                    logger.info("✅ ArUco: Nouvelle API (ArucoDetector)")
                else:
                    self.use_new_api = False
                    logger.info("✅ ArUco: Ancienne API (detectMarkers)")
            else:
                logger.warning("⚠️ ArUco non disponible, détection désactivée")
                self.detection_enabled[TargetType.ARUCO] = False
                
        except Exception as e:
            logger.error(f"❌ Erreur initialisation ArUco: {e}")
            self.detection_enabled[TargetType.ARUCO] = False
    
    def _configure_aruco_params(self):
        """Configure les paramètres de détection ArUco depuis la config"""
        params_config = self.aruco_config.get('detection_params', {})
        
        # Seuillage adaptatif
        self.aruco_params.adaptiveThreshWinSizeMin = params_config.get('adaptiveThreshWinSizeMin', 3)
        self.aruco_params.adaptiveThreshWinSizeMax = params_config.get('adaptiveThreshWinSizeMax', 23)
        
        # Périmètre des marqueurs
        self.aruco_params.minMarkerPerimeterRate = params_config.get('minMarkerPerimeterRate', 0.1)
        self.aruco_params.maxMarkerPerimeterRate = params_config.get('maxMarkerPerimeterRate', 4.0)
        
        # Précision polygonale
        self.aruco_params.polygonalApproxAccuracyRate = params_config.get('polygonalApproxAccuracyRate', 0.03)
        
        logger.debug("🔧 Paramètres ArUco configurés depuis JSON")
    
    def _init_morphology_kernels(self):
        """Initialise les kernels de morphologie pour marqueurs réfléchissants"""
        kernel_size = self.reflective_config.get('morphology', {}).get('kernel_size', 5)
        self.morph_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        
    def _init_kalman_filters(self):
        """Initialise les filtres de Kalman pour stabilisation"""
        self.kalman_filters = {}  # Un filtre par cible trackée
        self.kalman_config = self.target_config.get('kalman_filter', {})
    
    def set_roi(self, roi):
        """Définit la ROI active pour filtrer les détections"""
        self.active_roi = roi
        logger.info(f"📐 ROI active définie: {type(roi).__name__ if roi else 'Aucune'}")
    
    def set_detection_enabled(self, target_type: TargetType, enabled: bool):
        """Active/désactive la détection pour un type de cible"""
        self.detection_enabled[target_type] = enabled
        logger.info(f"🔍 Détection {target_type.value}: {'Activée' if enabled else 'Désactivée'}")
    
    def detect_all_targets(self, frame: np.ndarray) -> List[DetectionResult]:
        """MÉTHODE PRINCIPALE - Détection unifiée de toutes les cibles"""
        if frame is None or frame.size == 0:
            return []
        
        start_time = time.time()
        all_detections = []
        
        try:
            # Application ROI si définie
            roi_frame = self._apply_roi_mask(frame) if self.active_roi else frame
            
            # Détection ArUco
            if self.detection_enabled[TargetType.ARUCO]:
                aruco_detections = self._detect_aruco_markers(roi_frame)
                all_detections.extend(aruco_detections)
            
            # Détection marqueurs réfléchissants
            if self.detection_enabled[TargetType.REFLECTIVE]:
                reflective_detections = self._detect_reflective_markers(roi_frame)
                all_detections.extend(reflective_detections)
            
            # Détection LEDs colorées
            if self.detection_enabled[TargetType.LED]:
                led_detections = self._detect_led_markers(roi_frame)
                all_detections.extend(led_detections)
            
            # Filtrage Kalman si configuré
            if self.kalman_config.get('enabled', False):
                all_detections = self._apply_kalman_filtering(all_detections)
            
            # Mise à jour statistiques
            self._update_detection_stats(all_detections, time.time() - start_time)
            
            return all_detections
            
        except Exception as e:
            logger.error(f"❌ Erreur détection globale: {e}")
            return []
    
    def _apply_roi_mask(self, frame: np.ndarray) -> np.ndarray:
        """Applique le masque ROI au frame"""
        # TODO: Implémenter selon le type de ROI (rectangle, polygone)
        # Pour l'instant, retour du frame complet
        return frame
    
    def _detect_aruco_markers(self, frame: np.ndarray) -> List[DetectionResult]:
        """Détection des marqueurs ArUco"""
        detections = []
        
        try:
            if self.use_new_api and hasattr(self, 'aruco_detector'):
                # Nouvelle API OpenCV 4.7+
                corners, ids, _ = self.aruco_detector.detectMarkers(frame)
            else:
                # Ancienne API
                corners, ids, _ = cv2.aruco.detectMarkers(
                    frame, self.aruco_dict, parameters=self.aruco_params
                )
            
            if ids is not None and len(ids) > 0:
                for i, marker_id in enumerate(ids.flatten()):
                    corner_points = corners[i][0]
                    
                    # Calcul du centre
                    center = tuple(map(int, corner_points.mean(axis=0)))
                    
                    # Calcul de la taille (aire du marqueur)
                    area = cv2.contourArea(corner_points)
                    size = np.sqrt(area)
                    
                    # Calcul de la rotation
                    rotation = self._calculate_marker_rotation(corner_points)
                    
                    detection = DetectionResult(
                        target_type=TargetType.ARUCO,
                        id=int(marker_id),
                        center=center,
                        corners=[tuple(map(int, pt)) for pt in corner_points],
                        confidence=0.9,  # Confiance élevée pour ArUco
                        size=size,
                        rotation=rotation,
                        timestamp=time.time()
                    )
                    
                    detections.append(detection)
                    
        except Exception as e:
            logger.error(f"❌ Erreur détection ArUco: {e}")
        
        return detections
    
    def _detect_reflective_markers(self, frame: np.ndarray) -> List[DetectionResult]:
        """Détection des marqueurs réfléchissants"""
        detections = []
        
        try:
            # Conversion en HSV
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Seuillage pour marqueurs réfléchissants (valeurs élevées)
            hsv_ranges = self.reflective_config.get('hsv_ranges', {})
            lower = np.array(hsv_ranges.get('lower', [0, 0, 200]))
            upper = np.array(hsv_ranges.get('upper', [180, 30, 255]))
            
            mask = cv2.inRange(hsv, lower, upper)
            
            # Morphologie pour nettoyer
            iterations = self.reflective_config.get('morphology', {}).get('iterations', 2)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.morph_kernel, iterations=iterations)
            
            # Recherche de contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filtrage des contours
            filters = self.reflective_config.get('contour_filters', {})
            min_area = filters.get('min_area', 50)
            max_area = filters.get('max_area', 5000)
            min_circularity = filters.get('min_circularity', 0.7)
            
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                
                if min_area <= area <= max_area:
                    # Test de circularité
                    perimeter = cv2.arcLength(contour, True)
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter * perimeter)
                        
                        if circularity >= min_circularity:
                            # Calcul du centre
                            M = cv2.moments(contour)
                            if M['m00'] > 0:
                                cx = int(M['m10'] / M['m00'])
                                cy = int(M['m01'] / M['m00'])
                                
                                # Approximation rectangulaire pour corners
                                rect = cv2.boundingRect(contour)
                                corners = [
                                    (rect[0], rect[1]),
                                    (rect[0] + rect[2], rect[1]),
                                    (rect[0] + rect[2], rect[1] + rect[3]),
                                    (rect[0], rect[1] + rect[3])
                                ]
                                
                                detection = DetectionResult(
                                    target_type=TargetType.REFLECTIVE,
                                    id=i,  # ID basé sur l'ordre de détection
                                    center=(cx, cy),
                                    corners=corners,
                                    confidence=circularity,
                                    size=np.sqrt(area),
                                    rotation=0.0,
                                    timestamp=time.time(),
                                    additional_data={'area': area, 'circularity': circularity}
                                )
                                
                                detections.append(detection)
                                
        except Exception as e:
            logger.error(f"❌ Erreur détection marqueurs réfléchissants: {e}")
        
        return detections
    
    def _detect_led_markers(self, frame: np.ndarray) -> List[DetectionResult]:
        """Détection des LEDs colorées"""
        detections = []
        
        try:
            # Conversion en HSV
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Flou gaussien pour réduire le bruit
            gaussian_kernel = self.led_config.get('gaussian_blur_kernel', 5)
            hsv = cv2.GaussianBlur(hsv, (gaussian_kernel, gaussian_kernel), 0)
            
            # Détection par couleur
            color_presets = self.led_config.get('color_presets', {})
            
            for color_name, color_ranges in color_presets.items():
                # Seuillage couleur
                h_range = color_ranges.get('h', [0, 180])
                s_range = color_ranges.get('s', [50, 255])
                v_range = color_ranges.get('v', [50, 255])
                
                lower = np.array([h_range[0], s_range[0], v_range[0]])
                upper = np.array([h_range[1], s_range[1], v_range[1]])
                
                mask = cv2.inRange(hsv, lower, upper)
                
                # Recherche de contours
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for i, contour in enumerate(contours):
                    area = cv2.contourArea(contour)
                    
                    if area > 20:  # Filtre taille minimale
                        # Centre pondéré par intensité
                        M = cv2.moments(contour)
                        if M['m00'] > 0:
                            cx = int(M['m10'] / M['m00'])
                            cy = int(M['m01'] / M['m00'])
                            
                            # Rectangle englobant pour corners
                            rect = cv2.boundingRect(contour)
                            corners = [
                                (rect[0], rect[1]),
                                (rect[0] + rect[2], rect[1]),
                                (rect[0] + rect[2], rect[1] + rect[3]),
                                (rect[0], rect[1] + rect[3])
                            ]
                            
                            detection = DetectionResult(
                                target_type=TargetType.LED,
                                id=hash(color_name) % 1000,  # ID basé sur la couleur
                                center=(cx, cy),
                                corners=corners,
                                confidence=min(area / 1000.0, 1.0),
                                size=np.sqrt(area),
                                rotation=0.0,
                                timestamp=time.time(),
                                additional_data={'color': color_name, 'area': area}
                            )
                            
                            detections.append(detection)
                            
        except Exception as e:
            logger.error(f"❌ Erreur détection LEDs: {e}")
        
        return detections
    
    def _calculate_marker_rotation(self, corners: np.ndarray) -> float:
        """Calcule l'angle de rotation d'un marqueur ArUco"""
        try:
            # Vecteur du premier côté
            v1 = corners[1] - corners[0]
            # Angle avec l'axe horizontal
            angle = np.arctan2(v1[1], v1[0]) * 180 / np.pi
            return float(angle)
        except:
            return 0.0
    
    def _apply_kalman_filtering(self, detections: List[DetectionResult]) -> List[DetectionResult]:
        """Applique le filtrage Kalman pour stabiliser le tracking"""
        # TODO: Implémenter filtrage Kalman
        # Pour l'instant, retour des détections non filtrées
        return detections
    
    def _update_detection_stats(self, detections: List[DetectionResult], detection_time: float):
        """Met à jour les statistiques de détection"""
        self.stats['total_detections'] += len(detections)
        self.stats['last_detection_time'] = detection_time
        
        # Mise à jour temps moyen (moyenne mobile)
        alpha = 0.1
        self.stats['avg_detection_time'] = (
            alpha * detection_time + 
            (1 - alpha) * self.stats['avg_detection_time']
        )
        
        # Statistiques par type
        for detection in detections:
            self.stats['detections_by_type'][detection.target_type] += 1
    
    def get_detection_stats(self) -> Dict:
        """Retourne les statistiques de détection"""
        return self.stats.copy()
    
    def reset_stats(self):
        """Remet à zéro les statistiques"""
        self.stats = {
            'total_detections': 0,
            'detections_by_type': {t: 0 for t in TargetType},
            'avg_detection_time': 0.0,
            'last_detection_time': 0.0
        }