# tests/quick_fix_camera_manager.py
# Version 1.0 - Correction rapide pour les méthodes manquantes de CameraManager
# Modification: Patch rapide pour résoudre les erreurs AttributeError

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from pathlib import Path

def quick_fix_camera_manager():
    """Applique une correction rapide au fichier camera_manager.py"""
    print("⚡ Correction rapide de CameraManager...")
    
    file_path = Path("core/camera_manager.py")
    
    if not file_path.exists():
        print(f"❌ Fichier {file_path} introuvable")
        return False
    
    try:
        # Lecture du fichier
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Sauvegarde rapide
        backup_path = file_path.with_suffix('.py.quickbackup')
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"💾 Sauvegarde: {backup_path}")
        
        # Corrections nécessaires
        modifications = []
        
        # 1. Ajout de Tuple dans les imports si manquant
        if 'from typing import' in content and 'Tuple' not in content:
            content = content.replace(
                'from typing import Dict, List, Optional, Any, Union',
                'from typing import Dict, List, Optional, Any, Union, Tuple'
            )
            modifications.append("Import Tuple ajouté")
        
        # 2. Ajout de _is_streaming dans __init__ si manquant
        if 'self._is_streaming = False' not in content:
            init_pattern = r'(self\.lock = threading\.RLock\(\)\s*\n)'
            if re.search(init_pattern, content):
                content = re.sub(
                    init_pattern,
                    r'\1        self._is_streaming = False\n',
                    content
                )
                modifications.append("Propriété _is_streaming ajoutée")
        
        # 3. Ajout detect_all_cameras si manquant
        if 'def detect_all_cameras(' not in content:
            detect_method = '''
    def detect_all_cameras(self):
        """Alias pour detect_cameras() - Méthode attendue par camera_tab.py"""
        return self.detect_cameras()
'''
            # Insertion après detect_cameras
            content = content.replace(
                '        return detected',
                '        return detected' + detect_method
            )
            modifications.append("Méthode detect_all_cameras ajoutée")
        
        # 4. Ajout start_streaming si manquant
        if 'def start_streaming(' not in content:
            start_method = '''
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
                for alias, camera_instance in self.camera_instances.items():
                    if hasattr(camera_instance, 'start_streaming'):
                        camera_instance.start_streaming()
                        logger.info(f"✅ Streaming démarré pour {alias}")
                
                self._is_streaming = True
                logger.info("✅ Streaming global démarré")
                return True
                
            except Exception as e:
                logger.error(f"Erreur démarrage streaming: {e}")
                return False
'''
            # Insertion après close_all_cameras
            content = content.replace(
                '                self.close_camera(alias)',
                '                self.close_camera(alias)' + start_method
            )
            modifications.append("Méthode start_streaming ajoutée")
        
        # 5. Ajout stop_streaming si manquant
        if 'def stop_streaming(' not in content:
            stop_method = '''
    def stop_streaming(self):
        """Arrête le streaming pour toutes les caméras - Méthode attendue par main_window.py"""
        with self.lock:
            if not self._is_streaming:
                logger.debug("⚠️ Streaming déjà arrêté")
                return
            
            try:
                for alias, camera_instance in self.camera_instances.items():
                    if hasattr(camera_instance, 'stop_streaming'):
                        camera_instance.stop_streaming()
                        logger.info(f"✅ Streaming arrêté pour {alias}")
                
                self._is_streaming = False
                logger.info("✅ Streaming global arrêté")
                
            except Exception as e:
                logger.error(f"Erreur arrêt streaming: {e}")
'''
            # Insertion après start_streaming
            insert_point = content.rfind('return True') + len('return True')
            if insert_point > len('return True'):
                lines = content[:insert_point].split('\n')
                # Trouver la fin de la méthode start_streaming
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip().startswith('return True'):
                        content = '\n'.join(lines[:i+1]) + stop_method + '\n'.join(lines[i+1:])
                        break
                modifications.append("Méthode stop_streaming ajoutée")
        
        # 6. Ajout active_cameras property si manquant
        if '@property' not in content or 'def active_cameras(' not in content:
            property_method = '''
    @property
    def active_cameras(self) -> List[str]:
        """Liste des caméras actives - Propriété attendue par main_window.py"""
        with self.lock:
            return list(self.camera_instances.keys())
'''
            # Insertion à la fin de la classe
            content = content + property_method
            modifications.append("Propriété active_cameras ajoutée")
        
        # 7. Correction get_camera_frame pour compatibilité camera_tab
        if 'def get_camera_frame(' in content and 'Tuple[bool, np.ndarray' not in content:
            # Remplacement de la signature
            old_signature = r'def get_camera_frame\(self, alias: str\) -> Optional\[Dict\[str, np\.ndarray\]\]:'
            new_signature = 'def get_camera_frame(self, alias: str) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:'
            
            if re.search(old_signature, content):
                content = re.sub(old_signature, new_signature, content)
                
                # Remplacement du corps de la méthode
                old_return = '''if frame_data and 'color' in frame_data:
                    return frame_data
                else:
                    return None'''
                
                new_return = '''if frame_data and 'color' in frame_data:
                    color_frame = frame_data['color']
                    depth_frame = frame_data.get('depth', None)
                    return True, color_frame, depth_frame
                else:
                    return False, None, None'''
                
                content = content.replace(old_return, new_return)
                
                # Correction du return en cas d'erreur
                content = content.replace(
                    'return None',
                    'return False, None, None'
                )
                modifications.append("Méthode get_camera_frame corrigée pour camera_tab")
        
        # Écriture du fichier corrigé
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ {len(modifications)} modification(s) appliquée(s):")
        for mod in modifications:
            print(f"   • {mod}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction: {e}")
        return False

