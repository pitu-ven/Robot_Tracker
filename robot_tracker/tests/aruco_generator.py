#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_tracker/ui/aruco_generator.py
Générateur de codes ArUco imprimables - Version 1.0
Modification: Création de l'utilitaire de génération de marqueurs ArUco
"""

import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QSpinBox, QCheckBox,
    QGroupBox, QFrame, QTextEdit, QProgressBar, QFileDialog,
    QScrollArea, QWidget, QMessageBox, QSlider, QSpacerItem,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QPixmap, QImage, QFont, QPainter, QPen
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
import os
import time
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ArUcoGeneratorThread(QThread):
    """Thread pour la génération des marqueurs ArUco"""
    
    progress_updated = pyqtSignal(int)
    marker_generated = pyqtSignal(int, np.ndarray)
    generation_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, dictionary, marker_ids, marker_size):
        super().__init__()
        self.dictionary = dictionary
        self.marker_ids = marker_ids
        self.marker_size = marker_size
        self.should_stop = False
    
    def run(self):
        """Génère les marqueurs ArUco"""
        try:
            total_markers = len(self.marker_ids)
            
            for i, marker_id in enumerate(self.marker_ids):
                if self.should_stop:
                    break
                
                # Génération du marqueur
                marker_image = np.zeros((self.marker_size, self.marker_size), dtype=np.uint8)
                marker_image = cv2.aruco.generateImageMarker(self.dictionary, marker_id, self.marker_size, marker_image, 1)
                
                self.marker_generated.emit(marker_id, marker_image)
                
                # Mise à jour du progrès
                progress = int((i + 1) / total_markers * 100)
                self.progress_updated.emit(progress)
                
                self.msleep(10)  # Petite pause pour éviter de surcharger l'interface
            
            self.generation_finished.emit()
            
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def stop(self):
        """Arrête la génération"""
        self.should_stop = True

class MarkerWidget(QLabel):
    """Widget d'affichage d'un marqueur ArUco"""
    
    def __init__(self, marker_id, marker_image, config):
        super().__init__()
        self.marker_id = marker_id
        self.marker_image = marker_image
        self.config = config
        
        # Configuration du widget
        display_size = self.config.get('ui', 'aruco_generator.marker_display_size', 120)
        self.setFixedSize(display_size, display_size + 30)  # +30 pour le texte
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("border: 1px solid #ccc; margin: 2px;")
        
        self.update_display()
    
    def update_display(self):
        """Met à jour l'affichage du marqueur"""
        try:
            # Conversion de l'image OpenCV vers QPixmap
            height, width = self.marker_image.shape
            bytes_per_line = width
            q_image = QImage(self.marker_image.data, width, height, bytes_per_line, QImage.Format.Format_Grayscale8)
            
            # Redimensionnement pour l'affichage
            display_size = self.config.get('ui', 'aruco_generator.marker_display_size', 120)
            scaled_image = q_image.scaled(display_size - 20, display_size - 20, Qt.AspectRatioMode.KeepAspectRatio)
            
            pixmap = QPixmap.fromImage(scaled_image)
            
            # Ajout du texte avec l'ID
            painter = QPainter(pixmap)
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            
            # Dessin du texte en bas
            text_rect = pixmap.rect()
            text_rect.setTop(text_rect.bottom() - 20)
            painter.fillRect(text_rect, Qt.GlobalColor.white)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"ID: {self.marker_id}")
            painter.end()
            
            self.setPixmap(pixmap)
            
        except Exception as e:
            logger.error(f"Erreur affichage marqueur {self.marker_id}: {e}")
            self.setText(f"Erreur\nID: {self.marker_id}")

