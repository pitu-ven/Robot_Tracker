#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/core/camera_manager.py
Gestionnaire central des caméras USB3 et RealSense - Version 2.0
Modification: Intégration complète avec streaming temps réel et détection auto
"""

import cv2
import numpy as np
import time
import logging
from typing import Optional, Dict, Any, List, Tuple, Callable
from threading import Thread, Lock, Event
from enum import Enum
from dataclasses import dataclass

# Import des drivers
try:
    from ..hardware.usb3_camera_driver import USB3Camera, list_available_cameras
except ImportError:
    from hardware.usb3_camera_driver import USB3Camera, list_available_cameras

logger = logging.getLogger(__name__)

try:
    from ..hardware.realsense_driver import RealSenseCamera, list_available_realsense
    REALSENSE_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ RealSense non disponible - installation: pip install pyrealsense2")
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
        """Détecte toutes les caméras disponibles (USB3 + RealSense)"""
        logger.info("🔍 Détection globale des caméras...")
        
        all_cameras = []
        
        # 1. Caméras USB3
        try:
            usb_cameras = list_available_cameras()
            for cam in usb_cameras:
                camera_info = CameraInfo(
                    camera_type=CameraType.USB3_CAMERA,
                    device_id=cam['device_id'],
                    name=f"USB3: {cam['name']}",
                    details=cam
                )
                all_cameras.append(camera_info)
                logger.info(f"✅ USB3 trouvée: {camera_info.name}")
        except Exception as e:
            logger.error(f"❌ Erreur détection USB3: {e}")
        
        # 2. Caméras RealSense
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
                    logger.info(f"✅ RealSense trouvée: {camera_info.name}")
            except Exception as e:
                logger.error(f"❌ Erreur détection RealSense: {e}")
        else:
            logger.info("⚠️ RealSense non disponible")
        
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
                    camera = USB3Camera(self.config)
                    camera.device_id = camera_info.device_id
                    success = camera.open_camera()
                    
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
                    camera.close_camera()
                elif cam_data['info'].camera_type == CameraType.REALSENSE:
                    camera.stop_streaming()
                
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
                    ret, frame = camera.get_frame()
                    if ret:
                        cam_data['last_frame'] = frame
                        cam_data['last_timestamp'] = time.time()
                        cam_data['frame_count'] += 1
                    return ret, frame, None
                    
                elif cam_data['info'].camera_type == CameraType.REALSENSE:
                    ret, color_frame, depth_frame = camera.get_frames()
                    if ret:
                        cam_data['last_frame'] = color_frame
                        cam_data['last_timestamp'] = time.time()
                        cam_data['frame_count'] += 1
                    return ret, color_frame, depth_frame
                    
            except Exception as e:
                logger.error(f"❌ Erreur acquisition frame {alias}: {e}")
                return False, None, None
    
    def get_all_frames(self) -> Dict[str, Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]]:
        """Récupère les frames de toutes les caméras actives"""
        frames = {}
        
        with self.cameras_lock:
            camera_aliases = list(self.active_cameras.keys())
        
        for alias in camera_aliases:
            ret, color_frame, depth_frame = self.get_camera_frame(alias)
            frames[alias] = (ret, color_frame, depth_frame)
        
        return frames
    
    def start_streaming(self, frame_callback: Callable = None):
        """Démarre le streaming en continu de toutes les caméras"""
        if self.streaming:
            logger.warning("⚠️ Streaming déjà démarré")
            return
        
        logger.info("🎬 Démarrage streaming global...")
        
        if frame_callback:
            self.add_frame_callback(frame_callback)
        
        self.streaming = True
        self.streaming_stop_event.clear()
        self.streaming_thread = Thread(target=self._streaming_loop, daemon=True)
        self.streaming_thread.start()
        
        logger.info("✅ Streaming global démarré")
    
    def stop_streaming(self):
        """Arrête le streaming"""
        if not self.streaming:
            return
        
        logger.info("🛑 Arrêt streaming global...")
        
        self.streaming = False
        self.streaming_stop_event.set()
        
        if self.streaming_thread:
            self.streaming_thread.join(timeout=2.0)
            self.streaming_thread = None
        
        logger.info("✅ Streaming global arrêté")
    
    def _streaming_loop(self):
        """Boucle principale de streaming"""
        logger.info("🔄 Boucle streaming démarrée")
        
        while self.streaming and not self.streaming_stop_event.is_set():
            try:
                # Acquisition de toutes les frames
                all_frames = self.get_all_frames()
                
                if all_frames:
                    # Notification des callbacks
                    self._notify_frame_callbacks(all_frames)
                
                # Petite pause pour éviter la surcharge CPU
                time.sleep(0.01)  # ~100 FPS max
                
            except Exception as e:
                logger.error(f"❌ Erreur boucle streaming: {e}")
                time.sleep(0.1)
        
        logger.info("🔄 Boucle streaming terminée")
    
    def add_frame_callback(self, callback: Callable):
        """Ajoute un callback pour nouveaux frames"""
        with self.callbacks_lock:
            if callback not in self.frame_callbacks:
                self.frame_callbacks.append(callback)
                logger.info(f"➕ Callback frame ajouté: {callback.__name__}")
    
    def remove_frame_callback(self, callback: Callable):
        """Supprime un callback"""
        with self.callbacks_lock:
            if callback in self.frame_callbacks:
                self.frame_callbacks.remove(callback)
                logger.info(f"➖ Callback frame supprimé: {callback.__name__}")
    
    def _notify_frame_callbacks(self, frames_data: Dict):
        """Notifie tous les callbacks des nouveaux frames"""
        with self.callbacks_lock:
            for callback in self.frame_callbacks:
                try:
                    callback(frames_data)
                except Exception as e:
                    logger.error(f"❌ Erreur callback {callback.__name__}: {e}")
    
    def get_camera_stats(self, alias: str) -> Dict[str, Any]:
        """Récupère les statistiques d'une caméra"""
        with self.cameras_lock:
            if alias not in self.active_cameras:
                return {}
            
            cam_data = self.active_cameras[alias]
            camera = cam_data['camera']
            
            stats = {
                'alias': alias,
                'type': cam_data['info'].camera_type.value,
                'name': cam_data['info'].name,
                'frame_count': cam_data['frame_count'],
                'last_timestamp': cam_data['last_timestamp'],
                'is_active': True
            }
            
            # Stats spécifiques au type
            try:
                if cam_data['info'].camera_type == CameraType.USB3_CAMERA:
                    stats.update({
                        'fps': getattr(camera, 'current_fps', 0),
                        'resolution': f"{camera.width}x{camera.height}",
                        'device_id': camera.device_id
                    })
                elif cam_data['info'].camera_type == CameraType.REALSENSE:
                    stats.update({
                        'fps': getattr(camera, 'current_fps', 0),
                        'color_resolution': f"{camera.color_width}x{camera.color_height}",
                        'depth_resolution': f"{camera.depth_width}x{camera.depth_height}",
                        'serial': camera.device_serial
                    })
            except Exception as e:
                logger.warning(f"⚠️ Erreur récupération stats {alias}: {e}")
            
            return stats
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Récupère les statistiques de toutes les caméras"""
        all_stats = {}
        
        with self.cameras_lock:
            camera_aliases = list(self.active_cameras.keys())
        
        for alias in camera_aliases:
            all_stats[alias] = self.get_camera_stats(alias)
        
        return all_stats
    
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
                    # Pour USB3, on pourrait implémenter une calibration
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
        
        # 3. Test d'acquisition de frames
        start_time = time.time()
        frame_count = 0
        
        while time.time() - start_time < duration:
            ret, color_frame, depth_frame = manager.get_camera_frame("test_cam")
            if ret:
                frame_count += 1
                
                # Test périodique des stats
                if frame_count % 100 == 0:
                    stats = manager.get_camera_stats("test_cam")
                    logger.info(f"📊 Stats: {frame_count} frames, FPS: {stats.get('fps', 0):.1f}")
            
            time.sleep(0.01)
        
        # 4. Nettoyage
        manager.close_camera("test_cam")
        
        fps_avg = frame_count / duration
        logger.info(f"✅ Test réussi: {frame_count} frames en {duration}s ({fps_avg:.1f} FPS moyen)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur test manager: {e}")
        return False
    finally:
        manager.close_all_cameras()


# ============================================================================
# Point d'entrée pour tests
# ============================================================================

if __name__ == "__main__":
    # Configuration du logging pour les tests
    logging.basicConfig(level=logging.INFO)
    
    print("🎥 Test du CameraManager")
    print("=" * 50)
    
    # 1. Détection globale
    cameras = detect_all_available_cameras()
    print(f"\nCaméras disponibles: {len(cameras)}")
    for i, cam in enumerate(cameras):
        print(f"  {i+1}. {cam.name} ({cam.camera_type.value})")
    
    if cameras:
        # 2. Test complet
        print(f"\nTest complet du gestionnaire...")
        success = test_camera_manager(duration=5.0)
        if success:
            print("✅ Test gestionnaire réussi!")
        else:
            print("❌ Test gestionnaire échoué!")
    else:
        print("❌ Aucune caméra disponible pour les tests")
        print("💡 Connectez une caméra USB ou RealSense")