"""
VPN Client Layer - IPC Client

This module implements the client layer that communicates with the VPN service
via multiprocessing connections and provides the VpnConnectManager interface to the UI.
"""

import logging
import threading
import os
from typing import Optional, Dict, Any
from multiprocessing.connection import Client, Connection

from ipc.vpn_connect_interface import VpnStatusCallback, VpnStatus, LogStream, VpnErrorCode, VpnConnectManager
from ipc.service_interface import ServiceClientInterface
from ipc.json_message import encode_message, decode_message
from config.vpn_profiles import VPNProfile

logger = logging.getLogger(__name__)


class ServiceClient(ServiceClientInterface):
    def __init__(self, vpn_status_callback: VpnStatusCallback, server_name: str):
        self._vpn_status_callback = vpn_status_callback
        self.server_name = server_name
        self.connection: Optional[Connection] = None
        self.is_connected_to_service = False
        self.running = False
        self.receive_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        self._vpn_connect_manager_client = VpnConnectManagerClient(self, vpn_status_callback)

        # Connection address
        if os.name == 'nt':
            # Windows named pipe
            self.mp_address = f"\\\\.\\pipe\\{self.server_name}"
        else:
            # Unix domain socket
            self.mp_address = f"/tmp/{self.server_name}.sock"

    def get_vpn_connect_manager(self) -> VpnConnectManager:
        return self._vpn_connect_manager_client

    def connect_to_service(self) -> bool:
        """Connect to the VPN service"""
        with self.lock:
            if self.is_connected_to_service:
                return True

            try:
                if os.name == 'nt':
                    # Windows named pipe
                    self.connection = Client(self.mp_address, family='AF_PIPE')
                else:
                    # Unix domain socket
                    self.connection = Client(self.mp_address, family='AF_UNIX')

                logger.info(f"Connected to background IPC service via multiprocessing connection: {self.mp_address}")

                self.is_connected_to_service = True
                self.running = True

                # Start receive thread
                self.receive_thread = threading.Thread(target=self._receive_messages, daemon=True)
                self.receive_thread.start()

                return True

            except Exception as e:
                # Silent failure - the periodic timer will retry
                if self.connection:
                    try:
                        self.connection.close()
                    except:
                        pass
                    self.connection = None
                return False

    def _receive_messages(self) -> None:
        """Receive messages from service in background thread"""
        try:
            while self.running and self.is_connected_to_service:
                try:
                    if not self.connection:
                        break
                    data = self.connection.recv_bytes()
                    message = decode_message(data)
                    self._handle_service_message(message)
                except EOFError:
                    break
                except Exception as e:
                    if self.running:
                        logger.error(f"Error receiving from service: {e}")
                    break

        except Exception as e:
            logger.error(f"Error in receive thread: {e}")
        finally:
            self._disconnect_from_service()

    def _disconnect_from_service(self) -> None:
        """Internal disconnect from service"""
        with self.lock:
            if self.is_connected_to_service:
                self.is_connected_to_service = False
                logger.warning("Disconnected from background IPC service")

            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
                self.connection = None

    def _handle_service_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming message from service"""
        try:
            message_type = message.get("type")

            if message_type == "status_message":
                status = VpnStatus(message.get("status"))
                msg = message.get("message", "")
                data = message.get("data", {})
                self._vpn_status_callback.on_status_message(status, msg, data)

            elif message_type == "command_output":
                line = message.get("line", "")
                stream = LogStream(message.get("stream"))
                process_name = message.get("process_name", "unknown")
                self._vpn_status_callback.on_command_output(line, stream, process_name)

            elif message_type == "service_log":
                level = message.get("level", 20)  # Default to INFO
                msg = message.get("message", "")
                logger_name = message.get("logger_name", "")
                self._vpn_status_callback.on_service_log(level, msg, logger_name)

            elif message_type == "error":
                error_message = message.get("error_message", "")
                error_code = VpnErrorCode(message.get("error_code"))
                details = message.get("details")
                self._vpn_status_callback.on_error(error_message, error_code, details)
            else:
                logger.warning(f"Unknown message type from service: {message_type}")

        except Exception as e:
            logger.error(f"Error handling service message: {e}")

    def send_to_service(self, message: Dict[str, Any]) -> bool:
        """Send message to service using JSON serialization"""
        with self.lock:
            if not self.is_connected_to_service or not self.connection:
                logger.warning("Not connected background IPC service")
                return False

            try:
                data = encode_message(message)
                self.connection.send_bytes(data)
                return True
            except Exception as e:
                logger.error(f"Error sending to service: {e}")
                self._disconnect_from_service()
                return False

    def is_service_connected(self) -> bool:
        """Check if currently connected to the service"""
        with self.lock:
            return self.is_connected_to_service


class VpnConnectManagerClient(VpnConnectManager):
    def __init__(self, service_client: ServiceClient, vpn_status_callback: VpnStatusCallback):
        self._service_client = service_client
        self.vpn_status_callback = vpn_status_callback

    def connect(self, profile: VPNProfile, cookie: str) -> None:
        """Start VPN connection asynchronously."""
        message = {
            "type": "connect",
            "profile": {
                "name": profile.name,
                "url": profile.url,
                "destination_networks": [{"destination_ip": net.destination_ip, "netmask": net.netmask} for net in profile.routes]
            },
            "cookie": cookie
        }

        if not self._service_client.send_to_service(message):
            # If sending fails, report error via callback
            self.vpn_status_callback.on_error(
                "Failed to send connect request to VPN service",
                VpnErrorCode.NETWORK_ERROR,
                "IPC communication failed"
            )

    def disconnect(self) -> None:
        """Start VPN disconnection asynchronously."""
        message = {
            "type": "disconnect"
        }

        if not self._service_client.send_to_service(message):
            # If sending fails, report error via callback
            self.vpn_status_callback.on_error(
                "Failed to send disconnect request to VPN service",
                VpnErrorCode.NETWORK_ERROR,
                "IPC communication failed"
            )

    def query_status(self) -> None:
        """Query current VPN status asynchronously."""
        message = {
            "type": "query_status"
        }

        if not self._service_client.send_to_service(message):
            # If sending fails, report error via callback
            self.vpn_status_callback.on_error(
                "Failed to send status query to VPN service",
                VpnErrorCode.NETWORK_ERROR,
                "IPC communication failed"
            )

