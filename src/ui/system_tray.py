"""
System tray functionality for the application.

This module provides system tray icon management with context menu and
connection status updates.
"""

import logging
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QAction
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class SystemTrayManager(QObject):
    """
    Manager for system tray icon and related functionality.
    
    Provides a system tray icon with context menu for quick access to
    VPN connection controls and application management.
    """
    
    # Signals for tray actions
    show_window_requested = Signal()
    connect_requested = Signal()
    disconnect_requested = Signal()
    quit_requested = Signal()
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.tray_icon: Optional[QSystemTrayIcon] = None
        self.tray_connect_action: QAction
        self.tray_disconnect_action: QAction
        self.is_connected = False

        # Load icons
        self.load_icons()
        self.setup_tray_icon()

    def load_icons(self) -> None:
        """Load the application icons"""
        # Get the path to the images directory (relative to the src directory)
        images_dir = Path(__file__).parent.parent.parent / "images"

        # Load disconnected icon
        disconnected_icon_path = images_dir / "moshi-connect.ico"
        if disconnected_icon_path.exists():
            self.disconnected_icon = QIcon(str(disconnected_icon_path))
            logger.debug(f"Loaded disconnected icon: {disconnected_icon_path}")
        else:
            # Fallback to a simple pixmap
            pixmap = QPixmap(32, 32)
            pixmap.fill()
            self.disconnected_icon = QIcon(pixmap)
            logger.warning(f"Disconnected icon not found: {disconnected_icon_path}")

        # Load connected icon
        connected_icon_path = images_dir / "moshi-connect_connected.ico"
        if connected_icon_path.exists():
            self.connected_icon = QIcon(str(connected_icon_path))
            logger.debug(f"Loaded connected icon: {connected_icon_path}")
        else:
            # Fallback to the disconnected icon
            self.connected_icon = self.disconnected_icon
            logger.warning(f"Connected icon not found: {connected_icon_path}")
    
    def setup_tray_icon(self) -> None:
        """Setup system tray icon and context menu"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray is not available")
            return

        # Create tray icon with the disconnected icon
        self.tray_icon = QSystemTrayIcon(self.disconnected_icon, self.parent())
        
        # Create tray menu
        tray_menu = QMenu()
        
        # Show window action
        show_action = QAction("Open App", self)
        show_action.triggered.connect(self.show_window_requested.emit)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        # Connect action
        self.tray_connect_action = QAction("Connect", self)
        self.tray_connect_action.triggered.connect(self.connect_requested.emit)
        tray_menu.addAction(self.tray_connect_action)
        
        # Disconnect action
        self.tray_disconnect_action = QAction("Disconnect", self)
        self.tray_disconnect_action.triggered.connect(self.disconnect_requested.emit)
        self.tray_disconnect_action.setVisible(False)
        tray_menu.addAction(self.tray_disconnect_action)
        
        tray_menu.addSeparator()
        
        # Quit action
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_requested.emit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        
        # Show the tray icon
        self.tray_icon.show()
        logger.debug("System tray icon created and shown")
    
    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            logger.debug("System tray icon single-clicked")
            self.show_window_requested.emit()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            logger.debug("System tray icon double-clicked")
            self.show_window_requested.emit()
    
    def update_connection_status(self, connected: bool) -> None:
        """Update tray menu based on connection status"""
        self.is_connected = connected

        if self.tray_icon:
            self.tray_connect_action.setVisible(not connected)
            self.tray_disconnect_action.setVisible(connected)

            # Update icon based on connection status
            icon = self.connected_icon if connected else self.disconnected_icon
            self.tray_icon.setIcon(icon)

            # Update tooltip
            status = "Connected" if connected else "Disconnected"
            self.tray_icon.setToolTip(f"Moshi Connect - {status}")

            logger.debug(f"System tray updated for connection status: {status}")
    
    def show_message(self, title: str, message: str, icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information, timeout: int = 5000) -> None:
        """Show a system tray notification message"""
        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(title, message, icon, timeout)
            logger.debug(f"System tray message shown: {title} - {message}")
    
    def is_available(self) -> bool:
        """Check if system tray is available"""
        return QSystemTrayIcon.isSystemTrayAvailable()
    
    def is_visible(self) -> bool:
        """Check if tray icon is visible"""
        return self.tray_icon is not None and self.tray_icon.isVisible()
    
    def hide(self) -> None:
        """Hide the system tray icon"""
        if self.tray_icon:
            self.tray_icon.hide()
            logger.debug("System tray icon hidden")
    
    def show(self) -> None:
        """Show the system tray icon"""
        if self.tray_icon:
            self.tray_icon.show()
            logger.debug("System tray icon shown")
    
    def cleanup(self) -> None:
        """Cleanup system tray resources"""
        if self.tray_icon:
            self.tray_icon.hide()
            self.tray_icon = None
            logger.debug("System tray cleaned up")
