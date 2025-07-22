#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Driver pour caméra Intel RealSense
"""

import pyrealsense2 as rs
import numpy as np

class RealSenseCamera:
    """Driver pour caméra Intel RealSense D435"""
    
    def __init__(self, config):
        self.config = config
        self.pipeline = rs.pipeline()
        self.setup_streams()
    
    def setup_streams(self):
        """Configuration des streams depuis la config JSON"""
        # TODO: Implémenter la configuration depuis JSON
        pass
    
    def get_frames(self):
        """Récupère les frames couleur et profondeur"""
        # TODO: Implémenter l'acquisition
        pass
