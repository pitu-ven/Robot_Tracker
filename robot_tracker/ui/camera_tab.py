#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/ui/trajectory_tab.py
Onglet de gestion des trajectoires - Version 1.0
Modification: Interface de base avec chargement de fichiers et visualisation
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QLabel, QComboBox, QListWidget, QGroupBox, QTextEdit,
                           QFileDialog, QProgressBar, QSplitter, QTableWidget,
                           QTableWidgetItem, QHeaderView, QApplication)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import logging
import os

logger = logging.getLogger(__name__)

class TrajectoryTab(QWidget):
    """Onglet pour le chargement et visualisation des trajectoires"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        # État des trajectoires
        self.loaded_files = []
        self.current_trajectory = None
        
        self.setup_ui()
        logger.info("📊 TrajectoryTab initialisé")
    
    def setup_ui(self):
        """Configuration de l'interface"""
        layout = QHBoxLayout(self)
        
        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # === Panneau de contrôle (gauche) ===
        control_panel = self.create_control_panel()
        splitter.addWidget(control_panel)
        
        # === Zone de visualisation (droite) ===
        visualization_panel = self.create_visualization_panel()
        splitter.addWidget(visualization_panel)
        
        # Proportions
        splitter.setSizes([350, 650])
    
    def create_control_panel(self):
        """Création du panneau de contrôle"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # === Chargement de fichiers ===
        file_group = QGroupBox("Chargement de Trajectoires")
        file_layout = QVBoxLayout(file_group)
        
        # Boutons de chargement
        load_buttons = QHBoxLayout()
        
        self.load_file_btn = QPushButton("📁 Charger Fichier")
        self.load_file_btn.clicked.connect(self.load_trajectory_file)
        load_buttons.addWidget(self.load_file_btn)
        
        self.load_folder_btn = QPushButton("📂 Charger Dossier")
        self.load_folder_btn.clicked.connect(self.load_trajectory_folder)
        load_buttons.addWidget(self.load_folder_btn)
        
        file_layout.addLayout(load_buttons)
        
        # Format supportés
        format_label = QLabel("Formats supportés: VAL3, KRL, RAPID, G-Code")
        format_label.setStyleSheet("color: #888; font-size: 10px;")
        file_layout.addWidget(format_label)
        
        layout.addWidget(file_group)
        
        # === Liste des fichiers chargés ===
        list_group = QGroupBox("Fichiers Chargés")
        list_layout = QVBoxLayout(list_group)
        
        self.file_list = QListWidget()
        self.file_list.itemSelectionChanged.connect(self.on_file_selected)
        list_layout.addWidget(self.file_list)
        
        # Boutons de gestion
        list_buttons = QHBoxLayout()
        
        self.preview_btn = QPushButton("👁️ Aperçu")
        self.preview_btn.clicked.connect(self.preview_trajectory)
        self.preview_btn.setEnabled(False)
        list_buttons.addWidget(self.preview_btn)
        
        self.remove_btn = QPushButton("🗑️ Supprimer")
        self.remove_btn.clicked.connect(self.remove_trajectory)
        self.remove_btn.setEnabled(False)
        list_buttons.addWidget(self.remove_btn)
        
        list_layout.addLayout(list_buttons)
        layout.addWidget(list_group)
        
        # === Informations sur la trajectoire ===
        info_group = QGroupBox("Informations Trajectoire")
        info_layout = QVBoxLayout(info_group)
        
        self.info_text = QTextEdit()
        self.info_text.setMaximumHeight(150)
        self.info_text.setFont(QFont("Courier", 9))
        self.info_text.setText("Aucune trajectoire sélectionnée")
        info_layout.addWidget(self.info_text)
        
        layout.addWidget(info_group)
        
        # === Export et conversion ===
        export_group = QGroupBox("Export et Conversion")
        export_layout = QVBoxLayout(export_group)
        
        # Format de destination
        export_layout.addWidget(QLabel("Format de destination:"))
        self.export_format = QComboBox()
        self.export_format.addItems(["JSON", "CSV", "VAL3", "KRL", "G-Code"])
        export_layout.addWidget(self.export_format)
        
        self.export_btn = QPushButton("💾 Exporter")
        self.export_btn.clicked.connect(self.export_trajectory)
        self.export_btn.setEnabled(False)
        export_layout.addWidget(self.export_btn)
        
        layout.addWidget(export_group)
        
        layout.addStretch()
        return panel
    
    def create_visualization_panel(self):
        """Création du panneau de visualisation"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Titre
        title_label = QLabel("Visualisation 3D de la Trajectoire")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Zone de visualisation 3D
        # TODO: Intégrer Open3D ou matplotlib 3D
        self.visualization_area = QLabel()
        self.visualization_area.setMinimumSize(600, 400)
        self.visualization_area.setStyleSheet("""
            border: 2px solid #555;
            background-color: #1a1a1a;
            border-radius: 5px;
        """)
        self.visualization_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.visualization_area.setText("Visualisation 3D\n(Chargez une trajectoire)")
        layout.addWidget(self.visualization_area)
        
        # === Tableau des points ===
        table_label = QLabel("Points de Trajectoire")
        table_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(table_label)
        
        self.points_table = QTableWidget()
        self.points_table.setColumnCount(6)
        self.points_table.setHorizontalHeaderLabels(['#', 'X', 'Y', 'Z', 'RX', 'RY', 'RZ'])
        
        # Configuration du tableau
        header = self.points_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.points_table.setMaximumHeight(200)
        
        layout.addWidget(self.points_table)
        
        return panel
    
    def load_trajectory_file(self):
        """Charge un fichier de trajectoire"""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, 
            "Charger une Trajectoire",
            "",
            "Tous les formats (*.val3 *.krl *.rapid *.gcode *.txt);;VAL3 (*.val3);;KRL (*.krl);;RAPID (*.rapid);;G-Code (*.gcode);;Texte (*.txt)"
        )
        
        if file_path:
            self.process_trajectory_file(file_path)
    
    def load_trajectory_folder(self):
        """Charge tous les fichiers d'un dossier"""
        folder_dialog = QFileDialog()
        folder_path = folder_dialog.getExistingDirectory(self, "Charger un Dossier")
        
        if folder_path:
            # Recherche des fichiers supportés
            supported_extensions = ['.val3', '.krl', '.rapid', '.gcode', '.txt']
            
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                if any(file_name.lower().endswith(ext) for ext in supported_extensions):
                    self.process_trajectory_file(file_path)
    
    def process_trajectory_file(self, file_path):
        """Traite un fichier de trajectoire"""
        try:
            # Détection du format
            file_format = self.detect_file_format(file_path)
            
            # Ajout à la liste
            file_info = {
                'path': file_path,
                'name': os.path.basename(file_path),
                'format': file_format,
                'points': 0,  # À calculer après parsing
                'status': 'Chargé'
            }
            
            self.loaded_files.append(file_info)
            
            # Mise à jour de la liste
            self.file_list.addItem(f"{file_info['name']} ({file_format})")
            
            logger.info(f"✅ Fichier chargé: {file_info['name']}")
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement fichier: {e}")
    
    def detect_file_format(self, file_path):
        """Détecte le format du fichier"""
        extension = os.path.splitext(file_path)[1].lower()
        
        format_map = {
            '.val3': 'VAL3',
            '.krl': 'KRL',
            '.rapid': 'RAPID',
            '.gcode': 'G-Code',
            '.txt': 'Texte'
        }
        
        return format_map.get(extension, 'Inconnu')
    
    def on_file_selected(self):
        """Gestion de la sélection d'un fichier"""
        current_row = self.file_list.currentRow()
        
        if 0 <= current_row < len(self.loaded_files):
            self.current_trajectory = self.loaded_files[current_row]
            
            # Activation des boutons
            self.preview_btn.setEnabled(True)
            self.remove_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            
            # Mise à jour des informations
            self.update_trajectory_info()
        else:
            self.preview_btn.setEnabled(False)
            self.remove_btn.setEnabled(False)
            self.export_btn.setEnabled(False)
    
    def update_trajectory_info(self):
        """Met à jour les informations de la trajectoire"""
        if not self.current_trajectory:
            return
        
        info_text = f"""
Fichier: {self.current_trajectory['name']}
Format: {self.current_trajectory['format']}
Chemin: {self.current_trajectory['path']}
Points: {self.current_trajectory['points']} (estimation)
Status: {self.current_trajectory['status']}

Contenu (aperçu):
[Analyse en cours...]
        """.strip()
        
        self.info_text.setText(info_text)
    
    def preview_trajectory(self):
        """Aperçu de la trajectoire sélectionnée"""
        if not self.current_trajectory:
            return
        
        try:
            # Simulation du parsing et affichage
            self.visualization_area.setText(f"Visualisation de:\n{self.current_trajectory['name']}\n\n[Implémentation à venir]")
            
            # Simulation de points dans le tableau
            self.populate_points_table()
            
            logger.info(f"👁️ Aperçu de: {self.current_trajectory['name']}")
            
        except Exception as e:
            logger.error(f"❌ Erreur aperçu: {e}")
    
    def populate_points_table(self):
        """Remplit le tableau avec des points simulés"""
        # Simulation de quelques points de trajectoire
        sample_points = [
            [1, 100.0, 200.0, 300.0, 0.0, 0.0, 0.0],
            [2, 105.0, 205.0, 305.0, 0.1, 0.0, 0.0],
            [3, 110.0, 210.0, 310.0, 0.2, 0.0, 0.0],
            [4, 115.0, 215.0, 315.0, 0.3, 0.0, 0.0],
            [5, 120.0, 220.0, 320.0, 0.4, 0.0, 0.0],
        ]
        
        self.points_table.setRowCount(len(sample_points))
        
        for row, point in enumerate(sample_points):
            for col, value in enumerate(point):
                item = QTableWidgetItem(str(value))
                self.points_table.setItem(row, col, item)
    
    def remove_trajectory(self):
        """Supprime la trajectoire sélectionnée"""
        current_row = self.file_list.currentRow()
        
        if 0 <= current_row < len(self.loaded_files):
            removed_file = self.loaded_files.pop(current_row)
            self.file_list.takeItem(current_row)
            
            # Réinitialisation si c'était le fichier courant
            if self.current_trajectory == removed_file:
                self.current_trajectory = None
                self.info_text.setText("Aucune trajectoire sélectionnée")
                self.visualization_area.setText("Visualisation 3D\n(Chargez une trajectoire)")
                self.points_table.setRowCount(0)
            
            logger.info(f"🗑️ Fichier supprimé: {removed_file['name']}")
    
    def export_trajectory(self):
        """Exporte la trajectoire dans le format sélectionné"""
        if not self.current_trajectory:
            return
        
        format_selected = self.export_format.currentText()
        
        file_dialog = QFileDialog()
        export_path, _ = file_dialog.getSaveFileName(
            self,
            f"Exporter en {format_selected}",
            f"{self.current_trajectory['name']}.{format_selected.lower()}",
            f"{format_selected} (*.{format_selected.lower()})"
        )
        
        if export_path:
            try:
                # TODO: Implémenter la vraie conversion
                logger.info(f"💾 Export vers: {export_path} (format: {format_selected})")
                
            except Exception as e:
                logger.error(f"❌ Erreur export: {e}")
    
    def open_file_dialog(self):
        """Interface publique pour ouvrir un fichier (appelée depuis MainWindow)"""
        self.load_trajectory_file()
    
    def get_status_info(self):
        """Retourne les informations de status pour la barre principale"""
        if self.loaded_files:
            return f"📊 {len(self.loaded_files)} trajectoire(s) chargée(s)"
        else:
            return "📊 Aucune trajectoire chargée"
    
    def cleanup(self):
        """Nettoyage lors de la fermeture"""
        self.loaded_files.clear()
        logger.info("🧹 TrajectoryTab nettoyé")


