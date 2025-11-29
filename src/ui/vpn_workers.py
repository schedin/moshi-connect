"""
VPN connection worker threads for GUI.

This module provides worker threads for VPN connection operations and cookie monitoring,
separated from the main GUI code for better organization and maintainability.
"""

import logging
from typing import Optional, Dict
from PySide6.QtCore import QThread, Signal, QObject, QTimer
from PySide6.QtWidgets import QSystemTrayIcon

from ui.system_tray import SystemTrayManager
from config.vpn_profiles import VPNProfile
from ipc.vpn_connect_interface import VpnConnectManager, VpnStatusCallback, VpnStatus, LogStream, VpnErrorCode
from ipc.service_client import ServiceClient
from ipc.service_interface import ServiceClientInterface
from service.service_impl import SERVICE_FILENAME

import cookie.firefox_cookies as firefox_cookies
import cookie.cookies as cookies

logger = logging.getLogger(__name__)


class VpnSignalEmitter(QObject):
    """Signal emitter for VPN-related events"""
    connection_status_changed = Signal(bool)  # True = connected, False = disconnected (legacy)
    vpn_status_changed = Signal(str, str, dict)  # status, message, data - detailed status info
    cookie_detected = Signal(str)
    service_connection_changed = Signal(bool)  # True = connected to service, False = disconnected from service


class VpnCallbackAdapter(VpnStatusCallback):
    """Adapter that converts VPN manager callbacks to Qt signals"""

    def __init__(self, signal_emitter: VpnSignalEmitter, system_tray_manager: SystemTrayManager):
        self.signal_emitter = signal_emitter
        self.system_tray_manager = system_tray_manager
        self.current_status = VpnStatus.DISCONNECTED

    def on_status_message(self, status: VpnStatus, message: str, data: Optional[Dict[str, str]] = None) -> None:
        """Handle VPN status changes"""
        logger.info(f"VPN status: {status.value} - {message}")

        # Update internal status
        previous_status = self.current_status
        self.current_status = status

        # Emit detailed status signal
        self.signal_emitter.vpn_status_changed.emit(status.value, message, data or {})

        # Convert to legacy Qt signals for backward compatibility
        if status == VpnStatus.CONNECTED and previous_status != VpnStatus.CONNECTED:
            self.signal_emitter.connection_status_changed.emit(True)
            # Show connection success notification
            profile_name = data.get("profile_name", "VPN") if data else "VPN"
            self.system_tray_manager.show_message(
                "VPN Connected",
                f"Successfully connected to {profile_name}",
                QSystemTrayIcon.MessageIcon.Information,
                5000  # 5 seconds
            )
        elif status == VpnStatus.DISCONNECTED and previous_status != VpnStatus.DISCONNECTED:
            self.signal_emitter.connection_status_changed.emit(False)

            # Show tray notification for unexpected disconnections
            if data and data.get("was_error") == "true":
                reason = data.get("reason", "Unknown error")
                self.system_tray_manager.show_message(
                    "VPN Connection Lost",
                    f"VPN disconnected unexpectedly: {reason}",
                    QSystemTrayIcon.MessageIcon.Critical,
                    10000  # 10 seconds
                )
                logger.debug("Tray notification sent")
            else:
                # User-initiated disconnection - no notification needed
                disconnect_reason = data.get("reason", "unknown") if data else "unknown"
                logger.debug(f"VPN disconnected normally (reason: {disconnect_reason}) - no tray notification")

    def on_command_output(self, line: str, stream: LogStream, process_name: str) -> None:
        """Handle STDOUT/STDERR output from external commands"""
        # Log subprocess output with appropriate level based on stream
        if stream == LogStream.STDERR:
            logger.warning(f"[{process_name}] {line}")
        else:
            logger.info(f"[{process_name}] {line}")

    def on_service_log(self, level: int, message: str, logger_name: str) -> None:
        """Handle normal Python logging from the service"""
        # Re-emit service logs through local logging with original level
        logger.log(level, f"[service] {message}")

    def on_error(self, error_message: str, error_code: VpnErrorCode, details: Optional[str] = None) -> None:
        """Handle error conditions"""
        error_msg = f"VPN error [{error_code.value}]: {error_message}"
        if details:
            error_msg += f" - {details}"
        logger.error(error_msg)

        # Emit disconnected status on errors
        if self.current_status != VpnStatus.DISCONNECTED:
            self.current_status = VpnStatus.DISCONNECTED
            self.signal_emitter.connection_status_changed.emit(False)


