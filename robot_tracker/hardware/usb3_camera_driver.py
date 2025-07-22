#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/hardware/usb3_camera_driver.py
Driver pour caméra USB3 CMOS haute résolution - Version 1.1
Modification: Implémentation complète avec streaming temps réel
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
    """Driver pour caméra USB3 CMOS haute résolution"""
    
    def __init__(self, device_id: int = 0, config: Optional[Dict] = None):
        self.device_id = device_id
        self.config = config or {}
        
        # État de la caméra
        self.cap = None
        self.is_open = False
        self.is_streaming = False
        
        # Configuration par défaut
        self.width = self.config.get('width', 640)
        self.height = self.config.get('height', 480)
        self.fps = self.config.get('fps', 30)
        self.buffer_size = self.config.get('buffer_size', 1)
        self.auto_exposure = self.config.get('auto_exposure', True)
        self.exposure = self.config.get('exposure', -6)
        self.gain = self.config.get('gain', 0)
        
        # Streaming
        self.streaming_thread = None
        self.streaming_stop_event = Event()
        self.frame_lock = Lock()
        self.latest_frame = None
        
        logger.info(f"🔧 USB3CameraDriver initialisé (device_id={device_id})")
    
    def open(self) -> bool:
        """Ouvre la connexion avec la caméra"""
        try:
            if self.is_open:
                logger.warning("⚠️ Caméra déjà ouverte")
                return True
            
            logger.info(f"📷 Ouverture caméra USB3 {self.device_id}...")
            
            # Ouverture de la caméra
            self.cap = cv2.VideoCapture(self.device_id)
            
            if not self.cap.isOpened():
                raise USB3CameraError(f"Impossible d'ouvrir la caméra {self.device_id}")
            
            # Configuration des paramètres
            self._configure_camera()
            
            # Test de capture
            ret, frame = self.cap.read()
            if not ret:
                raise USB3CameraError("Impossible de capturer une frame de test")
            
            self.is_open = True
            logger.info(f"✅ Caméra USB3 {self.device_id} ouverte avec succès")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur ouverture caméra USB3: {e}")
            self.close()
            return False
    
    def _configure_camera(self):
        """Configure les paramètres de la caméra"""
        if not self.cap:
            return
        
        # Résolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        
        # FPS
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        # Buffer
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
        
        # Exposition
        if self.auto_exposure:
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
        else:
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, self.exposure)
        
        # Gain
        self.cap.set(cv2.CAP_PROP_GAIN, self.gain)
        
        # Vérification des paramètres appliqués
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        logger.info(f"📐 Résolution: {actual_width}x{actual_height} @ {actual_fps:.1f}fps")
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Capture une frame"""
        if not self.is_open or not self.cap:
            logger.warning("⚠️ Caméra non ouverte")
            return None
        
        try:
            ret, frame = self.cap.read()
            if ret:
                return frame
            else:
                logger.warning("⚠️ Échec capture frame")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur capture frame: {e}")
            return None
    
    def start_streaming(self) -> bool:
        """Démarre le streaming en arrière-plan"""
        if self.is_streaming:
            logger.warning("⚠️ Streaming déjà actif")
            return True
        
        if not self.is_open:
            logger.error("❌ Caméra non ouverte pour streaming")
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
        logger.debug("🔄 Début boucle streaming USB3")
        
        while not self.streaming_stop_event.is_set():
            frame = self.get_frame()
            
            if frame is not None:
                with self.frame_lock:
                    self.latest_frame = frame.copy()
            
            time.sleep(1.0 / self.fps)  # Contrôle de la fréquence
        
        logger.debug("🛑 Fin boucle streaming USB3")
    
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
            'exposure': self.cap.get(cv2.CAP_PROP_EXPOSURE),
            'gain': self.cap.get(cv2.CAP_PROP_GAIN)
        }
    
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
            # Test de capture
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
    logger.info(f"🧪 Test caméra USB {device_id} pendant {duration}s...")
    
    try:
        with USB3CameraDriver(device_id) as camera:
            if not camera.is_open:
                return False
            
            # Test de capture continue
            start_time = time.time()
            frame_count = 0
            
            while time.time() - start_time < duration:
                frame = camera.get_frame()
                if frame is not None:
                    frame_count += 1
                time.sleep(0.1)
            
            fps_measured = frame_count / duration
            logger.info(f"✅ Test réussi: {frame_count} frames, ~{fps_measured:.1f} fps")
            return True
            
    except Exception as e:
        logger.error(f"❌ Test échoué: {e}")
        return False

# Alias pour compatibilité
USB3Camera = USB3CameraDriver