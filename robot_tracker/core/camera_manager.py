#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/core/camera_manager.py
Gestionnaire central des caméras USB3 et RealSense - Version 2.2
Modification: Correction des appels aux méthodes des drivers
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
    """Informations d'une caméra détectée"""
    camera_type: CameraType
    device_id: Any  # int pour USB3, str pour RealSense
    name: str
    details: Dict[str, Any]

class CameraManager:
    """Gestionnaire central pour toutes les caméras"""
    
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
        
        # Thread safety
        self.cameras_lock = Lock()
        self.callbacks_lock = Lock()
        
        # Configuration par défaut
        self.auto_detect_interval = self.config.get('camera', 'manager.auto_detect_interval', 5.0)
        self.max_frame_buffer = self.config.get('camera', 'manager.max_frame_buffer', 5)
        
        logger.info("🎥 CameraManager initialisé")
    
    def detect_all_cameras(self) -> List[CameraInfo]:
        """Détecte toutes les caméras disponibles (USB3 + RealSense) avec évitement des doublons"""
        logger.info("🔍 Détection globale des caméras...")
        
        all_cameras = []
        realsense_serials = set()  # Pour éviter les doublons RealSense
        
        # 1. Détection RealSense en priorité (plus spécifique)
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
                # Filtrage des caméras RealSense détectées par OpenCV
                # Les RealSense apparaissent souvent sous forme de caméra USB générique
                camera_name = cam['name'].lower()
                is_likely_realsense = any([
                    'realsense' in camera_name,
                    'intel' in camera_name,
                    # Si on a déjà des RealSense et que c'est une caméra générique
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
            # Vérification si déjà ouverte
            if camera_alias in self.active_cameras:
                logger.warning(f"⚠️ Caméra {camera_alias} déjà ouverte")
                return True
            
            try:
                # Création de l'instance selon le type
                if camera_info.camera_type == CameraType.USB3_CAMERA:
                    # Préparation de la configuration pour USB3
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
                    success = camera.open()  # Utilisation de la méthode 'open()' correcte
                    
                elif camera_info.camera_type == CameraType.REALSENSE:
                    if not REALSENSE_AVAILABLE:
                        logger.error("❌ RealSense non disponible")
                        return False
                    
                    camera = RealSenseCamera(self.config)
                    camera.device_serial = camera_info.device_id
                    success = camera.start_streaming()  # Utilisation de la méthode 'start_streaming()' correcte
                    
                else:
                    logger.error(f"❌ Type de caméra non supporté: {camera_info.camera_type}")
                    return False
                
                if success:
                    self.active_cameras[camera_alias] = {
                        'camera': camera,
                        'info': camera_info,
                        'last_frame': None,
                        'last_timestamp': time.time(),
                        'frame_count': 0
                    }
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
                
                # Fermeture selon le type
                if cam_data['info'].camera_type == CameraType.USB3_CAMERA:
                    camera.close()  # Utilisation de la méthode 'close()' correcte
                elif cam_data['info'].camera_type == CameraType.REALSENSE:
                    camera.stop_streaming()  # Utilisation de la méthode 'stop_streaming()' correcte
                
                del self.active_cameras[alias]
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
        """Récupère une frame d'une caméra spécifique"""
        with self.cameras_lock:
            if alias not in self.active_cameras:
                return False, None, None
            
            cam_data = self.active_cameras[alias]
            camera = cam_data['camera']
            
            try:
                if cam_data['info'].camera_type == CameraType.USB3_CAMERA:
                    # Pour USB3: récupération de la frame couleur uniquement
                    frame = camera.get_frame()
                    if frame is not None:
                        cam_data['last_frame'] = frame
                        cam_data['last_timestamp'] = time.time()
                        cam_data['frame_count'] += 1
                        return True, frame, None
                    else:
                        return False, None, None
                        
                elif cam_data['info'].camera_type == CameraType.REALSENSE:
                    # Pour RealSense: récupération couleur + profondeur
                    color_frame, depth_frame, _ = camera.get_frames()
                    if color_frame is not None:
                        cam_data['last_frame'] = color_frame
                        cam_data['last_timestamp'] = time.time()
                        cam_data['frame_count'] += 1
                        return True, color_frame, depth_frame
                    else:
                        return False, None, None
                        
                else:
                    return False, None, None
                    
            except Exception as e:
                logger.error(f"❌ Erreur récupération frame {alias}: {e}")
                return False, None, None
    
    def get_all_frames(self) -> Dict[str, Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]]:
        """Récupère les frames de toutes les caméras actives"""
        all_frames = {}
        
        with self.cameras_lock:
            for alias in self.active_cameras.keys():
                all_frames[alias] = self.get_camera_frame(alias)
        
        return all_frames
    
    def start_streaming(self, frame_callback: Callable = None) -> bool:
        """Démarre le streaming de toutes les caméras"""
        if self.streaming:
            logger.warning("⚠️ Streaming déjà actif")
            return True
        
        if not self.active_cameras:
            logger.warning("⚠️ Aucune caméra ouverte pour streaming")
            return False
        
        # Ajout du callback si fourni
        if frame_callback:
            with self.callbacks_lock:
                self.frame_callbacks.append(frame_callback)
        
        # Démarrage du thread de streaming
        self.streaming_stop_event.clear()
        self.streaming_thread = Thread(target=self._streaming_loop, daemon=True)
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
            self.streaming_thread.join(timeout=2.0)
        
        self.streaming = False
        logger.info("⏹️ Streaming global arrêté")
    
    def _streaming_loop(self):
        """Boucle principale de streaming"""
        logger.debug("🔄 Début boucle streaming globale")
        
        while not self.streaming_stop_event.is_set():
            try:
                # Récupération des frames de toutes les caméras
                all_frames = self.get_all_frames()
                
                # Appel des callbacks
                with self.callbacks_lock:
                    for callback in self.frame_callbacks:
                        try:
                            callback(all_frames)
                        except Exception as e:
                            logger.error(f"❌ Erreur callback streaming: {e}")
                
                # Contrôle de la fréquence
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                logger.error(f"❌ Erreur boucle streaming: {e}")
                break
        
        logger.debug("🛑 Fin boucle streaming globale")
    
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
                            'type': 'USB3',
                            'device_id': camera_info['device_id'],
                            'resolution': f"{camera_info['width']}x{camera_info['height']}",
                            'fps': camera_info['fps'],
                            'status': camera_info['status'],
                            'frame_count': cam_data['frame_count'],
                            'last_timestamp': cam_data['last_timestamp']
                        }
                    elif info.camera_type == CameraType.REALSENSE:
                        camera_info = camera.get_info()
                        stats[alias] = {
                            'type': 'RealSense',
                            'device_serial': camera_info['device_serial'],
                            'color_resolution': camera_info['color_resolution'],
                            'depth_resolution': camera_info['depth_resolution'],
                            'fps': camera_info['fps'],
                            'status': camera_info['status'],
                            'frame_count': cam_data['frame_count'],
                            'last_timestamp': cam_data['last_timestamp']
                        }
                except Exception as e:
                    logger.error(f"❌ Erreur stats {alias}: {e}")
                    stats[alias] = {'error': str(e)}
        
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
                    # Pour USB3: paramètres basiques uniquement
                    return {
                        'color': {
                            'width': camera.width,
                            'height': camera.height,
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
            
            # Sauvegarde aussi la profondeur si disponible
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

def test_camera_manager(duration: float = 10.0) -> bool:
    """Test complet du gestionnaire de caméras"""
    logger.info(f"🧪 Test CameraManager pendant {duration}s...")
    
    # Configuration dummy
    dummy_config = type('Config', (), {
        'get': lambda self, section, key, default=None: default
    })()
    
    manager = CameraManager(dummy_config)
    
    try:
        # 1. Détection
        cameras = manager.detect_all_cameras()
        if not cameras:
            logger.warning("⚠️ Aucune caméra détectée")
            return False
        
        logger.info(f"📷 {len(cameras)} caméra(s) détectée(s)")
        
        # 2. Ouverture de la première caméra
        first_camera = cameras[0]
        if not manager.open_camera(first_camera, "test_cam"):
            logger.error("❌ Échec ouverture caméra")
            return False
        
        # 3. Test streaming
        if not manager.start_streaming():
            logger.error("❌ Échec démarrage streaming")
            return False
        
        # 4. Capture de frames pendant la durée spécifiée
        start_time = time.time()
        frame_count = 0
        
        while time.time() - start_time < duration:
            ret, color, depth = manager.get_camera_frame("test_cam")
            if ret:
                frame_count += 1
            time.sleep(0.1)
        
        fps_measured = frame_count / duration
        logger.info(f"✅ Test réussi: {frame_count} frames, ~{fps_measured:.1f} fps")
        
        # 5. Nettoyage
        manager.stop_streaming()
        manager.close_all_cameras()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test CameraManager échoué: {e}")
        return False
    finally:
        manager.stop_streaming()
        manager.close_all_cameras()