class VPNConnectionWorker(QThread):
    """Worker thread for VPN connection operations"""

    def __init__(self, profile: VPNProfile, cookie: str, vpn_connect_manager: VpnConnectManager):
        super().__init__()
        self.profile = profile
        self.cookie = cookie
        self.should_stop = False
        self.vpn_connect_manager = vpn_connect_manager


    def run(self) -> None:
        """Run VPN connection in background thread"""
        try:
            if not self.should_stop:
                logger.info(f"Starting VPN connection to {self.profile.name}")
                # The VPN manager will handle all status updates via its callback
                self.vpn_connect_manager.connect(self.profile, self.cookie)
            else:
                logger.info("VPN connection cancelled before starting")
        except Exception as e:
            logger.error(f"VPN connection error: {e}")

    def stop(self) -> None:
        """Request the worker to stop"""
        self.should_stop = True
        logger.debug("VPN connection worker stop requested")


class CookieMonitorWorker(QThread):
    """Worker thread for monitoring cookies"""

    def __init__(self, initial_cookies: list[str], signal_emitter: VpnSignalEmitter):
        super().__init__()
        self.initial_cookies = initial_cookies
        self.signal_emitter = signal_emitter
        self.should_stop = False

    def run(self) -> None:
        """Monitor for new webvpn cookies with proper cancellation support"""
        logger.debug("Starting cookie monitoring (cancellable)")

        try:
            cookie = cookies.get_vpn_cookie(
                self.initial_cookies,
                should_stop_callback=lambda: self.should_stop
            )

            # Emit signal if cookie found and not cancelled
            if cookie and not self.should_stop:
                logger.info("VPN cookie detected from Firefox")
                self.signal_emitter.cookie_detected.emit(cookie)
            elif self.should_stop:
                logger.debug("Cookie monitoring cancelled by user")
            else:
                logger.warning("No VPN cookie detected")
                
        except Exception as e:
            logger.error(f"Cookie monitoring error: {e}")

    def stop(self) -> None:
        """Request the worker to stop"""
        self.should_stop = True
        logger.debug("Cookie monitor worker stop requested")


class DisconnectWorker(QThread):
    """Worker thread for VPN disconnection to prevent UI blocking"""

    def __init__(self, vpn_connect_manager: VpnConnectManager):
        super().__init__()
        self.vpn_connect_manager = vpn_connect_manager

    def run(self) -> None:
        """Perform VPN disconnection in background thread"""
        try:
            logger.info("Starting VPN disconnection in background thread")
            # The VPN manager will handle all status updates via its callback
            self.vpn_connect_manager.disconnect()
        except Exception as e:
            logger.error(f"VPN disconnection failed: {e}")


