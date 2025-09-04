# robot_tracker/core/target_detector.py  
# Version 1.2 - CORRECTION: Détection ArUco cassée par ROI
# Modification: ROI uniquement appliquée si explicitement configurée et active

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
        
        # CORRECTION: ROI initialement désactivée
        self.current_roi = None
        self.roi_enabled = False
        
        # Initialisation détecteurs
        self._init_aruco_detector()
        self._init_morphology_kernels()
        
        # Statistiques
        self.stats = {
            'total_detections': 0,
            'detections_by_type': {t: 0 for t in TargetType},
            'avg_detection_time': 0.0,
            'last_detection_time': 0.0
        }
        
        logger.info("TargetDetector initialisé")
    
    def _init_aruco_detector(self):
        """Initialise le détecteur ArUco avec compatibilité multi-versions OpenCV"""
        try:
            # Dictionnaire ArUco depuis config
            dict_name = self.aruco_config.get('dictionary_type', '4X4_50')
            
            # Support des différentes versions d'OpenCV
            if hasattr(cv2, 'aruco'):
                try:
                    # Nouvelle API OpenCV 4.6+ (ArucoDetector)
                    if hasattr(cv2.aruco, 'ArucoDetector'):
                        # Dictionnaire ArUco
                        aruco_dict_map = {
                            '4X4_50': cv2.aruco.DICT_4X4_50,
                            '4X4_100': cv2.aruco.DICT_4X4_100,
                            '4X4_250': cv2.aruco.DICT_4X4_250,
                            '4X4_1000': cv2.aruco.DICT_4X4_1000,
                            '5X5_50': cv2.aruco.DICT_5X5_50,
                            '5X5_100': cv2.aruco.DICT_5X5_100,
                            '5X5_250': cv2.aruco.DICT_5X5_250,
                            '5X5_1000': cv2.aruco.DICT_5X5_1000,
                            '6X6_50': cv2.aruco.DICT_6X6_50,
                            '6X6_100': cv2.aruco.DICT_6X6_100,
                            '6X6_250': cv2.aruco.DICT_6X6_250,
                            '6X6_1000': cv2.aruco.DICT_6X6_1000,
                            '7X7_50': cv2.aruco.DICT_7X7_50,
                            '7X7_100': cv2.aruco.DICT_7X7_100,
                            '7X7_250': cv2.aruco.DICT_7X7_250,
                            '7X7_1000': cv2.aruco.DICT_7X7_1000
                        }
                        
                        dict_id = aruco_dict_map.get(dict_name, cv2.aruco.DICT_4X4_50)
                        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
                        
                        # Paramètres de détection
                        self.aruco_params = cv2.aruco.DetectorParameters()
                        
                        # Application des paramètres depuis config
                        detection_params = self.aruco_config.get('detection_params', {})
                        for param, value in detection_params.items():
                            if hasattr(self.aruco_params, param):
                                setattr(self.aruco_params, param, value)
                        
                        # Création du détecteur unifié (nouvelle API)
                        self.aruco_detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
                        self.use_modern_api = True
                        logger.info(f"ArUco initialisé: {dict_name} (API moderne ArucoDetector)")
                        
                    else:
                        # Ancienne API (OpenCV < 4.6)
                        aruco_dict_map = {
                            '4X4_50': cv2.aruco.DICT_4X4_50,
                            '4X4_100': cv2.aruco.DICT_4X4_100,
                            '4X4_250': cv2.aruco.DICT_4X4_250,
                            '4X4_1000': cv2.aruco.DICT_4X4_1000,
                            '5X5_50': cv2.aruco.DICT_5X5_50,
                            '5X5_100': cv2.aruco.DICT_5X5_100,
                            '5X5_250': cv2.aruco.DICT_5X5_250,
                            '5X5_1000': cv2.aruco.DICT_5X5_1000,
                            '6X6_50': cv2.aruco.DICT_6X6_50,
                            '6X6_100': cv2.aruco.DICT_6X6_100,
                            '6X6_250': cv2.aruco.DICT_6X6_250,
                            '6X6_1000': cv2.aruco.DICT_6X6_1000,
                            '7X7_50': cv2.aruco.DICT_7X7_50,
                            '7X7_100': cv2.aruco.DICT_7X7_100,
                            '7X7_250': cv2.aruco.DICT_7X7_250,
                            '7X7_1000': cv2.aruco.DICT_7X7_1000
                        }
                        
                        dict_id = aruco_dict_map.get(dict_name, cv2.aruco.DICT_4X4_50)
                        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id) if hasattr(cv2.aruco, 'getPredefinedDictionary') else cv2.aruco.Dictionary_get(dict_id)
                        
                        # Paramètres de détection
                        self.aruco_params = cv2.aruco.DetectorParameters_create() if hasattr(cv2.aruco, 'DetectorParameters_create') else cv2.aruco.DetectorParameters()
                        
                        # Application des paramètres depuis config
                        detection_params = self.aruco_config.get('detection_params', {})
                        for param, value in detection_params.items():
                            if hasattr(self.aruco_params, param):
                                setattr(self.aruco_params, param, value)
                        
                        self.aruco_detector = None  # Pas d'objet détecteur unifié
                        self.use_modern_api = False
                        logger.info(f"ArUco initialisé: {dict_name} (API classique)")
                        
                except Exception as e:
                    logger.error(f"Erreur configuration ArUco: {e}")
                    # Mode fallback minimal
                    self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50) if hasattr(cv2.aruco, 'getPredefinedDictionary') else cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
                    self.aruco_params = cv2.aruco.DetectorParameters_create() if hasattr(cv2.aruco, 'DetectorParameters_create') else cv2.aruco.DetectorParameters()
                    self.aruco_detector = None
                    self.use_modern_api = False
                    logger.warning("⚠️ Mode fallback ArUco activé")
                    
        except Exception as e:
            logger.error(f"Erreur init ArUco: {e}")
            self.detection_enabled[TargetType.ARUCO] = False
    
    def _init_morphology_kernels(self):
        """Initialize morphology kernels for processing"""
        # Kernel pour marqueurs réfléchissants
        refl_kernel_size = self.reflective_config.get('morphology', {}).get('kernel_size', 5)
        self.reflective_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (refl_kernel_size, refl_kernel_size)
        )
        
        # Kernel pour LEDs
        led_kernel_size = self.led_config.get('detection_params', {}).get('morphology_kernel', 3)
        self.led_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (led_kernel_size, led_kernel_size)
        )

    # CORRECTION: Nouvelle méthode pour configurer ROI
    def set_roi(self, roi=None, enabled=True):
        """Configure la ROI pour la détection"""
        self.current_roi = roi
        self.roi_enabled = enabled and roi is not None
        
        if self.roi_enabled:
            logger.info(f"ROI activée pour détection: {roi}")
        else:
            logger.info("ROI désactivée - détection sur frame complète")
    
    def detect_all_targets(self, frame: np.ndarray) -> List[DetectionResult]:
        """Détecte tous les types de cibles dans une frame"""
        start_time = time.time()
        results = []
        
        # CORRECTION: Prétraitement de frame selon ROI seulement si activée
        detection_frame = frame
        roi_offset = (0, 0)
        
        if self.roi_enabled and self.current_roi is not None:
            try:
                # Extraction de la région d'intérêt
                detection_frame, roi_offset = self._extract_roi_region(frame, self.current_roi)
                if detection_frame is None:
                    logger.warning("⚠️ ROI invalide - détection sur frame complète")
                    detection_frame = frame
                    roi_offset = (0, 0)
            except Exception as e:
                logger.error(f"❌ Erreur extraction ROI: {e}")
                detection_frame = frame
                roi_offset = (0, 0)
        
        # Détection ArUco
        if self.detection_enabled[TargetType.ARUCO]:
            aruco_results = self._detect_aruco_markers(detection_frame, roi_offset)
            results.extend(aruco_results)
            
        # Détection marqueurs réfléchissants
        if self.detection_enabled[TargetType.REFLECTIVE]:
            reflective_results = self._detect_reflective_markers(detection_frame, roi_offset)
            results.extend(reflective_results)
            
        # Détection LEDs
        if self.detection_enabled[TargetType.LED]:
            led_results = self._detect_led_markers(detection_frame, roi_offset)
            results.extend(led_results)
        
        # Mise à jour statistiques
        detection_time = time.time() - start_time
        self._update_stats(len(results), detection_time)
        
        return results

    def _extract_roi_region(self, frame, roi):
        """Extrait la région d'intérêt de la frame"""
        if not hasattr(roi, 'points') or not roi.points:
            return frame, (0, 0)
        
        try:
            # Calcul bounding box de la ROI
            points = np.array(roi.points)
            x, y, w, h = cv2.boundingRect(points)
            
            # Vérification limites
            height, width = frame.shape[:2]
            x = max(0, min(x, width - 1))
            y = max(0, min(y, height - 1))
            w = min(w, width - x)
            h = min(h, height - y)
            
            if w <= 0 or h <= 0:
                return None, (0, 0)
            
            # Extraction de la région
            roi_frame = frame[y:y+h, x:x+w]
            return roi_frame, (x, y)
            
        except Exception as e:
            logger.error(f"❌ Erreur extraction ROI: {e}")
            return frame, (0, 0)
    
    def _detect_aruco_markers(self, frame: np.ndarray, roi_offset=(0, 0)) -> List[DetectionResult]:
        """Détecte les marqueurs ArUco avec compatibilité multi-versions"""
        try:
            # Conversion en niveaux de gris si nécessaire
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            
            # Détection selon l'API disponible
            if self.use_modern_api and self.aruco_detector:
                # Nouvelle API (OpenCV 4.6+)
                corners, ids, rejected = self.aruco_detector.detectMarkers(gray)
            else:
                # Ancienne API (OpenCV < 4.6)
                if hasattr(cv2.aruco, 'detectMarkers'):
                    corners, ids, rejected = cv2.aruco.detectMarkers(
                        gray, self.aruco_dict, parameters=self.aruco_params
                    )
                else:
                    # Version très ancienne ou problème d'import
                    logger.error("❌ Aucune méthode de détection ArUco disponible")
                    return []
            
            results = []
            if ids is not None and len(ids) > 0:
                for i, marker_id in enumerate(ids.flatten()):
                    corner_points = corners[i][0]
                    
                    # CORRECTION: Ajout de l'offset ROI aux coordonnées
                    offset_x, offset_y = roi_offset
                    adjusted_corners = [(int(pt[0] + offset_x), int(pt[1] + offset_y)) for pt in corner_points]
                    
                    # Centre du marqueur (avec offset)
                    center = tuple(np.mean(corner_points, axis=0).astype(int))
                    center = (center[0] + offset_x, center[1] + offset_y)
                    
                    # Taille approximative
                    size = float(np.linalg.norm(corner_points[0] - corner_points[2]))
                    
                    # Rotation (angle du marqueur)
                    rotation = self._calculate_marker_rotation(corner_points)
                    
                    result = DetectionResult(
                        target_type=TargetType.ARUCO,
                        id=int(marker_id),
                        center=center,
                        corners=adjusted_corners,
                        confidence=1.0,  # ArUco a toujours confiance maximale
                        size=size,
                        rotation=rotation,
                        timestamp=time.time(),
                        additional_data={
                            'rejected_count': len(rejected) if rejected is not None else 0,
                            'roi_offset': roi_offset
                        }
                    )
                    results.append(result)
                    
            self.stats['detections_by_type'][TargetType.ARUCO] += len(results)
            
            if len(results) > 0:
                logger.debug(f"🎯 ArUco détectés: {len(results)} marqueurs")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Erreur détection ArUco: {e}")
            return []
    
    def _detect_reflective_markers(self, frame: np.ndarray, roi_offset=(0, 0)) -> List[DetectionResult]:
        """Détecte les marqueurs réfléchissants"""
        try:
            # Configuration depuis config
            config = self.reflective_config
            
            # Conversion HSV
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Seuillage adaptatif pour éléments réfléchissants
            lower_thresh = np.array(config.get('hsv_range', {}).get('lower', [0, 0, 200]))
            upper_thresh = np.array(config.get('hsv_range', {}).get('upper', [180, 30, 255]))
            
            mask = cv2.inRange(hsv, lower_thresh, upper_thresh)
            
            # Morphologie pour nettoyage
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.reflective_kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.reflective_kernel)
            
            # Détection contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            results = []
            min_area = config.get('detection_params', {}).get('min_area', 50)
            max_area = config.get('detection_params', {}).get('max_area', 5000)
            
            offset_x, offset_y = roi_offset
            
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                if min_area <= area <= max_area:
                    # Moments pour centroïde
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"]) + offset_x
                        cy = int(M["m01"] / M["m00"]) + offset_y
                        
                        # Bounding box pour coins
                        x, y, w, h = cv2.boundingRect(contour)
                        corners = [
                            (x + offset_x, y + offset_y),
                            (x + w + offset_x, y + offset_y),
                            (x + w + offset_x, y + h + offset_y),
                            (x + offset_x, y + h + offset_y)
                        ]
                        
                        result = DetectionResult(
                            target_type=TargetType.REFLECTIVE,
                            id=i,  # ID temporaire basé sur l'index
                            center=(cx, cy),
                            corners=corners,
                            confidence=min(1.0, area / max_area),
                            size=float(np.sqrt(area)),
                            rotation=0.0,  # TODO: Calcul orientation
                            timestamp=time.time(),
                            additional_data={
                                'area': area,
                                'roi_offset': roi_offset
                            }
                        )
                        results.append(result)
            
            self.stats['detections_by_type'][TargetType.REFLECTIVE] += len(results)
            return results
            
        except Exception as e:
            logger.error(f"❌ Erreur détection marqueurs réfléchissants: {e}")
            return []
    
    def _detect_led_markers(self, frame: np.ndarray, roi_offset=(0, 0)) -> List[DetectionResult]:
        """Détecte les marqueurs LED"""
        try:
            # Configuration depuis config
            config = self.led_config
            
            # Conversion HSV
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Seuillage pour LEDs (généralement zones très lumineuses)
            lower_thresh = np.array(config.get('detection_params', {}).get('hsv_lower', [0, 0, 240]))
            upper_thresh = np.array(config.get('detection_params', {}).get('hsv_upper', [180, 255, 255]))
            
            mask = cv2.inRange(hsv, lower_thresh, upper_thresh)
            
            # Morphologie légère
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.led_kernel)
            
            # Détection contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            results = []
            min_area = config.get('detection_params', {}).get('min_area', 10)
            max_area = config.get('detection_params', {}).get('max_area', 1000)
            
            offset_x, offset_y = roi_offset
            
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                if min_area <= area <= max_area:
                    # Circularité pour filtrer les LEDs rondes
                    perimeter = cv2.arcLength(contour, True)
                    if perimeter > 0:
                        circularity = 4 * np.pi * area / (perimeter * perimeter)
                        
                        min_circularity = config.get('detection_params', {}).get('min_circularity', 0.3)
                        if circularity >= min_circularity:
                            # Centroïde
                            M = cv2.moments(contour)
                            if M["m00"] != 0:
                                cx = int(M["m10"] / M["m00"]) + offset_x
                                cy = int(M["m01"] / M["m00"]) + offset_y
                                
                                # Bounding box approximatif
                                x, y, w, h = cv2.boundingRect(contour)
                                corners = [
                                    (x + offset_x, y + offset_y),
                                    (x + w + offset_x, y + offset_y),
                                    (x + w + offset_x, y + h + offset_y),
                                    (x + offset_x, y + h + offset_y)
                                ]
                                
                                result = DetectionResult(
                                    target_type=TargetType.LED,
                                    id=i,
                                    center=(cx, cy),
                                    corners=corners,
                                    confidence=circularity,
                                    size=float(np.sqrt(area)),
                                    rotation=0.0,
                                    timestamp=time.time(),
                                    additional_data={
                                        'area': area,
                                        'circularity': circularity,
                                        'roi_offset': roi_offset
                                    }
                                )
                                results.append(result)
            
            self.stats['detections_by_type'][TargetType.LED] += len(results)
            return results
            
        except Exception as e:
            logger.error(f"❌ Erreur détection LEDs: {e}")
            return []
    
    def _calculate_marker_rotation(self, corners):
        """Calcule la rotation d'un marqueur ArUco"""
        try:
            # Vecteur du premier coin vers le deuxième
            vec = corners[1] - corners[0]
            angle = np.arctan2(vec[1], vec[0]) * 180.0 / np.pi
            return float(angle)
        except:
            return 0.0
    
    def _update_stats(self, detection_count: int, detection_time: float):
        """Met à jour les statistiques de détection"""
        self.stats['total_detections'] += detection_count
        self.stats['last_detection_time'] = detection_time
        
        # Moyenne mobile simple
        if self.stats['avg_detection_time'] == 0:
            self.stats['avg_detection_time'] = detection_time
        else:
            self.stats['avg_detection_time'] = (
                self.stats['avg_detection_time'] * 0.9 + detection_time * 0.1
            )
    
    def set_detection_enabled(self, target_type: TargetType, enabled: bool):
        """Active/désactive un type de détection"""
        self.detection_enabled[target_type] = enabled
        logger.info(f"Détection {target_type.value}: {'activée' if enabled else 'désactivée'}")
    
    def get_stats(self) -> Dict:
        """Retourne les statistiques actuelles"""
        return self.stats.copy()
    
    def reset_stats(self):
        """Remet à zéro les statistiques"""
        self.stats = {
            'total_detections': 0,
            'detections_by_type': {t: 0 for t in TargetType},
            'avg_detection_time': 0.0,
            'last_detection_time': 0.0
        }
        logger.info("Statistiques de détection remises à zéro")