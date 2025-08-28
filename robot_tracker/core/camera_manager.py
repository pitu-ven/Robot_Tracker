# core/camera_manager.py
# Version 4.5 - Correction d'indentation et ajout méthodes manquantes
# Modification: Résolution erreur syntaxe + ajout detect_all_cameras et stop_streaming

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import threading
from typing import Dict, List, Optional, Any, Union, Tuple
import time
import numpy as np

try:
    import pyrealsense2 as rs
except ImportError:
    rs = None
    logging.warning("⚠️ pyrealsense2 non disponible - Mode simulation")

from hardware.realsense_driver import RealSenseCamera
from hardware.usb3_camera_driver import USB3CameraDriver

logger = logging.getLogger(__name__)

class CameraManager:
    """Gestionnaire centralisé des caméras avec support multi-types"""
    
    def __init__(self, config):
        self.config = config
        self.cameras = {}
        self.camera_instances = {}
        self.camera_threads = {}
        self.lock = threading.RLock()
        self._is_streaming = False
        
        # Configuration
        self.target_fps = self.config.get('camera', 'manager.target_fps', 30)
        self.detection_timeout = self.config.get('camera', 'manager.detection_timeout_ms', 3000) / 1000
        self.frame_buffer_size = self.config.get('camera', 'manager.frame_buffer_size', 10)
        
        logger.info("🎥 CameraManager initialisé")
    
    def detect_cameras(self):
        """Détecte toutes les caméras disponibles"""
        detected = {}
        
        # Détection RealSense
        if rs:
            try:
                ctx = rs.context()
                devices = ctx.query_devices()
                
                for i, device in enumerate(devices):
                    serial = device.get_info(rs.camera_info.serial_number)
                    name = device.get_info(rs.camera_info.name)
                    
                    camera_info = {
                        'type': 'realsense',
                        'serial': serial,
                        'name': name,
                        'alias': f"realsense_{i}",
                        'device_index': i,
                        'capabilities': {
                            'color': True,
                            'depth': True,
                            'infrared': True
                        }
                    }
                    detected[serial] = camera_info
                    
                logger.info(f"✅ {len(detected)} caméra(s) RealSense détectée(s)")
            except Exception as e:
                logger.warning(f"⚠️ Erreur détection RealSense: {e}")
        
        # Détection USB3 standard
        try:
            usb3_cameras = USB3CameraDriver.detect_cameras()
            for camera_info in usb3_cameras:
                detected[camera_info['serial']] = camera_info
                
            logger.info(f"✅ {len(usb3_cameras)} caméra(s) USB3 détectée(s)")
        except Exception as e:
            logger.warning(f"⚠️ Erreur détection USB3: {e}")
        
        self.cameras = detected
        return detected
    
    def detect_all_cameras(self):
        """Alias pour detect_cameras() - Méthode attendue par camera_tab.py"""
        return self.detect_cameras()
    
    def open_camera(self, camera_id: str, alias: Optional[str] = None):
        """Ouvre une caméra par ID ou alias"""
        with self.lock:
            if alias and self.is_camera_open(alias):
                warning_msg = self.config.get('core', 'camera_manager.messages.already_open', 
                                           'Camera already open: {alias}')
                logger.warning(warning_msg.format(alias=alias))
                return True
            
            camera_info = self._get_camera_info(camera_id)
            if not camera_info:
                error_msg = self.config.get('core', 'camera_manager.messages.not_found', 
                                          'Camera not found: {camera_id}')
                logger.error(error_msg.format(camera_id=camera_id))
                return False
            
            try:
                camera_instance = self._create_camera_instance(camera_info)
                if camera_instance:
                    if alias:
                        camera_info['alias'] = alias
                    self.camera_instances[alias or camera_id] = camera_instance
                    
                    success_msg = self.config.get('core', 'camera_manager.messages.opened', 
                                                'Camera opened: {alias}')
                    logger.info(success_msg.format(alias=alias or camera_id))
                    return True
                else:
                    return False
                    
            except Exception as e:
                error_msg = self.config.get('core', 'camera_manager.messages.open_error', 
                                          'Failed to open camera: {error}')
                logger.error(error_msg.format(error=str(e)))
                return False
    
    def close_camera(self, alias: str):
        """Ferme une caméra par alias"""
        with self.lock:
            if alias not in self.camera_instances:
                warning_msg = self.config.get('core', 'camera_manager.messages.not_open', 
                                            'Camera not open: {alias}')
                logger.warning(warning_msg.format(alias=alias))
                return False
            
            try:
                camera_instance = self.camera_instances[alias]
                if hasattr(camera_instance, 'stop_streaming'):
                    camera_instance.stop_streaming()
                if hasattr(camera_instance, 'close'):
                    camera_instance.close()
                
                del self.camera_instances[alias]
                
                # Nettoyage thread associé
                if alias in self.camera_threads:
                    del self.camera_threads[alias]
                
                success_msg = self.config.get('core', 'camera_manager.messages.closed', 
                                            'Camera closed: {alias}')
                logger.info(success_msg.format(alias=alias))
                return True
                
            except Exception as e:
                error_msg = self.config.get('core', 'camera_manager.messages.close_error', 
                                          'Failed to close camera: {error}')
                logger.error(error_msg.format(error=str(e)))
                return False
    
    def close_all_cameras(self):
        """Ferme toutes les caméras"""
        with self.lock:
            aliases = list(self.camera_instances.keys())
            for alias in aliases:
                self.close_camera(alias)
    
    def is_camera_open(self, alias: str) -> bool:
        """Vérifie si une caméra est ouverte"""
        with self.lock:
            return alias in self.camera_instances
    
    def start_streaming(self) -> bool:
        """Démarre le streaming pour toutes les caméras ouvertes"""
        with self.lock:
            if self._is_streaming:
                logger.warning("⚠️ Streaming déjà actif")
                return True
            
            if not self.camera_instances:
                logger.warning("⚠️ Aucune caméra ouverte pour le streaming")
                return False
            
            try:
                # Démarrage du streaming pour chaque caméra
                for alias, camera_instance in self.camera_instances.items():
                    if hasattr(camera_instance, 'start_streaming'):
                        camera_instance.start_streaming()
                        logger.info(f"✅ Streaming démarré pour {alias}")
                
                self._is_streaming = True
                success_msg = self.config.get('core', 'camera_manager.messages.streaming_started', 
                                            '✅ Streaming global démarré')
                logger.info(success_msg)
                return True
                
            except Exception as e:
                error_msg = self.config.get('core', 'camera_manager.messages.streaming_start_error', 
                                          'Erreur démarrage streaming: {error}')
                logger.error(error_msg.format(error=str(e)))
                return False
    
    def stop_streaming(self):
        """Arrête le streaming pour toutes les caméras - Méthode attendue par main_window.py"""
        with self.lock:
            if not self._is_streaming:
                logger.debug("⚠️ Streaming déjà arrêté")
                return
            
            try:
                # Arrêt du streaming pour chaque caméra
                for alias, camera_instance in self.camera_instances.items():
                    if hasattr(camera_instance, 'stop_streaming'):
                        camera_instance.stop_streaming()
                        logger.info(f"✅ Streaming arrêté pour {alias}")
                
                self._is_streaming = False
                success_msg = self.config.get('core', 'camera_manager.messages.streaming_stopped', 
                                            '✅ Streaming global arrêté')
                logger.info(success_msg)
                
            except Exception as e:
                error_msg = self.config.get('core', 'camera_manager.messages.streaming_stop_error', 
                                          'Erreur arrêt streaming: {error}')
                logger.error(error_msg.format(error=str(e)))
    
    def get_camera_frame(self, alias: str) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """Récupère une frame d'une caméra - Format compatible camera_tab.py"""
        with self.lock:
            if alias not in self.camera_instances:
                return False, None, None
            
            try:
                camera_instance = self.camera_instances[alias]
                frame_data = camera_instance.get_frame()
                
                if frame_data and 'color' in frame_data:
                    color_frame = frame_data['color']
                    depth_frame = frame_data.get('depth', None)
                    return True, color_frame, depth_frame
                else:
                    return False, None, None
                    
            except Exception as e:
                error_msg = self.config.get('core', 'camera_manager.messages.frame_error', 
                                          'Failed to get frame: {error}')
                logger.error(error_msg.format(error=str(e)))
                return False, None, None
    
    @property
    def active_cameras(self) -> List[str]:
        """Liste des caméras actives - Propriété attendue par main_window.py"""
        with self.lock:
            return list(self.camera_instances.keys())
    
    @property
    def is_streaming(self) -> bool:
        """État du streaming"""
        return self._is_streaming
    
    def get_camera_info(self, alias: str) -> Optional[Dict]:
        """Récupère les informations d'une caméra"""
        with self.lock:
            for camera_info in self.cameras.values():
                if camera_info.get('alias') == alias:
                    return camera_info
            return None
    
    def list_open_cameras(self) -> List[str]:
        """Liste des caméras ouvertes"""
        with self.lock:
            return list(self.camera_instances.keys())
    
    def _get_camera_info(self, camera_id: str) -> Optional[Dict]:
        """Récupère les infos d'une caméra par ID"""
        for serial, info in self.cameras.items():
            if serial == camera_id or info.get('alias') == camera_id:
                return info
        return None
    
    def _create_camera_instance(self, camera_info: Dict):
        """Crée une instance de caméra selon le type"""
        camera_type = camera_info.get('type')
        
        if camera_type == 'realsense':
            return RealSenseCamera(camera_info, self.config)
        elif camera_type == 'usb3':
            return USB3CameraDriver(camera_info, self.config)
        else:
            error_msg = self.config.get('core', 'camera_manager.messages.unknown_type', 
                                      'Unknown camera type: {type}')
            logger.error(error_msg.format(type=camera_type))
            return None