# ============================================================================
# Target Tab - Onglet de définition des cibles
# ============================================================================

class TargetTab(QWidget):
    """Onglet pour la définition et sélection des cibles"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        # État du tracking
        self.tracking_active = False
        self.selected_targets = []
        
        self.setup_ui()
        logger.info("🎯 TargetTab initialisé")
    
    def setup_ui(self):
        """Configuration de l'interface"""
        layout = QHBoxLayout(self)
        
        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # === Panneau de contrôle (gauche) ===
        control_panel = self.create_control_panel()
        splitter.addWidget(control_panel)
        
        # === Zone de sélection (droite) ===
        selection_panel = self.create_selection_panel()
        splitter.addWidget(selection_panel)
        
        splitter.setSizes([300, 700])
    
    def create_control_panel(self):
        """Création du panneau de contrôle"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # === Type de cibles ===
        target_type_group = QGroupBox("Type de Cibles")
        target_type_layout = QVBoxLayout(target_type_group)
        
        self.target_type = QComboBox()
        self.target_type.addItems([
            "Marqueurs ArUco",
            "Marqueurs Réfléchissants", 
            "LEDs Colorées",
            "Points Naturels"
        ])
        self.target_type.currentTextChanged.connect(self.on_target_type_changed)
        target_type_layout.addWidget(self.target_type)
        
        layout.addWidget(target_type_group)
        
        # === Configuration ArUco ===
        self.aruco_group = QGroupBox("Configuration ArUco")
        aruco_layout = QVBoxLayout(self.aruco_group)
        
        aruco_layout.addWidget(QLabel("Dictionnaire:"))
        self.aruco_dict = QComboBox()
        self.aruco_dict.addItems(["DICT_4X4_50", "DICT_5X5_100", "DICT_6X6_250"])
        self.aruco_dict.setCurrentText(
            self.config.get('tracking', 'aruco.dictionary', 'DICT_5X5_100')
        )
        aruco_layout.addWidget(self.aruco_dict)
        
        aruco_layout.addWidget(QLabel("Taille marqueur (m):"))
        self.marker_size = QComboBox()
        self.marker_size.addItems(["0.01", "0.02", "0.05", "0.10"])
        self.marker_size.setCurrentText("0.05")
        aruco_layout.addWidget(self.marker_size)
        
        layout.addWidget(self.aruco_group)
        
        # === Contrôles de tracking ===
        tracking_group = QGroupBox("Contrôles de Tracking")
        tracking_layout = QVBoxLayout(tracking_group)
        
        self.start_tracking_btn = QPushButton("▶️ Démarrer Tracking")
        self.start_tracking_btn.clicked.connect(self.start_tracking)
        tracking_layout.addWidget(self.start_tracking_btn)
        
        self.stop_tracking_btn = QPushButton("⏹️ Arrêter Tracking")
        self.stop_tracking_btn.clicked.connect(self.stop_tracking)
        self.stop_tracking_btn.setEnabled(False)
        tracking_layout.addWidget(self.stop_tracking_btn)
        
        layout.addWidget(tracking_group)
        
        # === Cibles détectées ===
        detected_group = QGroupBox("Cibles Détectées")
        detected_layout = QVBoxLayout(detected_group)
        
        self.targets_list = QListWidget()
        detected_layout.addWidget(self.targets_list)
        
        layout.addWidget(detected_group)
        
        layout.addStretch()
        return panel
    
    def create_selection_panel(self):
        """Création du panneau de sélection"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Titre
        title_label = QLabel("Sélection des Cibles")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Zone de sélection interactive
        self.selection_area = QLabel()
        self.selection_area.setMinimumSize(650, 500)
        self.selection_area.setStyleSheet("""
            border: 2px solid #555;
            background-color: #1a1a1a;
            border-radius: 5px;
        """)
        self.selection_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selection_area.setText("Zone de Sélection Interactive\n(Démarrez la caméra pour sélectionner des cibles)")
        
        layout.addWidget(self.selection_area)
        
        return panel
    
    def on_target_type_changed(self, target_type):
        """Gestion du changement de type de cible"""
        # Affichage conditionnel des groupes de configuration
        self.aruco_group.setVisible(target_type == "Marqueurs ArUco")
    
    def start_tracking(self):
        """Démarre le tracking des cibles"""
        try:
            self.tracking_active = True
            
            # Mise à jour de l'interface
            self.start_tracking_btn.setEnabled(False)
            self.stop_tracking_btn.setEnabled(True)
            
            # Simulation de détection de cibles
            self.simulate_target_detection()
            
            logger.info("🎯 Tracking des cibles démarré")
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage tracking: {e}")
    
    def stop_tracking(self):
        """Arrête le tracking des cibles"""
        try:
            self.tracking_active = False
            
            # Mise à jour de l'interface
            self.start_tracking_btn.setEnabled(True)
            self.stop_tracking_btn.setEnabled(False)
            
            # Nettoyage
            self.targets_list.clear()
            self.selected_targets.clear()
            
            logger.info("⏹️ Tracking des cibles arrêté")
            
        except Exception as e:
            logger.error(f"❌ Erreur arrêt tracking: {e}")
    
    def simulate_target_detection(self):
        """Simulation de détection de cibles"""
        # Simulation de cibles détectées
        simulated_targets = [
            "ArUco ID: 1 (x: 120, y: 80)",
            "ArUco ID: 2 (x: 340, y: 150)", 
            "ArUco ID: 5 (x: 560, y: 200)"
        ]
        
        self.targets_list.clear()
        for target in simulated_targets:
            self.targets_list.addItem(target)
        
        self.selection_area.setText("🎯 Cibles détectées\n(Cliquez pour sélectionner)")
    
    def get_status_info(self):
        """Retourne les informations de status"""
        if self.tracking_active:
            return f"🎯 Tracking actif - {len(self.selected_targets)} cible(s) sélectionnée(s)"
        else:
            return "🎯 Tracking inactif"
    
    def cleanup(self):
        """Nettoyage lors de la fermeture"""
        self.stop_tracking()
        logger.info("🧹 TargetTab nettoyé")


