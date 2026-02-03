"""
Dialog for importing and exporting settings via YAML
"""

import logging
import yaml
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QTabWidget, QWidget, QLabel, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from config.vpn_profiles import VPNProfileManager
from config.app_settings import AppSettings

logger = logging.getLogger(__name__)


class ExportDialog(QDialog):
    """Dialog for exporting settings to YAML"""

    def __init__(self, profile_manager: VPNProfileManager, 
                 app_settings: AppSettings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.app_settings = app_settings
        
        self.setWindowTitle("Export Settings")
        self.setMinimumSize(600, 400)
        
        self.setup_ui()
        self.load_yaml_data()

    def setup_ui(self) -> None:
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel("Copy the YAML settings below or save them to a file:")
        layout.addWidget(instructions)
        
        # Text area for YAML content
        self.yaml_text = QTextEdit()
        self.yaml_text.setReadOnly(False)
        self.yaml_text.setFont(QFont("Courier New", 10))
        layout.addWidget(self.yaml_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(self.copy_btn)
        
        self.save_btn = QPushButton("Save to File...")
        self.save_btn.clicked.connect(self.save_to_file)
        button_layout.addWidget(self.save_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)

    def load_yaml_data(self) -> None:
        """Load and display current settings as YAML"""
        try:
            # Combine profiles and settings into one export
            export_data = {
                'profiles': {
                    name: profile.to_dict() 
                    for name, profile in self.profile_manager.profiles.items()
                },
                'settings': self.app_settings.settings
            }
            
            yaml_str = yaml.safe_dump(export_data, indent=2, default_flow_style=False)
            self.yaml_text.setPlainText(yaml_str)
            logger.info("Loaded settings for export")
        except Exception as e:
            logger.error(f"Error loading settings for export: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load settings: {e}")

    def copy_to_clipboard(self) -> None:
        """Copy YAML content to clipboard"""
        try:
            from PySide6.QtGui import QClipboard
            from PySide6.QtWidgets import QApplication
            
            clipboard = QApplication.clipboard()
            clipboard.setText(self.yaml_text.toPlainText())
            QMessageBox.information(self, "Success", "Settings copied to clipboard!")
            logger.info("Settings copied to clipboard")
        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")
            QMessageBox.critical(self, "Error", f"Failed to copy to clipboard: {e}")

    def save_to_file(self) -> None:
        """Save YAML content to a file"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Settings",
                "moshi-connect-settings.yaml",
                "YAML Files (*.yaml *.yml);;All Files (*)"
            )
            
            if file_path:
                with open(file_path, 'w') as f:
                    f.write(self.yaml_text.toPlainText())
                QMessageBox.information(self, "Success", f"Settings saved to:\n{file_path}")
                logger.info(f"Settings saved to file: {file_path}")
        except Exception as e:
            logger.error(f"Error saving to file: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save to file: {e}")


class ImportDialog(QDialog):
    """Dialog for importing settings from YAML"""

    def __init__(self, profile_manager: VPNProfileManager,
                 app_settings: AppSettings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.app_settings = app_settings
        self.imported_successfully = False
        
        self.setWindowTitle("Import Settings")
        self.setMinimumSize(600, 400)
        
        self.setup_ui()

    def setup_ui(self) -> None:
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        
        # Tab widget for different import methods
        self.tab_widget = QTabWidget()
        
        # Tab 1: Import from file
        file_tab = QWidget()
        file_layout = QVBoxLayout(file_tab)
        
        file_instructions = QLabel("Select a YAML file to import settings:")
        file_layout.addWidget(file_instructions)
        
        file_button_layout = QHBoxLayout()
        self.select_file_btn = QPushButton("Select File...")
        self.select_file_btn.clicked.connect(self.select_file)
        file_button_layout.addWidget(self.select_file_btn)
        file_button_layout.addStretch()
        file_layout.addLayout(file_button_layout)
        
        self.file_path_label = QLabel("No file selected")
        file_layout.addWidget(self.file_path_label)
        
        file_layout.addStretch()
        
        self.tab_widget.addTab(file_tab, "From File")
        
        # Tab 2: Import from text
        text_tab = QWidget()
        text_layout = QVBoxLayout(text_tab)
        
        text_instructions = QLabel("Paste YAML settings below:")
        text_layout.addWidget(text_instructions)
        
        self.yaml_input = QTextEdit()
        self.yaml_input.setFont(QFont("Courier New", 10))
        self.yaml_input.setPlaceholderText("Paste YAML settings here...")
        text_layout.addWidget(self.yaml_input)
        
        self.tab_widget.addTab(text_tab, "From Text")
        
        layout.addWidget(self.tab_widget)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        self.import_btn = QPushButton("Import")
        self.import_btn.clicked.connect(self.import_settings)
        button_layout.addWidget(self.import_btn)
        
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)

    def select_file(self) -> None:
        """Open file dialog to select YAML file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Settings File",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        
        if file_path:
            self.file_path_label.setText(file_path)
            logger.info(f"Selected file for import: {file_path}")

    def import_settings(self) -> None:
        """Import settings from selected source"""
        try:
            yaml_content = ""
            
            # Determine source based on active tab
            if self.tab_widget.currentIndex() == 0:  # From File
                file_path = self.file_path_label.text()
                if file_path == "No file selected":
                    QMessageBox.warning(self, "Warning", "Please select a file first")
                    return
                
                with open(file_path, 'r') as f:
                    yaml_content = f.read()
            else:  # From Text
                yaml_content = self.yaml_input.toPlainText()
                if not yaml_content.strip():
                    QMessageBox.warning(self, "Warning", "Please paste YAML content first")
                    return
            
            # Parse YAML
            data = yaml.safe_load(yaml_content)
            
            if not isinstance(data, dict):
                raise ValueError("Invalid YAML format: expected a dictionary")
            
            # Confirm before importing
            reply = QMessageBox.question(
                self,
                "Confirm Import",
                "This will replace your current settings and profiles. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # Import profiles if present
            if 'profiles' in data:
                from config.vpn_profiles import VPNProfile
                self.profile_manager.profiles.clear()
                for name, profile_data in data['profiles'].items():
                    profile = VPNProfile.from_dict(profile_data)
                    self.profile_manager.profiles[profile.name] = profile
                self.profile_manager.save_profiles()
                logger.info(f"Imported {len(data['profiles'])} profiles")
            
            # Import settings if present
            if 'settings' in data:
                self.app_settings.settings = data['settings']
                self.app_settings.save_settings()
                logger.info("Imported application settings")
            
            self.imported_successfully = True
            QMessageBox.information(self, "Success", "Settings imported successfully!")
            self.accept()
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            QMessageBox.critical(self, "Error", f"Invalid YAML format:\n{e}")
        except Exception as e:
            logger.error(f"Error importing settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to import settings:\n{e}")
