# core/camera_manager.py
# Version 2.8 - Ajout méthode is_camera_open manquante
# Modification: Ajout méthode is_camera_open pour compatibilité camera_tab

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
    """Gestionnaire central pour toutes les caméras - Version avec is_camera_open"""
    
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
        
        logger.info("🎥 CameraManager v2.8 initialisé (méthode is_camera_open ajoutée)")
    
    def detect_all_cameras(self) -> List[CameraInfo]:
        """Détecte toutes les caméras disponibles (USB3 + RealSense) avec évitement des doublons"""
        logger.info("🔍 Détection globale des caméras...")
        
        all_cameras = []
        realsense_serials = set()
        
        # 1. Détection RealSense en premier (plus fiables)
        if REALSENSE_AVAILABLE:
            try:
                rs_cameras = list_available_realsense() 
                logger.info(f"🎥 RealSense: {len(rs_cameras)} caméra(s) détectée(s)")
                
                for rs_cam in rs_cameras:
                    serial = rs_cam.get('serial_number', 'unknown')
                    realsense_serials.add(serial)
                    
                    camera_info = CameraInfo(
                        camera_type=CameraType.REALSENSE,
                        device_id=serial,
                        name=rs_cam.get('name', f'RealSense {serial}'),
                        details=rs_cam
                    )
                    all_cameras.append(camera_info)
                    
            except Exception as e:
                logger.warning(f"⚠️ Erreur détection RealSense: {e}")
        
        # 2. Détection USB3 en évitant les doublons
        try:
            usb3_cameras = list_available_cameras()
            logger.info(f"🔌 USB3: {len(usb3_cameras)} caméra(s) détectée(s)")
            
            for usb_cam in usb3_cameras:
                # Vérification anti-doublon basique
                usb_name = usb_cam.get('name', f"USB3 Camera {usb_cam.get('index', 'unknown')}")
                
                # Filtrage des caméras RealSense déjà détectées
                if any(serial in usb_name for serial in realsense_serials):
                    logger.debug(f"🔄 Ignoré doublon USB3: {usb_name}")
                    continue
                
                camera_info = CameraInfo(
                    camera_type=CameraType.USB3_CAMERA,
                    device_id=usb_cam.get('index', 0),
                    name=usb_name,
                    details=usb_cam
                )
                all_cameras.append(camera_info)
                
        except Exception as e:
            logger.warning(f"⚠️ Erreur détection USB3: {e}")
        
        # Mise à jour cache
        self.available_cameras = all_cameras
        
        logger.info(f"✅ Détection terminée: {len(all_cameras)} caméra(s) unique(s)")
        return all_cameras
    
    def detect_cameras(self) -> List[CameraInfo]:
        """Alias pour detect_all_cameras pour compatibilité avec camera_tab"""
        return self.detect_all_cameras()
    
    def is_camera_open(self, alias: str) -> bool:
        """Vérifie si une caméra est ouverte"""
        with self.cameras_lock:
            return alias in self.active_cameras
    
    def open_camera(self, camera_info: CameraInfo, alias: str = None) -> bool:
        """Ouvre une caméra spécifique"""
        if not alias:
            alias = f"cam_{len(self.active_cameras)}"
        
        logger.info(f"🔓 Ouverture caméra {camera_info.name} (alias: {alias})")
        
        with self.cameras_lock:
            try:
                # Caméra déjà ouverte ?
                if alias in self.active_cameras:
                    logger.warning(f"⚠️ Caméra {alias} déjà ouverte")
                    return False
                
                # Création de l'instance caméra selon le type
                camera_instance = self._create_camera_instance(camera_info)
                
                if not camera_instance:
                    logger.error(f"❌ Échec création instance {camera_info.camera_type}")
                    return False
                
                # Ouverture effective
                if not self._open_camera_instance(camera_instance, camera_info):
                    logger.error(f"❌ Échec ouverture caméra {camera_info.name}")
                    return False
                
                # Enregistrement de la caméra active
                self.active_cameras[alias] = {
                    'camera': camera_instance,
                    'info': camera_info,
                    'opened_at': time.time(),
                    'frame_count': 0,
                    'last_frame_time': 0.0,
                    'is_streaming': False
                }
                
                logger.info(f"✅ Caméra {alias} ouverte avec succès")
                return True
                
            except Exception as e:
                logger.error(f"❌ Erreur ouverture caméra {alias}: {e}")
                return False
    
    def _create_camera_instance(self, camera_info: CameraInfo):
        """Crée l'instance appropriée selon le type de caméra"""
        try:
            if camera_info.camera_type == CameraType.REALSENSE:
                if not REALSENSE_AVAILABLE:
                    raise Exception("RealSense non disponible")
                return RealSenseCamera()
            
            elif camera_info.camera_type == CameraType.USB3_CAMERA:
                return USB3CameraDriver()
            
            else:
                raise Exception(f"Type de caméra non supporté: {camera_info.camera_type}")
                
        except Exception as e:
            logger.error(f"❌ Erreur création instance caméra: {e}")
            return None
    
    def _open_camera_instance(self, camera_instance, camera_info: CameraInfo) -> bool:
        """Ouvre l'instance de caméra avec la bonne configuration"""
        try:
            if camera_info.camera_type == CameraType.REALSENSE:
                # Configuration RealSense depuis JSON
                config_rs = {
                    'color_width': self.config.get('camera', 'realsense.color_width', 640),
                    'color_height': self.config.get('camera', 'realsense.color_height', 480),
                    'color_fps': self.config.get('camera', 'realsense.color_fps', 30),
                    'depth_width': self.config.get('camera', 'realsense.depth_width', 640),
                    'depth_height': self.config.get('camera', 'realsense.depth_height', 480),
                    'depth_fps': self.config.get('camera', 'realsense.depth_fps', 30)
                }
                return camera_instance.open(camera_info.device_id, config_rs)
            
            elif camera_info.camera_type == CameraType.USB3_CAMERA:
                # Configuration USB3 depuis JSON
                config_usb = {
                    'width': self.config.get('camera', 'usb3_camera.width', 640),
                    'height': self.config.get('camera', 'usb3_camera.height', 480),
                    'fps': self.config.get('camera', 'usb3_camera.fps', 30)
                }
                return camera_instance.open(camera_info.device_id, config_usb)
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur ouverture instance: {e}")
            return False
    
    def close_camera(self, alias: str) -> bool:
        """Ferme une caméra spécifique"""
        with self.cameras_lock:
            if alias not in self.active_cameras:
                logger.warning(f"⚠️ Caméra {alias} non trouvée pour fermeture")
                return False
            
            try:
                cam_data = self.active_cameras[alias]
                camera = cam_data['camera']
                
                # Arrêt du streaming si actif
                if cam_data.get('is_streaming', False):
                    camera.stop()
                
                # Fermeture de la caméra
                camera.close()
                
                # Suppression du cache
                if alias in self.frame_cache:
                    del self.frame_cache[alias]
                if alias in self.cache_timestamps:
                    del self.cache_timestamps[alias]
                
                # Suppression de la liste active
                del self.active_cameras[alias]
                
                logger.info(f"🔒 Caméra {alias} fermée")
                return True
                
            except Exception as e:
                logger.error(f"❌ Erreur fermeture caméra {alias}: {e}")
                return False
    
    def close_all_cameras(self):
        """Ferme toutes les caméras ouvertes"""
        aliases_to_close = list(self.active_cameras.keys())
        
        for alias in aliases_to_close:
            self.close_camera(alias)
        
        logger.info("🔒 Toutes les caméras fermées")
    
    def start_streaming(self) -> bool:
        """Démarre le streaming pour toutes les caméras ouvertes"""
        if self.streaming:
            logger.warning("⚠️ Streaming déjà actif")
            return True
        
        if not self.active_cameras:
            logger.warning("⚠️ Aucune caméra ouverte pour le streaming")
            return False
        
        try:
            # Démarrage du streaming pour chaque caméra
            for alias, cam_data in self.active_cameras.items():
                camera = cam_data['camera']
                
                if hasattr(camera, 'start'):
                    camera.start()
                    cam_data['is_streaming'] = True
                    logger.info(f"📹 Streaming démarré pour {alias}")
            
            # Thread de lecture des frames
            self.streaming = True
            self.streaming_stop_event.clear()
            
            self.streaming_thread = Thread(
                target=self._streaming_loop,
                name="CameraStreaming",
                daemon=True
            )
            self.streaming_thread.start()
            
            logger.info("🎬 Streaming global démarré")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage streaming: {e}")
            self.streaming = False
            return False
    
    def stop_streaming(self):
        """Arrête le streaming"""
        if not self.streaming:
            return
        
        logger.info("🛑 Arrêt du streaming...")
        
        # Signal d'arrêt
        self.streaming = False
        self.streaming_stop_event.set()
        
        # Attente fin du thread
        if self.streaming_thread and self.streaming_thread.is_alive():
            self.streaming_thread.join(timeout=2.0)
        
        # Arrêt du streaming pour chaque caméra
        with self.cameras_lock:
            for alias, cam_data in self.active_cameras.items():
                try:
                    camera = cam_data['camera']
                    
                    if hasattr(camera, 'stop'):
                        camera.stop()
                    
                    cam_data['is_streaming'] = False
                    logger.info(f"📹 Streaming arrêté pour {alias}")
                    
                except Exception as e:
                    logger.error(f"❌ Erreur arrêt streaming {alias}: {e}")
        
        # Nettoyage du cache
        with self.cache_lock:
            self.frame_cache.clear()
            self.cache_timestamps.clear()
        
        logger.info("✅ Streaming arrêté")
    
    def _streaming_loop(self):
        """Boucle principale de streaming"""
        logger.info("🔄 Démarrage boucle streaming")
        
        frame_interval = 1.0 / self.config.get('camera', 'manager.target_fps', 30)
        
        while self.streaming and not self.streaming_stop_event.is_set():
            try:
                current_time = time.time()
                
                # Lecture des frames pour chaque caméra active
                with self.cameras_lock:
                    cameras_to_process = list(self.active_cameras.items())
                
                for alias, cam_data in cameras_to_process:
                    if not cam_data.get('is_streaming', False):
                        continue
                    
                    try:
                        self._read_camera_frame(alias, cam_data, current_time)
                    except Exception as e:
                        logger.debug(f"Erreur lecture frame {alias}: {e}")
                        cam_data['poll_failures'] = cam_data.get('poll_failures', 0) + 1
                
                # Appel des callbacks
                self._notify_frame_callbacks()
                
                # Pause pour respecter la fréquence
                elapsed = time.time() - current_time
                sleep_time = max(0, frame_interval - elapsed)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                logger.error(f"❌ Erreur boucle streaming: {e}")
                time.sleep(0.1)  # Pause d'urgence
        
        logger.info("✅ Boucle streaming terminée")
    
    def _read_camera_frame(self, alias: str, cam_data: Dict, timestamp: float):
        """Lit une frame d'une caméra spécifique"""
        camera = cam_data['camera']
        
        try:
            # Lecture selon le type de caméra
            if cam_data['info'].camera_type == CameraType.REALSENSE:
                ret, color_frame, depth_frame = camera.get_frames()
            else:
                ret, color_frame = camera.get_frame()
                depth_frame = None
            
            if ret and color_frame is not None:
                # Mise à jour du cache
                with self.cache_lock:
                    self.frame_cache[alias] = (ret, color_frame, depth_frame)
                    self.cache_timestamps[alias] = timestamp
                
                # Statistiques
                cam_data['frame_count'] += 1
                cam_data['last_frame_time'] = timestamp
                cam_data['poll_failures'] = 0
                
            else:
                cam_data['poll_failures'] = cam_data.get('poll_failures', 0) + 1
                
        except Exception as e:
            logger.debug(f"Erreur lecture {alias}: {e}")
            cam_data['poll_failures'] = cam_data.get('poll_failures', 0) + 1
    
    def _notify_frame_callbacks(self):
        """Notifie les callbacks de nouvelles frames"""
        if not self.frame_callbacks:
            return
        
        try:
            # Frame la plus récente
            latest_frame = None
            latest_timestamp = 0
            
            with self.cache_lock:
                for alias, timestamp in self.cache_timestamps.items():
                    if timestamp > latest_timestamp and alias in self.frame_cache:
                        ret, color, depth = self.frame_cache[alias]
                        if ret and color is not None:
                            latest_frame = color
                            latest_timestamp = timestamp
            
            # Appel des callbacks
            if latest_frame is not None:
                for callback in self.frame_callbacks:
                    try:
                        callback(latest_frame)
                    except Exception as e:
                        logger.debug(f"Erreur callback frame: {e}")
                        
        except Exception as e:
            logger.debug(f"Erreur notification callbacks: {e}")
    
    def get_camera_frame(self, alias: str) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """Récupère la dernière frame d'une caméra"""
        with self.cache_lock:
            if alias in self.frame_cache:
                return self.frame_cache[alias]
            else:
                return False, None, None
    
    def add_frame_callback(self, callback: Callable):
        """Ajoute un callback pour les nouvelles frames"""
        if callback not in self.frame_callbacks:
            self.frame_callbacks.append(callback)
            logger.info("➕ Callback frame ajouté")
    
    def remove_frame_callback(self, callback: Callable):
        """Supprime un callback"""
        if callback in self.frame_callbacks:
            self.frame_callbacks.remove(callback)
            logger.info("➖ Callback frame supprimé")
    
    def get_active_cameras_info(self) -> Dict[str, Dict]:
        """Retourne des informations sur les caméras actives"""
        with self.cameras_lock:
            info = {}
            
            for alias, cam_data in self.active_cameras.items():
                info[alias] = {
                    'name': cam_data['info'].name,
                    'type': cam_data['info'].camera_type.value,
                    'opened_at': cam_data['opened_at'],
                    'frame_count': cam_data['frame_count'],
                    'is_streaming': cam_data.get('is_streaming', False),
                    'last_frame_time': cam_data.get('last_frame_time', 0),
                    'poll_failures': cam_data.get('poll_failures', 0)
                }
            
            return info
    
    def get_camera_stats(self) -> Dict[str, Dict]:
        """Statistiques détaillées des caméras"""
        with self.cameras_lock:
            stats = {}
            
            for alias, cam_data in self.active_cameras.items():
                info = cam_data['info']
                
                try:
                    stats[alias] = {
                        'name': info.name,
                        'type': info.camera_type.value,
                        'device_id': str(info.device_id),
                        'is_active': cam_data.get('is_streaming', False),
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
        try:
            self.stop_streaming()
            self.close_all_cameras()
        except Exception as e:
            logger.debug(f"Erreur destructeur: {e}")


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