# ============================================================================
# Calibration Tab - Onglet de calibration caméra-robot
# ============================================================================

class CalibrationTab(QWidget):
    """Onglet pour la calibration caméra-robot"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        self.calibration_active = False
        self.calibration_poses = []
        
        self.setup_ui()
        logger.info("⚙️ CalibrationTab initialisé")
    
    def setup_ui(self):
        """Configuration de l'interface"""
        layout = QVBoxLayout(self)
        
        # Titre principal
        title_label = QLabel("Calibration Caméra-Robot")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # === Panneau de contrôle (gauche) ===
        control_panel = self.create_control_panel()
        splitter.addWidget(control_panel)
        
        # === Zone de visualisation (droite) ===
        visualization_panel = self.create_visualization_panel()
        splitter.addWidget(visualization_panel)
        
        splitter.setSizes([400, 600])
    
    def create_control_panel(self):
        """Création du panneau de contrôle"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # === Wizard de calibration ===
        wizard_group = QGroupBox("Assistant de Calibration")
        wizard_layout = QVBoxLayout(wizard_group)
        
        self.start_wizard_btn = QPushButton("🚀 Démarrer l'Assistant")
        self.start_wizard_btn.clicked.connect(self.start_calibration_wizard)
        wizard_layout.addWidget(self.start_wizard_btn)
        
        # Étapes du wizard
        steps_text = """
