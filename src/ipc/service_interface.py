"""
Interface for the GUI to communicate with the background IPC service
"""


from typing import Protocol, runtime_checkable, Dict, Any
from ipc.vpn_connect_interface import VpnConnectManager


@runtime_checkable
class ServiceClientInterface(Protocol):
    def get_vpn_connect_manager(self) -> VpnConnectManager:
        """Get the VPN connection manager"""
        ...

    def is_service_connected(self) -> bool:
        """Check if currently connected to the service"""
        ...

    def connect_to_service(self) -> bool:
        """Connect to the VPN service

        Returns:
            True if connection was successful, False otherwise
        """
        ...

@runtime_checkable
class ServiceInterface(Protocol):
    def start_service(self) -> bool:
        ...
    
    def stop_service(self) -> None:
        ...

    def send_to_clients(self, message: Dict[str, Any]) -> None:
        """Sends a message to client"""
        ...

