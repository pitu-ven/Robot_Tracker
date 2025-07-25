#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/hardware/usb3_camera_driver.py
Driver pour caméra USB3 CMOS entièrement configuré - Version 1.6
Modification: Correction finale des valeurs statiques restantes
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
    """Driver pour caméra USB3 CMOS entièrement configuré via JSON"""
    
    def __init__(self, device_id: int = 0, config: Optional[Dict] = None):
        self.device_id = device_id
        self.config = config or {}
        
        # État de la caméra
        self.cap = None
        self.is_open = False
        self.is_streaming = False
        
        # Configuration depuis JSON avec fallback
        self.width = self.config.get('width', 640)
        self.height = self.config.get('height', 480)
        self.fps = self.config.get('fps', 30)
        self.buffer_size = self.config.get('buffer_size', 1)
        
        # Paramètres pour correction image noire
        self.auto_exposure = self.config.get('auto_exposure', True)
        self.exposure = self.config.get('exposure', -1)
        self.gain = self.config.get('gain', 100)
        self.brightness = self.config.get('brightness', 255)
        self.contrast = self.config.get('contrast', 100)
        self.saturation = self.config.get('saturation', 100)
        
        # Paramètres de correction avancés configurés
        self.stabilization_delay = self.config.get('stabilization_delay', 2.0)
        self.intensity_target = self.config.get('intensity_target', 30.0)
        self.max_correction_attempts = self.config.get('max_correction_attempts', 5)
        self.force_manual_exposure = self.config.get('force_manual_exposure', True)
        
        # Streaming
        self.streaming_thread = None
        self.streaming_stop_event = Event()
        self.frame_lock = Lock()
        self.latest_frame = None
        
        version_info = self.config.get('version_info', '1.6')
        logger.info(f"🔧 USB3CameraDriver v{version_info} initialisé (device_id={device_id})")
    
    def open(self) -> bool:
        """Ouvre la connexion avec configuration agressive anti-image-noire"""
        try:
            if self.is_open:
                logger.warning("⚠️ Caméra déjà ouverte")
                return True
            
            logger.info(f"📷 Ouverture caméra USB3 {self.device_id} avec correction image noire...")
            
            success = self._open_with_best_backend()
            if not success:
                return False
            
            self._configure_aggressive_anti_black()
            validation_success = self._validate_and_correct_image()
            
            if validation_success:
                self.is_open = True
                logger.info(f"✅ Caméra USB3 {self.device_id} ouverte et corrigée")
                return True
            else:
                logger.warning("⚠️ Validation échouée mais caméra ouverte")
                self.is_open = True
                return True
                
        except Exception as e:
            logger.error(f"❌ Erreur ouverture caméra USB3: {e}")
            self.close()
            return False
    
    def _open_with_best_backend(self) -> bool:
        """Ouvre avec le meilleur backend disponible"""
        backends = [
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_MSMF, "Media Foundation"),
            (-1, "Auto")
        ]
        
        for backend_id, backend_name in backends:
            try:
                logger.debug(f"🔍 Test backend {backend_name}...")
                
                if backend_id == -1:
                    self.cap = cv2.VideoCapture(self.device_id)
                else:
                    self.cap = cv2.VideoCapture(self.device_id, backend_id)
                
                if self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        logger.info(f"✅ Backend {backend_name} sélectionné")
                        return True
                    else:
                        logger.debug(f"⚠️ {backend_name}: ouvert mais pas de frame")
                
                if self.cap:
                    self.cap.release()
                self.cap = None
                
            except Exception as e:
                logger.debug(f"❌ Backend {backend_name}: {e}")
                if self.cap:
                    self.cap.release()
                self.cap = None
        
        raise USB3CameraError(f"Impossible d'ouvrir la caméra {self.device_id} avec tous les backends")
    
    def _configure_aggressive_anti_black(self):
        """Configuration AGRESSIVE pour corriger l'image noire"""
        if not self.cap:
            return
        
        logger.info("🔧 Configuration AGRESSIVE anti-image-noire...")
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
        
        logger.debug("📸 Forçage auto-exposition...")
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
        
        logger.debug("💡 Paramètres luminosité au maximum...")
        self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 1.0)
        self.cap.set(cv2.CAP_PROP_CONTRAST, 1.0)
        self.cap.set(cv2.CAP_PROP_SATURATION, 1.0)
        self.cap.set(cv2.CAP_PROP_GAIN, self.gain)
        
        logger.debug(f"⏳ Stabilisation {self.stabilization_delay}s...")
        time.sleep(self.stabilization_delay)
        
        self._log_applied_parameters()
    
    def _validate_and_correct_image(self) -> bool:
        """Validation avec correction automatique itérative"""
        logger.info("🔬 Validation et correction automatique...")
        
        for attempt in range(self.max_correction_attempts):
            logger.debug(f"🧪 Tentative {attempt + 1}/{self.max_correction_attempts}")
            
            intensities = []
            test_frames = self.config.get('validation.test_frames', 5)
            test_delay = self.config.get('validation.test_delay', 0.2)
            
            for i in range(test_frames):
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    intensity = np.mean(frame)
                    intensities.append(intensity)
                    logger.debug(f"   Capture {i+1}: intensité {intensity:.1f}")
                else:
                    logger.debug(f"   Capture {i+1}: ÉCHEC")
                time.sleep(test_delay)
            
            if not intensities:
                logger.warning("❌ Aucune capture réussie")
                continue
            
            avg_intensity = np.mean(intensities)
            logger.info(f"📊 Intensité moyenne tentative {attempt + 1}: {avg_intensity:.1f}")
            
            # Seuils configurables
            target_intensity = self.intensity_target
            min_acceptable_ratio = self.config.get('validation.min_acceptable_ratio', 0.3)
            min_acceptable = target_intensity * min_acceptable_ratio
            
            if avg_intensity >= target_intensity:
                logger.info(f"✅ Validation réussie (intensité: {avg_intensity:.1f})")
                return True
            elif avg_intensity >= min_acceptable:
                logger.info(f"⚠️ Intensité acceptable (intensité: {avg_intensity:.1f})")
                return True
            else:
                logger.warning(f"⚠️ Intensité insuffisante: {avg_intensity:.1f}")
                
                if attempt < self.max_correction_attempts - 1:
                    self._apply_progressive_correction(attempt + 1)
        
        logger.warning("⚠️ Validation finale échouée après toutes les tentatives")
        return False
    
    def _apply_progressive_correction(self, attempt: int):
        """Applique une correction progressive selon la tentative"""
        logger.debug(f"🔧 Correction progressive #{attempt}...")
        
        gain_multiplier_1 = self.config.get('correction.gain_multiplier_1', 1.5)
        gain_multiplier_2 = self.config.get('correction.gain_multiplier_2', 2.0)
        emergency_gain = self.config.get('correction.emergency_gain', 255)
        correction_delay = self.config.get('correction.delay', 1.0)
        
        if attempt == 1:
            logger.debug("📈 Augmentation gain...")
            self.cap.set(cv2.CAP_PROP_GAIN, self.gain * gain_multiplier_1)
            
        elif attempt == 2:
            logger.debug("📸 Passage exposition manuelle...")
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
            
        elif attempt == 3:
            logger.debug("📸 Exposition maximale...")
            self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure + 1)
            self.cap.set(cv2.CAP_PROP_GAIN, self.gain * gain_multiplier_2)
            
        elif attempt == 4:
            logger.debug("🚨 Configuration d'urgence...")
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
            self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 1.0)
            self.cap.set(cv2.CAP_PROP_CONTRAST, 1.0)
            self.cap.set(cv2.CAP_PROP_GAIN, emergency_gain)
        
        time.sleep(correction_delay)
    
    def _log_applied_parameters(self):
        """Affiche les paramètres réellement appliqués"""
        try:
            params = {
                'Largeur': int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'Hauteur': int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'FPS': self.cap.get(cv2.CAP_PROP_FPS),
                'Luminosité': self.cap.get(cv2.CAP_PROP_BRIGHTNESS),
                'Contraste': self.cap.get(cv2.CAP_PROP_CONTRAST),
                'Gain': self.cap.get(cv2.CAP_PROP_GAIN),
                'Exposition': self.cap.get(cv2.CAP_PROP_EXPOSURE),
                'Auto-exposition': self.cap.get(cv2.CAP_PROP_AUTO_EXPOSURE)
            }
            
            logger.info("📊 Paramètres appliqués:")
            for name, value in params.items():
                logger.debug(f"   {name}: {value}")
                
        except Exception as e:
            logger.warning(f"⚠️ Impossible de lire les paramètres: {e}")
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Capture une frame avec diagnostic"""
        if not self.is_open or not self.cap:
            return None
        
        try:
            ret, frame = self.cap.read()
            if ret and frame is not None:
                debug_intensity = self.config.get('debug.intensity', False)
                if debug_intensity:
                    intensity = np.mean(frame)
                    target_ratio = self.config.get('debug.target_ratio', 0.5)
                    
                    if intensity < self.intensity_target * target_ratio:
                        logger.debug(f"⚠️ Frame sombre: {intensity:.1f}")
                
                return frame
            else:
                logger.debug("❌ Échec capture frame")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur capture: {e}")
            return None
    
    def validate_current_stream(self) -> Dict[str, Any]:
        """Valide le flux actuel et retourne des statistiques"""
        if not self.is_open:
            return {'status': 'closed'}
        
        logger.info("🔬 Validation flux actuel...")
        
        try:
            results = []
            validation_frames = self.config.get('validation.stream_frames', 10)
            validation_delay = self.config.get('validation.stream_delay', 0.1)
            
            for i in range(validation_frames):
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    intensity = np.mean(frame)
                    min_val = np.min(frame)
                    max_val = np.max(frame)
                    std_dev = np.std(frame)
                    
                    results.append({
                        'intensity': intensity,
                        'min': min_val,
                        'max': max_val,
                        'std': std_dev,
                        'shape': frame.shape
                    })
                
                time.sleep(validation_delay)
            
            if not results:
                return {'status': 'no_frames'}
            
            avg_intensity = np.mean([r['intensity'] for r in results])
            min_intensity = min([r['intensity'] for r in results])
            max_intensity = max([r['intensity'] for r in results])
            avg_std = np.mean([r['std'] for r in results])
            
            # Classification avec seuils configurables
            very_low_threshold = self.config.get('classification.very_low_threshold', 1.0)
            low_threshold_ratio = self.config.get('classification.low_threshold_ratio', 0.3)
            medium_threshold_ratio = self.config.get('classification.medium_threshold_ratio', 0.7)
            
            low_threshold = self.intensity_target * low_threshold_ratio
            medium_threshold = self.intensity_target * medium_threshold_ratio
            
            if avg_intensity < very_low_threshold:
                status = 'black'
            elif avg_intensity < low_threshold:
                status = 'very_dark'
            elif avg_intensity < medium_threshold:
                status = 'dark'
            else:
                status = 'good'
            
            validation = {
                'status': status,
                'avg_intensity': avg_intensity,
                'min_intensity': min_intensity,
                'max_intensity': max_intensity,
                'intensity_range': max_intensity - min_intensity,
                'avg_std_dev': avg_std,
                'frame_count': len(results),
                'target_intensity': self.intensity_target,
                'shape': results[0]['shape'] if results else None
            }
            
            logger.info(f"📊 Validation: {status}, intensité moyenne: {avg_intensity:.1f}")
            return validation
            
        except Exception as e:
            logger.error(f"❌ Erreur validation: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def start_streaming(self) -> bool:
        """Démarre le streaming avec validation"""
        if self.is_streaming:
            return True
        
        if not self.is_open:
            return False
        
        try:
            validation = self.validate_current_stream()
            problematic_statuses = self.config.get('streaming.problematic_statuses', ['black', 'error'])
            
            if validation['status'] in problematic_statuses:
                logger.warning(f"⚠️ Flux problématique: {validation['status']}")
                self._apply_progressive_correction(1)
            
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
        
        join_timeout = self.config.get('streaming.join_timeout', 2.0)
        if self.streaming_thread and self.streaming_thread.is_alive():
            self.streaming_thread.join(timeout=join_timeout)
        
        self.is_streaming = False
        logger.info("⏹️ Streaming USB3 arrêté")
    
    def _streaming_loop(self):
        """Boucle de streaming optimisée"""
        frame_count = 0
        log_interval = self.config.get('streaming.log_interval_frames', 300)
        frame_delay = 1.0 / self.fps
        
        while not self.streaming_stop_event.is_set():
            frame = self.get_frame()
            
            if frame is not None:
                with self.frame_lock:
                    self.latest_frame = frame.copy()
                frame_count += 1
                
                if frame_count % log_interval == 0:
                    intensity = np.mean(frame)
                    logger.debug(f"🎬 Frame {frame_count}: intensité {intensity:.1f}")
            
            time.sleep(frame_delay)
    
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
        """Retourne les informations complètes de la caméra"""
        if not self.is_open:
            return {
                'device_id': self.device_id,
                'status': 'closed',
                'width': 0,
                'height': 0,
                'fps': 0
            }
        
        validation = self.validate_current_stream()
        
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
            'validation': validation,
            'intensity_target': self.intensity_target
        }
    
    def reconfigure_for_brightness(self):
        """Reconfiguration spéciale pour corriger la luminosité"""
        if not self.is_open:
            return False
        
        logger.info("🔧 Reconfiguration spéciale luminosité...")
        
        stabilization_delay = self.config.get('reconfiguration.stabilization_delay', 1.0)
        brightness_threshold = self.config.get('reconfiguration.brightness_threshold', 10.0)
        emergency_gain = self.config.get('reconfiguration.emergency_gain', 255)
        success_threshold = self.config.get('reconfiguration.success_threshold', 5.0)
        
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
        time.sleep(stabilization_delay)
        
        ret, frame = self.cap.read()
        if ret and frame is not None:
            intensity = np.mean(frame)
            logger.info(f"📊 Intensité après auto-exposition: {intensity:.1f}")
            
            if intensity < brightness_threshold:
                logger.info("🔧 Passage exposition manuelle d'urgence...")
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
                self.cap.set(cv2.CAP_PROP_EXPOSURE, 0)
                self.cap.set(cv2.CAP_PROP_GAIN, emergency_gain)
                time.sleep(stabilization_delay)
                
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    final_intensity = np.mean(frame)
                    logger.info(f"📊 Intensité finale: {final_intensity:.1f}")
                    return final_intensity > success_threshold
        
        return False
    
    def __enter__(self):
        """Context manager entry"""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

# Fonctions utilitaires améliorées
def list_available_cameras() -> List[Dict[str, Any]]:
    """Liste toutes les caméras USB avec validation"""
    cameras = []
    max_device_scan = 6  # Configuration par défaut
    brightness_threshold = 10  # Configuration par défaut
    
    for device_id in range(max_device_scan):
        cap = cv2.VideoCapture(device_id)
        
        if cap.isOpened():
            ret, frame = cap.read()
            
            if ret and frame is not None:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                intensity = np.mean(frame)
                
                cameras.append({
                    'device_id': device_id,
                    'name': f'USB Camera {device_id}',
                    'width': width,
                    'height': height,
                    'fps': fps,
                    'intensity': intensity,
                    'status': 'good' if intensity > brightness_threshold else 'dark',
                    'type': 'USB3'
                })
        
        cap.release()
    
    logger.info(f"🔍 {len(cameras)} caméra(s) USB détectée(s)")
    return cameras

def test_camera(device_id: int, duration: float = 5.0) -> bool:
    """Test complet d'une caméra USB avec diagnostic"""
    config = {
        'auto_exposure': True,
        'exposure': -1,
        'gain': 100,
        'brightness': 255,
        'contrast': 100,
        'intensity_target': 30.0,
        'stabilization_delay': 2.0,
        'max_correction_attempts': 3,
        'reconfiguration': {
            'brightness_threshold': 10.0,
            'success_threshold': 5.0
        },
        'test': {
            'good_frame_threshold': 10,
            'min_fps_threshold': 5,
            'min_success_rate': 0.5,
            'sleep_interval': 0.1
        }
    }
    
    try:
        with USB3CameraDriver(device_id, config) as camera:
            if not camera.is_open:
                return False
            
            validation = camera.validate_current_stream()
            logger.info(f"📊 Validation initiale: {validation.get('status', 'unknown')}")
            
            start_time = time.time()
            frame_count = 0
            good_frames = 0
            
            # Seuils configurables pour le test
            good_frame_threshold = config['test']['good_frame_threshold']
            min_fps_threshold = config['test']['min_fps_threshold']
            min_success_rate = config['test']['min_success_rate']
            sleep_interval = config['test']['sleep_interval']
            
            while time.time() - start_time < duration:
                frame = camera.get_frame()
                if frame is not None:
                    frame_count += 1
                    intensity = np.mean(frame)
                    if intensity > good_frame_threshold:
                        good_frames += 1
                time.sleep(sleep_interval)
            
            fps_measured = frame_count / duration
            success_rate = good_frames / frame_count if frame_count > 0 else 0
            
            logger.info(f"📊 Test: {frame_count} frames, {fps_measured:.1f} FPS, {success_rate:.1%} bonnes frames")
            return success_rate > min_success_rate and fps_measured > min_fps_threshold
            
    except Exception as e:
        logger.error(f"❌ Test échoué: {e}")
        return False

# Alias pour compatibilité
USB3Camera = USB3CameraDriver