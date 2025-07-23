#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/hardware/usb3_camera_driver.py
Driver pour caméra USB3 CMOS entièrement configurable JSON - Version 1.3
Modification: Configuration 100% dynamique via camera_config.json pour correction image noire
"""

import cv2
import numpy as np
import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from threading import Thread, Lock, Event

logger = logging.getLogger(__name__)

class USB3CameraError(Exception):
    """Exception spécifique aux caméras USB3"""
    pass

class USB3CameraDriver:
    """Driver pour caméra USB3 CMOS entièrement configurable via JSON"""
    
    def __init__(self, device_id: int = 0, config: Optional[Dict] = None):
        self.device_id = device_id
        self.config = config or {}
        
        # État de la caméra
        self.cap = None
        self.is_open = False
        self.is_streaming = False
        
        # Configuration depuis JSON avec fallback optimisés pour image noire
        self.width = self.config.get('width', 640)
        self.height = self.config.get('height', 480)
        self.fps = self.config.get('fps', 30)
        self.buffer_size = self.config.get('buffer_size', 1)
        
        # PARAMÈTRES CORRIGÉS POUR IMAGE NOIRE - Configurables JSON
        self.auto_exposure = self.config.get('auto_exposure', False)  # Désactivé par défaut
        self.exposure = self.config.get('exposure', -4)  # Exposition plus élevée
        self.gain = self.config.get('gain', 30)          # Gain augmenté
        self.brightness = self.config.get('brightness', 150)  # Luminosité élevée (0-255)
        self.contrast = self.config.get('contrast', 80)       # Contraste élevé (0-100)
        self.saturation = self.config.get('saturation', 70)   # Saturation (0-100)
        
        # PARAMÈTRES AVANCÉS CONFIGURABLES
        self.backend_preference = self.config.get('backend_preference', ['dshow', 'msmf', 'auto'])
        self.stabilization_delay = self.config.get('stabilization_delay', 1.0)  # Délai stabilisation
        self.intensity_target = self.config.get('intensity_target', 40.0)  # Intensité cible
        self.emergency_boost = self.config.get('emergency_boost', True)  # Boost automatique
        
        # Streaming
        self.streaming_thread = None
        self.streaming_stop_event = Event()
        self.frame_lock = Lock()
        self.latest_frame = None
        
        logger.info(f"🔧 USB3CameraDriver configurable initialisé (device_id={device_id})")
        logger.debug(f"📋 Config: exp={self.exposure}, gain={self.gain}, brightness={self.brightness}")
    
    def open(self) -> bool:
        """Ouvre la connexion avec la caméra en utilisant la config JSON"""
        try:
            if self.is_open:
                logger.warning("⚠️ Caméra déjà ouverte")
                return True
            
            logger.info(f"📷 Ouverture caméra USB3 {self.device_id}...")
            
            # Test des backends selon préférence de config
            backend_map = {
                'dshow': cv2.CAP_DSHOW,
                'msmf': cv2.CAP_MSMF,
                'v4l2': cv2.CAP_V4L2,
                'auto': -1
            }
            
            backends_to_try = []
            for backend_name in self.backend_preference:
                if backend_name in backend_map:
                    backends_to_try.append((backend_map[backend_name], backend_name))
            
            # Fallback si config invalide
            if not backends_to_try:
                backends_to_try = [(cv2.CAP_DSHOW, "DirectShow"), (-1, "Auto")]
            
            for backend_id, backend_name in backends_to_try:
                try:
                    logger.debug(f"🔍 Test backend {backend_name}...")
                    
                    if backend_id == -1:
                        self.cap = cv2.VideoCapture(self.device_id)
                    else:
                        self.cap = cv2.VideoCapture(self.device_id, backend_id)
                    
                    if self.cap.isOpened():
                        logger.info(f"✅ Backend {backend_name} sélectionné")
                        break
                    else:
                        if self.cap:
                            self.cap.release()
                        self.cap = None
                        
                except Exception as e:
                    logger.debug(f"❌ Backend {backend_name} échoué: {e}")
                    if self.cap:
                        self.cap.release()
                    self.cap = None
                    continue
            
            if not self.cap or not self.cap.isOpened():
                raise USB3CameraError(f"Impossible d'ouvrir la caméra {self.device_id}")
            
            # Configuration des paramètres depuis JSON
            self._configure_camera_from_json()
            
            # Test de capture avec validation d'intensité
            success = self._validate_image_quality()
            if not success:
                logger.warning("⚠️ Qualité d'image insuffisante, mais on continue")
            
            self.is_open = True
            logger.info(f"✅ Caméra USB3 {self.device_id} ouverte avec succès")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur ouverture caméra USB3: {e}")
            self.close()
            return False
    
    def _configure_camera_from_json(self):
        """Configuration complète de la caméra depuis les paramètres JSON"""
        if not self.cap:
            return
        
        logger.info("🔧 Configuration caméra depuis paramètres JSON...")
        
        # === PARAMÈTRES DE BASE ===
        logger.debug(f"📐 Résolution: {self.width}x{self.height} @ {self.fps}fps")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
        
        # === CORRECTION IMAGE NOIRE - PARAMÈTRES JSON ===
        logger.debug(f"💡 Luminosité/Contraste: {self.brightness}/{self.contrast}")
        
        # Auto-exposition selon config
        auto_exp_value = 1 if self.auto_exposure else 0
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, auto_exp_value)
        logger.debug(f"📸 Auto-exposition: {'ON' if self.auto_exposure else 'OFF'}")
        
        # Paramètres de luminosité depuis JSON
        # Note: OpenCV utilise des valeurs normalisées (0.0-1.0) pour certains paramètres
        brightness_normalized = self.brightness / 255.0  # Conversion 0-255 -> 0.0-1.0
        contrast_normalized = self.contrast / 100.0       # Conversion 0-100 -> 0.0-1.0
        saturation_normalized = self.saturation / 100.0   # Conversion 0-100 -> 0.0-1.0
        
        self.cap.set(cv2.CAP_PROP_BRIGHTNESS, brightness_normalized)
        self.cap.set(cv2.CAP_PROP_CONTRAST, contrast_normalized)
        self.cap.set(cv2.CAP_PROP_SATURATION, saturation_normalized)
        self.cap.set(cv2.CAP_PROP_GAIN, self.gain)
        
        # Exposition manuelle si nécessaire
        if not self.auto_exposure:
            self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
            logger.debug(f"📸 Exposition manuelle: {self.exposure}")
        
        # === ATTENDRE STABILISATION (configurable) ===
        logger.debug(f"⏳ Stabilisation pendant {self.stabilization_delay}s...")
        time.sleep(self.stabilization_delay)
        
        # Vérifier les paramètres appliqués
        self._log_applied_parameters()
    
    def _log_applied_parameters(self):
        """Affiche les paramètres réellement appliqués par OpenCV"""
        try:
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            actual_brightness = self.cap.get(cv2.CAP_PROP_BRIGHTNESS)
            actual_contrast = self.cap.get(cv2.CAP_PROP_CONTRAST)
            actual_exposure = self.cap.get(cv2.CAP_PROP_EXPOSURE)
            actual_gain = self.cap.get(cv2.CAP_PROP_GAIN)
            actual_auto_exp = self.cap.get(cv2.CAP_PROP_AUTO_EXPOSURE)
            
            logger.info(f"📐 Appliqué: {actual_width}x{actual_height} @ {actual_fps:.1f}fps")
            logger.debug(f"💡 Luminosité: {actual_brightness:.3f} (demandé: {self.brightness/255:.3f})")
            logger.debug(f"📊 Contraste: {actual_contrast:.3f} (demandé: {self.contrast/100:.3f})")
            logger.debug(f"📸 Exposition: {actual_exposure:.2f} (demandé: {self.exposure})")
            logger.debug(f"📈 Gain: {actual_gain:.2f} (demandé: {self.gain})")
            logger.debug(f"🔄 Auto-exp: {actual_auto_exp} (demandé: {1 if self.auto_exposure else 0})")
            
        except Exception as e:
            logger.warning(f"⚠️ Impossible de lire les paramètres appliqués: {e}")
    
    def _validate_image_quality(self) -> bool:
        """Valide la qualité de l'image selon les paramètres JSON"""
        logger.debug(f"🧪 Validation qualité image (cible: {self.intensity_target})...")
        
        # Plusieurs tentatives avec attente progressive
        for attempt in range(5):
            try:
                ret, frame = self.cap.read()
                
                if not ret or frame is None:
                    logger.debug(f"⚠️ Tentative {attempt+1}: Pas de frame")
                    time.sleep(0.2)
                    continue
                
                # Analyse de l'intensité
                mean_intensity = np.mean(frame)
                min_val = np.min(frame)
                max_val = np.max(frame)
                
                logger.debug(f"📊 Tentative {attempt+1}: Intensité={mean_intensity:.1f}, Min/Max={min_val}/{max_val}")
                
                # Diagnostic basé sur la cible configurable
                if mean_intensity < (self.intensity_target * 0.2):  # Moins de 20% de la cible
                    logger.warning(f"⚠️ Image très sombre (intensité: {mean_intensity:.1f}, cible: {self.intensity_target})")
                    if attempt < 4 and self.emergency_boost:  # Boost d'urgence si activé en config
                        logger.debug("🚨 Boost d'urgence activé...")
                        self._apply_emergency_boost()
                        time.sleep(0.5)
                        continue
                elif mean_intensity < (self.intensity_target * 0.5):  # Moins de 50% de la cible
                    logger.info(f"⚠️ Image sombre (intensité: {mean_intensity:.1f}, cible: {self.intensity_target})")
                else:
                    logger.info(f"✅ Image correcte (intensité: {mean_intensity:.1f}, cible: {self.intensity_target})")
                
                return mean_intensity >= (self.intensity_target * 0.3)  # Au moins 30% de la cible
                
            except Exception as e:
                logger.error(f"❌ Erreur validation tentative {attempt+1}: {e}")
                if attempt < 4:
                    time.sleep(0.2)
                    continue
                else:
                    return False
        
        logger.warning("⚠️ Validation échouée après 5 tentatives")
        return False
    
    def _apply_emergency_boost(self):
        """Applique un boost d'urgence configurable depuis JSON"""
        if not self.emergency_boost:
            return
        
        try:
            # Paramètres d'urgence - Configurables via JSON
            emergency_brightness = self.config.get('emergency_brightness', 200)  # Plus élevé
            emergency_contrast = self.config.get('emergency_contrast', 90)       # Plus élevé
            emergency_gain = self.config.get('emergency_gain', 50)               # Plus élevé
            emergency_exposure = self.config.get('emergency_exposure', -3)       # Plus élevé
            
            logger.debug(f"🚨 Boost d'urgence: luminosité={emergency_brightness}, contraste={emergency_contrast}")
            
            # Application des paramètres d'urgence
            self.cap.set(cv2.CAP_PROP_BRIGHTNESS, emergency_brightness / 255.0)
            self.cap.set(cv2.CAP_PROP_CONTRAST, emergency_contrast / 100.0)
            self.cap.set(cv2.CAP_PROP_GAIN, emergency_gain)
            
            # Forcer exposition manuelle pour le boost
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, emergency_exposure)
            
        except Exception as e:
            logger.warning(f"⚠️ Échec boost d'urgence: {e}")
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Capture une frame avec diagnostic optionnel"""
        if not self.is_open or not self.cap:
            return None
        
        try:
            ret, frame = self.cap.read()
            if ret and frame is not None:
                # Diagnostic optionnel selon config
                if self.config.get('debug_intensity', False):
                    intensity = np.mean(frame)
                    if intensity < self.intensity_target * 0.5:
                        logger.debug(f"⚠️ Frame sombre: intensité {intensity:.1f} (cible: {self.intensity_target})")
                
                return frame
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur capture frame: {e}")
            return None
    
    def start_streaming(self) -> bool:
        """Démarre le streaming en arrière-plan"""
        if self.is_streaming:
            return True
        
        if not self.is_open:
            return False
        
        try:
            self.streaming_stop_event.clear()
            self.streaming_thread = Thread(target=self._streaming_loop, daemon=True)
            self.streaming_thread.start()
            
            self.is_streaming = True
            logger.info("🎬 Streaming USB3 démarré")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage streaming: {e}")
            return False
    
    def stop_streaming(self):
        """Arrête le streaming"""
        if not self.is_streaming:
            return
        
        self.streaming_stop_event.set()
        
        if self.streaming_thread and self.streaming_thread.is_alive():
            self.streaming_thread.join(timeout=2.0)
        
        self.is_streaming = False
        logger.info("⏹️ Streaming USB3 arrêté")
    
    def _streaming_loop(self):
        """Boucle de streaming en arrière-plan"""
        while not self.streaming_stop_event.is_set():
            frame = self.get_frame()
            
            if frame is not None:
                with self.frame_lock:
                    self.latest_frame = frame.copy()
            
            time.sleep(1.0 / self.fps)
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Récupère la dernière frame du streaming"""
        with self.frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None
    
    def close(self):
        """Ferme la caméra"""
        if self.is_streaming:
            self.stop_streaming()
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.is_open = False
        logger.info(f"🔒 Caméra USB3 {self.device_id} fermée")
    
    def get_info(self) -> Dict[str, Any]:
        """Retourne les informations de la caméra"""
        if not self.is_open:
            return {
                'device_id': self.device_id,
                'status': 'closed',
                'width': 0,
                'height': 0,
                'fps': 0
            }
        
        return {
            'device_id': self.device_id,
            'status': 'open',
            'streaming': self.is_streaming,
            'width': int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': self.cap.get(cv2.CAP_PROP_FPS),
            'brightness': self.cap.get(cv2.CAP_PROP_BRIGHTNESS),
            'contrast': self.cap.get(cv2.CAP_PROP_CONTRAST),
            'exposure': self.cap.get(cv2.CAP_PROP_EXPOSURE),
            'gain': self.cap.get(cv2.CAP_PROP_GAIN),
            'configured_intensity_target': self.intensity_target
        }
    
    def reconfigure(self, new_config: Dict[str, Any]):
        """Reconfiguration dynamique depuis JSON"""
        logger.info("🔄 Reconfiguration dynamique des paramètres...")
        
        # Mise à jour de la config interne
        self.config.update(new_config)
        
        # Re-lecture des paramètres
        self.brightness = self.config.get('brightness', self.brightness)
        self.contrast = self.config.get('contrast', self.contrast)
        self.saturation = self.config.get('saturation', self.saturation)
        self.gain = self.config.get('gain', self.gain)
        self.exposure = self.config.get('exposure', self.exposure)
        self.auto_exposure = self.config.get('auto_exposure', self.auto_exposure)
        self.intensity_target = self.config.get('intensity_target', self.intensity_target)
        
        # Re-application si caméra ouverte
        if self.is_open:
            self._configure_camera_from_json()
            logger.info("✅ Reconfiguration appliquée")
        
    def __enter__(self):
        """Context manager entry"""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

