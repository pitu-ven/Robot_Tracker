#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/ui/camera_display_widget.py
Widget d'affichage caméra avec vues RGB et profondeur configurables - Version 1.1
Modification: Suppression des valeurs statiques, configuration entièrement via JSON
"""

import cv2
import numpy as np
import time
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QPixmap, QImage, QFont
import logging

logger = logging.getLogger(__name__)

class SingleCameraView(QLabel):
    """Vue simple d'une caméra (RGB ou profondeur) - Entièrement configurable"""
    
    def __init__(self, view_type: str, alias: str, config, parent=None):
        super().__init__(parent)
        self.view_type = view_type
        self.alias = alias
        self.config = config
        self.current_frame = None
        self.zoom_factor = config.get('ui', 'camera_display.single_view.default_zoom', 1.0)
        
        # Configuration des tailles depuis JSON
        min_width = config.get('ui', 'camera_display.single_view.min_width', 240)
        min_height = config.get('ui', 'camera_display.single_view.min_height', 180)
        max_width = config.get('ui', 'camera_display.single_view.max_width', 600)
        max_height = config.get('ui', 'camera_display.single_view.max_height', 450)
        
        # Ajustement pour vue double
        if view_type == "dual_context":
            min_width = config.get('ui', 'camera_display.dual_view.min_width', 240)
            min_height = config.get('ui', 'camera_display.dual_view.min_height', 180)
            max_width = config.get('ui', 'camera_display.dual_view.max_width', 600)
            max_height = config.get('ui', 'camera_display.dual_view.max_height', 450)
        
        self.setMinimumSize(min_width, min_height)
        self.setMaximumSize(max_width, max_height)
        self.setScaledContents(True)
        self.setFrameStyle(QFrame.Shape.Box)
        
        # Configuration des couleurs depuis JSON
        rgb_border = config.get('ui', 'camera_display.colors.rgb_border', '#007acc')
        depth_border = config.get('ui', 'camera_display.colors.depth_border', '#ff6600')
        default_border = config.get('ui', 'camera_display.colors.default_border', '#ccc')
        background = config.get('ui', 'camera_display.colors.background', '#f0f0f0')
        
        border_color = depth_border if view_type == "depth" else rgb_border
            
        self.setStyleSheet(f"""
            QLabel {{
                border: 2px solid {default_border};
                border-radius: 5px;
                background-color: {background};
            }}
            QLabel:hover {{
                border-color: {border_color};
            }}
        """)
        
        # Texte par défaut
        view_name = config.get('ui', f'camera_display.view_names.{view_type}', 
                             "Profondeur" if view_type == "depth" else "Couleur")
        self.setText(f"{view_name}: {alias}\nEn attente...")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Font configurée
        font = QFont()
        font_family = config.get('ui', 'theme.font_family', 'Arial')
        font_size = config.get('ui', 'theme.font_size', 9)
        font.setFamily(font_family)
        font.setPointSize(font_size)
        self.setFont(font)
    
    def update_frame(self, frame: np.ndarray):
        """Met à jour l'affichage avec une nouvelle frame"""
        if frame is None:
            return
        
        try:
            display_frame = frame.copy()
            
            # Traitement spécifique selon le type
            if self.view_type == "depth":
                if len(display_frame.shape) == 2:
                    display_frame = cv2.normalize(display_frame, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                    display_frame = cv2.applyColorMap(display_frame, cv2.COLORMAP_JET)
            
            # Application du zoom
            if self.zoom_factor != 1.0:
                h, w = display_frame.shape[:2]
                new_w, new_h = int(w * self.zoom_factor), int(h * self.zoom_factor)
                display_frame = cv2.resize(display_frame, (new_w, new_h))
            
            # Overlay d'informations
            self._add_overlay(display_frame)
            
            # Conversion pour Qt
            self.current_frame = display_frame
            self._update_qt_display(display_frame)
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour {self.view_type} {self.alias}: {e}")
    
    def _add_overlay(self, frame: np.ndarray):
        """Ajoute les informations en overlay - Configuration depuis JSON"""
        view_name = "Depth" if self.view_type == "depth" else "RGB"
        
        overlay_text = [
            f"{view_name}: {self.alias}",
            f"Size: {frame.shape[1]}x{frame.shape[0]}",
            f"Zoom: {self.zoom_factor:.1f}x"
        ]
        
        # Configuration overlay depuis JSON
        font_size = self.config.get('ui', 'camera_display.overlay.font_size', 0.5)
        font_thickness = self.config.get('ui', 'camera_display.overlay.font_thickness', 1)
        text_spacing = self.config.get('ui', 'camera_display.overlay.text_spacing', 18)
        text_offset_x = self.config.get('ui', 'camera_display.overlay.text_offset_x', 8)
        text_offset_y = self.config.get('ui', 'camera_display.overlay.text_offset_y', 20)
        
        # Couleurs configurables
        if self.view_type == "depth":
            text_color = self.config.get('ui', 'camera_display.overlay.depth_color', [0, 165, 255])
        else:
            text_color = self.config.get('ui', 'camera_display.overlay.rgb_color', [0, 255, 0])
        
        y_offset = text_offset_y
        for text in overlay_text:
            cv2.putText(frame, text, (text_offset_x, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, font_size, text_color, font_thickness)
            y_offset += text_spacing
        
        # Crosshair au centre (optionnel pour profondeur)
        if self.view_type == "rgb":
            h, w = frame.shape[:2]
            crosshair_size = self.config.get('ui', 'camera_display.overlay.crosshair_size', 15)
            crosshair_thickness = self.config.get('ui', 'camera_display.overlay.crosshair_thickness', 1)
            
            cv2.line(frame, (w//2 - crosshair_size, h//2), (w//2 + crosshair_size, h//2), text_color, crosshair_thickness)
            cv2.line(frame, (w//2, h//2 - crosshair_size), (w//2, h//2 + crosshair_size), text_color, crosshair_thickness)
    
    def _update_qt_display(self, frame: np.ndarray):
        """Met à jour l'affichage Qt"""
        try:
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            
            q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
            pixmap = QPixmap.fromImage(q_image)
            
            self.setPixmap(pixmap)
            
        except Exception as e:
            logger.error(f"❌ Erreur conversion Qt {self.view_type}: {e}")
    
    def set_zoom(self, zoom: float):
        """Définit le facteur de zoom avec limites configurables"""
        zoom_min = self.config.get('ui', 'camera_display.single_view.zoom_min', 0.1)
        zoom_max = self.config.get('ui', 'camera_display.single_view.zoom_max', 5.0)
        self.zoom_factor = max(zoom_min, min(zoom_max, zoom))

class CameraDisplayWidget(QWidget):
    """Widget d'affichage caméra avec vues RGB et profondeur - Entièrement configurable"""
    
    clicked = pyqtSignal(str)
    
    def __init__(self, alias: str, config, parent=None):
        super().__init__(parent)
        self.alias = alias
        self.config = config
        self.show_depth = False
        self.zoom_factor = config.get('ui', 'camera_display.single_view.default_zoom', 1.0)
        
        # Vues individuelles avec configuration
        self.rgb_view = SingleCameraView("rgb", alias, config, self)
        self.depth_view = SingleCameraView("depth", alias, config, self)
        
        # Layout dynamique avec espacement configurable
        self.main_layout = QHBoxLayout(self)
        margin = config.get('ui', 'camera_display.dual_view.margin', 5)
        spacing = config.get('ui', 'camera_display.dual_view.spacing', 10)
        
        self.main_layout.setContentsMargins(margin, margin, margin, margin)
        self.main_layout.setSpacing(spacing)
        
        # Configuration initiale
        self._update_layout()
        
        # Connexions
        self.rgb_view.mousePressEvent = self._on_click
        self.depth_view.mousePressEvent = self._on_click
    
    def _update_layout(self):
        """Met à jour le layout selon les vues actives"""
        # Suppression de tous les widgets
        for i in reversed(range(self.main_layout.count())):
            widget = self.main_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        if self.show_depth:
            # Mode double: RGB + Profondeur
            self.main_layout.addWidget(self.rgb_view)
            self.main_layout.addWidget(self.depth_view)
            
            # Tailles égales
            self.main_layout.setStretchFactor(self.rgb_view, 1)
            self.main_layout.setStretchFactor(self.depth_view, 1)
            
            # Tailles configurables pour vue double
            max_width = self.config.get('ui', 'camera_display.dual_view.max_width', 400)
            max_height = self.config.get('ui', 'camera_display.dual_view.max_height', 300)
            
            self.rgb_view.setMaximumSize(max_width, max_height)
            self.depth_view.setMaximumSize(max_width, max_height)
            self.depth_view.show()
        else:
            # Mode simple: RGB seulement
            self.main_layout.addWidget(self.rgb_view)
            
            # Taille pleine configurable pour vue simple
            max_width = self.config.get('ui', 'camera_display.single_view.max_width', 800)
            max_height = self.config.get('ui', 'camera_display.single_view.max_height', 600)
            
            self.rgb_view.setMaximumSize(max_width, max_height)
            self.depth_view.hide()
    
    def update_frame(self, color_frame: np.ndarray, depth_frame: np.ndarray = None):
        """Met à jour l'affichage avec les nouvelles frames"""
        try:
            # Mise à jour RGB
            if color_frame is not None:
                self.rgb_view.update_frame(color_frame)
            
            # Mise à jour profondeur si activée
            if self.show_depth and depth_frame is not None:
                self.depth_view.update_frame(depth_frame)
            
        except Exception as e:
            logger.error(f"❌ Erreur mise à jour frames {self.alias}: {e}")
    
    def toggle_depth_view(self):
        """Bascule l'affichage de la vue profondeur"""
        self.show_depth = not self.show_depth
        self._update_layout()
        
        logger.debug(f"🔄 Vue profondeur {self.alias}: {'ON' if self.show_depth else 'OFF'}")
    
    def set_depth_view(self, enabled: bool):
        """Active/désactive la vue profondeur"""
        if self.show_depth != enabled:
            self.show_depth = enabled
            self._update_layout()
    
    def set_zoom(self, zoom: float):
        """Définit le facteur de zoom pour les deux vues"""
        self.zoom_factor = zoom
        self.rgb_view.set_zoom(zoom)
        self.depth_view.set_zoom(zoom)
    
    def _on_click(self, event):
        """Gestion du clic sur une des vues"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.alias)
    
    def sizeHint(self):
        """Taille suggérée selon le mode d'affichage - Configurable"""
        if self.show_depth:
            suggested_width = self.config.get('ui', 'camera_display.dual_view.suggested_width', 820)
            suggested_height = self.config.get('ui', 'camera_display.dual_view.suggested_height', 320)
            return QSize(suggested_width, suggested_height)
        else:
            single_width = self.config.get('ui', 'camera_display.single_view.max_width', 400)
            single_height = self.config.get('ui', 'camera_display.single_view.max_height', 300)
            return QSize(single_width, single_height)
    
    def get_current_frames(self):
        """Retourne les frames actuellement affichées"""
        rgb_frame = getattr(self.rgb_view, 'current_frame', None)
        depth_frame = getattr(self.depth_view, 'current_frame', None) if self.show_depth else None
        
        return rgb_frame, depth_frame