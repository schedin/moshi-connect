import sys
import logging
import webbrowser
import signal
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QComboBox, QPushButton, QLineEdit, QLabel, QMessageBox, QFrame, QDialog
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QFont, QCloseEvent

from config.vpn_profiles import VPNProfileManager, VPNProfile
from config.app_settings import AppSettings
from ui.profile_dialog import ProfileConfigDialog
from cookie import cookies

from ui.gui_logging import GuiLogHandler, LogSignalEmitter
from ui.log_display_widget import LogDisplayWidget
from ui.vpn_workers import VpnConnectionManager, VpnSignalEmitter
from ui.system_tray import SystemTrayManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self, config_dir: Path, log_dir: Path):
        super().__init__()

        self.original_flags = self.windowFlags()

        # Initialize managers and settings
        self.profile_manager = VPNProfileManager(config_dir)
        self.settings = AppSettings(config_dir)

        # Initialize signal emitters
        self.log_signal_emitter = LogSignalEmitter()
        self.vpn_signal_emitter = VpnSignalEmitter()

        # Initialize log handler and setup logging FIRST
        self.log_handler = GuiLogHandler(self.log_signal_emitter)
        self.setup_logging()

        # Connection state (initialize before creating VPN manager)
        self.is_connected = False
        self.is_connecting = False  # Track if we're in the process of connecting
        self.is_waiting_for_cookie = False  # Track if we're waiting for cookie input/detection
        self.connecting_profile: Optional[VPNProfile] = None  # Store the profile we're connecting to
        self.is_service_connected: Optional[bool] = None  # Track service connection state (None = unknown initially)

        # Initialize components (now that GUI logging is active)
        self.system_tray = SystemTrayManager(self)

        self.setup_window_icon()
        self.setup_ui()

        # Connect signals BEFORE creating VPN manager so we don't miss initial connection status
        self.connect_signals()

        # Create VPN manager last - it will immediately try to connect and emit signals
        self.vpn_manager = VpnConnectionManager(self.vpn_signal_emitter, self.system_tray)

        # Ensure cookie input is enabled at startup
        self._enable_cookie_input(True)

        self._update_profile_button_states()
        self._update_connect_button_state()

        logger.debug("MainWindow initialized successfully")


    def setup_window_icon(self) -> None:
        """Setup the main window icon"""
        # Get the path to the images directory
        images_dir = Path(__file__).parent.parent.parent / "images"
        icon_path = images_dir / "moshi-connect.ico"

        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
            logger.debug(f"Set window icon: {icon_path}")
        else:
            logger.warning(f"Window icon not found: {icon_path}")
    
    def setup_logging(self) -> None:
        """Setup logging with custom handler for GUI"""
        self.log_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )

        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        root_logger.setLevel(logging.DEBUG)
    
    def setup_ui(self) -> None:
        """Setup the user interface"""
        self.setWindowTitle("Moshi Connect")
        self.setMinimumSize(750, 500)
        self.resize(750, 500)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)  # Reduce spacing between sections
        
        # VPN Profile section
        profile_layout = QVBoxLayout()
        profile_layout.setSpacing(5)  # Reduce spacing in profile section

        self.profile_combo = QComboBox()
        self.profile_combo.setEditable(False)
        self.profile_combo.currentTextChanged.connect(self.on_profile_selection_changed)

        self.update_profile_combo()

        # Main horizontal layout for profile section
        profile_main_layout = QHBoxLayout()

        # Left side: VPN Profile label and combobox grouped vertically
        profile_input_layout = QVBoxLayout()
        profile_input_layout.setSpacing(5)  # Reduce spacing between label and combobox
        profile_input_layout.addWidget(QLabel("VPN Profile:"))
        profile_input_layout.addWidget(self.profile_combo)
        profile_input_layout.addStretch()  # Push content to top

        # Right side: Profile management buttons grouped vertically
        profile_buttons_layout = QVBoxLayout()
        profile_buttons_layout.setSpacing(5)  # Consistent spacing between buttons

        self.add_profile_btn = QPushButton("Add Profile...")
        self.add_profile_btn.setMaximumWidth(120)
        profile_buttons_layout.addWidget(self.add_profile_btn)

        self.configure_btn = QPushButton("Edit Profile...")
        self.configure_btn.setMaximumWidth(120)
        profile_buttons_layout.addWidget(self.configure_btn)

        self.delete_profile_btn = QPushButton("Delete Profile...")
        self.delete_profile_btn.setMaximumWidth(120)
        profile_buttons_layout.addWidget(self.delete_profile_btn)
        profile_buttons_layout.addStretch()  # Push buttons to top

        profile_main_layout.addLayout(profile_input_layout)
        profile_main_layout.addLayout(profile_buttons_layout)
        profile_main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        profile_layout.addLayout(profile_main_layout)

        # Control buttons - placed right after profile selection
        button_layout = QHBoxLayout()

        self.connect_btn = QPushButton("Connect")
        self.cancel_btn = QPushButton("Cancel")
        self.disconnect_btn = QPushButton("Disconnect")

        self.cancel_btn.setVisible(False)
        self.disconnect_btn.setVisible(False)

        button_layout.addWidget(self.connect_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.disconnect_btn)
        button_layout.addStretch()

        profile_layout.addLayout(button_layout)

        layout.addLayout(profile_layout)

        # Cookie section
        cookie_layout = QVBoxLayout()
        cookie_layout.setSpacing(5)  # Reduce spacing in cookie section

        self.cookie_input = QLineEdit()
        self.cookie_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.cookie_input.setPlaceholderText("Paste webvpn cookie here (optional - auto-detection will be attempted)")
        # Set fixed width to accommodate cookie size like "14112F@584429568@7EE9@A53C0A65D1E56C27DF8233C8FDC4CB24830EAC44"
        self.cookie_input.setFixedWidth(500)
        self.cookie_input.textChanged.connect(self.on_cookie_input_changed)
        cookie_layout.addWidget(QLabel("Session Cookie:"))
        cookie_layout.addWidget(self.cookie_input)

        layout.addLayout(cookie_layout)

        # Log output using our new widget
        self.log_display_widget = LogDisplayWidget(self.log_handler)
        layout.addWidget(self.log_display_widget, 1)  # Give log section stretch factor of 1 to expand

        # VPN Status bar at the bottom (like VS Code status bar)
        self.setup_status_display()
        layout.addWidget(self.status_frame)
        
        # Connect button signals
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        self.cancel_btn.clicked.connect(self.on_cancel_clicked)
        self.disconnect_btn.clicked.connect(self.on_disconnect_clicked)
        self.configure_btn.clicked.connect(self.on_configure_clicked)
        self.add_profile_btn.clicked.connect(self.on_add_profile_clicked)
        self.delete_profile_btn.clicked.connect(self.on_delete_profile_clicked)

    def setup_status_display(self) -> None:
        """Setup the VPN status display widget (VS Code style status bar)"""
        self.status_frame = QFrame()

        # Simple status bar styling (default background)
        self.status_frame.setStyleSheet("""
            QFrame {
                border: none;
            }
            QLabel {
                background-color: transparent;
                padding: 0px;
                margin: 0px;
            }
        """)

        self.status_frame.setFixedHeight(20)  # Slimmer status bar

        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(8, 2, 8, 2)
        status_layout.setSpacing(8)

        # Status indicator (small colored circle)
        self.status_indicator = QLabel("●")
        font = QFont()
        font.setPointSize(10)
        self.status_indicator.setFont(font)
        status_layout.addWidget(self.status_indicator)

        # Status text (compact)
        self.status_text = QLabel("Disconnected")
        font = QFont()
        font.setPointSize(9)
        self.status_text.setFont(font)
        status_layout.addWidget(self.status_text)

        # Status details (smaller, muted)
        self.status_details = QLabel("")
        font = QFont()
        font.setPointSize(8)
        self.status_details.setFont(font)
        status_layout.addWidget(self.status_details)

        status_layout.addStretch()

        # Initialize with disconnected state
        self.update_status_display("disconnected", "VPN is disconnected", {})


    def connect_signals(self) -> None:
        """Connect internal signals"""
        # VPN signals
        self.vpn_signal_emitter.connection_status_changed.connect(self.on_connection_status_changed)
        self.vpn_signal_emitter.vpn_status_changed.connect(self.on_vpn_status_changed)
        self.vpn_signal_emitter.cookie_detected.connect(self.on_cookie_detected)
        self.vpn_signal_emitter.service_connection_changed.connect(self.on_service_connection_changed)

        # System tray signals
        self.system_tray.show_window_requested.connect(self.show_window)
        self.system_tray.connect_requested.connect(self.on_connect_clicked)
        self.system_tray.disconnect_requested.connect(self.on_disconnect_clicked)
        self.system_tray.quit_requested.connect(self.quit_application)

    def update_profile_combo(self) -> None:
        """Update the profile combo box with available profiles"""
        self.profile_combo.clear()
        for profile_name in self.profile_manager.get_profile_names():
            self.profile_combo.addItem(profile_name)

        if hasattr(self, 'add_profile_btn'):
            self._update_profile_button_states()
        if hasattr(self, 'connect_btn'):
            self._update_connect_button_state()

        # Restore last selected profile if available
        last_selected = self.settings.get_last_selected_profile()
        if last_selected:
            index = self.profile_combo.findText(last_selected)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
                logger.debug(f"Restored last selected profile: {last_selected}")
            else:
                # Profile was deleted, clear the setting
                self.settings.set_last_selected_profile("")

    def on_profile_selection_changed(self, text: str) -> None:
        """Handle profile selection change"""
        # Only save if it's an existing profile (not just typed text)
        if text and text in self.profile_manager.get_profile_names():
            self.settings.set_last_selected_profile(text)

    def on_cookie_input_changed(self, text: str) -> None:
        """Handle cookie input field changes - stop monitoring and continue connection if complete cookie is pasted"""
        text = text.strip()

        # If user has typed a substantial cookie (more than 10 chars), stop cookie monitoring
        if len(text) > 10:
            logger.debug("Manual cookie detected, stopping browser cookie monitoring")
            self.vpn_manager.stop_cookie_monitoring()

            # If we're waiting for a cookie or connecting and this looks like a complete cookie, continue the connection
            if (self.is_waiting_for_cookie or self.is_connecting) and self.connecting_profile and self._is_complete_cookie(text):
                logger.info(f"Complete cookie pasted during connection, continuing with VPN connection")
                logger.info(f"Using manually pasted cookie: {cookies.mask_cookie(text)}")

                # Reset waiting state if we were waiting
                if self.is_waiting_for_cookie:
                    self.is_waiting_for_cookie = False

                self._enable_cookie_input(False)

                # Start the VPN connection with the pasted cookie
                self.start_vpn_connection(self.connecting_profile, text)

    def _enable_cookie_input(self, enabled: bool = True) -> None:
        """Enable or disable the cookie input field"""
        self.cookie_input.setEnabled(enabled)
        if enabled:
            logger.debug("Cookie input field enabled")
        else:
            logger.debug("Cookie input field disabled")

    def _update_profile_button_states(self) -> None:
        """Update the enable/disable state of profile management buttons"""
        has_profiles = len(self.profile_manager.get_profile_names()) > 0

        self.add_profile_btn.setEnabled(True)

        # Edit and Delete buttons are only enabled when profiles exist
        self.configure_btn.setEnabled(has_profiles)
        self.delete_profile_btn.setEnabled(has_profiles)

        logger.debug(f"Profile buttons updated: has_profiles={has_profiles}")

    def _update_connect_button_state(self) -> None:
        """Update the enable/disable state of the Connect button"""
        has_profiles = len(self.profile_manager.get_profile_names()) > 0

        # Connect button is only enabled when profiles exist and we're not connecting/connected
        should_enable = has_profiles and not self.is_connecting and not self.is_connected
        self.connect_btn.setEnabled(should_enable)

        logger.debug(f"Connect button updated: enabled={should_enable} (has_profiles={has_profiles}, is_connecting={self.is_connecting}, is_connected={self.is_connected})")

    def _is_complete_cookie(self, text: str) -> bool:
        """Check if the text looks like a complete webvpn cookie"""
        text = text.strip()

        # Basic checks for a valid webvpn cookie
        # Typical format: alphanumeric with @ symbols, like "14112F@584429568@7EE9@A53C0A65D1E56C27DF8233C8FDC4CB24830EAC44"
        if len(text) < 30:  # Too short to be a complete cookie
            return False

        if len(text) > 200:  # Too long to be a typical cookie
            return False

        # Should contain mostly alphanumeric characters and @ symbols
        allowed_chars = set('0123456789ABCDEFabcdef@')
        if not all(c in allowed_chars for c in text):
            return False

        # Should contain at least one @ symbol (typical webvpn cookie format)
        if '@' not in text:
            return False

        return True

    def get_current_profile(self) -> Optional[VPNProfile]:
        """Get the currently selected profile"""
        profile_text = self.profile_combo.currentText().strip()
        if not profile_text:
            return None

        # Return the existing profile (combobox is no longer editable)
        return self.profile_manager.get_profile(profile_text)

    def on_configure_clicked(self) -> None:
        """Handle configure profile button click"""
        current_text = self.profile_combo.currentText().strip()

        # Get existing profile or create new one
        profile = None
        if current_text:
            profile = self.profile_manager.get_profile(current_text)
            if not profile:
                if current_text.startswith(('http://', 'https://')):
                    url = current_text
                    name = current_text.split('//')[1].split('/')[0]
                else:
                    url = f"https://{current_text}"
                    name = current_text
                profile = VPNProfile(name=name, url=url, routes=[])

        # Open configuration dialog
        dialog = ProfileConfigDialog(profile, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            configured_profile = dialog.get_profile()
            if configured_profile:
                # Save the profile
                self.profile_manager.add_profile(configured_profile)

                self.update_profile_combo()
                index = self.profile_combo.findText(configured_profile.name)
                if index >= 0:
                    self.profile_combo.setCurrentIndex(index)

    def on_add_profile_clicked(self) -> None:
        """Handle add profile button click"""
        # Open configuration dialog for new profile
        dialog = ProfileConfigDialog(None, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_profile = dialog.get_profile()
            if new_profile:
                # Save the profile
                self.profile_manager.add_profile(new_profile)

                self.update_profile_combo()
                index = self.profile_combo.findText(new_profile.name)
                if index >= 0:
                    self.profile_combo.setCurrentIndex(index)

                logger.info(f"Added new profile: {new_profile.name}")

    def on_delete_profile_clicked(self) -> None:
        """Handle delete profile button click"""
        current_text = self.profile_combo.currentText().strip()

        if not current_text:
            return  # Button should be disabled when no profile is selected

        # Check if it's an existing profile
        if current_text not in self.profile_manager.get_profile_names():
            return  # Button should be disabled when no valid profile is selected

        if self.profile_manager.remove_profile(current_text):
            self.update_profile_combo()

            # Clear the last selected profile setting if it was the deleted one
            if self.settings.get_last_selected_profile() == current_text:
                self.settings.set_last_selected_profile("")

            logger.info(f"Deleted profile: {current_text}")
        else:
            logger.error(f"Failed to delete profile: {current_text}")

    def on_connect_clicked(self) -> None:
        """Handle connect button click"""
        profile = self.get_current_profile()
        if not profile:
            QMessageBox.warning(self, "Error", "Please enter a VPN server address")
            return

        # Save the selected profile as the last used
        self.settings.set_last_selected_profile(profile.name)

        logger.info(f"Starting connection to {profile.name}")

        # Store connecting profile for reference
        self.connecting_profile = profile

        # Check if user provided manual cookie
        manual_cookie = self.cookie_input.text().strip()
        if manual_cookie:
            logger.info("Using manually provided cookie")
            # Stop any existing cookie monitoring since we have a manual cookie
            self.vpn_manager.stop_cookie_monitoring()
            self.start_vpn_connection(profile, manual_cookie)
        else:
            # Enter waiting for cookie state
            self.is_waiting_for_cookie = True
            self.update_status_display("waiting_for_cookie", "Waiting for cookie", {"profile_name": profile.name})

            # Update UI for waiting state
            self.connect_btn.setVisible(False)
            self.cancel_btn.setVisible(True)
            self.disconnect_btn.setVisible(False)

            # Open browser and start cookie monitoring
            logger.info("Opening browser for authentication")
            webbrowser.open(profile.url)

            # Start cookie monitoring using the VPN manager
            self.vpn_manager.start_cookie_monitoring()

    def on_cancel_clicked(self) -> None:
        """Handle cancel button click"""
        if self.is_waiting_for_cookie:
            logger.info("User cancelled waiting for cookie")
            # Stop cookie monitoring
            self.vpn_manager.stop_cookie_monitoring()
            # Reset waiting state
            self.is_waiting_for_cookie = False
            self.update_status_display("disconnected", "VPN is disconnected", {})
        else:
            logger.info("User cancelled connection attempt")
            # Stop any ongoing VPN operations
            self.vpn_manager.stop_connection()
            self.vpn_manager.stop_cookie_monitoring()

        # Reset connection state
        self.is_connecting = False
        self.connecting_profile = None

        # Re-enable cookie input field
        self._enable_cookie_input(True)
        self._update_connect_button_state()

        # Reset UI state
        self.connect_btn.setVisible(True)
        self.cancel_btn.setVisible(False)
        self.disconnect_btn.setVisible(False)
        self.update_tray_menu_visibility()

        logger.info("Operation cancelled successfully")

    def on_disconnect_clicked(self) -> None:
        """Handle disconnect button click"""
        logger.info("User requested VPN disconnection")

        # Start asynchronous disconnection (status will be updated via signal)
        self.vpn_manager.disconnect_vpn()

    def start_vpn_connection(self, profile: VPNProfile, cookie: str) -> None:
        """Start VPN connection with given profile and cookie"""
        self.vpn_manager.start_connection(profile, cookie)

    def on_cookie_detected(self, cookie: str) -> None:
        """Handle detected cookie from Firefox"""
        logger.info("Cookie detected, starting VPN connection")

        # Stop cookie monitoring (handled by VPN manager)
        self.vpn_manager.stop_cookie_monitoring()

        # Reset waiting state if we were waiting
        if self.is_waiting_for_cookie:
            self.is_waiting_for_cookie = False

        # Get current profile and start connection
        profile = self.get_current_profile()
        if profile:
            self.start_vpn_connection(profile, cookie)

    def on_connection_status_changed(self, connected: bool) -> None:
        """Handle VPN connection status change"""
        self.is_connected = connected

        if connected:
            logger.info("VPN connection established")
            # Reset connecting state since we're now connected
            self.is_connecting = False
            self.connecting_profile = None

            self.connect_btn.setVisible(False)
            self.cancel_btn.setVisible(False)
            self.disconnect_btn.setVisible(True)
            self.disconnect_btn.setText("Disconnect")
            self.disconnect_btn.setEnabled(True)
        else:
            logger.info("VPN disconnected")
            # Reset connecting state since we're now disconnected
            self.is_connecting = False
            self.connecting_profile = None

            # Re-enable cookie input field for next connection
            self._enable_cookie_input(True)

            self.connect_btn.setVisible(True)
            self.cancel_btn.setVisible(False)
            self.disconnect_btn.setVisible(False)
            self.disconnect_btn.setText("Disconnect")
            self.disconnect_btn.setEnabled(True)

        self.update_tray_menu_visibility()
        self.update_profile_combo()
        self._update_connect_button_state()

    def on_service_connection_changed(self, connected: bool) -> None:
        """Handle service connection status change"""
        # Only log and update UI if the status actually changed
        if self.is_service_connected != connected:
            if connected:
                logger.info("GUI reconnected background IPC service")
                # Update status display to show we're connected to service
                if not self.is_connected and not self.is_connecting:
                    self.update_status_display("disconnected", "VPN is disconnected", {})
            else:
                logger.warning("GUI disconnected background IPC service")
                # Update status display to show service is disconnected
                if not self.is_connected and not self.is_connecting:
                    self.update_status_display("service_disconnected", "Disconnected background IPC service (waiting for service to start...)", {})

            # Update tracked state
            self.is_service_connected = connected

    def on_vpn_status_changed(self, status: str, message: str, data: dict) -> None:
        """Handle detailed VPN status changes"""
        self.update_status_display(status, message, data)

        # Update UI state based on status
        if status == "connecting":
            self.is_connecting = True
            self.is_waiting_for_cookie = False  # No longer waiting for cookie
            self.connect_btn.setVisible(False)
            self.cancel_btn.setVisible(True)
            self.disconnect_btn.setVisible(False)
        elif status == "connected":
            self.is_connecting = False
            self.is_waiting_for_cookie = False
            self.is_connected = True
            self.connect_btn.setVisible(False)
            self.cancel_btn.setVisible(False)
            self.disconnect_btn.setVisible(True)
            self.disconnect_btn.setText("Disconnect")
            self.disconnect_btn.setEnabled(True)
            # Disable cookie input when connected
            self._enable_cookie_input(False)
        elif status == "disconnecting":
            self.is_waiting_for_cookie = False
            self.disconnect_btn.setText("Disconnecting...")
            self.disconnect_btn.setEnabled(False)
        elif status == "disconnected":
            self.is_connecting = False
            self.is_waiting_for_cookie = False
            self.is_connected = False
            self.connect_btn.setVisible(True)
            self.cancel_btn.setVisible(False)
            self.disconnect_btn.setVisible(False)
            self.disconnect_btn.setText("Disconnect")
            self.disconnect_btn.setEnabled(True)
            # Re-enable cookie input when disconnected
            self._enable_cookie_input(True)

        self._update_connect_button_state()
        self.update_tray_menu_visibility()

    def update_status_display(self, status: str, message: str, data: dict) -> None:
        """Update the status display widget (VS Code style)"""
        # Define status colors for indicator ball only
        status_config = {
            "waiting_for_cookie": {
                "indicator_color": "#FFD700",  # Gold indicator
                "text": "Waiting for cookie",
                "icon": "●"
            },
            "connecting": {
                "indicator_color": "#FFA500",  # Orange indicator
                "text": "Connecting",
                "icon": "●"
            },
            "connected": {
                "indicator_color": "#00AA00",  # Green indicator
                "text": "Connected",
                "icon": "●"
            },
            "disconnecting": {
                "indicator_color": "#FF6600",  # Dark orange indicator
                "text": "Disconnecting",
                "icon": "●"
            },
            "disconnected": {
                "indicator_color": "#CCCCCC",  # Light gray indicator
                "text": "Disconnected",
                "icon": "●"
            },
            "service_disconnected": {
                "indicator_color": "#FF9900",  # Orange indicator
                "text": "Service Disconnected",
                "icon": "●"
            }
        }

        config = status_config.get(status, status_config["disconnected"])

        # Update status indicator color (only the ball changes color)
        self.status_indicator.setStyleSheet(f"color: {config['indicator_color']};")
        self.status_indicator.setText(config["icon"])
        self.status_text.setText(config["text"])

        # Update status details with muted color (gray for default background)
        self.status_details.setStyleSheet("color: #666666;")

        # Update details based on status and data
        details = ""
        if status == "waiting_for_cookie" and data.get("profile_name"):
            details = f"for {data['profile_name']}"
        elif status == "connecting" and data.get("profile_name"):
            details = f"to {data['profile_name']}"
        elif status == "connected" and data.get("profile_name"):
            device_info = ""
            if data.get("device_name"):
                device_info = f" via {data['device_name']}"
            details = f"to {data['profile_name']}{device_info}"
        elif status == "disconnected" and data.get("reason"):
            reason = data["reason"]
            if reason == "user_requested":
                details = "by user"
            elif reason == "process_terminated":
                details = "connection lost"
            elif reason != "not_connected":
                details = f"({reason})"
        elif status == "service_disconnected":
            details = "Attempting to reconnect..."

        self.status_details.setText(details)

    def update_tray_menu_visibility(self) -> None:
        """Update tray menu item visibility based on connection status"""
        self.system_tray.update_connection_status(self.is_connected)

    def show_window(self) -> None:
        """Show and raise the main window"""
        self.setWindowFlags(self.original_flags | Qt.WindowType.WindowStaysOnTopHint)
        self.show()
        self.setWindowFlags(self.original_flags)
        self.show()        

    def quit_application(self, force_quit: bool = False) -> None:
        """Quit the application"""
        logger.info(f"Quitting application (force_quit={force_quit})")

        if self.is_connected:
            if force_quit:
                # Force quit from signal handler - disconnect without asking
                logger.info("Force quitting - disconnecting VPN without confirmation")
                self.vpn_manager.disconnect_vpn()
            else:
                # Normal quit - ask user
                reply = QMessageBox.question(
                    self, "Quit Application",
                    "VPN is currently connected. Disconnect and quit?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    logger.info("User confirmed - disconnecting VPN")
                    self.vpn_manager.disconnect_vpn()
                else:
                    logger.info("User cancelled quit operation")
                    return

        # Cleanup VPN manager and system tray
        self.vpn_manager.cleanup()
        self.system_tray.cleanup()

        logger.info("Exiting application")
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close event"""
        if self.system_tray.is_visible():
            # Minimize to tray instead of closing
            self.hide()
            event.ignore()
        else:
            event.accept()




def init_gui(config_dir: Path, log_dir: Path) -> tuple[MainWindow, QApplication]:
    """Initialize the GUI and return the main window"""
    app = QApplication()
    app.setQuitOnLastWindowClosed(False)

    images_dir = Path(__file__).parent.parent / "images"
    icon_path = images_dir / "moshi-connect.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
        logger.debug(f"Set application icon: {icon_path}")

    return MainWindow(config_dir, log_dir), app


def start_gui(window: MainWindow, app: QApplication) -> None:
    """Start the GUI application"""
    # This is needed because Qt's event loop can block signal processing
    timer = QTimer()
    timer.timeout.connect(lambda: None)  # Do nothing, just allow signals to be processed
    timer.start(100)  # Check every 100ms

    window.show_window()

    sys.exit(app.exec())
