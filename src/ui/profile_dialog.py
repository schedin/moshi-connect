from typing import Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QPushButton, QLabel, QMessageBox, QWidget
)
from PySide6.QtGui import QIcon

from config.vpn_profiles import VPNProfile, DestinationNetwork


class ProfileConfigDialog(QDialog):
    """Dialog for configuring VPN profile settings"""
    
    def __init__(self, profile: Optional[VPNProfile] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.profile = profile
        self.setup_ui()
        
        if profile:
            self.load_profile_data()
    
    def setup_ui(self) -> None:
        """Setup the dialog UI"""
        self.setWindowTitle("VPN Profile Configuration")
        self.setModal(True)
        self.setFixedSize(500, 400)

        # Set dialog icon
        images_dir = Path(__file__).parent.parent / "images"
        icon_path = images_dir / "moshi-connect.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        layout = QVBoxLayout(self)
        
        # Form layout for profile fields
        form_layout = QFormLayout()
        
        # Profile name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Company VPN")
        form_layout.addRow("Profile Name:", self.name_edit)
        
        # VPN URL
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("e.g., https://vpn.company.com")
        form_layout.addRow("VPN Server URL:", self.url_edit)
        
        layout.addLayout(form_layout)
        
        # Routes section
        routes_label = QLabel("Split Tunnel Routes (optional):")
        routes_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(routes_label)
        
        help_label = QLabel(
            "Enter IP ranges in CIDR notation, one per line.\n"
            "Example: 10.0.0.0/8\n"
            "Leave empty to route all traffic through VPN."
        )
        help_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(help_label)
        
        self.routes_edit = QTextEdit()
        self.routes_edit.setPlaceholderText(
            "10.0.0.0/8\n"
            "192.168.100.0/24\n"
            "172.16.0.0/12"
        )
        self.routes_edit.setMaximumHeight(120)
        layout.addWidget(self.routes_edit)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        self.save_btn.clicked.connect(self.save_profile)
        self.cancel_btn.clicked.connect(self.reject)
    
    def load_profile_data(self) -> None:
        """Load existing profile data into the form"""
        if not self.profile:
            return
        
        self.name_edit.setText(self.profile.name)
        self.url_edit.setText(self.profile.url)
        
        if self.profile.routes:
            routes_text = '\n'.join(repr(route) for route in self.profile.routes)
            self.routes_edit.setPlainText(routes_text)
    
    def save_profile(self) -> None:
        """Validate and save the profile"""
        name = self.name_edit.text().strip()
        url = self.url_edit.text().strip()
        routes_text = self.routes_edit.toPlainText().strip()
        
        # Validation
        if not name:
            QMessageBox.warning(self, "Validation Error", "Profile name is required.")
            return
        
        if not url:
            QMessageBox.warning(self, "Validation Error", "VPN server URL is required.")
            return
        
        # Ensure URL has protocol
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        # Parse routes
        routes: list[DestinationNetwork] = []
        if routes_text:
            for line in routes_text.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):  # Allow comments
                    # Basic CIDR validation
                    if '/' in line:
                        try:
                            routes.append(DestinationNetwork.from_cidr(line))
                        except ValueError as e:
                            QMessageBox.warning(
                                self, "Validation Error", 
                                f"Invalid route format: {line}\n"
                                f"Expected CIDR notation (e.g., 10.0.0.0/8)"
                            )
                            return
                    else:
                        QMessageBox.warning(
                            self, "Validation Error",
                            f"Invalid route format: {line}\n"
                            f"Expected CIDR notation (e.g., 10.0.0.0/8)"
                        )
                        return
        
        # Create or update profile
        if self.profile:
            self.profile.name = name
            self.profile.url = url
            self.profile.routes = routes
        else:
            self.profile = VPNProfile(name=name, url=url, routes=routes)
        
        self.accept()
    
    def get_profile(self) -> Optional[VPNProfile]:
        """Get the configured profile"""
        return self.profile