# Fonctions utilitaires
def list_available_cameras() -> List[Dict[str, Any]]:
    """Liste toutes les caméras USB disponibles"""
    cameras = []
    
    # Test des indices 0 à 5
    for device_id in range(6):
        cap = cv2.VideoCapture(device_id)
        
        if cap.isOpened():
            ret, frame = cap.read()
            
            if ret:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                
                cameras.append({
                    'device_id': device_id,
                    'name': f'USB Camera {device_id}',
                    'width': width,
                    'height': height,
                    'fps': fps,
                    'type': 'USB3'
                })
        
        cap.release()
    
    logger.info(f"🔍 {len(cameras)} caméra(s) USB détectée(s)")
    return cameras

def test_camera(device_id: int, duration: float = 3.0) -> bool:
    """Test rapide d'une caméra USB"""
    config = {
        'auto_exposure': False,
        'exposure': -4,
        'gain': 30,
        'brightness': 150,
        'contrast': 80,
        'intensity_target': 40.0
    }
    
    try:
        with USB3CameraDriver(device_id, config) as camera:
            if not camera.is_open:
                return False
            
            start_time = time.time()
            frame_count = 0
            
            while time.time() - start_time < duration:
                frame = camera.get_frame()
                if frame is not None:
                    frame_count += 1
                time.sleep(0.1)
            
            fps_measured = frame_count / duration
            return fps_measured > 10
            
    except Exception as e:
        logger.error(f"❌ Test échoué: {e}")
        return False

# Alias pour compatibilité
USB3Camera = USB3CameraDriver