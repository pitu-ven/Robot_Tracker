#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilitaires d'export de données
"""

import json
import csv
from pathlib import Path

class DataExporter:
    """Exporteur de données vers différents formats"""
    
    def __init__(self, config):
        self.config = config
    
    def export_to_csv(self, data, filepath):
        """Export vers CSV"""
        # TODO: Implémenter l'export CSV
        pass
    
    def export_to_json(self, data, filepath):
        """Export vers JSON"""
        # TODO: Implémenter l'export JSON
        pass
