"""
Implementation of VpnConnectManager interface that manages VPN connections
using OpenConnect.
"""

import sys
import threading
import subprocess
import logging
from typing import Optional, List, Dict, Match

from utils.subprocess_logger import SubprocessReader, PatternMatcher
from service.route_manager import RouteManager
from service.openconnect_finder import find_openconnect
from config.vpn_profiles import VPNProfile
from ipc.vpn_connect_interface import VpnStatusCallback, VpnStatus, LogStream, VpnErrorCode, VpnConnectManager

logger = logging.getLogger(__name__)


class VpnConnectManagerImpl(VpnConnectManager):
    def __init__(self, callback: VpnStatusCallback) -> None:
        self.callback = callback
        self.current_vpn_url: Optional[str] = None
        self.current_profile: Optional[VPNProfile] = None
        self.route_manager: Optional[RouteManager] = None
        self.vpn_process: Optional[subprocess.Popen[str]] = None
        self.subprocess_reader: Optional[SubprocessReader] = None
        self.current_status: VpnStatus = VpnStatus.DISCONNECTED
        self._lock = threading.Lock()

    def connect(self, profile: VPNProfile, cookie: str) -> None:
        """Start VPN connection asynchronously"""
        with self._lock:
            if self.current_status in [VpnStatus.CONNECTING, VpnStatus.CONNECTED]:
                self.callback.on_error(
                    "Connection already in progress or established",
                    VpnErrorCode.UNKNOWN_ERROR,
                    f"Current status: {self.current_status.value}"
                )
                return

            self.current_profile = profile
            self.current_vpn_url = profile.url
            self.route_manager = RouteManager(profile.routes or [])
            self._set_status(VpnStatus.CONNECTING, f"Starting connection to {profile.name}", {
                "vpn_url": profile.url,
                "profile_name": profile.name
            })

        # Start connection in background thread
        threading.Thread(target=self._connect_worker, args=(profile, cookie), daemon=True).start()

    def _connect_worker(self, profile: VPNProfile, cookie: str) -> None:
        """Worker thread for VPN connection"""
        try:
            # Find OpenConnect executable
            openconnect_path = find_openconnect()
            if not openconnect_path:
                self._handle_connection_error("OpenConnect executable not found", VpnErrorCode.OPENCONNECT_NOT_FOUND)
                return
            else:
                logger.info(f"Using OpenConnect at: {openconnect_path}")

            # Start OpenConnect process
            cmd = [str(openconnect_path), profile.url, "--cookie", cookie]
            self._log_command(cmd)

            creationflags = 0
            if sys.platform == "win32":
                creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
                creationflags |= subprocess.CREATE_NO_WINDOW  # <- hides the console of openconnect.exe

            try:
                self.vpn_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=creationflags,
                )
            except Exception as e:
                self._handle_connection_error(f"Failed to start OpenConnect: {e}", VpnErrorCode.NETWORK_ERROR, str(e))
                return

            # Set up subprocess monitoring
            self._setup_subprocess_monitoring()

        except Exception as e:
            self._handle_connection_error(f"Unexpected error during connection: {e}", VpnErrorCode.UNKNOWN_ERROR, str(e))


    def _log_command(self, cmd: List[str]) -> None:
        """Log the command being executed (masking sensitive data)"""
        masked_cmd = cmd[:-1] + ["***"]  # Mask the cookie
        logger.info(f"Executing command: {' '.join(masked_cmd)}")

    def _setup_subprocess_monitoring(self) -> None:
        """Set up monitoring of OpenConnect subprocess"""
        if not self.vpn_process:
            return

        # Pattern for detecting successful connection
        # Handles TAP-Windows format: "Using TAP-Windows device 'name', index N"
        # Wintun format: "Using Wintun device 'name', index N"
        # and other formats: "Using TAP device 'name', index N"
        connected_pattern = r"Using (?P<devicename>[\w-]+) device '(?P<name>[^']+)', index (?P<index>\d+)"

        def on_connection_established(line: str, match: Match[str]) -> None:
            device_name = match.group('name')
            device_type = match.group('devicename')
            device_index = match.group('index')

            logger.info(f"Connection established: {device_type} device '{device_name}', index {device_index}")

            # Update status to connected
            profile_name = self.current_profile.name if self.current_profile else None
            self._set_status(VpnStatus.CONNECTED, f"Connected to {profile_name}", {
                "device_name": device_name,
                "device_type": device_type,
                "device_index": device_index,
                "vpn_url": self.current_vpn_url or ""
            })

            # Apply custom routes if needed
            if self.route_manager and self.route_manager.routes:
                # Sleep to allow for the connection to finish setting up, before applying routes
                import time
                time.sleep(2)
                logger.info(f"Applying {len(self.route_manager.routes)} custom routes for split tunneling")
                try:
                    self.route_manager.apply_routes(device_index)
                except Exception as e:
                    logger.warning(f"Failed to apply some routes: {e}")
            else:
                logger.info("No custom routes specified, using default OpenConnect routing")

        pattern_matcher = PatternMatcher(connected_pattern, on_connection_established)

        # Create command output handlers - these forward raw output to client
        def stdout_handler(line: str) -> None:
            self.callback.on_command_output(line, LogStream.STDOUT, "openconnect")

        def stderr_handler(line: str) -> None:
            self.callback.on_command_output(line, LogStream.STDERR, "openconnect")

        # Start subprocess reader with pattern matching on stdout
        from utils.subprocess_logger import DemultiplexerLineConsumer
        stdout_with_pattern = DemultiplexerLineConsumer(stdout_handler, pattern_matcher.create_handler())
        stderr_with_pattern = DemultiplexerLineConsumer(stderr_handler, pattern_matcher.create_handler())

        self.subprocess_reader = SubprocessReader(
            stdout=self.vpn_process.stdout,
            stderr=self.vpn_process.stderr,
            stdout_handler=stdout_with_pattern,
            stderr_handler=stderr_with_pattern,
            process_name="openconnect"
        )
        self.subprocess_reader.start()

        # Monitor process in background
        threading.Thread(target=self._monitor_process, daemon=True).start()

    def _monitor_process(self) -> None:
        """Monitor the OpenConnect process for unexpected termination"""
        if not self.vpn_process:
            return

        try:
            # Wait for process to complete
            exit_code = self.vpn_process.wait()

            # Process has terminated
            with self._lock:
                if self.current_status == VpnStatus.DISCONNECTING:
                    # Expected termination
                    self._set_status(VpnStatus.DISCONNECTED, "VPN disconnected successfully", {
                        "reason": "user_requested",
                        "was_error": "false"
                    })
                else:
                    # Unexpected termination
                    reason = f"OpenConnect process terminated unexpectedly (exit code: {exit_code})"
                    self._set_status(VpnStatus.DISCONNECTED, reason, {
                        "reason": reason,
                        "was_error": "true"
                    })

                self._cleanup_connection()

        except Exception as e:
            self._handle_connection_error(f"Error monitoring process: {e}", VpnErrorCode.UNKNOWN_ERROR, str(e))

    def _handle_connection_error(self, message: str, error_code: VpnErrorCode, details: Optional[str] = None) -> None:
        """Handle connection errors"""
        logger.warning(f"{message}")
        with self._lock:
            self.callback.on_error(message, error_code, details)

            self._set_status(VpnStatus.DISCONNECTED, f"Connection failed: {message}", {
                "reason": message,
                "was_error": "true"
            })

            self._cleanup_connection()

    def _set_status(self, status: VpnStatus, message: str, data: Optional[Dict[str, str]] = None) -> None:
        """Update status and notify callback"""
        self.current_status = status
        self.callback.on_status_message(status, message, data)

    def _cleanup_connection(self) -> None:
        """Clean up connection resources (must be called with lock held)"""
        if self.subprocess_reader:
            self.subprocess_reader.stop()
            self.subprocess_reader = None

        self.vpn_process = None
        self.current_vpn_url = None
        self.current_profile = None

    def disconnect(self) -> None:
        """Start VPN disconnection asynchronously"""
        with self._lock:
            if self.current_status == VpnStatus.DISCONNECTED:
                self.callback.on_status_message(VpnStatus.DISCONNECTED, "Already disconnected", {
                    "reason": "already_disconnected",
                    "was_error": "false"
                })
                return

            if self.current_status == VpnStatus.DISCONNECTING:
                self.callback.on_error("Disconnection already in progress", VpnErrorCode.UNKNOWN_ERROR)
                return

            self._set_status(VpnStatus.DISCONNECTING, "Starting VPN disconnection", {
                "reason": "user_requested"
            })

        # Start disconnection in background thread
        threading.Thread(target=self._disconnect_worker, daemon=True).start()

    def _disconnect_worker(self) -> None:
        """Worker thread for VPN disconnection"""
        try:
            logger.info("Disconnecting VPN")

            # Clean up routes first
            if self.route_manager:
                try:
                    self.route_manager.cleanup_routes()
                    logger.info("Custom routes cleaned up")
                except Exception as e:
                    logger.warning(f"Failed to clean up some routes: {e}")

            # Terminate OpenConnect process
            vpn_process = self.vpn_process
            if vpn_process and vpn_process.poll() is None:
                self._terminate_openconnect_process(vpn_process)
            else:
                # Process already terminated
                with self._lock:
                    self._set_status(VpnStatus.DISCONNECTED, "VPN disconnected successfully", {
                        "reason": "user_requested",
                        "was_error": "false"
                    })
                    self._cleanup_connection()

        except Exception as e:
            self._handle_connection_error(f"Error during disconnection: {e}", VpnErrorCode.UNKNOWN_ERROR, str(e))

    def _terminate_openconnect_process(self, vpn_process: subprocess.Popen[str]) -> None:
        """Terminate OpenConnect process gracefully"""
        try:
            logger.info("Attempting graceful OpenConnect termination")
            vpn_process.terminate()

            # Wait for shutdown
            vpn_process.wait(timeout=3)
            logger.info("OpenConnect terminated gracefully via terminate()")

        except subprocess.TimeoutExpired:
            logger.warning("OpenConnect did not terminate gracefully, forcing kill")
            try:
                # Force kill as last resort
                vpn_process.kill()
                vpn_process.wait(timeout=2)
                logger.warning("OpenConnect force-killed")
            except Exception as e:
                logger.error(f"Error force-killing OpenConnect: {e}")
        except Exception as e:
            logger.error(f"Error during graceful termination: {e}")

    def query_status(self) -> None:
        """Query current VPN status asynchronously"""
        with self._lock:
            status = self.current_status

            if status == VpnStatus.CONNECTED and self.current_profile:
                # For connected status, include connection details
                data = {
                    "vpn_url": self.current_vpn_url or "",
                    "profile_name": self.current_profile.name
                }
                # Try to get device info if available
                if self.vpn_process and self.vpn_process.poll() is None:
                    message = f"Connected to {self.current_profile.name}"
                else:
                    # Process died but we haven't detected it yet
                    status = VpnStatus.DISCONNECTED
                    message = "Connection lost"
                    data = {"reason": "process_terminated", "was_error": "true"}
            elif status == VpnStatus.CONNECTING and self.current_profile:
                data = {
                    "vpn_url": self.current_vpn_url or "",
                    "profile_name": self.current_profile.name
                }
                message = f"Connecting to {self.current_profile.name}"
            elif status == VpnStatus.DISCONNECTING:
                data = {"reason": "user_requested"}
                message = "Disconnecting VPN"
            else:  # DISCONNECTED
                data = {"reason": "not_connected", "was_error": "false"}
                message = "VPN is disconnected"

            self.callback.on_status_message(status, message, data)