Étapes de calibration:
1. Configuration du pattern échiquier
2. Capture des poses caméra
3. Enregistrement des poses robot  
4. Calcul de la transformation
5. Validation des résultats
        """.strip()
        
        steps_label = QLabel(steps_text)
        steps_label.setStyleSheet("color: #888; font-size: 10px;")
        wizard_layout.addWidget(steps_label)
        
        layout.addWidget(wizard_group)
        
        # === Configuration du pattern ===
        pattern_group = QGroupBox("Configuration Pattern")
        pattern_layout = QVBoxLayout(pattern_group)
        
        pattern_layout.addWidget(QLabel("Type de pattern:"))
        self.pattern_type = QComboBox()
        self.pattern_type.addItems(["Échiquier", "Cercles", "ArUco Board"])
        pattern_layout.addWidget(self.pattern_type)
        
        pattern_layout.addWidget(QLabel("Dimensions (cases):"))
        pattern_dims = QHBoxLayout()
        self.pattern_width = QComboBox()
        self.pattern_width.addItems(["6", "7", "8", "9", "10"])
        self.pattern_width.setCurrentText("9")
        pattern_dims.addWidget(self.pattern_width)
        
        pattern_dims.addWidget(QLabel("×"))
        
        self.pattern_height = QComboBox()
        self.pattern_height.addItems(["4", "5", "6", "7", "8"])
        self.pattern_height.setCurrentText("6")
        pattern_dims.addWidget(self.pattern_height)
        
        pattern_layout.addLayout(pattern_dims)
        
        pattern_layout.addWidget(QLabel("Taille case (mm):"))
        self.square_size = QComboBox()
        self.square_size.addItems(["10", "15", "20", "25", "30"])
        self.square_size.setCurrentText("20")
        pattern_layout.addWidget(self.square_size)
        
        layout.addWidget(pattern_group)
        
        # === Poses capturées ===
        poses_group = QGroupBox("Poses Capturées")
        poses_layout = QVBoxLayout(poses_group)
        
        self.poses_list = QListWidget()
        poses_layout.addWidget(self.poses_list)
        
        # Boutons de capture
        capture_buttons = QHBoxLayout()
        
        self.capture_pose_btn = QPushButton("📸 Capturer Pose")
        self.capture_pose_btn.clicked.connect(self.capture_pose)
        self.capture_pose_btn.setEnabled(False)
        capture_buttons.addWidget(self.capture_pose_btn)
        
        self.clear_poses_btn = QPushButton("🗑️ Effacer")
        self.clear_poses_btn.clicked.connect(self.clear_poses)
        capture_buttons.addWidget(self.clear_poses_btn)
        
        poses_layout.addLayout(capture_buttons)
        layout.addWidget(poses_group)
        
        # === Calcul de calibration ===
        calc_group = QGroupBox("Calcul de Calibration")
        calc_layout = QVBoxLayout(calc_group)
        
        self.calculate_btn = QPushButton("🧮 Calculer Calibration")
        self.calculate_btn.clicked.connect(self.calculate_calibration)
        self.calculate_btn.setEnabled(False)
        calc_layout.addWidget(self.calculate_btn)
        
        self.save_calibration_btn = QPushButton("💾 Sauvegarder Résultats")
        self.save_calibration_btn.clicked.connect(self.save_calibration)
        self.save_calibration_btn.setEnabled(False)
        calc_layout.addWidget(self.save_calibration_btn)
        
        layout.addWidget(calc_group)
        
        layout.addStretch()
        return panel
    
    def create_visualization_panel(self):
        """Création du panneau de visualisation"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Zone de visualisation de la calibration
        self.calibration_view = QLabel()
        self.calibration_view.setMinimumSize(580, 400)
        self.calibration_view.setStyleSheet("""
            border: 2px solid #555;
            background-color: #1a1a1a;
            border-radius: 5px;
        """)
        self.calibration_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.calibration_view.setText("Visualisation de Calibration\n(Démarrez l'assistant)")
        
        layout.addWidget(self.calibration_view)
        
        # === Résultats de calibration ===
        results_group = QGroupBox("Résultats de Calibration")
        results_layout = QVBoxLayout(results_group)
        
        self.results_text = QTextEdit()
        self.results_text.setMaximumHeight(150)
        self.results_text.setFont(QFont("Courier", 9))
        self.results_text.setText("Aucun résultat de calibration disponible")
        results_layout.addWidget(self.results_text)
        
        layout.addWidget(results_group)
        
        return panel
    
    def start_calibration_wizard(self):
        """Démarre l'assistant de calibration"""
        try:
            self.calibration_active = True
            
            # Activation des contrôles
            self.capture_pose_btn.setEnabled(True)
            self.start_wizard_btn.setEnabled(False)
            
            # Mise à jour de la visualisation
            self.calibration_view.setText("🎯 Calibration en cours\nPositionnez le pattern et capturez des poses")
            
            logger.info("🚀 Assistant de calibration démarré")
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage calibration: {e}")
    
    def capture_pose(self):
        """Capture une nouvelle pose pour la calibration"""
        try:
            pose_count = len(self.calibration_poses) + 1
            
            # Simulation d'une pose capturée
            pose_info = {
                'id': pose_count,
                'robot_pose': [100 + pose_count * 10, 200, 300, 0, 0, 0],
                'pattern_detected': True,
                'reprojection_error': 0.5 + pose_count * 0.1
            }
            
            self.calibration_poses.append(pose_info)
            
            # Mise à jour de la liste
            self.poses_list.addItem(f"Pose {pose_count}: Erreur reprojection = {pose_info['reprojection_error']:.2f}px")
            
            # Activation du calcul si assez de poses
            if len(self.calibration_poses) >= 10:
                self.calculate_btn.setEnabled(True)
            
            logger.info(f"📸 Pose {pose_count} capturée")
            
        except Exception as e:
            logger.error(f"❌ Erreur capture pose: {e}")
    
    def clear_poses(self):
        """Efface toutes les poses capturées"""
        self.calibration_poses.clear()
        self.poses_list.clear()
        self.calculate_btn.setEnabled(False)
        self.save_calibration_btn.setEnabled(False)
        
        logger.info("🗑️ Poses effacées")
    
    def calculate_calibration(self):
        """Calcule la calibration caméra-robot"""
        try:
            # Simulation du calcul de calibration
            results = {
                'translation': [45.2, -12.8, 156.3],
                'rotation': [0.1, -0.05, 1.57],
                'reprojection_error': 0.85,
                'poses_used': len(self.calibration_poses)
            }
            
            # Affichage des résultats
            results_text = f"""
Calibration Hand-Eye calculée:

Translation (mm):
  X: {results['translation'][0]:.2f}
  Y: {results['translation'][1]:.2f}
  Z: {results['translation'][2]:.2f}

Rotation (rad):
  RX: {results['rotation'][0]:.3f}
  RY: {results['rotation'][1]:.3f}
  RZ: {results['rotation'][2]:.3f}

Erreur de reprojection: {results['reprojection_error']:.2f} px
Poses utilisées: {results['poses_used']}

Status: ✅ Calibration réussie
            """.strip()
            
            self.results_text.setText(results_text)
            self.save_calibration_btn.setEnabled(True)
            
            logger.info("🧮 Calibration calculée avec succès")
            
        except Exception as e:
            logger.error(f"❌ Erreur calcul calibration: {e}")
    
    def save_calibration(self):
        """Sauvegarde les résultats de calibration"""
        try:
            # TODO: Sauvegarder dans la configuration
            logger.info("💾 Résultats de calibration sauvegardés")
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde calibration: {e}")
    
    def get_status_info(self):
        """Retourne les informations de status"""
        if self.calibration_active:
            return f"⚙️ Calibration en cours - {len(self.calibration_poses)} pose(s) capturée(s)"
        else:
            return "⚙️ Calibration inactive"
    
    def cleanup(self):
        """Nettoyage lors de la fermeture"""
        self.calibration_active = False
        logger.info("🧹 CalibrationTab nettoyé")