class VpnConnectionManager:
    """
    Manager class for VPN connection operations and worker threads.

    This class provides a high-level interface for managing VPN connections,
    including starting/stopping workers and handling their lifecycle.
    """

    def __init__(self, signal_emitter: VpnSignalEmitter, system_tray_manager: SystemTrayManager):
        self.signal_emitter = signal_emitter
        self.vpn_worker: Optional[VPNConnectionWorker] = None
        self.cookie_worker: Optional[CookieMonitorWorker] = None
        self.disconnect_worker: Optional[DisconnectWorker] = None
        self.is_connected = False
        self.is_service_connected = False
        self.callback_adapter = VpnCallbackAdapter(signal_emitter, system_tray_manager)
        self._service_client: ServiceClientInterface = ServiceClient(self.callback_adapter, SERVICE_FILENAME)

        # Try initial connection to service
        self._try_connect_to_service()

        # Set up periodic reconnection timer (every 5 seconds)
        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self._try_connect_to_service)
        self.reconnect_timer.start(5000)  # 5 seconds

    def _try_connect_to_service(self) -> None:
        """Try to connect to the background IPC service and emit signal with current status"""
        was_connected = self.is_service_connected

        # Try to connect if not already connected
        if not self._service_client.is_service_connected():
            self._service_client.connect_to_service()

        # Check current status
        is_now_connected = self._service_client.is_service_connected()

        # Update state and emit signal (always emit to ensure UI stays in sync)
        self.is_service_connected = is_now_connected
        self.signal_emitter.service_connection_changed.emit(is_now_connected)

        # Log only when status changes to avoid log spam
        if was_connected != is_now_connected:
            if is_now_connected:
                logger.info("Successfully connected background IPC service")
            else:
                logger.warning("Disconnected from background IPC service")

    def start_connection(self, profile: VPNProfile, cookie: str) -> None:
        """Start VPN connection with given profile and cookie"""
        # Stop any existing connection
        self.stop_connection()

        logger.info(f"Starting VPN connection to {profile.name}")
        self.vpn_worker = VPNConnectionWorker(profile, cookie, self._service_client.get_vpn_connect_manager())
        self.vpn_worker.start()
    
    def start_cookie_monitoring(self, initial_cookies: Optional[list[str]]=None) -> None:
        """Start cookie monitoring for automatic authentication"""
        # Stop any existing monitoring
        self.stop_cookie_monitoring()
        
        if initial_cookies is None:
            # TODO: Add cookie host filter
            initial_cookies = firefox_cookies.get_webvpn_cookies() or []
        
        logger.debug(f"Starting cookie monitoring with {len(initial_cookies)} initial cookies")
        self.cookie_worker = CookieMonitorWorker(initial_cookies, self.signal_emitter)
        self.cookie_worker.start()
    
    def stop_connection(self) -> None:
        """Stop VPN connection and cleanup worker"""
        if self.vpn_worker:
            logger.info("Stopping VPN connection worker")
            self.vpn_worker.stop()
            if not self.vpn_worker.wait(3000):  # Wait max 3 seconds
                logger.warning("VPN worker did not stop gracefully, terminating...")
                self.vpn_worker.terminate()
                self.vpn_worker.wait(1000)
            self.vpn_worker = None
    
    def stop_cookie_monitoring(self) -> None:
        """Stop cookie monitoring and cleanup worker"""
        if self.cookie_worker:
            logger.debug("Stopping cookie monitoring worker")
            self.cookie_worker.stop()
            if not self.cookie_worker.wait(3000):  # Wait max 3 seconds
                logger.warning("Cookie worker did not stop gracefully, terminating...")
                self.cookie_worker.terminate()
                self.cookie_worker.wait(1000)
            self.cookie_worker = None
    
    def disconnect_vpn(self) -> None:
        """Disconnect VPN and stop all workers (asynchronously)"""
        logger.info("Starting VPN disconnection")

        # Stop workers immediately
        self.stop_connection()
        self.stop_cookie_monitoring()

        # Start disconnect worker thread to avoid UI blocking
        if self.disconnect_worker and self.disconnect_worker.isRunning():
            logger.warning("Disconnect already in progress")
            return

        self.disconnect_worker = DisconnectWorker(self._service_client.get_vpn_connect_manager())
        self.disconnect_worker.finished.connect(self._on_disconnect_worker_finished)
        self.disconnect_worker.start()

    def _on_disconnect_worker_finished(self) -> None:
        """Handle disconnect worker completion"""
        logger.debug("Disconnect worker finished")

        # Clean up worker
        if self.disconnect_worker:
            self.disconnect_worker.deleteLater()
            self.disconnect_worker = None
    
    def cleanup(self) -> None:
        """Cleanup all workers and resources"""
        logger.info("Cleaning up VPN connection manager")

        # Stop reconnection timer
        if self.reconnect_timer:
            self.reconnect_timer.stop()

        self.stop_connection()
        self.stop_cookie_monitoring()
    
    def set_connected(self, connected: bool) -> None:
        """Set the connection status"""
        self.is_connected = connected

    def get_connected(self) -> bool:
        """Get the current connection status"""
        return self.is_connected

    def query_status(self) -> None:
        """Query current VPN status from the manager"""
        self._service_client.get_vpn_connect_manager().query_status()
