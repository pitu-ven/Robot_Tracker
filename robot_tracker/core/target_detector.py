# core/target_detector.py  
# Version 1.0 - Création détecteur multi-types (ArUco, réfléchissants, LEDs)
# Modification: Implémentation détection unifiée avec configuration JSON

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
        """Initialise le détecteur ArUco"""
        try:
            # Dictionnaire ArUco depuis config
            dict_name = self.aruco_config.get('dictionary_type', '4X4_50')
            self.aruco_dict = cv2.aruco.getPredefinedDictionary(
                getattr(cv2.aruco, f'DICT_{dict_name}')
            )
            
            # Paramètres de détection depuis config
            self.aruco_params = cv2.aruco.DetectorParameters()
            detection_params = self.aruco_config.get('detection_params', {})
            
            for param, value in detection_params.items():
                if hasattr(self.aruco_params, param):
                    setattr(self.aruco_params, param, value)
                    
            logger.info(f"ArUco initialisé: {dict_name}")
            
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
    
    def detect_all_targets(self, frame: np.ndarray) -> List[DetectionResult]:
        """Détecte tous les types de cibles dans une frame"""
        start_time = time.time()
        results = []
        
        # Détection ArUco
        if self.detection_enabled[TargetType.ARUCO]:
            aruco_results = self._detect_aruco_markers(frame)
            results.extend(aruco_results)
            
        # Détection marqueurs réfléchissants
        if self.detection_enabled[TargetType.REFLECTIVE]:
            reflective_results = self._detect_reflective_markers(frame)
            results.extend(reflective_results)
            
        # Détection LEDs
        if self.detection_enabled[TargetType.LED]:
            led_results = self._detect_led_markers(frame)
            results.extend(led_results)
        
        # Mise à jour statistiques
        detection_time = time.time() - start_time
        self._update_stats(len(results), detection_time)
        
        return results
    
    def _detect_aruco_markers(self, frame: np.ndarray) -> List[DetectionResult]:
        """Détecte les marqueurs ArUco"""
        try:
            # Conversion en niveaux de gris si nécessaire
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            
            # Détection
            corners, ids, rejected = cv2.aruco.detectMarkers(
                gray, self.aruco_dict, parameters=self.aruco_params
            )
            
            results = []
            if ids is not None:
                for i, marker_id in enumerate(ids.flatten()):
                    corner_points = corners[i][0]
                    
                    # Centre du marqueur
                    center = tuple(np.mean(corner_points, axis=0).astype(int))
                    
                    # Taille approximative
                    size = np.linalg.norm(corner_points[0] - corner_points[2])
                    
                    # Rotation (angle du marqueur)
                    rotation = self._calculate_marker_rotation(corner_points)
                    
                    result = DetectionResult(
                        target_type=TargetType.ARUCO,
                        id=int(marker_id),
                        center=center,
                        corners=[tuple(pt.astype(int)) for pt in corner_points],
                        confidence=1.0,  # ArUco a toujours confiance maximale
                        size=size,
                        rotation=rotation,
                        timestamp=time.time(),
                        additional_data={'rejected_count': len(rejected) if rejected is not None else 0}
                    )
                    results.append(result)
                    
            self.stats['detections_by_type'][TargetType.ARUCO] += len(results)
            return results
            
        except Exception as e:
            logger.error(f"Erreur détection ArUco: {e}")
            return []
    
    def _detect_reflective_markers(self, frame: np.ndarray) -> List[DetectionResult]:
        """Détecte les marqueurs réfléchissants"""
        try:
            # Conversion HSV
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Seuillage depuis config
            hsv_ranges = self.reflective_config.get('hsv_ranges', {})
            lower = np.array(hsv_ranges.get('lower', [0, 0, 200]))
            upper = np.array(hsv_ranges.get('upper', [180, 30, 255]))
            
            mask = cv2.inRange(hsv, lower, upper)
            
            # Morphologie pour nettoyer
            morph_config = self.reflective_config.get('morphology', {})
            iterations = morph_config.get('iterations', 2)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.reflective_kernel, iterations=iterations)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.reflective_kernel, iterations=iterations)
            
            # Détection des contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            results = []
            contour_filters = self.reflective_config.get('contour_filters', {})
            min_area = contour_filters.get('min_area', 50)
            max_area = contour_filters.get('max_area', 5000)
            min_circularity = contour_filters.get('min_circularity', 0.7)
            
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                
                # Filtrage par taille
                if not (min_area <= area <= max_area):
                    continue
                    
                # Filtrage par circularité
                perimeter = cv2.arcLength(contour, True)
                if perimeter == 0:
                    continue
                    
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                if circularity < min_circularity:
                    continue
                
                # Centre et propriétés
                M = cv2.moments(contour)
                if M['m00'] == 0:
                    continue
                    
                center_x = int(M['m10'] / M['m00'])
                center_y = int(M['m01'] / M['m00'])
                center = (center_x, center_y)
                
                # Approximation rectangulaire pour les coins
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                corners = [tuple(pt[0]) for pt in approx]
                
                result = DetectionResult(
                    target_type=TargetType.REFLECTIVE,
                    id=i,  # ID séquentiel pour réfléchissants
                    center=center,
                    corners=corners,
                    confidence=circularity,  # Circularité comme confiance
                    size=np.sqrt(area),
                    rotation=0.0,  # Pas de rotation pour les cercles
                    timestamp=time.time(),
                    additional_data={
                        'area': area,
                        'perimeter': perimeter,
                        'circularity': circularity
                    }
                )
                results.append(result)
                
            self.stats['detections_by_type'][TargetType.REFLECTIVE] += len(results)
            return results
            
        except Exception as e:
            logger.error(f"Erreur détection réfléchissants: {e}")
            return []
    
    def _detect_led_markers(self, frame: np.ndarray) -> List[DetectionResult]:
        """Détecte les LEDs colorées"""
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            results = []
            
            # Détection pour chaque couleur configurée
            color_presets = self.led_config.get('color_presets', {})
            detection_params = self.led_config.get('detection_params', {})
            
            for color_name, color_range in color_presets.items():
                # Masque couleur
                lower = np.array([color_range['h'][0], color_range['s'][0], color_range['v'][0]])
                upper = np.array([color_range['h'][1], color_range['s'][1], color_range['v'][1]])
                
                mask = cv2.inRange(hsv, lower, upper)
                
                # Filtrage gaussien
                blur_size = detection_params.get('gaussian_blur_size', 5)
                mask = cv2.GaussianBlur(mask, (blur_size, blur_size), 0)
                
                # Morphologie
                iterations = detection_params.get('morphology_iterations', 2)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.led_kernel, iterations=iterations)
                
                # Détection contours
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                min_area = detection_params.get('min_contour_area', 30)
                max_area = detection_params.get('max_contour_area', 2000)
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    
                    if not (min_area <= area <= max_area):
                        continue
                    
                    # Centre
                    M = cv2.moments(contour)
                    if M['m00'] == 0:
                        continue
                        
                    center_x = int(M['m10'] / M['m00'])
                    center_y = int(M['m01'] / M['m00'])
                    center = (center_x, center_y)
                    
                    # Enclosing circle pour taille
                    (x, y), radius = cv2.minEnclosingCircle(contour)
                    
                    # Corners approximatifs (carré autour du cercle)
                    corners = [
                        (int(x - radius), int(y - radius)),
                        (int(x + radius), int(y - radius)),
                        (int(x + radius), int(y + radius)),  
                        (int(x - radius), int(y + radius))
                    ]
                    
                    result = DetectionResult(
                        target_type=TargetType.LED,
                        id=hash(color_name) % 1000,  # ID basé sur la couleur
                        center=center,
                        corners=corners,
                        confidence=min(1.0, area / max_area),
                        size=radius * 2,
                        rotation=0.0,
                        timestamp=time.time(),
                        additional_data={
                            'color': color_name,
                            'area': area,
                            'radius': radius
                        }
                    )
                    results.append(result)
                    
            self.stats['detections_by_type'][TargetType.LED] += len(results)
            return results
            
        except Exception as e:
            logger.error(f"Erreur détection LEDs: {e}")
            return []
    
    def _calculate_marker_rotation(self, corners: np.ndarray) -> float:
        """Calcule la rotation d'un marqueur ArUco"""
        try:
            # Vecteur du premier au deuxième coin
            vec = corners[1] - corners[0]
            angle = np.arctan2(vec[1], vec[0])
            return float(np.degrees(angle))
        except:
            return 0.0
    
    def _update_stats(self, detection_count: int, detection_time: float):
        """Met à jour les statistiques de détection"""
        self.stats['total_detections'] += detection_count
        self.stats['last_detection_time'] = detection_time
        
        # Moyenne mobile du temps de détection
        alpha = 0.1  # Facteur de lissage
        if self.stats['avg_detection_time'] == 0:
            self.stats['avg_detection_time'] = detection_time
        else:
            self.stats['avg_detection_time'] = (
                alpha * detection_time + 
                (1 - alpha) * self.stats['avg_detection_time']
            )
    
    def set_detection_enabled(self, target_type: TargetType, enabled: bool):
        """Active/désactive la détection pour un type de cible"""
        self.detection_enabled[target_type] = enabled
        logger.info(f"Détection {target_type.value}: {'activée' if enabled else 'désactivée'}")
    
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
        logger.info("Statistiques de détection remises à zéro")
    
    def update_detection_params(self, target_type: TargetType, params: Dict):
        """Met à jour les paramètres de détection"""
        try:
            if target_type == TargetType.ARUCO:
                for param, value in params.items():
                    if hasattr(self.aruco_params, param):
                        setattr(self.aruco_params, param, value)
                        
            elif target_type == TargetType.REFLECTIVE:
                self.reflective_config.update(params)
                
            elif target_type == TargetType.LED:
                self.led_config.update(params)
                
            logger.info(f"Paramètres {target_type.value} mis à jour")
            
        except Exception as e:
            logger.error(f"Erreur mise à jour paramètres {target_type.value}: {e}")
    
    def draw_detections(self, frame: np.ndarray, detections: List[DetectionResult]) -> np.ndarray:
        """Dessine les détections sur l'image"""
        display_config = self.ui_config.get('display', {})
        colors = display_config.get('colors', {})
        fonts = display_config.get('fonts', {})
        overlays = display_config.get('overlays', {})
        
        result_frame = frame.copy()
        
        for detection in detections:
            # Couleur selon le type
            color_key = f"{detection.target_type.value}_detection"
            color = tuple(colors.get(color_key, [255, 255, 255]))
            
            # Dessin des coins
            if len(detection.corners) >= 4:
                pts = np.array(detection.corners, dtype=np.int32)
                cv2.polylines(result_frame, [pts], True, color, 2)
            
            # Centre
            cv2.circle(result_frame, detection.center, 3, color, -1)
            
            # ID si activé
            if overlays.get('show_marker_ids', True):
                font_config = fonts.get('marker_id', {})
                font_size = font_config.get('size', 12) / 30.0  # Normalisation OpenCV
                thickness = font_config.get('thickness', 2)
                
                text = f"ID:{detection.id}"
                text_pos = (detection.center[0] + 10, detection.center[1] - 10)
                
                cv2.putText(result_frame, text, text_pos, 
                          cv2.FONT_HERSHEY_SIMPLEX, font_size, color, thickness)
            
            # Confiance si activée
            if overlays.get('show_confidence', True) and detection.target_type != TargetType.ARUCO:
                conf_text = f"{detection.confidence:.2f}"
                conf_pos = (detection.center[0] + 10, detection.center[1] + 25)
                
                cv2.putText(result_frame, conf_text, conf_pos,
                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        
        return result_frame