# ============================================================================
# Measures Tab - Onglet de mesures et rapports  
# ============================================================================

class MeasuresTab(QWidget):
    """Onglet pour les mesures et génération de rapports"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        self.measurement_data = []
        self.report_active = False
        
        self.setup_ui()
        logger.info("📊 MeasuresTab initialisé")
    
    def setup_ui(self):
        """Configuration de l'interface"""
        layout = QVBoxLayout(self)
        
        # Titre principal
        title_label = QLabel("Mesures et Rapports")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # === Panneau de contrôle (gauche) ===
        control_panel = self.create_control_panel()
        splitter.addWidget(control_panel)
        
        # === Zone de visualisation (droite) ===
        metrics_panel = self.create_metrics_panel()
        splitter.addWidget(metrics_panel)
        
        splitter.setSizes([350, 650])
    
    def create_control_panel(self):
        """Création du panneau de contrôle"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # === Acquisition de mesures ===
        acquisition_group = QGroupBox("Acquisition de Mesures")
        acquisition_layout = QVBoxLayout(acquisition_group)
        
        self.start_measurement_btn = QPushButton("📊 Démarrer Mesures")
        self.start_measurement_btn.clicked.connect(self.start_measurements)
        acquisition_layout.addWidget(self.start_measurement_btn)
        
        self.stop_measurement_btn = QPushButton("⏹️ Arrêter Mesures")
        self.stop_measurement_btn.clicked.connect(self.stop_measurements)
        self.stop_measurement_btn.setEnabled(False)
        acquisition_layout.addWidget(self.stop_measurement_btn)
        
        layout.addWidget(acquisition_group)
        
        # === Métriques temps réel ===
        realtime_group = QGroupBox("Métriques Temps Réel")
        realtime_layout = QVBoxLayout(realtime_group)
        
        self.position_label = QLabel("Position 3D: --")
        realtime_layout.addWidget(self.position_label)
        
        self.deviation_label = QLabel("Écart trajectoire: --")
        realtime_layout.addWidget(self.deviation_label)
        
        self.precision_label = QLabel("Précision: --")
        realtime_layout.addWidget(self.precision_label)
        
        layout.addWidget(realtime_group)
        
        # === Génération de rapports ===
        report_group = QGroupBox("Génération de Rapports")
        report_layout = QVBoxLayout(report_group)
        
        self.generate_pdf_btn = QPushButton("📄 Générer Rapport PDF")
        self.generate_pdf_btn.clicked.connect(self.generate_pdf_report)
        report_layout.addWidget(self.generate_pdf_btn)
        
        self.export_csv_btn = QPushButton("📊 Exporter Données CSV")
        self.export_csv_btn.clicked.connect(self.export_csv_data)
        report_layout.addWidget(self.export_csv_btn)
        
        layout.addWidget(report_group)
        
        layout.addStretch()
        return panel
    
    def create_metrics_panel(self):
        """Création du panneau de métriques"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Zone de graphiques
        self.metrics_view = QLabel()
        self.metrics_view.setMinimumSize(620, 400)
        self.metrics_view.setStyleSheet("""
            border: 2px solid #555;
            background-color: #1a1a1a;
            border-radius: 5px;
        """)
        self.metrics_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.metrics_view.setText("Graphiques de Mesures\n(Démarrez l'acquisition)")
        
        layout.addWidget(self.metrics_view)
        
        # === Statistiques ===
        stats_group = QGroupBox("Statistiques")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_text = QTextEdit()
        self.stats_text.setMaximumHeight(150)
        self.stats_text.setFont(QFont("Courier", 9))
        self.stats_text.setText("Aucune donnée de mesure disponible")
        stats_layout.addWidget(self.stats_text)
        
        layout.addWidget(stats_group)
        
        return panel
    
    def start_measurements(self):
        """Démarre l'acquisition de mesures"""
        try:
            self.report_active = True
            
            # Mise à jour de l'interface
            self.start_measurement_btn.setEnabled(False)
            self.stop_measurement_btn.setEnabled(True)
            
            # Simulation de mesures
            self.simulate_measurements()
            
            logger.info("📊 Acquisition de mesures démarrée")
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage mesures: {e}")
    
    def stop_measurements(self):
        """Arrête l'acquisition de mesures"""
        try:
            self.report_active = False
            
            # Mise à jour de l'interface
            self.start_measurement_btn.setEnabled(True)
            self.stop_measurement_btn.setEnabled(False)
            
            logger.info("⏹️ Acquisition de mesures arrêtée")
            
        except Exception as e:
            logger.error(f"❌ Erreur arrêt mesures: {e}")
    
    def simulate_measurements(self):
        """Simulation de données de mesures"""
        # Simulation de métriques temps réel
        self.position_label.setText("Position 3D: X=123.45, Y=234.56, Z=345.67 mm")
        self.deviation_label.setText("Écart trajectoire: 0.85 mm")
        self.precision_label.setText("Précision: ±0.12 mm")
        
        # Simulation de statistiques
        stats_text = """
Statistiques de Mesure:

Précision de pose (AP): 0.8 mm
Répétabilité (RP): 0.15 mm
Écart-type: 0.22 mm
Erreur maximum: 1.2 mm
Points mesurés: 156
Durée acquisition: 2.5 min

Conformité ISO 9283:
✅ Précision < 0.5 mm: NON (0.8 mm)
✅ Répétabilité < 0.1 mm: NON (0.15 mm)
        """.strip()
        
        self.stats_text.setText(stats_text)
        self.metrics_view.setText("📊 Mesures en cours\n(Graphiques temps réel)")
    
    def generate_pdf_report(self):
        """Génère un rapport PDF"""
        try:
            file_dialog = QFileDialog()
            pdf_path, _ = file_dialog.getSaveFileName(
                self,
                "Sauvegarder Rapport PDF",
                "rapport_trajectoire.pdf",
                "PDF (*.pdf)"
            )
            
            if pdf_path:
                # TODO: Implémenter la vraie génération PDF avec ReportLab
                logger.info(f"📄 Rapport PDF généré: {pdf_path}")
                
        except Exception as e:
            logger.error(f"❌ Erreur génération PDF: {e}")
    
    def export_csv_data(self):
        """Exporte les données en CSV"""
        try:
            file_dialog = QFileDialog()
            csv_path, _ = file_dialog.getSaveFileName(
                self,
                "Exporter Données CSV",
                "donnees_mesures.csv",
                "CSV (*.csv)"
            )
            
            if csv_path:
                # TODO: Implémenter l'export CSV réel
                logger.info(f"📊 Données exportées: {csv_path}")
                
        except Exception as e:
            logger.error(f"❌ Erreur export CSV: {e}")
    
    def save_report_dialog(self):
        """Interface publique pour sauvegarder (appelée depuis MainWindow)"""
        self.generate_pdf_report()
    
    def get_status_info(self):
        """Retourne les informations de status"""
        if self.report_active:
            return f"📊 Mesures actives - {len(self.measurement_data)} point(s) acquis"
        else:
            return "📊 Mesures inactives"
    
    def cleanup(self):
        """Nettoyage lors de la fermeture"""
        self.stop_measurements()
        logger.info("🧹 MeasuresTab nettoyé")#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/ui/camera_tab.py
