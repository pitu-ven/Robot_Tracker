# core/target_detector.py  
# Version 1.1 - Correction compatibilité OpenCV ArUco 4.6+
# Modification: Support des nouvelles API ArUco (ArucoDetector) et anciennes (detectMarkers)

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
        """Initialise le détecteur ArUco avec compatibilité multi-versions OpenCV"""
        try:
            # Dictionnaire ArUco depuis config
            dict_name = self.aruco_config.get('dictionary_type', '4X4_50')
            
            # Support des différentes versions d'OpenCV
            try:
                # Nouvelle API (OpenCV 4.6+)
                if hasattr(cv2.aruco, 'getPredefinedDictionary'):
                    self.aruco_dict = cv2.aruco.getPredefinedDictionary(
                        getattr(cv2.aruco, f'DICT_{dict_name}')
                    )
                else:
                    # Ancienne API (OpenCV < 4.6)
                    self.aruco_dict = cv2.aruco.Dictionary_get(
                        getattr(cv2.aruco, f'DICT_{dict_name}')
                    )
            except AttributeError:
                # Fallback pour versions très anciennes
                self.aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
                logger.warning(f"⚠️ Dictionnaire {dict_name} non trouvé, utilisation de DICT_4X4_50")
            
            # Paramètres de détection selon la version d'OpenCV
            detection_params = self.aruco_config.get('detection_params', {})
            
            try:
                # Nouvelle API (OpenCV 4.6+) - ArucoDetector
                if hasattr(cv2.aruco, 'ArucoDetector'):
                    # Création des paramètres
                    if hasattr(cv2.aruco, 'DetectorParameters'):
                        self.aruco_params = cv2.aruco.DetectorParameters()
                    else:
                        self.aruco_params = cv2.aruco.DetectorParameters_create()
                    
                    # Configuration des paramètres
                    for param, value in detection_params.items():
                        if hasattr(self.aruco_params, param):
                            setattr(self.aruco_params, param, value)
                    
                    # Création du détecteur moderne
                    self.aruco_detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
                    self.use_modern_api = True
                    logger.info(f"ArUco initialisé: {dict_name} (API moderne)")
                    
                else:
                    # Ancienne API (OpenCV < 4.6) - detectMarkers
                    if hasattr(cv2.aruco, 'DetectorParameters_create'):
                        self.aruco_params = cv2.aruco.DetectorParameters_create()
                    else:
                        self.aruco_params = cv2.aruco.DetectorParameters()
                    
                    # Configuration des paramètres
                    for param, value in detection_params.items():
                        if hasattr(self.aruco_params, param):
                            setattr(self.aruco_params, param, value)
                    
                    self.aruco_detector = None  # Pas d'objet détecteur unifié
                    self.use_modern_api = False
                    logger.info(f"ArUco initialisé: {dict_name} (API classique)")
                    
            except Exception as e:
                logger.error(f"Erreur configuration ArUco: {e}")
                # Mode fallback minimal
                self.aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
                self.aruco_params = cv2.aruco.DetectorParameters_create()
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
                    
                    # Centre du marqueur
                    center = tuple(np.mean(corner_points, axis=0).astype(int))
                    
                    # Taille approximative
                    size = float(np.linalg.norm(corner_points[0] - corner_points[2]))
                    
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
            
            # Seuillage pour marqueurs réfléchissants (surfaces très claires)
            hsv_ranges = self.reflective_config.get('hsv_ranges', {
                'lower': [0, 0, 200],
                'upper': [180, 30, 255]
            })
            
            lower = np.array(hsv_ranges['lower'])
            upper = np.array(hsv_ranges['upper'])
            mask = cv2.inRange(hsv, lower, upper)
            
            # Morphologie pour nettoyage
            if self.reflective_config.get('morphology', {}).get('enabled', True):
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.reflective_kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.reflective_kernel)
            
            # Détection de contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            results = []
            contour_filters = self.reflective_config.get('contour_filters', {})
            min_area = contour_filters.get('min_area', 50)
            max_area = contour_filters.get('max_area', 5000)
            min_circularity = contour_filters.get('min_circularity', 0.7)
            
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                
                # Filtrage par aire
                if area < min_area or area > max_area:
                    continue
                
                # Calcul de la circularité
                perimeter = cv2.arcLength(contour, True)
                if perimeter == 0:
                    continue
                    
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                if circularity < min_circularity:
                    continue
                
                # Centre de masse
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                else:
                    continue
                
                # Boîte englobante pour les coins
                rect = cv2.minAreaRect(contour)
                box = cv2.boxPoints(rect)
                box = np.int0(box)
                
                result = DetectionResult(
                    target_type=TargetType.REFLECTIVE,
                    id=i,  # ID séquentiel pour les marqueurs réfléchissants
                    center=(cx, cy),
                    corners=[tuple(pt) for pt in box],
                    confidence=min(1.0, circularity),  # Confiance basée sur circularité
                    size=float(np.sqrt(area)),
                    rotation=float(rect[2]),
                    timestamp=time.time(),
                    additional_data={
                        'area': area,
                        'circularity': circularity,
                        'perimeter': perimeter
                    }
                )
                results.append(result)
            
            self.stats['detections_by_type'][TargetType.REFLECTIVE] += len(results)
            return results
            
        except Exception as e:
            logger.error(f"Erreur détection marqueurs réfléchissants: {e}")
            return []
    
    def _detect_led_markers(self, frame: np.ndarray) -> List[DetectionResult]:
        """Détecte les marqueurs LED colorés"""
        try:
            if not self.led_config.get('enabled', False):
                return []
            
            # Conversion HSV
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            results = []
            
            # Détection pour chaque couleur configurée
            color_presets = self.led_config.get('color_presets', {})
            
            for color_name, color_config in color_presets.items():
                h_range = color_config.get('h_range', [0, 10])
                s_range = color_config.get('s_range', [50, 255])
                v_range = color_config.get('v_range', [50, 255])
                
                # Création du masque de couleur
                lower = np.array([h_range[0], s_range[0], v_range[0]])
                upper = np.array([h_range[1], s_range[1], v_range[1]])
                mask = cv2.inRange(hsv, lower, upper)
                
                # Gestion du rouge (qui traverse 0 en teinte)
                if 'secondary_h' in color_config:
                    sec_h = color_config['secondary_h']
                    lower2 = np.array([sec_h[0], s_range[0], v_range[0]])
                    upper2 = np.array([sec_h[1], s_range[1], v_range[1]])
                    mask2 = cv2.inRange(hsv, lower2, upper2)
                    mask = cv2.bitwise_or(mask, mask2)
                
                # Morphologie
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.led_kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.led_kernel)
                
                # Détection de contours
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for i, contour in enumerate(contours):
                    area = cv2.contourArea(contour)
                    
                    # Filtrage par aire
                    if area < 20 or area > 2000:
                        continue
                    
                    # Centre de masse
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                    else:
                        continue
                    
                    # Boîte englobante
                    x, y, w, h = cv2.boundingRect(contour)
                    corners = [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]
                    
                    result = DetectionResult(
                        target_type=TargetType.LED,
                        id=hash(color_name) % 1000 + i,  # ID basé sur couleur + index
                        center=(cx, cy),
                        corners=corners,
                        confidence=min(1.0, area / 500.0),  # Confiance basée sur taille
                        size=float(np.sqrt(area)),
                        rotation=0.0,
                        timestamp=time.time(),
                        additional_data={
                            'color': color_name,
                            'area': area,
                            'hsv_mask_pixels': cv2.countNonZero(mask)
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