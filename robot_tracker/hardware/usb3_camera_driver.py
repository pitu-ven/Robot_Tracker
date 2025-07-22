#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/hardware/usb3_camera_driver.py
Driver pour caméra USB3 CMOS - Version 1.0
Modification: Implémentation complète avec OpenCV et configuration
"""

import cv2
import numpy as np
import time
import logging
from threading import Lock
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

class USB3Camera:
    """Driver pour caméra USB3 CMOS haute résolution"""
    
    def __init__(self, config):
        self.config = config
        self.cap = None
        self.is_opened = False
        self.last_frame = None
        self.frame_count = 0
        self.fps_counter = 0
        self.last_fps_time = time.time()
        self.current_fps = 0.0
        
        # Thread safety
        self.frame_lock = Lock()
        
        # Configuration par défaut
        self.device_id = self.config.get('camera', 'usb3_camera.device_id', 0)
        self.width = self.config.get('camera', 'usb3_camera.width', 1280)
        self.height = self.config.get('camera', 'usb3_camera.height', 720)
        self.fps = self.config.get('camera', 'usb3_camera.fps', 30)
        
        logger.info(f"🎥 USB3Camera initialisé - Device: {self.device_id}")
    
    def detect_cameras(self) -> list:
        """Détecte toutes les caméras USB disponibles"""
        available_cameras = []
        
        logger.info("🔍 Détection des caméras USB...")
        
        # Test jusqu'à 10 devices
        for device_id in range(10):
            try:
                cap = cv2.VideoCapture(device_id)
                if cap.isOpened():
                    # Test de lecture d'une frame
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        # Récupération des propriétés
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        
                        camera_info = {
                            'device_id': device_id,
                            'name': f'USB Camera {device_id}',
                            'resolution': f'{width}x{height}',
                            'fps': fps,
                            'backend': cap.getBackendName()
                        }
                        available_cameras.append(camera_info)
                        
                        logger.info(f"✅ Caméra trouvée: {camera_info}")
                    
                    cap.release()
                else:
                    # Device existe mais pas accessible
                    pass
                    
            except Exception as e:
                # Erreur normale pour device inexistant
                continue
        
        logger.info(f"📷 {len(available_cameras)} caméra(s) USB détectée(s)")
        return available_cameras
    
    def open_camera(self) -> bool:
        """Ouvre la caméra avec la configuration"""
        try:
            if self.is_opened:
                logger.warning("⚠️ Caméra déjà ouverte")
                return True
            
            logger.info(f"📷 Ouverture caméra USB device {self.device_id}...")
            
            # Création de l'objet capture
            self.cap = cv2.VideoCapture(self.device_id)
            
            if not self.cap.isOpened():
                logger.error(f"❌ Impossible d'ouvrir la caméra {self.device_id}")
                return False
            
            # Configuration des propriétés
            self._configure_camera()
            
            # Test de capture
            ret, frame = self.cap.read()
            if not ret or frame is None:
                logger.error("❌ Impossible de capturer une frame de test")
                self.cap.release()
                return False
            
            self.is_opened = True
            self.frame_count = 0
            self.last_fps_time = time.time()
            
            # Affichage des propriétés finales
            self._log_camera_properties()
            
            logger.info("✅ Caméra USB ouverte avec succès")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur ouverture caméra: {e}")
            if self.cap:
                self.cap.release()
            return False
    
    def _configure_camera(self):
        """Configure les propriétés de la caméra"""
        try:
            # Résolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            
            # FPS
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            
            # Buffer size (important pour les hautes fréquences)
            buffer_size = self.config.get('camera', 'usb3_camera.buffer_size', 1)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, buffer_size)
            
            # Auto-exposition (si supporté)
            auto_exposure = self.config.get('camera', 'usb3_camera.auto_exposure', True)
            if auto_exposure:
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
            else:
                self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
                exposure = self.config.get('camera', 'usb3_camera.exposure', -6)
                self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
            
            # Gain
            gain = self.config.get('camera', 'usb3_camera.gain', 0)
            self.cap.set(cv2.CAP_PROP_GAIN, gain)
            
            # Format de pixel (si supporté)
            try:
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
            except:
                pass  # Pas grave si non supporté
            
            logger.info("⚙️ Configuration caméra appliquée")
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur configuration caméra: {e}")
    
    def _log_camera_properties(self):
        """Affiche les propriétés actuelles de la caméra"""
        try:
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            backend = self.cap.getBackendName()
            
            logger.info(f"📊 Propriétés caméra:")
            logger.info(f"   - Résolution: {actual_width}x{actual_height}")
            logger.info(f"   - FPS: {actual_fps}")
            logger.info(f"   - Backend: {backend}")
            
        except Exception as e:
            logger.warning(f"⚠️ Impossible de lire les propriétés: {e}")
    
    def get_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Récupère une frame de la caméra"""
        if not self.is_opened or not self.cap:
            return False, None
        
        try:
            ret, frame = self.cap.read()
            
            if ret and frame is not None:
                with self.frame_lock:
                    self.last_frame = frame.copy()
                    self.frame_count += 1
                    self._update_fps()
                
                return True, frame
            else:
                logger.warning("⚠️ Frame vide reçue")
                return False, None
                
        except Exception as e:
            logger.error(f"❌ Erreur capture frame: {e}")
            return False, None
    
    def _update_fps(self):
        """Met à jour le calcul de FPS"""
        self.fps_counter += 1
        current_time = time.time()
        
        if current_time - self.last_fps_time >= 1.0:  # Calcul chaque seconde
            self.current_fps = self.fps_counter / (current_time - self.last_fps_time)
            self.fps_counter = 0
            self.last_fps_time = current_time
    
    def get_last_frame(self) -> Optional[np.ndarray]:
        """Retourne la dernière frame capturée"""
        with self.frame_lock:
            return self.last_frame.copy() if self.last_frame is not None else None
    
    def get_fps(self) -> float:
        """Retourne le FPS actuel"""
        return self.current_fps
    
    def get_frame_count(self) -> int:
        """Retourne le nombre total de frames capturées"""
        return self.frame_count
    
    def get_camera_info(self) -> Dict[str, Any]:
        """Retourne les informations sur la caméra"""
        if not self.is_opened:
            return {'status': 'closed'}
        
        try:
            return {
                'status': 'opened',
                'device_id': self.device_id,
                'resolution': f"{int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}",
                'fps_config': self.cap.get(cv2.CAP_PROP_FPS),
                'fps_actual': self.current_fps,
                'frame_count': self.frame_count,
                'backend': self.cap.getBackendName() if hasattr(self.cap, 'getBackendName') else 'Unknown'
            }
        except Exception as e:
            logger.warning(f"⚠️ Erreur lecture info caméra: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def set_resolution(self, width: int, height: int) -> bool:
        """Change la résolution de la caméra"""
        if not self.is_opened:
            return False
        
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            # Vérification
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if actual_width == width and actual_height == height:
                self.width = width
                self.height = height
                logger.info(f"✅ Résolution changée: {width}x{height}")
                return True
            else:
                logger.warning(f"⚠️ Résolution demandée {width}x{height}, obtenue {actual_width}x{actual_height}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur changement résolution: {e}")
            return False
    
    def set_fps(self, fps: float) -> bool:
        """Change le FPS de la caméra"""
        if not self.is_opened:
            return False
        
        try:
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            self.fps = fps
            logger.info(f"✅ FPS configuré: {fps} (actuel: {actual_fps})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur changement FPS: {e}")
            return False
    
    def close_camera(self):
        """Ferme la caméra"""
        try:
            if self.cap:
                self.cap.release()
                self.cap = None
            
            self.is_opened = False
            self.last_frame = None
            self.frame_count = 0
            
            logger.info("📷 Caméra USB fermée")
            
        except Exception as e:
            logger.error(f"❌ Erreur fermeture caméra: {e}")
    
    def __del__(self):
        """Destructeur - ferme la caméra automatiquement"""
        self.close_camera()


# ============================================================================
# Fonctions utilitaires
# ============================================================================

def list_available_cameras() -> list:
    """Liste toutes les caméras USB disponibles"""
    dummy_config = type('Config', (), {
        'get': lambda self, section, key, default=None: default
    })()
    
    camera = USB3Camera(dummy_config)
    return camera.detect_cameras()

def test_camera(device_id: int = 0, duration: float = 5.0) -> bool:
    """Test rapide d'une caméra"""
    logger.info(f"🧪 Test caméra device {device_id} pendant {duration}s...")
    
    dummy_config = type('Config', (), {
        'get': lambda self, section, key, default=None: {
            'camera.usb3_camera.device_id': device_id,
            'camera.usb3_camera.width': 640,
            'camera.usb3_camera.height': 480,
            'camera.usb3_camera.fps': 30
        }.get(f"{section}.{key}", default)
    })()
    
    camera = USB3Camera(dummy_config)
    
    try:
        if not camera.open_camera():
            return False
        
        start_time = time.time()
        frame_count = 0
        
        while time.time() - start_time < duration:
            ret, frame = camera.get_frame()
            if ret:
                frame_count += 1
                
                # Affichage optionnel (décommentez pour voir la vidéo)
                # cv2.imshow(f'Test Camera {device_id}', frame)
                # if cv2.waitKey(1) & 0xFF == ord('q'):
                #     break
            
            time.sleep(0.01)  # ~100 FPS max
        
        # cv2.destroyAllWindows()
        
        fps_measured = frame_count / duration
        logger.info(f"✅ Test réussi: {frame_count} frames en {duration}s ({fps_measured:.1f} FPS)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur test caméra: {e}")
        return False
    finally:
        camera.close_camera()


# ============================================================================
# Point d'entrée pour tests
# ============================================================================

if __name__ == "__main__":
    # Configuration du logging pour les tests
    logging.basicConfig(level=logging.INFO)
    
    print("🎥 Test du driver caméra USB3")
    print("=" * 40)
    
    # 1. Détection des caméras
    cameras = list_available_cameras()
    print(f"Caméras détectées: {len(cameras)}")
    for cam in cameras:
        print(f"  - {cam}")
    
    if cameras:
        # 2. Test de la première caméra
        device_id = cameras[0]['device_id']
        print(f"\nTest de la caméra {device_id}...")
        
        success = test_camera(device_id, duration=3.0)
        if success:
            print("✅ Test réussi!")
        else:
            print("❌ Test échoué!")
    else:
        print("❌ Aucune caméra détectée")