Onglet de gestion des caméras - Version 1.0
Modification: Interface de base fonctionnelle avec preview et contrôles
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QLabel, QComboBox, QSpinBox, QCheckBox, QGroupBox,
                           QGridLayout, QTextEdit, QProgressBar, QFrame, QSplitter)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QPixmap, QFont
import numpy as np
import logging

logger = logging.getLogger(__name__)

class CameraTab(QWidget):
    """Onglet pour la configuration et contrôle des caméras"""
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        # État des caméras
        self.realsense_connected = False
        self.usb3_connected = False
        self.camera_thread = None
        
        # Timer pour les mises à jour
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        
        self.setup_ui()
        self.setup_connections()
        self.detect_cameras()
        
        logger.info("📷 CameraTab initialisé")
    
    def setup_ui(self):
        """Configuration de l'interface"""
        layout = QHBoxLayout(self)
        
        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # === Panneau de contrôle (gauche) ===
        control_panel = self.create_control_panel()
        splitter.addWidget(control_panel)
        
        # === Zone de prévisualisation (droite) ===
        preview_panel = self.create_preview_panel()
        splitter.addWidget(preview_panel)
        
        # Proportions : 30% contrôles, 70% preview
        splitter.setSizes([300, 700])
    
    def create_control_panel(self):
        """Création du panneau de contrôle"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # === Détection des caméras ===
        detection_group = QGroupBox("Détection des Caméras")
        detection_layout = QVBoxLayout(detection_group)
        
        self.detect_btn = QPushButton("🔍 Détecter les Caméras")
        self.detect_btn.clicked.connect(self.detect_cameras)
        detection_layout.addWidget(self.detect_btn)
        
        # Status des caméras
        self.realsense_status = QLabel("RealSense D435: ❌ Non détectée")
        self.usb3_status = QLabel("Caméra USB3: ❌ Non détectée")
        detection_layout.addWidget(self.realsense_status)
        detection_layout.addWidget(self.usb3_status)
        
        layout.addWidget(detection_group)
        
        # === Configuration RealSense ===
        realsense_group = QGroupBox("Intel RealSense D435")
        realsense_layout = QGridLayout(realsense_group)
        
        # Activation
        self.realsense_enabled = QCheckBox("Activée")
        self.realsense_enabled.setChecked(
            self.config.get('camera', 'realsense.enabled', True)
        )
        realsense_layout.addWidget(self.realsense_enabled, 0, 0, 1, 2)
        
        # Résolution couleur
        realsense_layout.addWidget(QLabel("Résolution:"), 1, 0)
        self.realsense_resolution = QComboBox()
        self.realsense_resolution.addItems(["640x480", "1280x720", "1920x1080"])
        self.realsense_resolution.setCurrentText("1280x720")
        realsense_layout.addWidget(self.realsense_resolution, 1, 1)
        
        # FPS
        realsense_layout.addWidget(QLabel("FPS:"), 2, 0)
        self.realsense_fps = QSpinBox()
        self.realsense_fps.setRange(15, 90)
        self.realsense_fps.setValue(
            self.config.get('camera', 'realsense.color_stream.fps', 30)
        )
        realsense_layout.addWidget(self.realsense_fps, 2, 1)
        
        # Auto-exposition
        self.realsense_auto_exposure = QCheckBox("Auto-exposition")
        self.realsense_auto_exposure.setChecked(
            self.config.get('camera', 'realsense.auto_exposure', True)
        )
        realsense_layout.addWidget(self.realsense_auto_exposure, 3, 0, 1, 2)
        
        layout.addWidget(realsense_group)
        
        # === Configuration USB3 ===
        usb3_group = QGroupBox("Caméra USB3 CMOS")
        usb3_layout = QGridLayout(usb3_group)
        
        # Activation
        self.usb3_enabled = QCheckBox("Activée")
        self.usb3_enabled.setChecked(
            self.config.get('camera', 'usb3_camera.enabled', True)
        )
        usb3_layout.addWidget(self.usb3_enabled, 0, 0, 1, 2)
        
        # ID de device
        usb3_layout.addWidget(QLabel("Device ID:"), 1, 0)
        self.usb3_device_id = QSpinBox()
        self.usb3_device_id.setRange(0, 10)
        self.usb3_device_id.setValue(
            self.config.get('camera', 'usb3_camera.device_id', 0)
        )
        usb3_layout.addWidget(self.usb3_device_id, 1, 1)
        
        # Résolution
        usb3_layout.addWidget(QLabel("Résolution:"), 2, 0)
        self.usb3_resolution = QComboBox()
        self.usb3_resolution.addItems(["1024x768", "1280x1024", "2048x1536", "2448x2048"])
        self.usb3_resolution.setCurrentText("2448x2048")
        usb3_layout.addWidget(self.usb3_resolution, 2, 1)
        
        # FPS
        usb3_layout.addWidget(QLabel("FPS:"), 3, 0)
        self.usb3_fps = QSpinBox()
        self.usb3_fps.setRange(5, 70)
        self.usb3_fps.setValue(
            self.config.get('camera', 'usb3_camera.fps', 20)
        )
        usb3_layout.addWidget(self.usb3_fps, 3, 1)
        
        layout.addWidget(usb3_group)
        
        # === Contrôles d'acquisition ===
        acquisition_group = QGroupBox("Acquisition")
        acquisition_layout = QVBoxLayout(acquisition_group)
        
        self.start_preview_btn = QPushButton("▶️ Démarrer Prévisualisation")
        self.start_preview_btn.clicked.connect(self.start_preview)
        acquisition_layout.addWidget(self.start_preview_btn)
        
        self.stop_preview_btn = QPushButton("⏹️ Arrêter Prévisualisation")
        self.stop_preview_btn.clicked.connect(self.stop_preview)
        self.stop_preview_btn.setEnabled(False)
        acquisition_layout.addWidget(self.stop_preview_btn)
        
        # Sauvegarde d'images
        self.save_images = QCheckBox("Sauvegarder les images")
        self.save_images.setChecked(
            self.config.get('camera', 'general.save_images', False)
        )
        acquisition_layout.addWidget(self.save_images)
        
        layout.addWidget(acquisition_group)
        
        # === Tests et performances ===
        test_group = QGroupBox("Tests et Performances")
        test_layout = QVBoxLayout(test_group)
        
        self.test_latency_btn = QPushButton("📊 Test de Latence")
        self.test_latency_btn.clicked.connect(self.test_latency)
        test_layout.addWidget(self.test_latency_btn)
        
        self.performance_label = QLabel("Latence: -- ms | FPS: --")
        test_layout.addWidget(self.performance_label)
        
        # Barre de progression pour les tests
        self.test_progress = QProgressBar()
        self.test_progress.setVisible(False)
        test_layout.addWidget(self.test_progress)
        
        layout.addWidget(test_group)
        
        # === Log des événements ===
        log_group = QGroupBox("Journal des Événements")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setFont(QFont("Courier", 8))
        self.log_text.append("📷 Interface caméra initialisée")
        log_layout.addWidget(self.log_text)
        
        # Bouton pour effacer les logs
        clear_log_btn = QPushButton("🗑️ Effacer les Logs")
        clear_log_btn.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_log_btn)
        
        layout.addWidget(log_group)
        
        # Spacer pour pousser les éléments vers le haut
        layout.addStretch()
        
        return panel
    
    def create_preview_panel(self):
        """Création du panneau de prévisualisation"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Titre
        title_label = QLabel("Prévisualisation des Caméras")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Splitter pour les deux caméras
        preview_splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(preview_splitter)
        
        # === Prévisualisation RealSense ===
        realsense_frame = QFrame()
        realsense_frame.setFrameStyle(QFrame.Shape.Box)
        realsense_layout = QVBoxLayout(realsense_frame)
        
        realsense_title = QLabel("Intel RealSense D435 - Couleur + Profondeur")
        realsense_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        realsense_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        realsense_layout.addWidget(realsense_title)
        
        # Container pour les images côte à côte
        realsense_images = QHBoxLayout()
        
        # Image couleur
        color_container = QVBoxLayout()
        color_container.addWidget(QLabel("Image Couleur"))
        self.realsense_color_label = QLabel()
        self.realsense_color_label.setMinimumSize(400, 300)
        self.realsense_color_label.setStyleSheet("border: 1px solid gray; background-color: #2a2a2a;")
        self.realsense_color_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.realsense_color_label.setText("Caméra non connectée")
        color_container.addWidget(self.realsense_color_label)
        realsense_images.addLayout(color_container)
        
        # Image de profondeur
        depth_container = QVBoxLayout()
        depth_container.addWidget(QLabel("Image de Profondeur"))
        self.realsense_depth_label = QLabel()
        self.realsense_depth_label.setMinimumSize(400, 300)
        self.realsense_depth_label.setStyleSheet("border: 1px solid gray; background-color: #2a2a2a;")
        self.realsense_depth_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.realsense_depth_label.setText("Profondeur non disponible")
        depth_container.addWidget(self.realsense_depth_label)
        realsense_images.addLayout(depth_container)
        
        realsense_layout.addLayout(realsense_images)
        preview_splitter.addWidget(realsense_frame)
        
        # === Prévisualisation USB3 ===
        usb3_frame = QFrame()
        usb3_frame.setFrameStyle(QFrame.Shape.Box)
        usb3_layout = QVBoxLayout(usb3_frame)
        
        usb3_title = QLabel("Caméra USB3 CMOS - Haute Résolution")
        usb3_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        usb3_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        usb3_layout.addWidget(usb3_title)
        
        self.usb3_image_label = QLabel()
        self.usb3_image_label.setMinimumSize(800, 300)
        self.usb3_image_label.setStyleSheet("border: 1px solid gray; background-color: #2a2a2a;")
        self.usb3_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.usb3_image_label.setText("Caméra USB3 non connectée")
        usb3_layout.addWidget(self.usb3_image_label)
        
        preview_splitter.addWidget(usb3_frame)
        
        # Proportions 50/50 entre les deux caméras
        preview_splitter.setSizes([400, 400])
        
        # === Informations de status en bas ===
        status_layout = QHBoxLayout()
        
        self.fps_display = QLabel("FPS: --")
        self.fps_display.setStyleSheet("color: #00ff00; font-weight: bold;")
        status_layout.addWidget(self.fps_display)
        
        status_layout.addStretch()
        
        self.resolution_display = QLabel("Résolution: --")
        status_layout.addWidget(self.resolution_display)
        
        status_layout.addStretch()
        
        self.timestamp_display = QLabel("Dernière image: --")
        status_layout.addWidget(self.timestamp_display)
        
        layout.addLayout(status_layout)
        
        return panel
    
    def setup_connections(self):
        """Configuration des connexions entre les composants"""
        # Connexions pour sauvegarder automatiquement les paramètres
        self.realsense_enabled.toggled.connect(self.save_camera_config)
        self.realsense_fps.valueChanged.connect(self.save_camera_config)
        self.usb3_enabled.toggled.connect(self.save_camera_config)
        self.usb3_fps.valueChanged.connect(self.save_camera_config)
        
        # Timer pour les mises à jour de status
        self.update_timer.start(1000)  # Mise à jour chaque seconde
    
    def detect_cameras(self):
        """Détection des caméras disponibles"""
        self.log_text.append("🔍 Détection des caméras en cours...")
        
        # Simulation de la détection RealSense
        try:
            # TODO: Implémenter la vraie détection avec pyrealsense2
            self.realsense_connected = True  # Simulation
            self.realsense_status.setText("RealSense D435: ✅ Détectée")
            self.log_text.append("✅ RealSense D435 détectée")
        except Exception as e:
            self.realsense_connected = False
            self.realsense_status.setText("RealSense D435: ❌ Non détectée")
            self.log_text.append(f"❌ RealSense non détectée: {e}")
        
        # Simulation de la détection USB3
        try:
            # TODO: Implémenter la vraie détection avec OpenCV
            self.usb3_connected = True  # Simulation
            self.usb3_status.setText("Caméra USB3: ✅ Détectée")
            self.log_text.append("✅ Caméra USB3 détectée")
        except Exception as e:
            self.usb3_connected = False
            self.usb3_status.setText("Caméra USB3: ❌ Non détectée")
            self.log_text.append(f"❌ Caméra USB3 non détectée: {e}")
    
    def start_preview(self):
        """Démarre la prévisualisation des caméras"""
        if not (self.realsense_connected or self.usb3_connected):
            self.log_text.append("⚠️ Aucune caméra détectée pour la prévisualisation")
            return
        
        try:
            # Configuration du thread d'acquisition
            self.camera_thread = CameraThread(self.config)
            self.camera_thread.frame_ready.connect(self.update_preview)
            self.camera_thread.status_update.connect(self.update_camera_status)
            
            # Démarrage
            self.camera_thread.start()
            
            # Mise à jour de l'interface
            self.start_preview_btn.setEnabled(False)
            self.stop_preview_btn.setEnabled(True)
            
            self.log_text.append("▶️ Prévisualisation démarrée")
            
        except Exception as e:
            self.log_text.append(f"❌ Erreur démarrage prévisualisation: {e}")
    
    def stop_preview(self):
        """Arrête la prévisualisation des caméras"""
        try:
            if self.camera_thread and self.camera_thread.isRunning():
                self.camera_thread.stop()
                self.camera_thread.wait()
            
            # Mise à jour de l'interface
            self.start_preview_btn.setEnabled(True)
            self.stop_preview_btn.setEnabled(False)
            
            # Nettoyage des images
            self.realsense_color_label.setText("Prévisualisation arrêtée")
            self.realsense_depth_label.setText("Prévisualisation arrêtée")
            self.usb3_image_label.setText("Prévisualisation arrêtée")
            
            self.log_text.append("⏹️ Prévisualisation arrêtée")
            
        except Exception as e:
            self.log_text.append(f"❌ Erreur arrêt prévisualisation: {e}")
    
    def update_preview(self, frame_data):
        """Met à jour la prévisualisation avec les nouvelles images"""
        try:
            # frame_data contient les images des caméras
            # TODO: Convertir les numpy arrays en QPixmap et afficher
            
            # Pour l'instant, simulation
            self.realsense_color_label.setText("📹 Image en cours...")
            self.realsense_depth_label.setText("📊 Profondeur en cours...")
            self.usb3_image_label.setText("📷 USB3 en cours...")
            
        except Exception as e:
            self.log_text.append(f"❌ Erreur mise à jour preview: {e}")
    
    def update_camera_status(self, status_info):
        """Met à jour les informations de status des caméras"""
        try:
            fps = status_info.get('fps', '--')
            resolution = status_info.get('resolution', '--')
            timestamp = status_info.get('timestamp', '--')
            
            self.fps_display.setText(f"FPS: {fps}")
            self.resolution_display.setText(f"Résolution: {resolution}")
            self.timestamp_display.setText(f"Dernière image: {timestamp}")
            
        except Exception as e:
            logger.warning(f"Erreur mise à jour status caméra: {e}")
    
    def test_latency(self):
        """Test de latence des caméras"""
        self.log_text.append("📊 Test de latence en cours...")
        self.test_progress.setVisible(True)
        self.test_progress.setValue(0)
        
        # Simulation du test
        for i in range(101):
            self.test_progress.setValue(i)
            QApplication.processEvents()
        
        # Résultats simulés
        latency = 15.2  # ms
        fps_measured = 28.7
        
        self.performance_label.setText(f"Latence: {latency} ms | FPS: {fps_measured}")
        self.log_text.append(f"✅ Test terminé - Latence: {latency}ms, FPS: {fps_measured}")
        
        self.test_progress.setVisible(False)
    
    def save_camera_config(self):
        """Sauvegarde la configuration des caméras"""
        try:
            # Mise à jour de la configuration
            self.config.set('camera', 'realsense.enabled', self.realsense_enabled.isChecked())
            self.config.set('camera', 'realsense.color_stream.fps', self.realsense_fps.value())
            self.config.set('camera', 'usb3_camera.enabled', self.usb3_enabled.isChecked())
            self.config.set('camera', 'usb3_camera.fps', self.usb3_fps.value())
            self.config.set('camera', 'usb3_camera.device_id', self.usb3_device_id.value())
            self.config.set('camera', 'general.save_images', self.save_images.isChecked())
            
            # Sauvegarde
            self.config.save_config('camera')
            
        except Exception as e:
            logger.warning(f"Erreur sauvegarde config caméra: {e}")
    
    def update_status(self):
        """Mise à jour périodique du status"""
        try:
            # Mise à jour des informations de performance si caméras actives
            if hasattr(self, 'camera_thread') and self.camera_thread and self.camera_thread.isRunning():
                # Simulation de données en temps réel
                import time
                current_time = time.strftime("%H:%M:%S")
                self.timestamp_display.setText(f"Dernière image: {current_time}")
        
        except Exception:
            pass
    
    def get_status_info(self):
        """Retourne les informations de status pour la barre principale"""
        if hasattr(self, 'camera_thread') and self.camera_thread and self.camera_thread.isRunning():
            return "📷 Caméras actives - Acquisition en cours"
        elif self.realsense_connected or self.usb3_connected:
            return f"📷 {int(self.realsense_connected) + int(self.usb3_connected)} caméra(s) détectée(s)"
        else:
            return "📷 Aucune caméra détectée"
    
    def cleanup(self):
        """Nettoyage lors de la fermeture"""
        try:
            self.stop_preview()
            self.update_timer.stop()
            self.save_camera_config()
            logger.info("🧹 CameraTab nettoyé")
        except Exception as e:
            logger.warning(f"Erreur nettoyage CameraTab: {e}")


