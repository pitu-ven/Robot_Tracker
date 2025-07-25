#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/core/camera_manager.py
Gestionnaire central des caméras sans valeurs statiques - Version 2.6
Modification: Suppression complète des valeurs hardcodées, configuration via JSON
"""

import cv2
import numpy as np
import time
import logging
from typing import Optional, Dict, Any, List, Tuple, Callable
from threading import Thread, Lock, Event
from enum import Enum
from dataclasses import dataclass

# Import des drivers avec gestion d'erreur améliorée
try:
    from hardware.usb3_camera_driver import USB3CameraDriver, list_available_cameras
except ImportError as e:
    raise ImportError(f"❌ Erreur import USB3CameraDriver: {e}")

logger = logging.getLogger(__name__)

# Import RealSense avec gestion d'erreur robuste
REALSENSE_AVAILABLE = False
try:
    import pyrealsense2 as rs
    from hardware.realsense_driver import RealSenseCamera, list_available_realsense
    REALSENSE_AVAILABLE = True
    logger.info("✅ RealSense importé avec succès")
except ImportError as e:
    logger.warning(f"⚠️ RealSense non disponible: {e}")
    REALSENSE_AVAILABLE = False

class CameraType(Enum):
    """Types de caméras supportées"""
    USB3_CAMERA = "usb3"
    REALSENSE = "realsense"
    UNKNOWN = "unknown"

@dataclass
class CameraInfo:
    """Classe pour stocker les informations d'une caméra"""
    camera_type: CameraType
    device_id: Any
    name: str
    details: Dict[str, Any]

