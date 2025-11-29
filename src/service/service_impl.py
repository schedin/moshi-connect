"""
IPC Server for GUI. This module implements the service layer that handles VPN operations
and communicates with clients via multiprocessing connections.
"""

import logging
import threading
import os
from typing import Optional, Dict, Any, List
from multiprocessing.connection import Listener, Connection

from ipc.vpn_connect_interface import VpnStatusCallback, VpnStatus, LogStream, VpnErrorCode
from ipc.json_message import encode_message, decode_message
from ipc.service_interface import ServiceInterface
from service.vpn_connect_manager_impl import VpnConnectManagerImpl

from config.vpn_profiles import VPNProfile, DestinationNetwork

if os.name == 'nt':
    from service.windows_pipe_server import WindowsPipeListener

logger = logging.getLogger(__name__)

SERVICE_NAME = "Moshi Connect service"
SERVICE_FILENAME = "moshi_connect_service"


class VpnServiceCallback(VpnStatusCallback):
    """Callback adapter that forwards VPN events to IPC clients"""

    def __init__(self, service: ServiceInterface):
        self.service = service

    def on_status_message(self, status: VpnStatus, message: str, data: Optional[Dict[str, str]] = None) -> None:
        """Forward status messages to IPC clients"""
        self.service.send_to_clients({
            "type": "status_message",
            "status": status.value,
            "message": message,
            "data": data or {}
        })

    def on_command_output(self, line: str, stream: LogStream, process_name: str) -> None:
        """Forward command output to IPC clients"""
        self.service.send_to_clients({
            "type": "command_output",
            "line": line,
            "stream": stream.value,
            "process_name": process_name
        })

    def on_service_log(self, level: int, message: str, logger_name: str) -> None:
        """Forward service log messages to IPC clients"""
        self.service.send_to_clients({
            "type": "service_log",
            "level": level,
            "message": message,
            "logger_name": logger_name
        })

    def on_error(self, error_message: str, error_code: VpnErrorCode, details: Optional[str] = None) -> None:
        """Forward error messages to IPC clients"""
        self.service.send_to_clients({
            "type": "error",
            "error_message": error_message,
            "error_code": error_code.value,
            "details": details
        })


class ClientConnection:
    """Represents a multiprocessing client connection"""

    def __init__(self, connection: Connection, address: str):
        self.connection = connection  # multiprocessing.connection.Connection
        self.address = address
        self.running = True
        self.lock = threading.Lock()

    def send_message(self, message: Dict[str, Any]) -> bool:
        """Send message to client using JSON serialization"""
        try:
            with self.lock:
                if not self.running:
                    return False
                data = encode_message(message)
                self.connection.send_bytes(data)
                return True
        except Exception as e:
            logger.warning(f"Error sending to client {self.address}: {e}", extra={ServiceLogBroadcastHandler.SUPPRESS_BROADCAST_ATTR: True})
            return False

    def receive_message(self) -> Optional[Dict[str, Any]]:
        """Receive message from client using JSON deserialization"""
        try:
            data = self.connection.recv_bytes()
            return decode_message(data)
        except EOFError:
            return None

    def close(self) -> None:
        """Close client connection"""
        with self.lock:
            self.running = False
            try:
                self.connection.close()
            except:
                pass


class ServiceLogBroadcastHandler(logging.Handler):
    """Logging handler that forwards service logs to connected clients via callback."""

    # Attribute name for suppressing broadcast of log records
    SUPPRESS_BROADCAST_ATTR = "suppress_broadcast"
    # Only broadcast logs from service modules
    SERVICE_LOGGER_PREFIX = "service."

    def __init__(self, callback: VpnServiceCallback) -> None:
        super().__init__()
        self.callback = callback
        self.setLevel(logging.NOTSET)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Only broadcast logs from service modules (prevents infinite loop in single-process mode)
            if not record.name.startswith(self.SERVICE_LOGGER_PREFIX):
                return

            # Check if this log should be suppressed from client broadcast
            if getattr(record, self.SUPPRESS_BROADCAST_ATTR, False):
                return

            self.callback.on_service_log(record.levelno, record.getMessage(), record.name)
        except Exception:
            self.handleError(record)


