#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/hardware/realsense_driver.py
Driver pour caméra Intel RealSense entièrement configuré - Version 2.5
Modification: Correction définitive du bloc try-except
"""

import pyrealsense2 as rs
import numpy as np
import cv2
import time
import logging
from threading import Lock, Thread
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger(__name__)

class RealSenseCamera:
    """Driver pour caméra Intel RealSense D435/D455 entièrement configuré"""
    
    def __init__(self, config):
        self.config = config
        
        # Pipeline principal
        self.pipeline = None
        self.config_rs = None
        self.is_streaming = False
        
        # Données des frames
        self.color_frame = None
        self.depth_frame = None
        self.aligned_frames = None
        self.last_timestamp = 0
        
        # Thread safety
        self.frame_lock = Lock()
        
        # Statistiques
        self.frame_count = 0
        self.fps_counter = 0
        self.last_fps_time = time.time()
        self.current_fps = 0.0
        
        # Configuration depuis JSON
        self.device_serial = self.config.get('camera', 'realsense.device_serial', None)
        self.color_width = self.config.get('camera', 'realsense.color_width', 640)
        self.color_height = self.config.get('camera', 'realsense.color_height', 480)
        self.color_fps = self.config.get('camera', 'realsense.color_fps', 30)
        self.depth_width = self.config.get('camera', 'realsense.depth_width', 640)
        self.depth_height = self.config.get('camera', 'realsense.depth_height', 480)
        self.depth_fps = self.config.get('camera', 'realsense.depth_fps', 30)
        self.enable_infrared = self.config.get('camera', 'realsense.enable_infrared', False)
        
        # Filtrages et post-processing
        self.enable_filters = self.config.get('camera', 'realsense.enable_filters', True)
        self.enable_align = self.config.get('camera', 'realsense.enable_align', True)
        
        version_info = self.config.get('camera', 'realsense.version', '2.5')
        logger.info(f"🎥 RealSense v{version_info} initialisé - Série: {self.device_serial or 'Auto'}")
    
    def detect_cameras(self) -> List[Dict[str, Any]]:
        """Détecte toutes les caméras RealSense disponibles"""
        available_cameras = []
        
        logger.info("🔍 Détection des caméras RealSense...")
        
        try:
            ctx = rs.context()
            devices = ctx.query_devices()
            
            if len(devices) == 0:
                logger.warning("⚠️ Aucune caméra RealSense détectée")
                return available_cameras
            
            for i in range(len(devices)):
                device = devices[i]
                
                try:
                    device_info = {
                        'device_id': i,
                        'name': device.get_info(rs.camera_info.name),
                        'serial': device.get_info(rs.camera_info.serial_number),
                        'firmware': device.get_info(rs.camera_info.firmware_version),
                        'product_line': device.get_info(rs.camera_info.product_line),
                        'sensors': []
                    }
                    
                    sensors = device.query_sensors()
                    for sensor in sensors:
                        sensor_info = {
                            'name': sensor.get_info(rs.camera_info.name),
                            'streams': []
                        }
                        
                        profiles = sensor.get_stream_profiles()
                        for profile in profiles:
                            if profile.stream_type() in [rs.stream.color, rs.stream.depth, rs.stream.infrared]:
                                stream_info = {
                                    'type': str(profile.stream_type()).split('.')[-1],
                                    'format': str(profile.format()).split('.')[-1],
                                    'width': profile.as_video_stream_profile().width(),
                                    'height': profile.as_video_stream_profile().height(),
                                    'fps': profile.fps()
                                }
                                sensor_info['streams'].append(stream_info)
                        
                        device_info['sensors'].append(sensor_info)
                    
                    available_cameras.append(device_info)
                    logger.info(f"✅ RealSense trouvée: {device_info['name']} (S/N: {device_info['serial']})")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Erreur lecture device {i}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"❌ Erreur détection RealSense: {e}")
        
        logger.info(f"📷 {len(available_cameras)} caméra(s) RealSense détectée(s)")
        return available_cameras
    
    def start_streaming(self) -> bool:
        """Démarre le streaming avec la configuration"""
        try:
            if self.is_streaming:
                logger.warning("⚠️ Streaming déjà démarré")
                return True
            
            logger.info("📷 Démarrage streaming RealSense...")
            
            self.pipeline = rs.pipeline()
            self.config_rs = rs.config()
            
            if self.device_serial:
                self.config_rs.enable_device(self.device_serial)
                logger.info(f"🎯 Device sélectionné: {self.device_serial}")
            
            self._configure_streams()
            
            profile = self.pipeline.start(self.config_rs)
            
            self._setup_post_processing()
            
            # Test d'acquisition avec timeout configurable
            test_attempts = self.config.get('camera', 'realsense.test_attempts', 5)
            test_timeout = self.config.get('camera', 'realsense.test_timeout', 1000)
            test_sleep = self.config.get('camera', 'realsense.test_sleep', 0.1)
            
            for i in range(test_attempts):
                frames = self.pipeline.wait_for_frames(timeout_ms=test_timeout)
                if frames:
                    break
                time.sleep(test_sleep)
            else:
                raise Exception("Impossible d'acquérir des frames de test")
            
            self.is_streaming = True
            self.frame_count = 0
            self.last_fps_time = time.time()
            
            self._log_device_info(profile)
            
            logger.info("✅ Streaming RealSense démarré")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage streaming: {e}")
            self._cleanup()
            return False
    
    def _configure_streams(self):
        """Configure les streams couleur et profondeur"""
        self.config_rs.enable_stream(
            rs.stream.color,
            self.color_width,
            self.color_height,
            rs.format.bgr8,
            self.color_fps
        )
        
        self.config_rs.enable_stream(
            rs.stream.depth,
            self.depth_width,
            self.depth_height,
            rs.format.z16,
            self.depth_fps
        )
        
        if self.enable_infrared:
            self.config_rs.enable_stream(
                rs.stream.infrared,
                self.depth_width,
                self.depth_height,
                rs.format.y8,
                self.depth_fps
            )
        
        logger.info(f"⚙️ Streams configurés: {self.color_width}x{self.color_height}@{self.color_fps}fps")
    
    def _setup_post_processing(self):
        """Configure les filtres de post-traitement"""
        if not self.enable_filters:
            return
        
        if self.enable_align:
            self.align = rs.align(rs.stream.color)
        
        self.decimation_filter = rs.decimation_filter()
        self.temporal_filter = rs.temporal_filter()
        self.spatial_filter = rs.spatial_filter()
        self.hole_filling_filter = rs.hole_filling_filter()
        
        # Configuration des filtres depuis JSON
        spatial_magnitude = self.config.get('camera', 'realsense.spatial_magnitude', 2.0)
        spatial_smooth_alpha = self.config.get('camera', 'realsense.spatial_smooth_alpha', 0.5)
        temporal_smooth_alpha = self.config.get('camera', 'realsense.temporal_smooth_alpha', 0.4)
        
        self.spatial_filter.set_option(rs.option.filter_magnitude, spatial_magnitude)
        self.spatial_filter.set_option(rs.option.filter_smooth_alpha, spatial_smooth_alpha)
        self.temporal_filter.set_option(rs.option.filter_smooth_alpha, temporal_smooth_alpha)
        
        logger.info("🔧 Filtres post-traitement configurés")

    def get_frames(self) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """Récupère les frames couleur et profondeur"""
        if not self.is_streaming:
            return False, None, None
        
        try:
            frames = self.pipeline.poll_for_frames()
            if not frames:
                return False, None, None
            
            with self.frame_lock:
                if self.enable_filters:
                    depth_frame = frames.get_depth_frame()
                    if depth_frame:
                        depth_frame = self.decimation_filter.process(depth_frame)
                        depth_frame = self.spatial_filter.process(depth_frame)
                        depth_frame = self.temporal_filter.process(depth_frame)
                        depth_frame = self.hole_filling_filter.process(depth_frame)
                
                if self.enable_align and hasattr(self, 'align'):
                    frames = self.align.process(frames)
                
                color_frame = frames.get_color_frame()
                depth_frame = frames.get_depth_frame()
                
                if not color_frame:
                    return False, None, None
                
                color_image = np.asanyarray(color_frame.get_data())
                depth_image = np.asanyarray(depth_frame.get_data()) if depth_frame else None
                
                self.color_frame = color_frame
                self.depth_frame = depth_frame
                self.last_timestamp = frames.get_timestamp()
                
                self._update_fps_stats()
                
                return True, color_image, depth_image
                
        except Exception as e:
            logger.error(f"❌ Erreur acquisition frames: {e}")
            return False, None, None
    
    def get_depth_at_pixel(self, x: int, y: int) -> float:
        """Récupère la profondeur à un pixel donné (en mètres)"""
        if not self.depth_frame:
            return 0.0
        
        try:
            depth_value = self.depth_frame.get_distance(x, y)
            return depth_value
            
        except Exception as e:
            logger.error(f"❌ Erreur lecture profondeur: {e}")
            return 0.0
    
    def get_depth_scale(self) -> float:
        """Récupère l'échelle de profondeur de la caméra"""
        try:
            if self.pipeline:
                profile = self.pipeline.get_active_profile()
                depth_sensor = profile.get_device().first_depth_sensor()
                return depth_sensor.get_depth_scale()
            
            # Si pas de pipeline actif, retourner valeur par défaut
            default_scale = self.config.get('camera', 'realsense.default_depth_scale', 0.001)
            return default_scale
            
        except Exception as e:
            # En cas d'erreur, retourner valeur de configuration par défaut
            logger.debug(f"Erreur récupération depth_scale: {e}")
            return self.config.get('camera', 'realsense.default_depth_scale', 0.001)
    
    def get_intrinsics(self) -> Dict[str, Any]:
        """Récupère les paramètres intrinsèques des caméras"""
        if not self.pipeline:
            return {}
        
        try:
            profile = self.pipeline.get_active_profile()
            
            color_stream = profile.get_stream(rs.stream.color)
            color_intrinsics = color_stream.as_video_stream_profile().get_intrinsics()
            
            depth_stream = profile.get_stream(rs.stream.depth)
            depth_intrinsics = depth_stream.as_video_stream_profile().get_intrinsics()
            
            extrinsics = depth_stream.get_extrinsics_to(color_stream)
            
            return {
                'color': {
                    'width': color_intrinsics.width,
                    'height': color_intrinsics.height,
                    'fx': color_intrinsics.fx,
                    'fy': color_intrinsics.fy,
                    'cx': color_intrinsics.ppx,
                    'cy': color_intrinsics.ppy,
                    'distortion': color_intrinsics.coeffs
                },
                'depth': {
                    'width': depth_intrinsics.width,
                    'height': depth_intrinsics.height,
                    'fx': depth_intrinsics.fx,
                    'fy': depth_intrinsics.fy,
                    'cx': depth_intrinsics.ppx,
                    'cy': depth_intrinsics.ppy,
                    'distortion': depth_intrinsics.coeffs
                },
                'extrinsics': {
                    'rotation': extrinsics.rotation,
                    'translation': extrinsics.translation
                },
                'depth_scale': self.get_depth_scale()
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur récupération intrinsèques: {e}")
            return {}

    def get_info(self) -> Dict[str, Any]:
        """Retourne les informations de la caméra"""
        if not self.is_streaming:
            return {
                'device_serial': self.device_serial or 'Auto',
                'status': 'stopped',
                'color_resolution': f"{self.color_width}x{self.color_height}",
                'depth_resolution': f"{self.depth_width}x{self.depth_height}",
                'fps': 0.0,
                'frame_count': 0,
                'last_timestamp': 0
            }
        
        return {
            'device_serial': self.device_serial or 'Auto',
            'status': 'streaming',
            'color_resolution': f"{self.color_width}x{self.color_height}",
            'depth_resolution': f"{self.depth_width}x{self.depth_height}",
            'fps': self.current_fps,
            'frame_count': self.frame_count,
            'last_timestamp': self.last_timestamp
        }
    
    def _update_fps_stats(self):
        """Met à jour les statistiques FPS"""
        self.frame_count += 1
        current_time = time.time()
        
        fps_update_interval = self.config.get('ui', 'realsense.logging.fps_update_interval', 1.0)
        
        if current_time - self.last_fps_time >= fps_update_interval:
            self.current_fps = self.frame_count / (current_time - self.last_fps_time)
            self.frame_count = 0
            self.last_fps_time = current_time
    
    def _log_device_info(self, profile):
        """Affiche les informations du device actif"""
        try:
            device = profile.get_device()
            
            logger.info(f"📷 Device: {device.get_info(rs.camera_info.name)}")
            logger.info(f"📦 S/N: {device.get_info(rs.camera_info.serial_number)}")
            logger.info(f"🔧 Firmware: {device.get_info(rs.camera_info.firmware_version)}")
            
            for stream in profile.get_streams():
                stream_profile = stream.as_video_stream_profile()
                logger.info(f"🎬 {stream.stream_type()}: {stream_profile.width()}x{stream_profile.height()}@{stream.fps()}fps")
                
        except Exception as e:
            logger.warning(f"⚠️ Erreur affichage infos device: {e}")
    
    def stop_streaming(self):
        """Arrête le streaming"""
        try:
            if self.is_streaming and self.pipeline:
                self.pipeline.stop()
                logger.info("📷 Streaming RealSense arrêté")
            
            self._cleanup()
            
        except Exception as e:
            logger.error(f"❌ Erreur arrêt streaming: {e}")
    
    def _cleanup(self):
        """Nettoyage des ressources"""
        self.is_streaming = False
        self.pipeline = None
        self.config_rs = None
        self.color_frame = None
        self.depth_frame = None
        self.frame_count = 0
    
    def __del__(self):
        """Destructeur - arrête le streaming automatiquement"""
        self.stop_streaming()


# ============================================================================
# Fonctions utilitaires
# ============================================================================

def list_available_realsense() -> List[Dict[str, Any]]:
    """Liste toutes les caméras RealSense disponibles"""
    dummy_config = type('Config', (), {
        'get': lambda self, section, key, default=None: default
    })()
    
    camera = RealSenseCamera(dummy_config)
    return camera.detect_cameras()

def test_realsense(device_serial: Optional[str] = None, duration: float = 5.0) -> bool:
    """Test rapide d'une caméra RealSense"""
    logger.info(f"🧪 Test RealSense {device_serial or 'auto'} pendant {duration}s...")
    
    # Configuration de test avec toutes les valeurs externalisées
    test_config = {
        'camera.realsense.device_serial': device_serial,
        'camera.realsense.color_width': 640,
        'camera.realsense.color_height': 480,
        'camera.realsense.color_fps': 30,
        'camera.realsense.depth_width': 640,
        'camera.realsense.depth_height': 480,
        'camera.realsense.depth_fps': 30,
        'camera.realsense.enable_filters': False,
        'camera.realsense.enable_align': True,
        'ui.realsense.logging.frame_log_interval': 30,
        'test.frame_delay': 0.01
    }
    
    dummy_config = type('Config', (), {
        'get': lambda self, section, key, default=None: test_config.get(f"{section}.{key}", default)
    })()
    
    camera = RealSenseCamera(dummy_config)
    
    try:
        if not camera.start_streaming():
            return False
        
        start_time = time.time()
        frame_count = 0
        
        # Configuration du logging depuis JSON
        frame_log_interval = dummy_config.get('ui', 'realsense.logging.frame_log_interval', 30)
        frame_delay = dummy_config.get('test', 'frame_delay', 0.01)
        
        while time.time() - start_time < duration:
            ret, color_img, depth_img = camera.get_frames()
            if ret:
                frame_count += 1
                
                if depth_img is not None:
                    h, w = depth_img.shape
                    center_depth = camera.get_depth_at_pixel(w//2, h//2)
                    if frame_count % frame_log_interval == 0:
                        logger.info(f"📏 Profondeur centre: {center_depth:.3f}m")
            
            time.sleep(frame_delay)
        
        fps_measured = frame_count / duration
        logger.info(f"✅ Test réussi: {frame_count} frames en {duration}s ({fps_measured:.1f} FPS)")
        
        intrinsics = camera.get_intrinsics()
        if intrinsics:
            logger.info("📐 Paramètres intrinsèques récupérés")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur test RealSense: {e}")
        return False
    finally:
        camera.stop_streaming()


# ============================================================================
# Point d'entrée pour tests
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🎥 Test du driver RealSense")
    print("=" * 40)
    
    cameras = list_available_realsense()
    print(f"Caméras RealSense détectées: {len(cameras)}")
    for cam in cameras:
        print(f"  - {cam['name']} (S/N: {cam['serial']})")
    
    if cameras:
        device_serial = cameras[0]['serial']
        print(f"\nTest de la caméra {device_serial}...")
        
        test_duration = 3.0
        success = test_realsense(device_serial, duration=test_duration)
        if success:
            print("✅ Test réussi!")
        else:
            print("❌ Test échoué!")
    else:
        print("❌ Aucune caméra RealSense détectée")
        print("💡 Vérifiez que le SDK RealSense est installé et qu'une caméra est connectée")