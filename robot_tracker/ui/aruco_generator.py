# robot_tracker/ui/aruco_generator.py
# Version 1.1 - Générateur ArUco optimisé complet
# Modification: Intégration avec configuration JSON dédiée

import sys
import cv2
import numpy as np
import logging
from pathlib import Path
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                           QGroupBox, QLabel, QComboBox, QSpinBox, QCheckBox,
                           QPushButton, QScrollArea, QWidget, QMessageBox,
                           QFileDialog, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QFont, QImage
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

logger = logging.getLogger(__name__)

class MarkerWidget(QLabel):
    """Widget d'affichage d'un marqueur ArUco"""
    
    def __init__(self, marker_id: int, marker_image: np.ndarray, display_size: int):
        super().__init__()
        self.marker_id = marker_id
        self.display_size = display_size
        
        try:
            # Conversion OpenCV vers QPixmap
            height, width = marker_image.shape
            bytes_per_line = width
            q_image = QImage(marker_image.data, width, height, bytes_per_line, QImage.Format.Format_Grayscale8)
            pixmap = QPixmap.fromImage(q_image).scaled(display_size, display_size, Qt.AspectRatioMode.KeepAspectRatio)
            
            self.setPixmap(pixmap)
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setStyleSheet("border: 1px solid #ddd; padding: 5px; margin: 2px;")
            self.setToolTip(f"Marqueur ArUco ID: {marker_id}")
            
        except Exception as e:
            logger.error(f"Erreur création widget marqueur {marker_id}: {e}")
            self.setText(f"Erreur\nID: {marker_id}")

class ArUcoGeneratorThread(QThread):
    """Thread de génération des marqueurs ArUco"""
    
    progress_updated = pyqtSignal(int, int)  # current, total
    marker_generated = pyqtSignal(int, object)  # id, image
    generation_completed = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, dictionary_name: str, marker_size: int, id_start: int, id_end: int):
        super().__init__()
        self.dictionary_name = dictionary_name
        self.marker_size = marker_size
        self.id_start = id_start
        self.id_end = id_end
        self.should_stop = False
    
    def stop(self):
        """Arrête la génération"""
        self.should_stop = True
    
    def run(self):
        """Génère les marqueurs ArUco"""
        try:
            # Récupération du dictionnaire
            dict_attr = getattr(cv2.aruco, self.dictionary_name, None)
            if dict_attr is None:
                self.error_occurred.emit(f"Dictionnaire inconnu: {self.dictionary_name}")
                return
            
            aruco_dict = cv2.aruco.getPredefinedDictionary(dict_attr)
            total_markers = self.id_end - self.id_start + 1
            
            for i, marker_id in enumerate(range(self.id_start, self.id_end + 1)):
                if self.should_stop:
                    break
                
                # Génération du marqueur
                marker_image = cv2.aruco.generateImageMarker(aruco_dict, marker_id, self.marker_size)
                
                # Émission du signal
                self.marker_generated.emit(marker_id, marker_image)
                self.progress_updated.emit(i + 1, total_markers)
                
                # Pause pour la responsivité
                self.msleep(10)
            
            if not self.should_stop:
                self.generation_completed.emit()
                
        except Exception as e:
            self.error_occurred.emit(f"Erreur génération: {str(e)}")