class ServiceImpl(ServiceInterface):
    """Windows/Linux Service that serves the GUI (via IPC) and connects to the user VPN provider"""

    def __init__(self) -> None:
        self.mp_listener: Listener
        self.clients: List[ClientConnection] = []
        self.clients_lock = threading.Lock()
        self.running = False

        self.callback = VpnServiceCallback(self)
        self.log_handler = ServiceLogBroadcastHandler(self.callback)
        self.vpn_connect_manager_impl = VpnConnectManagerImpl(self.callback)

        # Connection address
        if os.name == 'nt':
            # Windows named pipe
            self.mp_address = f"\\\\.\\pipe\\{SERVICE_FILENAME}"
        else:
            # Unix domain socket
            self.mp_address = f"/tmp/{SERVICE_FILENAME}.sock"

    # def get_vpn_connect_manager(self) -> VpnConnectManager:
    #     return self.vpn_connect_manager_impl

    def start_service(self) -> bool:
        """Start the service IPC server"""
        try:
            if os.name == 'nt':
                self.mp_listener = WindowsPipeListener(self.mp_address)
            else:
                # Unix domain socket - clean up existing socket file
                if os.path.exists(self.mp_address):
                    os.unlink(self.mp_address)
                self.mp_listener = Listener(self.mp_address, family='AF_UNIX')

            self.running = True
            logging.getLogger().addHandler(self.log_handler)

            # Start multiprocessing connection accept thread
            accept_thread = threading.Thread(target=self._accept_mp_connections, daemon=True)
            accept_thread.start()
            logger.info(f"{SERVICE_NAME} started on multiprocessing connection: {self.mp_address}")
            return True

        except Exception as e:
            logger.error(f"Failed to start {SERVICE_NAME}: {e}")
            return False

    def _accept_mp_connections(self) -> None:
        """Accept incoming multiprocessing connections"""
        while self.running:
            try:
                # Accept a new connection
                conn = self.mp_listener.accept()
                logger.info(f"New multiprocessing client connected: {self.mp_address}")

                client = ClientConnection(conn, self.mp_address)

                with self.clients_lock:
                    self.clients.append(client)

                # Start client handler thread
                client_thread = threading.Thread(
                    target=self._handle_mp_client,
                    args=(client,),
                    daemon=True
                )
                client_thread.start()

            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting multiprocessing connection: {e}")
                break

    def _handle_mp_client(self, client: ClientConnection) -> None:
        """Handle messages from a multiprocessing client"""
        try:
            while client.running and self.running:
                message = client.receive_message()
                if message is None:
                    logger.debug(f"Client disconnected: {client.address}")
                    break

                logger.debug(f"Received from MP client: {message}")
                self._handle_client_message(client, message)

        except Exception as e:
            if self.running:
                logger.error(f"Error handling MP client {client.address}: {e}")
        finally:
            self._remove_client(client)

    def _remove_client(self, client: ClientConnection) -> None:
        """Remove client from active connections"""
        with self.clients_lock:
            if client in self.clients:
                self.clients.remove(client)

            # Check if this was the last client
            remaining_clients = len(self.clients)

        client.close()
        logger.info(f"Client disconnected: {client.address}")

        # If no clients remain, terminate any running OpenConnect processes
        if remaining_clients == 0:
            self._handle_last_client_disconnect()

    def _handle_last_client_disconnect(self) -> None:
        """Handle the case when the last client disconnects"""
        try:
            logger.info("Last client disconnected, checking for active VPN connections...")

            # Check if there's an active VPN connection
            current_status = self.vpn_connect_manager_impl.current_status
            logger.debug(f"Current VPN status: {current_status}")

            if current_status not in [VpnStatus.DISCONNECTED, VpnStatus.DISCONNECTING]:
                logger.info(f"Active VPN connection detected (status: {current_status}), terminating OpenConnect processes...")

                # Disconnect the VPN which will terminate OpenConnect processes
                self.vpn_connect_manager_impl.disconnect()
                logger.info("VPN disconnection initiated due to last client disconnect")
            else:
                logger.debug(f"VPN already disconnected or disconnecting (status: {current_status}), no action needed")

        except Exception as e:
            logger.error(f"Error handling last client disconnect: {e}")

    def _handle_client_message(self, client: ClientConnection, message: Dict[str, Any]) -> None:
        """Handle incoming message from client"""
        message_type = message.get("type")

        if message_type == "connect":
            self._handle_connect_request(client, message)
        elif message_type == "disconnect":
            self._handle_disconnect_request(client, message)
        elif message_type == "query_status":
            self._handle_query_status_request(client, message)
        else:
            logger.warning(f"Unknown message type: {message_type}")

    def _handle_connect_request(self, client: ClientConnection, message: Dict[str, Any]) -> None:
        """Handle VPN connect request"""
        try:
            profile_data = message.get("profile")
            cookie = message.get("cookie")

            if not profile_data or not cookie:
                self._send_error_to_client(client, "Missing profile or cookie")
                return

            # Create VPNProfile from data
            destination_networks = []
            for net_data in profile_data.get("destination_networks", []):
                if isinstance(net_data, dict):
                    destination_networks.append(DestinationNetwork(
                        destination_ip=net_data["destination_ip"],
                        netmask=net_data["netmask"]
                    ))

            profile = VPNProfile(
                name=profile_data["name"],
                url=profile_data["url"],
                routes=destination_networks
            )

            # Start VPN connection
            self.vpn_connect_manager_impl.connect(profile, cookie)

        except Exception as e:
            logging.error(f"Error handling connect request: {e}")
            self._send_error_to_client(client, f"Connect failed: {e}")

    def _handle_disconnect_request(self, client: ClientConnection, message: Dict[str, Any]) -> None:
        """Handle VPN disconnect request"""
        try:
            self.vpn_connect_manager_impl.disconnect()
        except Exception as e:
            logging.error(f"Error handling disconnect request: {e}")
            self._send_error_to_client(client, f"Disconnect failed: {e}")

    def _handle_query_status_request(self, client: ClientConnection, message: Dict[str, Any]) -> None:
        """Handle VPN status query request"""
        try:
            self.vpn_connect_manager_impl.query_status()
        except Exception as e:
            logging.error(f"Error handling status query: {e}")
            self._send_error_to_client(client, f"Status query failed: {e}")

    def _send_error_to_client(self, client: ClientConnection, error_message: str) -> None:
        """Send error message to specific client"""
        client.send_message({
            "type": "error",
            "error_message": error_message,
            "error_code": VpnErrorCode.UNKNOWN_ERROR.value,
            "details": None
        })

    def send_to_clients(self, message: Dict[str, Any]) -> None:
        """Send message to all connected clients"""
        with self.clients_lock:
            for client in self.clients[:]:  # Copy list to avoid modification during iteration
                if not client.send_message(message):
                    # Remove failed clients
                    self.clients.remove(client)
                    client.close()

    def stop_service(self) -> None:
        logging.info(f"Stopping {SERVICE_NAME}...")
        self.running = False
        logging.getLogger().removeHandler(self.log_handler)

        # Close all client connections
        with self.clients_lock:
            for client in self.clients[:]:
                client.close()
            self.clients.clear()

        # Close multiprocessing listener
        if self.mp_listener:
            try:
                self.mp_listener.close()
            except:
                pass

        # Clean up Unix socket file (Windows named pipes are cleaned up automatically)
        if os.name != 'nt' and os.path.exists(self.mp_address):
            try:
                os.unlink(self.mp_address)
            except:
                pass

        logging.info(f"{SERVICE_NAME} stopped")