class CameraThread(QThread):
    """Thread dédié à l'acquisition caméra"""
    
    frame_ready = pyqtSignal(dict)
    status_update = pyqtSignal(dict)
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.running = False
        self.frame_count = 0
        
    def run(self):
        """Boucle d'acquisition principale"""
        self.running = True
        logger.info("🚀 Thread caméra démarré")
        
        import time
        
        while self.running:
            try:
                # Simulation d'acquisition d'images
                # TODO: Implémenter la vraie acquisition avec les drivers
                
                time.sleep(1/30)  # Simulation 30 FPS
                
                # Données simulées
                frame_data = {
                    'realsense_color': np.zeros((480, 640, 3), dtype=np.uint8),
                    'realsense_depth': np.zeros((480, 640), dtype=np.uint16),
                    'usb3_image': np.zeros((1024, 1280, 3), dtype=np.uint8)
                }
                
                status_info = {
                    'fps': 30,
                    'resolution': '640x480',
                    'timestamp': time.strftime("%H:%M:%S")
                }
                
                self.frame_ready.emit(frame_data)
                self.status_update.emit(status_info)
                
                self.frame_count += 1
                
            except Exception as e:
                logger.error(f"Erreur dans thread caméra: {e}")
                break
        
        logger.info("⏹️ Thread caméra arrêté")
    
    def stop(self):
        """Arrêt du thread"""
        self.running = False