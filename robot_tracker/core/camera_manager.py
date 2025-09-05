# core/camera_manager.py
# Version 4.7 - Ajout méthode get_camera_stats manquante
# Modification: Ajout des méthodes get_camera_stats et get_global_stats

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
    
    def open_camera(self, camera_data, alias: Optional[str] = None):
        """Ouvre une caméra - Version corrigée avec gestion des formats"""
        with self.lock:
            if alias and self.is_camera_open(alias):
                warning_msg = self.config.get('core', 'camera_manager.messages.already_open', 
                                        'Camera already open: {alias}')
                logger.warning(warning_msg.format(alias=alias))
                return True
            
            # Gestion robuste des formats de camera_data
            camera_info = None
            camera_serial = None
            
            if isinstance(camera_data, dict):
                # Format dictionnaire (nouveau)
                camera_info = camera_data
                camera_serial = camera_data.get('serial')
            elif hasattr(camera_data, 'camera_type'):
                # Format objet (ancien) 
                camera_type_value = camera_data.camera_type.value if hasattr(camera_data.camera_type, 'value') else str(camera_data.camera_type)
                camera_info = {
                    'type': camera_type_value.lower(),
                    'serial': getattr(camera_data, 'device_id', getattr(camera_data, 'serial', 'unknown')),
                    'name': getattr(camera_data, 'name', 'Unknown Camera'),
                    'device_index': getattr(camera_data, 'device_id', 0)
                }
                camera_serial = getattr(camera_data, 'device_id', getattr(camera_data, 'serial', None))
            elif isinstance(camera_data, str):
                # Format string - supposer que c'est un serial/nom
                camera_serial = camera_data
                # Essayer de retrouver les infos depuis self.cameras
                for serial, info in self.cameras.items():
                    if serial == camera_data or info.get('name') == camera_data:
                        camera_info = info
                        camera_serial = serial
                        break
                
                if not camera_info:
                    # Créer une info basique pour RealSense
                    camera_info = {
                        'type': 'realsense',  # Assumption par défaut
                        'serial': camera_serial,
                        'name': f'RealSense {camera_serial}',
                        'device_index': 0
                    }
            else:
                error_msg = self.config.get('core', 'camera_manager.messages.invalid_format', 
                                        'Invalid camera data format: {type}')
                logger.error(error_msg.format(type=type(camera_data).__name__))
                return False
            
            if not camera_info:
                error_msg = self.config.get('core', 'camera_manager.messages.not_found', 
                                        'Camera not found: {camera_id}')
                logger.error(error_msg.format(camera_id=str(camera_data)))
                return False
            
            try:
                # Création de l'instance de caméra
                camera_instance = self._create_camera_instance(camera_info)
                
                if not camera_instance:
                    error_msg = self.config.get('core', 'camera_manager.messages.instance_failed', 
                                            'Failed to create camera instance')
                    logger.error(error_msg)
                    return False
                
                # Tentative d'ouverture/démarrage
                success = False
                if hasattr(camera_instance, 'start_streaming') and callable(camera_instance.start_streaming):
                    success = camera_instance.start_streaming()
                elif hasattr(camera_instance, 'start') and callable(camera_instance.start):
                    success = camera_instance.start()
                elif hasattr(camera_instance, 'open') and callable(camera_instance.open):
                    success = camera_instance.open()
                else:
                    # Pas de méthode d'ouverture explicite - vérifier l'état
                    success = getattr(camera_instance, 'is_streaming', True)
                
                if success:
                    final_alias = alias or f"{camera_info['type']}_{camera_info.get('device_index', 0)}"
                    self.camera_instances[final_alias] = camera_instance
                    
                    success_msg = self.config.get('core', 'camera_manager.messages.opened', 
                                            'Camera {alias} opened successfully')
                    logger.info(success_msg.format(alias=final_alias))
                    return True
                else:
                    error_msg = self.config.get('core', 'camera_manager.messages.open_failed', 
                                            'Failed to open camera: {name}')
                    logger.error(error_msg.format(name=camera_info.get('name', 'Unknown')))
                    
                    # Nettoyage de l'instance échouée
                    if hasattr(camera_instance, 'stop_streaming'):
                        try:
                            camera_instance.stop_streaming()
                        except:
                            pass
                            
                    return False
                    
            except Exception as e:
                error_msg = self.config.get('core', 'camera_manager.messages.open_error', 
                                        'Failed to open camera: {error}')
                logger.error(error_msg.format(error=str(e)))
                
                # Log détaillé pour debug
                import traceback
                logger.debug(f"Exception complète: {traceback.format_exc()}")
                
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
        """Ferme toutes les caméras ouvertes"""
        with self.lock:
            aliases_to_close = list(self.camera_instances.keys())
            
            for alias in aliases_to_close:
                try:
                    self.close_camera(alias)
                except Exception as e:
                    logger.error(f"❌ Erreur fermeture {alias}: {e}")
            
            logger.info("✅ Toutes les caméras fermées")
    
    def is_camera_open(self, alias: str) -> bool:
        """Vérifie si une caméra est ouverte"""
        with self.lock:
            return alias in self.camera_instances
    
    def start_streaming(self):
        """Démarre le streaming global"""
        with self.lock:
            if self._is_streaming:
                logger.warning("⚠️ Streaming déjà démarré")
                return True
            
            if not self.camera_instances:
                logger.warning("⚠️ Aucune caméra ouverte pour streaming")
                return False
            
            try:
                success_count = 0
                for alias, instance in self.camera_instances.items():
                    if hasattr(instance, 'start_streaming'):
                        if instance.start_streaming():
                            success_count += 1
                            logger.info(f"✅ Streaming démarré pour {alias}")
                    elif hasattr(instance, 'start'):
                        if instance.start():
                            success_count += 1
                            logger.info(f"✅ Streaming démarré pour {alias}")
                
                if success_count > 0:
                    self._is_streaming = True
                    logger.info("✅ Streaming global démarré")
                    return True
                else:
                    logger.error("❌ Échec démarrage streaming")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Erreur démarrage streaming: {e}")
                return False
    
    def stop_streaming(self):
        """Arrête le streaming global"""
        with self.lock:
            if not self._is_streaming:
                return True
            
            try:
                # Arrêter le streaming pour chaque caméra
                for alias, instance in self.camera_instances.items():
                    if hasattr(instance, 'stop_streaming'):
                        instance.stop_streaming()
                    elif hasattr(instance, 'stop'):
                        instance.stop()
                
                self._is_streaming = False
                logger.info("✅ Streaming global arrêté")
                return True
                
            except Exception as e:
                logger.error(f"❌ Erreur arrêt streaming: {e}")
                return False
    
    def get_camera_frame(self, alias: str) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """Récupère une frame d'une caméra - Format compatible camera_tab.py - Version corrigée"""
        with self.lock:
            if alias not in self.camera_instances:
                return False, None, None
            
            try:
                camera_instance = self.camera_instances[alias]
                
                # CORRECTION: RealSenseCamera a get_frames() (avec 's') pas get_frame()
                if hasattr(camera_instance, 'get_frames'):
                    # RealSenseCamera: get_frames() -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]
                    return camera_instance.get_frames()
                    
                elif hasattr(camera_instance, 'get_frame'):
                    # Autres drivers: get_frame() -> Dict
                    frame_data = camera_instance.get_frame()
                    
                    if frame_data and isinstance(frame_data, dict) and 'color' in frame_data:
                        color_frame = frame_data['color']
                        depth_frame = frame_data.get('depth', None)
                        return True, color_frame, depth_frame
                    else:
                        return False, None, None
                        
                elif hasattr(camera_instance, 'read'):
                    # OpenCV-style: read() -> Tuple[bool, np.ndarray]
                    ret, frame = camera_instance.read()
                    return ret, frame, None
                    
                else:
                    # Pas de méthode de capture trouvée
                    logger.warning(f"⚠️ Pas de méthode de capture pour {alias}")
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
        """Crée une instance de caméra selon le type - Version corrigée"""
        camera_type = camera_info.get('type')
        
        if camera_type == 'realsense':
            # CORRECTION: RealSenseCamera prend seulement config en paramètre
            # Nous devons configurer le device_serial dans la config avant de créer l'instance
            
            # Option 1: Modifier temporairement la configuration (RECOMMANDÉ)
            camera_instance = RealSenseCamera(self.config)
            
            # Configurer le serial spécifique après création
            camera_serial = camera_info.get('serial')
            if camera_serial and hasattr(camera_instance, 'device_serial'):
                camera_instance.device_serial = camera_serial
                logger.debug(f"🎯 Serial configuré: {camera_serial}")
            
            return camera_instance
            
        elif camera_type == 'usb3':
            # USB3CameraDriver prend camera_info + config
            return USB3CameraDriver(camera_info, self.config)
        else:
            error_msg = self.config.get('core', 'camera_manager.messages.unknown_type', 
                                    'Unknown camera type: {type}')
            logger.error(error_msg.format(type=camera_type))
            return None
        
    def get_camera_stats(self, alias: str) -> Optional[Dict[str, Any]]:
        """Retourne les statistiques d'une caméra spécifique"""
        with self.lock:
            if alias not in self.camera_instances:
                logger.warning(f"⚠️ Caméra {alias} non trouvée pour stats")
                return None
            
            try:
                camera_instance = self.camera_instances[alias]
                
                # Vérifier si l'instance a une méthode get_info() (RealSense)
                if hasattr(camera_instance, 'get_info'):
                    stats = camera_instance.get_info()
                    if stats:
                        return {
                            'fps': stats.get('fps', 0.0),
                            'resolution': stats.get('color_resolution', 'N/A'),
                            'depth_resolution': stats.get('depth_resolution', 'N/A'),
                            'frame_count': stats.get('frame_count', 0),
                            'status': stats.get('status', 'unknown'),
                            'device_serial': stats.get('device_serial', 'unknown')
                        }
                
                # Méthode alternative pour autres types de caméras
                elif hasattr(camera_instance, 'current_fps'):
                    return {
                        'fps': getattr(camera_instance, 'current_fps', 0.0),
                        'resolution': 'N/A',
                        'depth_resolution': 'N/A',
                        'frame_count': getattr(camera_instance, 'frame_count', 0),
                        'status': 'active' if getattr(camera_instance, 'is_streaming', False) else 'inactive',
                        'device_serial': getattr(camera_instance, 'serial', 'unknown')
                    }
                
                # Statistiques basiques par défaut
                else:
                    return {
                        'fps': 0.0,
                        'resolution': 'N/A',
                        'depth_resolution': 'N/A',
                        'frame_count': 0,
                        'status': 'active',
                        'device_serial': 'unknown'
                    }
                    
            except Exception as e:
                logger.error(f"❌ Erreur récupération stats {alias}: {e}")
                return None

    def get_global_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques globales du CameraManager"""
        with self.lock:
            active_count = len(self.camera_instances)
            streaming_count = 0
            total_fps = 0.0
            
            for alias, instance in self.camera_instances.items():
                if hasattr(instance, 'is_streaming') and instance.is_streaming:
                    streaming_count += 1
                
                stats = self.get_camera_stats(alias)
                if stats:
                    total_fps += stats.get('fps', 0.0)
            
            return {
                'active_cameras': active_count,
                'streaming_cameras': streaming_count,
                'total_fps': total_fps,
                'average_fps': total_fps / active_count if active_count > 0 else 0.0,
                'detected_cameras': len(self.cameras),
                'last_detection': getattr(self, '_last_detection_time', 0)
            }