class CameraManager:
    """Gestionnaire central pour toutes les caméras - Version entièrement configurable"""
    
    def __init__(self, config):
        self.config = config
        
        # Caméras actives
        self.active_cameras: Dict[str, Any] = {}
        self.available_cameras: List[CameraInfo] = []
        
        # Streaming
        self.streaming = False
        self.streaming_thread = None
        self.streaming_stop_event = Event()
        
        # Callbacks pour nouveaux frames
        self.frame_callbacks: List[Callable] = []
        
        # Cache des frames pour performance
        self.frame_cache: Dict[str, Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]] = {}
        self.cache_timestamps: Dict[str, float] = {}
        
        # Thread safety - locks simplifiés
        self.cameras_lock = Lock()
        self.cache_lock = Lock()
        
        # Configuration depuis JSON
        self.auto_detect_interval = self.config.get('camera', 'manager.auto_detect_interval', 5.0)
        self.max_frame_buffer = self.config.get('camera', 'manager.max_frame_buffer', 5)
        
        logger.info("🎥 CameraManager v2.6 initialisé (configuration complète)")
    
    def detect_all_cameras(self) -> List[CameraInfo]:
        """Détecte toutes les caméras disponibles (USB3 + RealSense) avec évitement des doublons"""
        logger.info("🔍 Détection globale des caméras...")
        
        all_cameras = []
        realsense_serials = set()
        
        # 1. Détection RealSense en priorité
        if REALSENSE_AVAILABLE:
            try:
                rs_cameras = list_available_realsense()
                for cam in rs_cameras:
                    camera_info = CameraInfo(
                        camera_type=CameraType.REALSENSE,
                        device_id=cam['serial'],
                        name=f"RealSense: {cam['name']} (S/N: {cam['serial']})",
                        details=cam
                    )
                    all_cameras.append(camera_info)
                    realsense_serials.add(cam['serial'])
                    logger.info(f"✅ RealSense trouvée: {camera_info.name}")
            except Exception as e:
                logger.error(f"❌ Erreur détection RealSense: {e}")
        else:
            logger.info("⚠️ RealSense non disponible")
        
        # 2. Détection USB3 (en excluant les RealSense déjà détectées)
        try:
            usb_cameras = list_available_cameras()
            usb_count = 0
            
            for cam in usb_cameras:
                camera_name = cam['name'].lower()
                is_likely_realsense = any([
                    'realsense' in camera_name,
                    'intel' in camera_name,
                    (len(realsense_serials) > 0 and 'usb camera' in camera_name)
                ])
                
                if not is_likely_realsense:
                    camera_info = CameraInfo(
                        camera_type=CameraType.USB3_CAMERA,
                        device_id=cam['device_id'],
                        name=f"USB3: {cam['name']}",
                        details=cam
                    )
                    all_cameras.append(camera_info)
                    usb_count += 1
                    logger.info(f"✅ USB3 trouvée: {camera_info.name}")
                else:
                    logger.debug(f"🔄 Caméra USB ignorée (probable RealSense): {cam['name']}")
            
            logger.info(f"🔍 {usb_count} caméra(s) USB distincte(s) détectée(s)")
            
        except Exception as e:
            logger.error(f"❌ Erreur détection USB3: {e}")
        
        self.available_cameras = all_cameras
        logger.info(f"📷 {len(all_cameras)} caméra(s) détectée(s) au total")
        
        return all_cameras
    
    def open_camera(self, camera_info: CameraInfo, alias: str = None) -> bool:
        """Ouvre une caméra spécifique"""
        camera_alias = alias or f"{camera_info.camera_type.value}_{camera_info.device_id}"
        
        logger.info(f"📷 Ouverture caméra: {camera_info.name} (alias: {camera_alias})")
        
        with self.cameras_lock:
            if camera_alias in self.active_cameras:
                logger.warning(f"⚠️ Caméra {camera_alias} déjà ouverte")
                return True
            
            try:
                if camera_info.camera_type == CameraType.USB3_CAMERA:
                    usb_config = {
                        'width': self.config.get('camera', 'usb3_camera.width', 640),
                        'height': self.config.get('camera', 'usb3_camera.height', 480),
                        'fps': self.config.get('camera', 'usb3_camera.fps', 30),
                        'buffer_size': self.config.get('camera', 'usb3_camera.buffer_size', 1),
                        'auto_exposure': self.config.get('camera', 'usb3_camera.auto_exposure', True),
                        'exposure': self.config.get('camera', 'usb3_camera.exposure', -6),
                        'gain': self.config.get('camera', 'usb3_camera.gain', 0)
                    }
                    
                    camera = USB3CameraDriver(camera_info.device_id, usb_config)
                    success = camera.open()
                    
                elif camera_info.camera_type == CameraType.REALSENSE:
                    if not REALSENSE_AVAILABLE:
                        logger.error("❌ RealSense non disponible")
                        return False
                    
                    camera = RealSenseCamera(self.config)
                    camera.device_serial = camera_info.device_id
                    success = camera.start_streaming()
                    
                else:
                    logger.error(f"❌ Type de caméra non supporté: {camera_info.camera_type}")
                    return False
                
                if success:
                    self.active_cameras[camera_alias] = {
                        'camera': camera,
                        'info': camera_info,
                        'last_frame_time': 0,
                        'frame_count': 0,
                        'is_active': True,
                        'poll_failures': 0
                    }
                    
                    # Initialiser le cache pour cette caméra
                    with self.cache_lock:
                        self.frame_cache[camera_alias] = (False, None, None)
                        self.cache_timestamps[camera_alias] = 0
                    
                    logger.info(f"✅ Caméra {camera_alias} ouverte avec succès")
                    return True
                else:
                    logger.error(f"❌ Échec ouverture caméra {camera_alias}")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Erreur ouverture caméra {camera_alias}: {e}")
                return False
    
    def close_camera(self, alias: str) -> bool:
        """Ferme une caméra spécifique"""
        logger.info(f"📷 Fermeture caméra: {alias}")
        
        with self.cameras_lock:
            if alias not in self.active_cameras:
                logger.warning(f"⚠️ Caméra {alias} non trouvée")
                return False
            
            try:
                cam_data = self.active_cameras[alias]
                camera = cam_data['camera']
                
                if cam_data['info'].camera_type == CameraType.USB3_CAMERA:
                    camera.close()
                elif cam_data['info'].camera_type == CameraType.REALSENSE:
                    camera.stop_streaming()
                
                del self.active_cameras[alias]
                
                with self.cache_lock:
                    if alias in self.frame_cache:
                        del self.frame_cache[alias]
                    if alias in self.cache_timestamps:
                        del self.cache_timestamps[alias]
                
                logger.info(f"✅ Caméra {alias} fermée")
                return True
                
            except Exception as e:
                logger.error(f"❌ Erreur fermeture caméra {alias}: {e}")
                return False
    
    def close_all_cameras(self):
        """Ferme toutes les caméras"""
        logger.info("📷 Fermeture de toutes les caméras...")
        
        with self.cameras_lock:
            aliases_to_close = list(self.active_cameras.keys())
            
        for alias in aliases_to_close:
            self.close_camera(alias)
        
        logger.info("✅ Toutes les caméras fermées")
    
    def get_camera_frame(self, alias: str) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """Récupère une frame d'une caméra spécifique - VERSION OPTIMISÉE"""
        # Vérification rapide dans le cache d'abord
        cache_max_age = self.config.get('ui', 'camera_manager.streaming.cache_max_age', 0.1)
        
        with self.cache_lock:
            if alias in self.frame_cache:
                cached_result = self.frame_cache[alias]
                cache_time = self.cache_timestamps.get(alias, 0)
                
                if time.time() - cache_time < cache_max_age and cached_result[0]:
                    return cached_result
        
        return self._acquire_fresh_frame(alias)
    
    def _acquire_fresh_frame(self, alias: str) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """Acquiert une frame fraîche (méthode interne)"""
        with self.cameras_lock:
            if alias not in self.active_cameras:
                return False, None, None
            
            cam_data = self.active_cameras[alias]
            if not cam_data.get('is_active', False):
                return False, None, None
                
            camera = cam_data['camera']
            current_time = time.time()
            
            try:
                if cam_data['info'].camera_type == CameraType.USB3_CAMERA:
                    if hasattr(camera, 'get_latest_frame') and camera.is_streaming:
                        frame = camera.get_latest_frame()
                    else:
                        frame = camera.get_frame()
                    
                    if frame is not None:
                        cam_data['last_frame_time'] = current_time
                        cam_data['frame_count'] += 1
                        cam_data['poll_failures'] = 0
                        result = (True, frame, None)
                    else:
                        cam_data['poll_failures'] += 1
                        result = (False, None, None)
                        
                elif cam_data['info'].camera_type == CameraType.REALSENSE:
                    success, color_frame, depth_frame = camera.get_frames()
                    
                    if success and color_frame is not None:
                        cam_data['last_frame_time'] = current_time
                        cam_data['frame_count'] += 1
                        cam_data['poll_failures'] = 0
                        result = (True, color_frame, depth_frame)
                    else:
                        cam_data['poll_failures'] += 1
                        with self.cache_lock:
                            if alias in self.frame_cache:
                                result = self.frame_cache[alias]
                            else:
                                result = (False, None, None)
                        
                else:
                    result = (False, None, None)
                
                if result[0]:
                    with self.cache_lock:
                        self.frame_cache[alias] = result
                        self.cache_timestamps[alias] = current_time
                
                return result
                    
            except Exception as e:
                logger.error(f"❌ Erreur récupération frame {alias}: {e}")
                cam_data['poll_failures'] += 1
                return False, None, None
    
    def get_all_frames(self) -> Dict[str, Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]]:
        """Récupère les frames de toutes les caméras actives - VERSION CACHE"""
        all_frames = {}
        
        with self.cache_lock:
            for alias in self.active_cameras.keys():
                if alias in self.frame_cache:
                    all_frames[alias] = self.frame_cache[alias]
                else:
                    all_frames[alias] = (False, None, None)
        
        return all_frames
    
    def start_streaming(self, frame_callback: Callable = None) -> bool:
        """Démarre le streaming de toutes les caméras - VERSION OPTIMISÉE"""
        if self.streaming:
            logger.warning("⚠️ Streaming déjà actif")
            return True
        
        if not self.active_cameras:
            logger.warning("⚠️ Aucune caméra ouverte pour streaming")
            return False
        
        if frame_callback:
            self.frame_callbacks.append(frame_callback)
        
        with self.cameras_lock:
            for alias, cam_data in self.active_cameras.items():
                camera = cam_data['camera']
                if cam_data['info'].camera_type == CameraType.USB3_CAMERA:
                    try:
                        camera.start_streaming()
                        logger.info(f"🎬 Streaming USB3 démarré pour {alias}")
                    except Exception as e:
                        logger.error(f"❌ Erreur démarrage streaming USB3 {alias}: {e}")
        
        self.streaming_stop_event.clear()
        self.streaming_thread = Thread(target=self._streaming_loop_optimized, daemon=True)
        self.streaming_thread.start()
        
        self.streaming = True
        logger.info("🎬 Streaming global démarré")
        return True
    
    def stop_streaming(self):
        """Arrête le streaming global"""
        if not self.streaming:
            return
        
        self.streaming_stop_event.set()
        
        if self.streaming_thread and self.streaming_thread.is_alive():
            join_timeout = self.config.get('ui', 'camera_manager.streaming.join_timeout', 1.0)
            self.streaming_thread.join(timeout=join_timeout)
        
        with self.cameras_lock:
            for alias, cam_data in self.active_cameras.items():
                camera = cam_data['camera']
                if cam_data['info'].camera_type == CameraType.USB3_CAMERA:
                    try:
                        camera.stop_streaming()
                        logger.info(f"⏹️ Streaming USB3 arrêté pour {alias}")
                    except Exception as e:
                        logger.error(f"❌ Erreur arrêt streaming USB3 {alias}: {e}")
        
        self.streaming = False
        logger.info("⏹️ Streaming global arrêté")
    
    def _streaming_loop_optimized(self):
        """Boucle principale de streaming - VERSION OPTIMISÉE CONFIGURÉE"""
        logger.debug("🔄 Début boucle streaming optimisée")
        
        frame_update_count = 0
        loop_count = 0
        last_successful_poll = {}
        
        # Configuration depuis JSON
        base_sleep_time = self.config.get('ui', 'camera_manager.streaming.base_sleep_time', 0.033)
        high_failure_threshold = self.config.get('ui', 'camera_manager.streaming.poll_failure_thresholds.high_failure', 10)
        medium_failure_threshold = self.config.get('ui', 'camera_manager.streaming.poll_failure_thresholds.medium_failure', 5)
        
        problematic_interval = self.config.get('ui', 'camera_manager.streaming.polling_intervals.problematic', 0.1)
        medium_interval = self.config.get('ui', 'camera_manager.streaming.polling_intervals.medium', 0.05)
        normal_interval = self.config.get('ui', 'camera_manager.streaming.polling_intervals.normal', 0.025)
        
        log_interval = self.config.get('ui', 'camera_manager.streaming.log_interval_loops', 300)
        
        while not self.streaming_stop_event.is_set():
            loop_count += 1
            updated_any = False
            current_time = time.time()
            
            try:
                with self.cameras_lock:
                    active_cameras_copy = dict(self.active_cameras)
                
                for alias, cam_data in active_cameras_copy.items():
                    if not cam_data.get('is_active', False):
                        continue
                    
                    poll_failures = cam_data.get('poll_failures', 0)
                    last_poll = last_successful_poll.get(alias, 0)
                    
                    if poll_failures > high_failure_threshold:
                        min_interval = problematic_interval
                    elif poll_failures > medium_failure_threshold:
                        min_interval = medium_interval
                    else:
                        min_interval = normal_interval
                    
                    if current_time - last_poll < min_interval:
                        continue
                    
                    camera = cam_data['camera']
                    
                    try:
                        if cam_data['info'].camera_type == CameraType.REALSENSE:
                            success, color_frame, depth_frame = camera.get_frames()
                            if success and color_frame is not None:
                                with self.cache_lock:
                                    self.frame_cache[alias] = (True, color_frame, depth_frame)
                                    self.cache_timestamps[alias] = current_time
                                
                                cam_data['last_frame_time'] = current_time
                                cam_data['frame_count'] += 1
                                cam_data['poll_failures'] = max(0, cam_data['poll_failures'] - 1)
                                
                                last_successful_poll[alias] = current_time
                                updated_any = True
                                
                        elif cam_data['info'].camera_type == CameraType.USB3_CAMERA:
                            if hasattr(camera, 'get_latest_frame') and camera.is_streaming:
                                frame = camera.get_latest_frame()
                                if frame is not None:
                                    with self.cache_lock:
                                        self.frame_cache[alias] = (True, frame, None)
                                        self.cache_timestamps[alias] = current_time
                                    
                                    cam_data['last_frame_time'] = current_time
                                    cam_data['frame_count'] += 1
                                    cam_data['poll_failures'] = max(0, cam_data['poll_failures'] - 1)
                                    
                                    last_successful_poll[alias] = current_time
                                    updated_any = True
                                    
                    except Exception as e:
                        cam_data['poll_failures'] = cam_data.get('poll_failures', 0) + 1
                        logger.debug(f"Poll échoué pour {alias}: {e}")
                        continue
                
                if updated_any:
                    frame_update_count += 1
                    
                    with self.cache_lock:
                        current_frames = dict(self.frame_cache)
                    
                    frame_max_age = self.config.get('ui', 'camera_manager.streaming.frame_max_age', 0.5)
                    valid_frames = {}
                    for alias, frames in current_frames.items():
                        cache_age = current_time - self.cache_timestamps.get(alias, 0)
                        if frames[0] and cache_age < frame_max_age:
                            valid_frames[alias] = frames
                    
                    if valid_frames:
                        for callback in self.frame_callbacks:
                            try:
                                callback(valid_frames)
                            except Exception as e:
                                logger.error(f"❌ Erreur callback streaming: {e}")
                
                if updated_any:
                    time.sleep(base_sleep_time)
                else:
                    time.sleep(base_sleep_time * 2)
                
                if loop_count % log_interval == 0:
                    logger.debug(f"🔄 Loop {loop_count}, {frame_update_count} frames, caméras actives: {len(active_cameras_copy)}")
                
            except Exception as e:
                logger.error(f"❌ Erreur boucle streaming: {e}")
                error_sleep = self.config.get('ui', 'camera_manager.streaming.error_sleep', 0.1)
                time.sleep(error_sleep)
        
        logger.debug(f"🛑 Fin boucle streaming optimisée ({frame_update_count} frames sur {loop_count} loops)")
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Récupère les statistiques de toutes les caméras"""
        stats = {}
        
        with self.cameras_lock:
            for alias, cam_data in self.active_cameras.items():
                camera = cam_data['camera']
                info = cam_data['info']
                
                try:
                    if info.camera_type == CameraType.USB3_CAMERA:
                        camera_info = camera.get_info()
                        stats[alias] = {
                            'name': info.name,
                            'type': 'USB3',
                            'device_id': camera_info['device_id'],
                            'resolution': f"{camera_info['width']}x{camera_info['height']}",
                            'fps': camera_info.get('fps', 0),
                            'status': camera_info['status'],
                            'is_active': cam_data.get('is_active', False),
                            'frame_count': cam_data['frame_count'],
                            'last_timestamp': cam_data.get('last_frame_time', 0),
                            'poll_failures': cam_data.get('poll_failures', 0)
                        }
                    elif info.camera_type == CameraType.REALSENSE:
                        camera_info = camera.get_info()
                        stats[alias] = {
                            'name': info.name,
                            'type': 'realsense',
                            'device_serial': camera_info['device_serial'],
                            'color_resolution': camera_info['color_resolution'],
                            'depth_resolution': camera_info.get('depth_resolution', 'N/A'),
                            'fps': camera_info.get('fps', 0),
                            'status': camera_info['status'],
                            'is_active': cam_data.get('is_active', False),
                            'frame_count': cam_data['frame_count'],
                            'last_timestamp': cam_data.get('last_frame_time', 0),
                            'poll_failures': cam_data.get('poll_failures', 0)
                        }
                except Exception as e:
                    logger.error(f"❌ Erreur stats {alias}: {e}")
                    stats[alias] = {
                        'name': info.name,
                        'type': info.camera_type.value,
                        'error': str(e),
                        'is_active': False
                    }
        
        return stats
    
    def get_camera_intrinsics(self, alias: str) -> Dict[str, Any]:
        """Récupère les paramètres intrinsèques d'une caméra"""
        with self.cameras_lock:
            if alias not in self.active_cameras:
                return {}
            
            cam_data = self.active_cameras[alias]
            camera = cam_data['camera']
            
            try:
                if cam_data['info'].camera_type == CameraType.REALSENSE:
                    return camera.get_intrinsics()
                else:
                    camera_info = camera.get_info()
                    return {
                        'color': {
                            'width': camera_info.get('width', 640),
                            'height': camera_info.get('height', 480),
                            'note': 'Calibration manuelle requise pour USB3'
                        }
                    }
            except Exception as e:
                logger.error(f"❌ Erreur intrinsèques {alias}: {e}")
                return {}
    
    def save_camera_frame(self, alias: str, filepath: str) -> bool:
        """Sauvegarde une frame d'une caméra"""
        ret, color_frame, depth_frame = self.get_camera_frame(alias)
        
        if not ret or color_frame is None:
            return False
        
        try:
            cv2.imwrite(filepath, color_frame)
            logger.info(f"💾 Frame sauvegardée: {filepath}")
            
            if depth_frame is not None:
                depth_filepath = filepath.replace('.jpg', '_depth.png').replace('.png', '_depth.png')
                cv2.imwrite(depth_filepath, depth_frame)
                logger.info(f"💾 Profondeur sauvegardée: {depth_filepath}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde frame: {e}")
            return False
    
    def __del__(self):
        """Destructeur - nettoyage automatique"""
        self.stop_streaming()
        self.close_all_cameras()


