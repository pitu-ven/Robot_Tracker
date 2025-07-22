#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Communication avec les robots
"""

import socket
from abc import ABC, abstractmethod

class RobotAdapter(ABC):
    """Interface abstraite pour adaptateurs robot"""
    
    def __init__(self, config):
        self.config = config
    
    @abstractmethod
    def connect(self, ip, port):
        """Connexion au robot"""
        pass
    
    @abstractmethod
    def get_pose(self):
        """Récupère la pose actuelle"""
        pass
    
    @abstractmethod
    def move_to(self, pose):
        """Déplace vers une pose"""
        pass

class StaubliAdapter(RobotAdapter):
    """Adaptateur pour robots Stäubli"""
    
    def connect(self, ip, port):
        # TODO: Implémenter la connexion VAL3
        pass

class KukaAdapter(RobotAdapter):
    """Adaptateur pour robots KUKA"""
    
    def connect(self, ip, port):
        # TODO: Implémenter la connexion KRL
        pass