class ArUcoGeneratorDialog(QDialog):
    """Dialog de génération de codes ArUco"""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.generated_markers = {}  # {marker_id: marker_image}
        self.generation_thread = None
        
        self.init_ui()
        self.connect_signals()
        
        logger.info("🎯 Générateur ArUco initialisé")
    
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        self.setWindowTitle(self.config.get('ui', 'aruco_generator.window_title', "Générateur de Codes ArUco"))
        self.setModal(True)
        
        # Taille de la fenêtre depuis config
        window_width = self.config.get('ui', 'aruco_generator.window_width', 900)
        window_height = self.config.get('ui', 'aruco_generator.window_height', 700)
        self.resize(window_width, window_height)
        
        layout = QVBoxLayout(self)
        
        # === Configuration ===
        config_group = self.create_config_group()
        layout.addWidget(config_group)
        
        # === Contrôles ===
        controls_group = self.create_controls_group()
        layout.addWidget(controls_group)
        
        # === Zone d'affichage ===
        display_group = self.create_display_group()
        layout.addWidget(display_group)
        
        # === Boutons d'action ===
        buttons_layout = self.create_action_buttons()
        layout.addLayout(buttons_layout)
    
    def create_config_group(self):
        """Crée le groupe de configuration"""
        group = QGroupBox(self.config.get('ui', 'aruco_generator.labels.config_group', "📋 Configuration"))
        layout = QGridLayout(group)
        
        # Dictionnaire ArUco
        dict_label = QLabel(self.config.get('ui', 'aruco_generator.labels.dictionary', "Dictionnaire ArUco:"))
        self.dictionary_combo = QComboBox()
        
        # Dictionnaires disponibles depuis config
        dictionaries = self.config.get('ui', 'aruco_generator.dictionaries', [
            "DICT_4X4_50", "DICT_5X5_100", "DICT_6X6_250", "DICT_7X7_1000",
            "DICT_ARUCO_ORIGINAL", "DICT_APRILTAG_16h5", "DICT_APRILTAG_25h9"
        ])
        
        for dict_name in dictionaries:
            self.dictionary_combo.addItem(dict_name, getattr(cv2.aruco, dict_name))
        
        # Sélection par défaut
        default_dict = self.config.get('ui', 'aruco_generator.default_dictionary', "DICT_5X5_100")
        default_index = next((i for i, d in enumerate(dictionaries) if d == default_dict), 1)
        self.dictionary_combo.setCurrentIndex(default_index)
        
        layout.addWidget(dict_label, 0, 0)
        layout.addWidget(self.dictionary_combo, 0, 1)
        
        # Taille du marqueur
        size_label = QLabel(self.config.get('ui', 'aruco_generator.labels.marker_size', "Taille marqueur (pixels):"))
        self.size_spinbox = QSpinBox()
        size_min = self.config.get('ui', 'aruco_generator.marker_size_min', 50)
        size_max = self.config.get('ui', 'aruco_generator.marker_size_max', 1000)
        size_default = self.config.get('ui', 'aruco_generator.marker_size_default', 200)
        
        self.size_spinbox.setRange(size_min, size_max)
        self.size_spinbox.setValue(size_default)
        self.size_spinbox.setSuffix(" px")
        
        layout.addWidget(size_label, 1, 0)
        layout.addWidget(self.size_spinbox, 1, 1)
        
        # Plage d'IDs
        id_range_label = QLabel(self.config.get('ui', 'aruco_generator.labels.id_range', "Plage d'IDs:"))
        
        id_layout = QHBoxLayout()
        self.start_id_spinbox = QSpinBox()
        self.start_id_spinbox.setRange(0, 9999)
        self.start_id_spinbox.setValue(0)
        
        id_layout.addWidget(QLabel("De:"))
        id_layout.addWidget(self.start_id_spinbox)
        
        self.end_id_spinbox = QSpinBox()
        self.end_id_spinbox.setRange(0, 9999)
        self.end_id_spinbox.setValue(9)
        
        id_layout.addWidget(QLabel("À:"))
        id_layout.addWidget(self.end_id_spinbox)
        
        layout.addWidget(id_range_label, 2, 0)
        layout.addLayout(id_layout, 2, 1)
        
        # Options d'impression
        print_options_label = QLabel(self.config.get('ui', 'aruco_generator.labels.print_options', "Options impression:"))
        
        options_layout = QVBoxLayout()
        
        self.add_border_cb = QCheckBox(self.config.get('ui', 'aruco_generator.labels.add_border', "Ajouter bordure"))
        self.add_border_cb.setChecked(True)
        options_layout.addWidget(self.add_border_cb)
        
        self.add_id_text_cb = QCheckBox(self.config.get('ui', 'aruco_generator.labels.add_id_text', "Ajouter ID en texte"))
        self.add_id_text_cb.setChecked(True)
        options_layout.addWidget(self.add_id_text_cb)
        
        self.high_quality_cb = QCheckBox(self.config.get('ui', 'aruco_generator.labels.high_quality', "Haute qualité"))
        self.high_quality_cb.setChecked(False)
        options_layout.addWidget(self.high_quality_cb)
        
        layout.addWidget(print_options_label, 3, 0)
        layout.addLayout(options_layout, 3, 1)
        
        return group
    
    def create_controls_group(self):
        """Crée les contrôles de génération"""
        group = QGroupBox(self.config.get('ui', 'aruco_generator.labels.controls_group', "🎬 Contrôles"))
        layout = QHBoxLayout(group)
        
        # Bouton génération
        generate_text = self.config.get('ui', 'aruco_generator.labels.generate_button', "🎯 Générer Marqueurs")
        self.generate_btn = QPushButton(generate_text)
        self.generate_btn.setMinimumHeight(40)
        layout.addWidget(self.generate_btn)
        
        # Bouton arrêt
        stop_text = self.config.get('ui', 'aruco_generator.labels.stop_button', "⏹️ Arrêter")
        self.stop_btn = QPushButton(stop_text)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Statut
        self.status_label = QLabel(self.config.get('ui', 'aruco_generator.messages.ready', "Prêt à générer"))
        layout.addWidget(self.status_label)
        
        return group
    
    def create_display_group(self):
        """Crée la zone d'affichage des marqueurs"""
        group = QGroupBox(self.config.get('ui', 'aruco_generator.labels.display_group', "🖼️ Aperçu des Marqueurs"))
        layout = QVBoxLayout(group)
        
        # Zone de défilement
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Widget conteneur pour les marqueurs
        self.markers_widget = QWidget()
        self.markers_layout = QGridLayout(self.markers_widget)
        
        # Configuration du layout
        grid_spacing = self.config.get('ui', 'aruco_generator.grid_spacing', 10)
        self.markers_layout.setSpacing(grid_spacing)
        
        scroll_area.setWidget(self.markers_widget)
        layout.addWidget(scroll_area)
        
        # Label par défaut
        default_text = self.config.get('ui', 'aruco_generator.messages.no_markers', 
                                     "Aucun marqueur généré\n\nConfigurez les paramètres et cliquez sur 'Générer'")
        self.default_label = QLabel(default_text)
        self.default_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.default_label.setStyleSheet("color: #666; font-size: 14px; padding: 50px;")
        self.markers_layout.addWidget(self.default_label, 0, 0)
        
        return group
    
    def create_action_buttons(self):
        """Crée les boutons d'action"""
        layout = QHBoxLayout()
        
        layout.addStretch()
        
        # Bouton sauvegarde
        save_text = self.config.get('ui', 'aruco_generator.labels.save_button', "💾 Sauvegarder Images")
        self.save_btn = QPushButton(save_text)
        self.save_btn.setEnabled(False)
        layout.addWidget(self.save_btn)
        
        # Bouton impression
        print_text = self.config.get('ui', 'aruco_generator.labels.print_button', "🖨️ Imprimer")
        self.print_btn = QPushButton(print_text)
        self.print_btn.setEnabled(False)
        layout.addWidget(self.print_btn)
        
        # Bouton fermeture
        close_text = self.config.get('ui', 'aruco_generator.labels.close_button', "❌ Fermer")
        close_btn = QPushButton(close_text)
        layout.addWidget(close_btn)
        close_btn.clicked.connect(self.accept)
        
        return layout
    
    def connect_signals(self):
        """Connecte les signaux"""
        self.generate_btn.clicked.connect(self.start_generation)
        self.stop_btn.clicked.connect(self.stop_generation)
        self.save_btn.clicked.connect(self.save_markers)
        self.print_btn.clicked.connect(self.print_markers)
        
        # Validation automatique des IDs
        self.start_id_spinbox.valueChanged.connect(self.validate_id_range)
        self.end_id_spinbox.valueChanged.connect(self.validate_id_range)
        self.dictionary_combo.currentTextChanged.connect(self.validate_dictionary_limits)
    
    def validate_id_range(self):
        """Valide la plage d'IDs"""
        start_id = self.start_id_spinbox.value()
        end_id = self.end_id_spinbox.value()
        
        if start_id > end_id:
            self.end_id_spinbox.setValue(start_id)
        
        # Validation selon le dictionnaire
        self.validate_dictionary_limits()
    
    def validate_dictionary_limits(self):
        """Valide les limites selon le dictionnaire"""
        dict_name = self.dictionary_combo.currentText()
        
        # Limites par dictionnaire
        limits = {
            "DICT_4X4_50": 50,
            "DICT_5X5_100": 100,
            "DICT_6X6_250": 250,
            "DICT_7X7_1000": 1000,
            "DICT_ARUCO_ORIGINAL": 1024,
            "DICT_APRILTAG_16h5": 30,
            "DICT_APRILTAG_25h9": 35
        }
        
        max_id = limits.get(dict_name, 1000) - 1
        
        self.start_id_spinbox.setMaximum(max_id)
        self.end_id_spinbox.setMaximum(max_id)
        
        # Ajustement si nécessaire
        if self.start_id_spinbox.value() > max_id:
            self.start_id_spinbox.setValue(0)
        if self.end_id_spinbox.value() > max_id:
            self.end_id_spinbox.setValue(min(9, max_id))
    
    def start_generation(self):
        """Démarre la génération des marqueurs"""
        try:
            # Validation des paramètres
            start_id = self.start_id_spinbox.value()
            end_id = self.end_id_spinbox.value()
            
            if start_id > end_id:
                QMessageBox.warning(self, "Erreur", "L'ID de début doit être inférieur ou égal à l'ID de fin")
                return
            
            marker_count = end_id - start_id + 1
            max_markers = self.config.get('ui', 'aruco_generator.max_markers_warning', 100)
            
            if marker_count > max_markers:
                reply = QMessageBox.question(self, "Confirmation", 
                                           f"Vous allez générer {marker_count} marqueurs. Continuer ?")
                if reply != QMessageBox.StandardButton.Yes:
                    return
            
            # Préparation de la génération
            dictionary = self.dictionary_combo.currentData()
            marker_ids = list(range(start_id, end_id + 1))
            marker_size = self.size_spinbox.value()
            
            # Nettoyage de l'affichage précédent
            self.clear_markers_display()
            
            # Configuration de l'interface
            self.generate_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            generating_msg = self.config.get('ui', 'aruco_generator.messages.generating', 
                                           "Génération en cours...")
            self.status_label.setText(generating_msg)
            
            # Démarrage du thread
            self.generation_thread = ArUcoGeneratorThread(dictionary, marker_ids, marker_size)
            self.generation_thread.progress_updated.connect(self.update_progress)
            self.generation_thread.marker_generated.connect(self.add_marker_to_display)
            self.generation_thread.generation_finished.connect(self.generation_completed)
            self.generation_thread.error_occurred.connect(self.generation_error)
            self.generation_thread.start()
            
            logger.info(f"Génération démarrée: {marker_count} marqueurs ({start_id}-{end_id})")
            
        except Exception as e:
            logger.error(f"Erreur démarrage génération: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur lors du démarrage: {e}")
    
    def stop_generation(self):
        """Arrête la génération"""
        if self.generation_thread and self.generation_thread.isRunning():
            self.generation_thread.stop()
            self.generation_thread.wait(3000)  # Attendre 3 secondes maximum
            
            stopped_msg = self.config.get('ui', 'aruco_generator.messages.stopped', "Génération arrêtée")
            self.status_label.setText(stopped_msg)
            
            self.reset_generation_ui()
    
    def update_progress(self, value):
        """Met à jour la barre de progression"""
        self.progress_bar.setValue(value)
    
    def add_marker_to_display(self, marker_id, marker_image):
        """Ajoute un marqueur à l'affichage"""
        try:
            # Suppression du label par défaut si c'est le premier marqueur
            if not self.generated_markers:
                self.default_label.setParent(None)
            
            # Stockage du marqueur
            self.generated_markers[marker_id] = marker_image
            
            # Création du widget d'affichage
            marker_widget = MarkerWidget(marker_id, marker_image, self.config)
            
            # Positionnement dans la grille
            markers_per_row = self.config.get('ui', 'aruco_generator.markers_per_row', 6)
            row = len(self.generated_markers) // markers_per_row
            col = (len(self.generated_markers) - 1) % markers_per_row
            
            self.markers_layout.addWidget(marker_widget, row, col)
            
        except Exception as e:
            logger.error(f"Erreur ajout marqueur {marker_id}: {e}")
    
    def generation_completed(self):
        """Génération terminée avec succès"""
        completed_msg = self.config.get('ui', 'aruco_generator.messages.completed', 
                                       f"✅ {len(self.generated_markers)} marqueur(s) généré(s)")
        self.status_label.setText(completed_msg)
        
        self.reset_generation_ui()
        
        # Activation des boutons d'export
        self.save_btn.setEnabled(True)
        self.print_btn.setEnabled(True)
        
        logger.info(f"Génération terminée: {len(self.generated_markers)} marqueurs")
    
    def generation_error(self, error_message):
        """Erreur lors de la génération"""
        error_msg = self.config.get('ui', 'aruco_generator.messages.error', 
                                   f"❌ Erreur: {error_message}")
        self.status_label.setText(error_msg)
        
        self.reset_generation_ui()
        
        QMessageBox.critical(self, "Erreur de génération", error_message)
    
    def reset_generation_ui(self):
        """Remet l'interface dans l'état initial"""
        self.generate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
    
    def clear_markers_display(self):
        """Efface l'affichage des marqueurs"""
        # Suppression de tous les widgets
        for i in reversed(range(self.markers_layout.count())):
            item = self.markers_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        
        # Réinitialisation
        self.generated_markers.clear()
        
        # Remise du label par défaut
        default_text = self.config.get('ui', 'aruco_generator.messages.no_markers', 
                                     "Aucun marqueur généré\n\nConfigurez les paramètres et cliquez sur 'Générer'")
        self.default_label = QLabel(default_text)
        self.default_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.default_label.setStyleSheet("color: #666; font-size: 14px; padding: 50px;")
        self.markers_layout.addWidget(self.default_label, 0, 0)
        
        # Désactivation des boutons d'export
        self.save_btn.setEnabled(False)
        self.print_btn.setEnabled(False)
    
    def save_markers(self):
        """Sauvegarde les marqueurs générés"""
        if not self.generated_markers:
            return
        
        # Sélection du répertoire
        default_dir = self.config.get('ui', 'aruco_generator.default_save_dir', './aruco_markers')
        save_dir = QFileDialog.getExistingDirectory(self, "Sélectionner le répertoire de sauvegarde", default_dir)
        
        if not save_dir:
            return
        
        try:
            save_path = Path(save_dir)
            save_path.mkdir(exist_ok=True)
            
            saved_count = 0
            
            for marker_id, marker_image in self.generated_markers.items():
                # Traitement de l'image selon les options
                final_image = self.process_marker_for_export(marker_image, marker_id)
                
                # Nom de fichier
                filename = f"aruco_marker_{marker_id:04d}.png"
                filepath = save_path / filename
                
                # Sauvegarde
                success = cv2.imwrite(str(filepath), final_image)
                if success:
                    saved_count += 1
            
            # Message de confirmation
            QMessageBox.information(self, "Sauvegarde terminée", 
                                  f"{saved_count} marqueur(s) sauvegardé(s) dans:\n{save_path}")
            
            logger.info(f"Sauvegarde terminée: {saved_count} marqueurs dans {save_path}")
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde: {e}")
    
    def process_marker_for_export(self, marker_image, marker_id):
        """Traite un marqueur pour l'export selon les options"""
        try:
            processed_image = marker_image.copy()
            
            # Redimensionnement si haute qualité
            if self.high_quality_cb.isChecked():
                scale_factor = self.config.get('ui', 'aruco_generator.high_quality_scale', 4)
                new_size = marker_image.shape[0] * scale_factor
                processed_image = cv2.resize(processed_image, (new_size, new_size), interpolation=cv2.INTER_NEAREST)
            
            # Ajout de bordure
            if self.add_border_cb.isChecked():
                border_size = self.config.get('ui', 'aruco_generator.border_size', 20)
                processed_image = cv2.copyMakeBorder(
                    processed_image, border_size, border_size, border_size, border_size,
                    cv2.BORDER_CONSTANT, value=255
                )
            
            # Ajout du texte ID
            if self.add_id_text_cb.isChecked():
                height, width = processed_image.shape
                
                # Ajout d'espace en bas pour le texte
                text_height = self.config.get('ui', 'aruco_generator.text_height', 40)
                text_area = np.full((text_height, width), 255, dtype=np.uint8)
                processed_image = np.vstack([processed_image, text_area])
                
                # Dessin du texte
                font_scale = self.config.get('ui', 'aruco_generator.font_scale', 1.0)
                text = f"ArUco ID: {marker_id}"
                text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2)[0]
                text_x = (width - text_size[0]) // 2
                text_y = height + text_height // 2 + text_size[1] // 2
                
                cv2.putText(processed_image, text, (text_x, text_y), 
                           cv2.FONT_HERSHEY_SIMPLEX, font_scale, 0, 2)
            
            return processed_image
            
        except Exception as e:
            logger.error(f"Erreur traitement marqueur {marker_id}: {e}")
            return marker_image
    
    def print_markers(self):
        """Imprime les marqueurs générés"""
        if not self.generated_markers:
            return
        
        try:
            # Création du document d'impression
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setPageSize(QPrinter.PageSize.A4)
            
            # Dialog d'impression
            print_dialog = QPrintDialog(printer, self)
            if print_dialog.exec() == QPrintDialog.DialogCode.Accepted:
                
                # Création du document
                painter = QPainter(printer)
                self.paint_markers_for_printing(painter, printer)
                painter.end()
                
                print_success_msg = self.config.get('ui', 'aruco_generator.messages.print_success', 
                                                   "Impression terminée avec succès")
                QMessageBox.information(self, "Impression", print_success_msg)
                
                logger.info("Impression des marqueurs terminée")
            
        except Exception as e:
            logger.error(f"Erreur impression: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'impression: {e}")
    
    def paint_markers_for_printing(self, painter, printer):
        """Dessine les marqueurs pour l'impression"""
        try:
            page_rect = printer.pageRect(QPrinter.Unit.Point)
            page_width = page_rect.width()
            page_height = page_rect.height()
            
            # Configuration de la grille d'impression
            markers_per_row = self.config.get('ui', 'aruco_generator.print_markers_per_row', 4)
            markers_per_col = self.config.get('ui', 'aruco_generator.print_markers_per_col', 6)
            margin = self.config.get('ui', 'aruco_generator.print_margin', 50)
            
            # Calcul des dimensions
            available_width = page_width - 2 * margin
            available_height = page_height - 2 * margin
            
            marker_width = available_width / markers_per_row
            marker_height = available_height / markers_per_col
            marker_size = min(marker_width, marker_height) * 0.8  # 80% pour laisser de l'espace
            
            markers_list = list(self.generated_markers.items())
            markers_per_page = markers_per_row * markers_per_col
            
            for page_num in range(0, len(markers_list), markers_per_page):
                if page_num > 0:
                    printer.newPage()
                
                page_markers = markers_list[page_num:page_num + markers_per_page]
                
                for i, (marker_id, marker_image) in enumerate(page_markers):
                    row = i // markers_per_row
                    col = i % markers_per_row
                    
                    # Position du marqueur
                    x = margin + col * marker_width + (marker_width - marker_size) / 2
                    y = margin + row * marker_height + (marker_height - marker_size) / 2
                    
                    # Traitement de l'image
                    processed_image = self.process_marker_for_export(marker_image, marker_id)
                    
                    # Conversion pour Qt
                    height, width = processed_image.shape
                    bytes_per_line = width
                    q_image = QImage(processed_image.data, width, height, bytes_per_line, QImage.Format.Format_Grayscale8)
                    
                    # Dessin
                    target_rect = painter.viewport()
                    target_rect.setX(int(x))
                    target_rect.setY(int(y))
                    target_rect.setWidth(int(marker_size))
                    target_rect.setHeight(int(marker_size))
                    
                    painter.drawImage(target_rect, q_image)
                    
                    # Ajout du texte ID si option activée
                    if self.add_id_text_cb.isChecked():
                        text_y = y + marker_size + 20
                        text_rect = painter.viewport()
                        text_rect.setX(int(x))
                        text_rect.setY(int(text_y))
                        text_rect.setWidth(int(marker_size))
                        text_rect.setHeight(20)
                        
                        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"ID: {marker_id}")
            
        except Exception as e:
            logger.error(f"Erreur dessin impression: {e}")
            raise
    
    def closeEvent(self, event):
        """Gestion de la fermeture"""
        try:
            # Arrêt du thread si en cours
            if self.generation_thread and self.generation_thread.isRunning():
                self.generation_thread.stop()
                self.generation_thread.wait(1000)
            
            event.accept()
            
        except Exception as e:
            logger.error(f"Erreur fermeture: {e}")
            event.accept()


