#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Algorithmes de tracking
"""

import cv2
import numpy as np

class ArUcoTracker:
    """Tracker basé sur les marqueurs ArUco"""
    
    def __init__(self, config):
        self.config = config
        self.setup_detector()
    
    def setup_detector(self):
        """Configuration du détecteur ArUco"""
        # TODO: Implémenter la configuration depuis JSON
        pass
    
    def detect_markers(self, frame):
        """Détection des marqueurs dans une frame"""
        # TODO: Implémenter la détection
        pass

class ReflectiveTracker:
    """Tracker pour marqueurs réfléchissants"""
    
    def __init__(self, config):
        self.config = config
    
    def detect_markers(self, frame):
        """Détection des marqueurs réfléchissants"""
        # TODO: Implémenter la détection
        pass
