# core/camera_manager.py
# Version 2.9 - Correction ouverture RealSense avec configuration
# Modification: Ajout configuration pour RealSenseCamera dans _create_camera_instance

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
    """Gestionnaire central pour toutes les caméras - Version avec ouverture RealSense corrigée"""
    
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
        
        # Thread safety
        self.cameras_lock = Lock()
        self.cache_lock = Lock()
        
        # Configuration depuis JSON
        self.auto_detect_interval = self.config.get('camera', 'manager.auto_detect_interval', 5.0)
        self.max_frame_buffer = self.config.get('camera', 'manager.max_frame_buffer', 5)
        
        logger.info("🎥 CameraManager v2.9 initialisé (correction ouverture RealSense)")
    
    def detect_all_cameras(self) -> List[CameraInfo]:
        """Détecte toutes les caméras disponibles (USB3 + RealSense)"""
        logger.info("🔍 Détection globale des caméras...")
        
        all_cameras = []
        realsense_serials = set()
        
        # 1. Détection RealSense
        if REALSENSE_AVAILABLE:
            try:
                rs_cameras = list_available_realsense() 
                logger.info(f"🎥 RealSense: {len(rs_cameras)} caméra(s) détectée(s)")
                
                for rs_cam in rs_cameras:
                    serial = rs_cam.get('serial_number', rs_cam.get('serial', 'unknown'))
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
        """Alias pour detect_all_cameras pour compatibilité"""
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
        """Crée l'instance appropriée selon le type de caméra avec configuration"""
        try:
            if camera_info.camera_type == CameraType.REALSENSE:
                if not REALSENSE_AVAILABLE:
                    raise Exception("RealSense non disponible")
                
                # CORRECTION: Passer la configuration à RealSenseCamera
                return RealSenseCamera(self.config)
            
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
                # Démarrer le streaming RealSense
                success = camera_instance.start_streaming()
                if success:
                    logger.info(f"✅ Streaming RealSense démarré pour {camera_info.name}")
                return success
                
            elif camera_info.camera_type == CameraType.USB3_CAMERA:
                # Ouvrir caméra USB3
                success = camera_instance.open_camera(camera_info.device_id)
                if success:
                    logger.info(f"✅ Caméra USB3 ouverte: {camera_info.name}")
                return success
                
            else:
                logger.error(f"❌ Type de caméra non supporté: {camera_info.camera_type}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur ouverture instance caméra: {e}")
            return False
    
    def close_camera(self, alias: str) -> bool:
        """Ferme une caméra spécifique"""
        with self.cameras_lock:
            try:
                if alias not in self.active_cameras:
                    logger.warning(f"⚠️ Caméra {alias} non ouverte")
                    return False
                
                camera_data = self.active_cameras[alias]
                camera_instance = camera_data['camera']
                camera_info = camera_data['info']
                
                # Fermeture selon le type
                if camera_info.camera_type == CameraType.REALSENSE:
                    camera_instance.stop_streaming()
                elif camera_info.camera_type == CameraType.USB3_CAMERA:
                    camera_instance.close_camera()
                
                # Suppression du cache
                del self.active_cameras[alias]
                
                # Nettoyage du cache des frames
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
    
    def get_camera_frame(self, alias: str) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """Récupère une frame d'une caméra active"""
        with self.cameras_lock:
            if alias not in self.active_cameras:
                return False, None, None
            
            camera_data = self.active_cameras[alias]
            camera_instance = camera_data['camera']
            camera_info = camera_data['info']
            
            try:
                if camera_info.camera_type == CameraType.REALSENSE:
                    ret, color_img, depth_img = camera_instance.get_frames()
                    if ret:
                        camera_data['frame_count'] += 1
                        camera_data['last_frame_time'] = time.time()
                    return ret, color_img, depth_img
                    
                elif camera_info.camera_type == CameraType.USB3_CAMERA:
                    ret, frame = camera_instance.get_frame()
                    if ret:
                        camera_data['frame_count'] += 1
                        camera_data['last_frame_time'] = time.time()
                    return ret, frame, None
                    
                else:
                    return False, None, None
                    
            except Exception as e:
                logger.error(f"❌ Erreur lecture frame {alias}: {e}")
                return False, None, None
    
    def get_camera_stats(self, alias: str) -> Dict[str, Any]:
        """Récupère les statistiques d'une caméra"""
        with self.cameras_lock:
            if alias not in self.active_cameras:
                return {}
            
            camera_data = self.active_cameras[alias]
            camera_info = camera_data['info']
            
            current_time = time.time()
            uptime = current_time - camera_data['opened_at']
            
            stats = {
                'name': camera_info.name,
                'type': camera_info.camera_type.value,
                'device_id': camera_info.device_id,
                'uptime': uptime,
                'frame_count': camera_data['frame_count'],
                'is_streaming': camera_data['is_streaming'],
                'last_frame_time': camera_data['last_frame_time']
            }
            
            # Calcul FPS approximatif
            if camera_data['frame_count'] > 0 and uptime > 0:
                stats['avg_fps'] = camera_data['frame_count'] / uptime
            else:
                stats['avg_fps'] = 0.0
            
            return stats
    
    def list_active_cameras(self) -> List[str]:
        """Retourne la liste des caméras actives"""
        with self.cameras_lock:
            return list(self.active_cameras.keys())
    
    def close_all_cameras(self):
        """Ferme toutes les caméras actives"""
        with self.cameras_lock:
            camera_aliases = list(self.active_cameras.keys())
        
        for alias in camera_aliases:
            self.close_camera(alias)
        
        logger.info("🔒 Toutes les caméras fermées")
    
    def __del__(self):
        """Destructeur - ferme automatiquement toutes les caméras"""
        self.close_all_cameras()