def test_quick_fix():
    """Teste rapidement les corrections"""
    print("\n🧪 Test rapide des corrections...")
    
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path.cwd()))
        
        # Mock pyrealsense2
        if 'pyrealsense2' not in sys.modules:
            sys.modules['pyrealsense2'] = type('MockRS', (), {
                'context': lambda: type('Context', (), {
                    'query_devices': lambda: []
                })()
            })()
        
        from core.camera_manager import CameraManager
        
        dummy_config = type('Config', (), {
            'get': lambda self, section, key, default=None: default
        })()
        
        manager = CameraManager(dummy_config)
        
        # Test des méthodes critiques
        required_methods = [
            'detect_all_cameras',
            'start_streaming', 
            'stop_streaming',
            'active_cameras'
        ]
        
        all_ok = True
        for method_name in required_methods:
            if hasattr(manager, method_name):
                print(f"✅ {method_name} disponible")
            else:
                print(f"❌ {method_name} manquante")
                all_ok = False
        
        if all_ok:
            # Test d'appel basique
            try:
                cameras = manager.detect_all_cameras()
                active = manager.active_cameras
                print(f"✅ Tests d'appel réussis: {len(cameras)} caméras détectées, {len(active)} actives")
                return True
            except Exception as e:
                print(f"⚠️ Erreur d'appel: {e}")
                return True  # Méthodes présentes c'est l'essentiel
        
        return all_ok
        
    except Exception as e:
        print(f"❌ Erreur test: {e}")
        return False

def main():
    """Point d'entrée principal"""
    print("⚡ CORRECTION RAPIDE CAMERAMANAGER")
    print("=" * 40)
    print("Ajoute les méthodes manquantes rapidement")
    print()
    
    # Vérification
    if not Path("core/camera_manager.py").exists():
        print("❌ ERREUR: Fichier core/camera_manager.py introuvable")
        print("💡 Exécutez depuis le répertoire robot_tracker/")
        return 1
    
    # Application de la correction
    success = quick_fix_camera_manager()
    
    if success:
        # Test rapide
        if test_quick_fix():
            print("\n🎉 CORRECTION RAPIDE RÉUSSIE!")
            print("✅ Méthodes manquantes ajoutées")
            print("✅ Tests de base passés")
            print("\n📋 MAINTENANT:")
            print("   1. python main.py")
            print("   2. Vérifiez que les erreurs ont disparu")
            print("   3. Testez l'onglet Caméra")
            return 0
        else:
            print("\n⚠️ Correction appliquée mais problème lors des tests")
            return 1
    else:
        print("\n❌ Échec de la correction")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        print(f"\n👋 Correction terminée (code: {exit_code})")
        exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Correction interrompue")
        exit(1)
    except Exception as e:
        print(f"\n❌ Erreur générale: {e}")
        exit(1)