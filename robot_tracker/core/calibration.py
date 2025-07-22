#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modules de calibration caméra-robot
"""

import cv2
import numpy as np

class HandEyeCalibration:
    """Calibration main-œil pour robots"""
    
    def __init__(self, config):
        self.config = config
        self.robot_poses = []
        self.camera_poses = []
    
    def add_pose_pair(self, robot_pose, marker_pose):
        """Ajoute une paire de poses robot/caméra"""
        # TODO: Implémenter l'ajout de poses
        pass
    
    def compute_calibration(self):
        """Calcul de la calibration hand-eye"""
        # TODO: Implémenter le calcul AX=XB
        pass
