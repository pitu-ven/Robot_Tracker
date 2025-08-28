# hardware/usb3_camera_driver.py
# Version 2.1 - Correction indentation et ajout detect_cameras
# Modification: Résolution erreur syntaxe + méthode detect_cameras

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import cv2
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
import threading
import time

logger = logging.getLogger(__name__)

class USB3CameraDriver:
    """Driver pour caméras USB3 standard utilisant OpenCV"""
    
    def __init__(self, camera_info: Dict, config):
        self.camera_info = camera_info
        self.config = config
        self.device_id = camera_info.get('device_index', 0)
        self.cap = None
        self.is_streaming = False
        self.lock = threading.Lock()
        
        # Configuration
        self.width = self.config.get('camera', 'usb3.width', 640)
        self.height = self.config.get('camera', 'usb3.height', 480)
        self.fps = self.config.get('camera', 'usb3.fps', 30)
        
        logger.info(f"🔌 USB3CameraDriver initialisé pour device {self.device_id}")
    
    @staticmethod
    def detect_cameras():
        """Détecte les caméras USB3 disponibles"""
        detected_cameras = []
        
        try:
            # Test des indices de caméra de 0 à 5
            for i in range(6):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    # Test de lecture d'une frame
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        camera_info = {
                            'type': 'usb3',
                            'serial': f'usb_camera_{i}',
                            'name': f'USB Camera {i}',
                            'alias': f'usb3_{i}',
                            'device_index': i,
                            'capabilities': {
                                'color': True,
                                'depth': False,
                                'infrared': False
                            }
                        }
                        detected_cameras.append(camera_info)
                        logger.info(f"✅ Caméra USB détectée: index {i}")
                    
                    cap.release()
                
        except Exception as e:
            logger.warning(f"⚠️ Erreur détection USB3: {e}")
        
        return detected_cameras
    
    def open(self):
        """Ouvre la caméra USB3"""
        with self.lock:
            if self.cap is not None:
                logger.warning("⚠️ Caméra déjà ouverte")
                return True
            
            try:
                self.cap = cv2.VideoCapture(self.device_id)
                
                if not self.cap.isOpened():
                    logger.error(f"❌ Impossible d'ouvrir la caméra USB {self.device_id}")
                    return False
                
                # Configuration de la caméra
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                
                logger.info(f"✅ Caméra USB {self.device_id} ouverte")
                return True
                
            except Exception as e:
                logger.error(f"❌ Erreur ouverture caméra USB {self.device_id}: {e}")
                return False
    
    def close(self):
        """Ferme la caméra USB3"""
        with self.lock:
            if self.cap is not None:
                try:
                    self.stop_streaming()
                    self.cap.release()
                    self.cap = None
                    logger.info(f"✅ Caméra USB {self.device_id} fermée")
                except Exception as e:
                    logger.error(f"❌ Erreur fermeture caméra USB: {e}")
    
    def start_streaming(self):
        """Démarre le streaming"""
        with self.lock:
            if not self.cap or not self.cap.isOpened():
                logger.error("❌ Caméra non ouverte pour le streaming")
                return False
            
            self.is_streaming = True
            logger.info(f"✅ Streaming démarré pour caméra USB {self.device_id}")
            return True
    
    def stop_streaming(self):
        """Arrête le streaming"""
        with self.lock:
            self.is_streaming = False
            logger.info(f"✅ Streaming arrêté pour caméra USB {self.device_id}")
    
    def get_frame(self) -> Optional[Dict[str, np.ndarray]]:
        """Récupère une frame de la caméra"""
        with self.lock:
            if not self.cap or not self.cap.isOpened() or not self.is_streaming:
                return None
            
            try:
                ret, frame = self.cap.read()
                
                if ret and frame is not None:
                    return {
                        'color': frame,
                        'depth': None  # USB3 standard n'a pas de profondeur
                    }
                else:
                    return None
                    
            except Exception as e:
                logger.error(f"❌ Erreur capture frame USB {self.device_id}: {e}")
                return None
    
    def get_camera_info(self) -> Dict:
        """Retourne les informations de la caméra"""
        return {
            'type': 'usb3',
            'device_id': self.device_id,
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'is_streaming': self.is_streaming
        }
    
    def set_parameter(self, param: str, value: Any) -> bool:
        """Configure un paramètre de la caméra"""
        with self.lock:
            if not self.cap or not self.cap.isOpened():
                return False
            
            try:
                param_map = {
                    'brightness': cv2.CAP_PROP_BRIGHTNESS,
                    'contrast': cv2.CAP_PROP_CONTRAST,
                    'saturation': cv2.CAP_PROP_SATURATION,
                    'exposure': cv2.CAP_PROP_EXPOSURE,
                    'gain': cv2.CAP_PROP_GAIN
                }
                
                if param in param_map:
                    success = self.cap.set(param_map[param], value)
                    if success:
                        logger.info(f"✅ Paramètre {param} configuré à {value}")
                    else:
                        logger.warning(f"⚠️ Échec configuration {param}")
                    return success
                else:
                    logger.warning(f"⚠️ Paramètre {param} non supporté")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Erreur configuration paramètre {param}: {e}")
                return False
    
    def __enter__(self):
        """Context manager entry"""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