# ============================================================================
# Fonctions utilitaires globales
# ============================================================================

def detect_all_available_cameras(config=None) -> List[CameraInfo]:
    """Fonction utilitaire pour détecter toutes les caméras"""
    if config is None:
        config = type('Config', (), {
            'get': lambda self, section, key, default=None: default
        })()
    
    manager = CameraManager(config)
    return manager.detect_all_cameras()

def test_camera_manager(duration: float = 5.0) -> bool:
    """Test complet du gestionnaire de caméras - VERSION RAPIDE"""
    logger.info(f"🧪 Test CameraManager pendant {duration}s...")
    
    dummy_config = type('Config', (), {
        'get': lambda self, section, key, default=None: default
    })()
    
    manager = CameraManager(dummy_config)
    
    try:
        cameras = manager.detect_all_cameras()
        if not cameras:
            logger.warning("⚠️ Aucune caméra détectée")
            return False
        
        logger.info(f"📷 {len(cameras)} caméra(s) détectée(s)")
        
        first_camera = cameras[0]
        if not manager.open_camera(first_camera, "test_cam"):
            logger.error("❌ Échec ouverture caméra")
            return False
        
        if not manager.start_streaming():
            logger.error("❌ Échec démarrage streaming")
            return False
        
        start_time = time.time()
        frame_count = 0
        
        test_sleep_interval = dummy_config.get('ui', 'camera_manager.streaming.test_sleep_interval', 0.05)
        
        while time.time() - start_time < duration:
            ret, color, depth = manager.get_camera_frame("test_cam")
            if ret and color is not None:
                frame_count += 1
            time.sleep(test_sleep_interval)
        
        fps_measured = frame_count / duration
        logger.info(f"✅ Test réussi: {frame_count} frames, ~{fps_measured:.1f} fps")
        
        manager.stop_streaming()
        manager.close_all_cameras()
        
        min_fps_threshold = dummy_config.get('ui', 'camera_manager.streaming.min_fps_threshold', 10)
        return fps_measured > min_fps_threshold
        
    except Exception as e:
        logger.error(f"❌ Test CameraManager échoué: {e}")
        return False
    finally:
        manager.stop_streaming()
        manager.close_all_cameras()