class ArUcoGeneratorDialog(QDialog):
    """Dialog de génération de codes ArUco optimisé"""
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.generated_markers = {}
        self.generation_thread = None
        
        self.init_ui()
        self.connect_signals()
        
        logger.info("🎯 Générateur ArUco initialisé")
    
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        # Configuration depuis fichier JSON
        aruco_config = self.config.get_aruco_config()
        window_config = aruco_config.get('window', {})
        
        self.setWindowTitle(window_config.get('title', "Générateur de Codes ArUco"))
        self.setModal(True)
        self.resize(
            window_config.get('width', 900),
            window_config.get('height', 700)
        )
        
        layout = QVBoxLayout(self)
        
        # Configuration
        config_group = self.create_config_group()
        layout.addWidget(config_group)
        
        # Contrôles
        controls_group = self.create_controls_group()
        layout.addWidget(controls_group)
        
        # Zone d'affichage
        display_group = self.create_display_group()
        layout.addWidget(display_group)
        
        # Boutons d'action
        buttons_layout = self.create_action_buttons()
        layout.addLayout(buttons_layout)
    
    def create_config_group(self):
        """Crée le groupe de configuration"""
        aruco_config = self.config.get_aruco_config()
        labels_config = aruco_config.get('labels', {})
        
        group = QGroupBox(labels_config.get('config_group', "📋 Configuration"))
        layout = QGridLayout(group)
        
        # Dictionnaire ArUco
        dict_label = QLabel(labels_config.get('dictionary', "Dictionnaire ArUco:"))
        self.dictionary_combo = QComboBox()
        
        dictionaries = aruco_config.get('dictionaries', ["DICT_4X4_50", "DICT_5X5_100"])
        self.dictionary_combo.addItems(dictionaries)
        
        default_dict = aruco_config.get('default_dictionary', 'DICT_5X5_100')
        if default_dict in dictionaries:
            self.dictionary_combo.setCurrentText(default_dict)
        
        # Taille marqueur
        size_config = aruco_config.get('marker_size', {})
        size_label = QLabel(labels_config.get('marker_size', "Taille marqueur:"))
        self.size_spinbox = QSpinBox()
        self.size_spinbox.setRange(
            size_config.get('min', 50),
            size_config.get('max', 1000)
        )
        self.size_spinbox.setValue(size_config.get('default', 200))
        self.size_spinbox.setSuffix(" px")
        
        # Plage d'IDs
        id_config = aruco_config.get('id_range', {})
        id_label = QLabel(labels_config.get('id_range', "Plage d'IDs:"))
        
        self.id_start_spinbox = QSpinBox()
        self.id_start_spinbox.setRange(0, 9999)
        self.id_start_spinbox.setValue(id_config.get('default_start', 0))
        
        self.id_end_spinbox = QSpinBox()
        self.id_end_spinbox.setRange(0, 9999)
        self.id_end_spinbox.setValue(id_config.get('default_end', 9))
        
        # Options d'impression
        print_label = QLabel(labels_config.get('print_options', "Options:"))
        self.add_border_checkbox = QCheckBox(labels_config.get('add_border', "Bordure"))
        self.add_id_text_checkbox = QCheckBox(labels_config.get('add_id_text', "ID texte"))
        self.high_quality_checkbox = QCheckBox(labels_config.get('high_quality', "Haute qualité"))
        
        # Assemblage layout
        layout.addWidget(dict_label, 0, 0)
        layout.addWidget(self.dictionary_combo, 0, 1, 1, 2)
        layout.addWidget(size_label, 1, 0)
        layout.addWidget(self.size_spinbox, 1, 1)
        layout.addWidget(id_label, 2, 0)
        
        id_layout = QHBoxLayout()
        id_layout.addWidget(self.id_start_spinbox)
        id_layout.addWidget(QLabel("à"))
        id_layout.addWidget(self.id_end_spinbox)
        
        id_widget = QWidget()
        id_widget.setLayout(id_layout)
        layout.addWidget(id_widget, 2, 1, 1, 2)
        
        layout.addWidget(print_label, 3, 0)
        
        options_layout = QHBoxLayout()
        options_layout.addWidget(self.add_border_checkbox)
        options_layout.addWidget(self.add_id_text_checkbox)
        options_layout.addWidget(self.high_quality_checkbox)
        
        options_widget = QWidget()
        options_widget.setLayout(options_layout)
        layout.addWidget(options_widget, 3, 1, 1, 2)
        
        return group
    
    def create_controls_group(self):
        """Crée le groupe de contrôles"""
        aruco_config = self.config.get_aruco_config()
        labels_config = aruco_config.get('labels', {})
        
        group = QGroupBox(labels_config.get('controls_group', "🎬 Contrôles"))
        layout = QHBoxLayout(group)
        
        self.generate_button = QPushButton(labels_config.get('generate_button', "🎯 Générer"))
        self.stop_button = QPushButton(labels_config.get('stop_button', "⏹️ Arrêter"))
        self.stop_button.setEnabled(False)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        layout.addWidget(self.generate_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.progress_bar)
        layout.addStretch()
        
        return group
    
    def create_display_group(self):
        """Crée la zone d'affichage des marqueurs"""
        aruco_config = self.config.get_aruco_config()
        labels_config = aruco_config.get('labels', {})
        
        group = QGroupBox(labels_config.get('display_group', "🖼️ Aperçu"))
        layout = QVBoxLayout(group)
        
        # Zone de scroll pour les marqueurs
        self.scroll_area = QScrollArea()
        self.markers_widget = QWidget()
        self.markers_layout = QGridLayout(self.markers_widget)
        
        self.scroll_area.setWidget(self.markers_widget)
        self.scroll_area.setWidgetResizable(True)
        
        layout.addWidget(self.scroll_area)
        
        return group
    
    def create_action_buttons(self):
        """Crée les boutons d'action"""
        aruco_config = self.config.get_aruco_config()
        labels_config = aruco_config.get('labels', {})
        
        layout = QHBoxLayout()
        
        self.save_button = QPushButton(labels_config.get('save_button', "💾 Sauvegarder"))
        self.print_button = QPushButton(labels_config.get('print_button', "🖨️ Imprimer"))
        self.close_button = QPushButton(labels_config.get('close_button', "❌ Fermer"))
        
        self.save_button.setEnabled(False)
        self.print_button.setEnabled(False)
        
        layout.addWidget(self.save_button)
        layout.addWidget(self.print_button)
        layout.addStretch()
        layout.addWidget(self.close_button)
        
        return layout
    
    def connect_signals(self):
        """Connecte les signaux"""
        self.generate_button.clicked.connect(self.start_generation)
        self.stop_button.clicked.connect(self.stop_generation)
        self.save_button.clicked.connect(self.save_markers)
        self.print_button.clicked.connect(self.print_markers)
        self.close_button.clicked.connect(self.close)
    
    def start_generation(self):
        """Démarre la génération"""
        if self.generation_thread and self.generation_thread.isRunning():
            return
        
        # Configuration
        dictionary_name = self.dictionary_combo.currentText()
        marker_size = self.size_spinbox.value()
        id_start = self.id_start_spinbox.value()
        id_end = self.id_end_spinbox.value()
        
        # Validation
        if id_start > id_end:
            QMessageBox.warning(self, "Erreur", "ID de début doit être ≤ ID de fin")
            return
        
        # Nettoyage affichage précédent
        self.clear_markers_display()
        self.generated_markers.clear()
        
        # Configuration UI
        self.generate_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(id_end - id_start + 1)
        
        # Lancement thread
        self.generation_thread = ArUcoGeneratorThread(dictionary_name, marker_size, id_start, id_end)
        self.generation_thread.progress_updated.connect(self.update_progress)
        self.generation_thread.marker_generated.connect(self.add_marker_to_display)
        self.generation_thread.generation_completed.connect(self.generation_finished)
        self.generation_thread.error_occurred.connect(self.handle_error)
        
        self.generation_thread.start()
    
    def stop_generation(self):
        """Arrête la génération"""
        if self.generation_thread:
            self.generation_thread.stop()
    
    def update_progress(self, current: int, total: int):
        """Met à jour la barre de progression"""
        self.progress_bar.setValue(current)
    
    def add_marker_to_display(self, marker_id: int, marker_image: np.ndarray):
        """Ajoute un marqueur à l'affichage"""
        self.generated_markers[marker_id] = marker_image
        
        aruco_config = self.config.get_aruco_config()
        display_config = aruco_config.get('display', {})
        display_size = display_config.get('marker_display_size', 120)
        markers_per_row = display_config.get('markers_per_row', 6)
        
        # Création widget marqueur
        marker_widget = MarkerWidget(marker_id, marker_image, display_size)
        
        # Position dans la grille
        row = len(self.generated_markers) // markers_per_row
        col = (len(self.generated_markers) - 1) % markers_per_row
        
        self.markers_layout.addWidget(marker_widget, row, col)
    
    def generation_finished(self):
        """Fin de génération"""
        self.generate_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        self.save_button.setEnabled(len(self.generated_markers) > 0)
        self.print_button.setEnabled(len(self.generated_markers) > 0)
        
        aruco_config = self.config.get_aruco_config()
        messages_config = aruco_config.get('messages', {})
        
        QMessageBox.information(self, "Succès", 
                               messages_config.get('completed', "✅ Génération terminée"))
    
    def handle_error(self, error_message: str):
        """Gestion des erreurs"""
        self.generate_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        aruco_config = self.config.get_aruco_config()
        messages_config = aruco_config.get('messages', {})
        
        QMessageBox.critical(self, "Erreur", 
                            f"{messages_config.get('error', 'Erreur')}: {error_message}")
    
    def clear_markers_display(self):
        """Nettoie l'affichage des marqueurs"""
        while self.markers_layout.count():
            child = self.markers_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def save_markers(self):
        """Sauvegarde les marqueurs générés"""
        if not self.generated_markers:
            return
        
        aruco_config = self.config.get_aruco_config()
        export_config = aruco_config.get('export', {})
        default_dir = export_config.get('default_save_dir', './aruco_markers')
        
        save_dir = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier de sauvegarde", default_dir
        )
        
        if not save_dir:
            return
        
        save_path = Path(save_dir)
        save_path.mkdir(exist_ok=True)
        
        try:
            for marker_id, marker_image in self.generated_markers.items():
                # Application des options
                final_image = marker_image.copy()
                
                if self.add_border_checkbox.isChecked():
                    border_size = export_config.get('border_size', 20)
                    final_image = cv2.copyMakeBorder(
                        final_image, border_size, border_size, border_size, border_size,
                        cv2.BORDER_CONSTANT, value=255
                    )
                
                if self.add_id_text_checkbox.isChecked():
                    text_height = export_config.get('text_height', 40)
                    font_scale = export_config.get('font_scale', 1.0)
                    
                    h, w = final_image.shape
                    final_image = cv2.copyMakeBorder(
                        final_image, 0, text_height, 0, 0,
                        cv2.BORDER_CONSTANT, value=255
                    )
                    
                    cv2.putText(final_image, f"ID: {marker_id}", 
                               (10, h + 25), cv2.FONT_HERSHEY_SIMPLEX, 
                               font_scale, 0, 2)
                
                if self.high_quality_checkbox.isChecked():
                    scale = export_config.get('high_quality_scale', 4)
                    final_image = cv2.resize(final_image, None, fx=scale, fy=scale, 
                                           interpolation=cv2.INTER_NEAREST)
                
                # Sauvegarde
                filename = save_path / f"aruco_marker_{marker_id:04d}.png"
                cv2.imwrite(str(filename), final_image)
            
            messages_config = aruco_config.get('messages', {})
            QMessageBox.information(self, "Succès", 
                                   f"{messages_config.get('save_success', 'Sauvegarde réussie')}\n"
                                   f"Dossier: {save_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur sauvegarde: {e}")
    
    def print_markers(self):
        """Imprime les marqueurs"""
        if not self.generated_markers:
            return
        
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        print_dialog = QPrintDialog(printer, self)
        
        if print_dialog.exec() == QPrintDialog.DialogCode.Accepted:
            try:
                aruco_config = self.config.get_aruco_config()
                print_config = aruco_config.get('printing', {})
                
                # Configuration impression depuis JSON
                markers_per_row = print_config.get('markers_per_row', 4)
                markers_per_col = print_config.get('markers_per_col', 6)
                margin = print_config.get('margin', 50)
                
                # Création de l'image d'impression
                self._create_print_layout(printer, markers_per_row, markers_per_col, margin)
                
                messages_config = aruco_config.get('messages', {})
                QMessageBox.information(self, "Succès", 
                                       messages_config.get('print_success', "Impression réussie"))
                
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur impression: {e}")
    
    def _create_print_layout(self, printer, markers_per_row: int, markers_per_col: int, margin: int):
        """Crée la mise en page d'impression"""
        from PyQt6.QtGui import QPainter
        
        painter = QPainter(printer)
        page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
        
        available_width = page_rect.width() - 2 * margin
        available_height = page_rect.height() - 2 * margin
        
        marker_width = available_width // markers_per_row
        marker_height = available_height // markers_per_col
        marker_size = min(marker_width, marker_height) - 10  # Espacement
        
        markers_list = list(self.generated_markers.items())
        
        for i, (marker_id, marker_image) in enumerate(markers_list):
            if i >= markers_per_row * markers_per_col:
                break
            
            row = i // markers_per_row
            col = i % markers_per_row
            
            x = margin + col * marker_width + (marker_width - marker_size) // 2
            y = margin + row * marker_height + (marker_height - marker_size) // 2
            
            # Conversion en QPixmap pour l'impression
            height, width = marker_image.shape
            q_image = QImage(marker_image.data, width, height, width, QImage.Format.Format_Grayscale8)
            pixmap = QPixmap.fromImage(q_image).scaled(
                marker_size, marker_size, Qt.AspectRatioMode.KeepAspectRatio
            )
            
            painter.drawPixmap(x, y, pixmap)
            
            # Ajout de l'ID sous le marqueur
            painter.drawText(x, y + marker_size + 15, f"ID: {marker_id}")
        
        painter.end()

# Fonction d'aide pour les tests
def create_test_dialog():
    """Crée un dialog de test avec configuration minimale"""
    from PyQt6.QtWidgets import QApplication
    import tempfile
    import json
    
    # Configuration de test
    class TestConfig:
        def __init__(self):
            self.aruco_config = {
                "window": {"title": "Test ArUco", "width": 800, "height": 600},
                "dictionaries": ["DICT_4X4_50", "DICT_5X5_100"],
                "default_dictionary": "DICT_4X4_50",
                "marker_size": {"min": 50, "max": 500, "default": 100},
                "id_range": {"default_start": 0, "default_end": 9},
                "display": {"marker_display_size": 100, "markers_per_row": 4},
                "labels": {
                    "config_group": "Configuration",
                    "generate_button": "Générer",
                    "stop_button": "Arrêter"
                },
                "messages": {"completed": "Terminé"}
            }
        
        def get_aruco_config(self):
            return self.aruco_config
    
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    config = TestConfig()
    dialog = ArUcoGeneratorDialog(config)
    
    return dialog, app

# Point d'entrée pour test direct
if __name__ == "__main__":
    dialog, app = create_test_dialog()
    dialog.show()
    sys.exit(app.exec())