# Point d'entrée pour test
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    from pathlib import Path
    
    # Configuration de test
    class TestConfig:
        def get(self, section, key, default=None):
            config_values = {
                'ui.aruco_generator.window_title': "Générateur de Codes ArUco",
                'ui.aruco_generator.window_width': 900,
                'ui.aruco_generator.window_height': 700,
                'ui.aruco_generator.marker_display_size': 120,
                'ui.aruco_generator.dictionaries': [
                    "DICT_4X4_50", "DICT_5X5_100", "DICT_6X6_250", 
                    "DICT_7X7_1000", "DICT_ARUCO_ORIGINAL"
                ],
                'ui.aruco_generator.default_dictionary': "DICT_5X5_100",
                'ui.aruco_generator.marker_size_min': 50,
                'ui.aruco_generator.marker_size_max': 1000,
                'ui.aruco_generator.marker_size_default': 200,
                'ui.aruco_generator.grid_spacing': 10,
                'ui.aruco_generator.markers_per_row': 6,
                'ui.aruco_generator.max_markers_warning': 100,
                'ui.aruco_generator.labels.config_group': "📋 Configuration",
                'ui.aruco_generator.labels.dictionary': "Dictionnaire ArUco:",
                'ui.aruco_generator.labels.marker_size': "Taille marqueur (pixels):",
                'ui.aruco_generator.labels.id_range': "Plage d'IDs:",
                'ui.aruco_generator.labels.print_options': "Options impression:",
                'ui.aruco_generator.labels.add_border': "Ajouter bordure",
                'ui.aruco_generator.labels.add_id_text': "Ajouter ID en texte",
                'ui.aruco_generator.labels.high_quality': "Haute qualité",
                'ui.aruco_generator.labels.controls_group': "🎬 Contrôles",
                'ui.aruco_generator.labels.generate_button': "🎯 Générer Marqueurs",
                'ui.aruco_generator.labels.stop_button': "⏹️ Arrêter",
                'ui.aruco_generator.labels.display_group': "🖼️ Aperçu des Marqueurs",
                'ui.aruco_generator.labels.save_button': "💾 Sauvegarder Images",
                'ui.aruco_generator.labels.print_button': "🖨️ Imprimer",
                'ui.aruco_generator.labels.close_button': "❌ Fermer",
                'ui.aruco_generator.messages.ready': "Prêt à générer",
                'ui.aruco_generator.messages.no_markers': "Aucun marqueur généré\n\nConfigurez les paramètres et cliquez sur 'Générer'",
                'ui.aruco_generator.messages.generating': "Génération en cours...",
                'ui.aruco_generator.messages.stopped': "Génération arrêtée",
                'ui.aruco_generator.messages.completed': "✅ Marqueurs générés avec succès",
                'ui.aruco_generator.messages.error': "❌ Erreur de génération",
                'ui.aruco_generator.messages.print_success': "Impression terminée avec succès",
                'ui.aruco_generator.default_save_dir': './aruco_markers',
                'ui.aruco_generator.high_quality_scale': 4,
                'ui.aruco_generator.border_size': 20,
                'ui.aruco_generator.text_height': 40,
                'ui.aruco_generator.font_scale': 1.0,
                'ui.aruco_generator.print_markers_per_row': 4,
                'ui.aruco_generator.print_markers_per_col': 6,
                'ui.aruco_generator.print_margin': 50
            }
            return config_values.get(f"{section}.{key}", default)
    
    app = QApplication(sys.argv)
    config = TestConfig()
    
    dialog = ArUcoGeneratorDialog(config)
    dialog.show()
    
    sys.exit(app.exec())