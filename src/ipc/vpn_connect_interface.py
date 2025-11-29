"""
Interface (asynchronous) for connecting and disconnecting to a VPN.
"""

from typing import Protocol, runtime_checkable, Optional, Dict
from enum import Enum
from config.vpn_profiles import VPNProfile


class VpnStatus(Enum):
    """VPN connection status states"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"


class LogStream(Enum):
    """Source stream for command output"""
    STDOUT = "stdout"
    STDERR = "stderr"


class VpnErrorCode(Enum):
    """Standard VPN error codes"""
    OPENCONNECT_NOT_FOUND = "OPENCONNECT_NOT_FOUND"
    AUTH_FAILED = "AUTH_FAILED"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


@runtime_checkable
class VpnStatusCallback(Protocol):
    """Interface for receiving messages from VPN manager to client"""

    def on_status_message(self, status: VpnStatus, message: str, data: Optional[Dict[str, str]] = None) -> None:
        """Handle VPN status changes with additional data.

        Args:
            status: Current VPN status (connecting/connected/disconnecting/disconnected)
            message: Human-readable status message
            data: Additional status-specific data:
                - For CONNECTED: {"device_name": str, "device_type": str, "device_index": str, "vpn_url": str}
                - For DISCONNECTED: {"reason": str, "was_error": str}  # was_error: "true"/"false"
                - For CONNECTING: {"vpn_url": str, "profile_name": str}
                - For DISCONNECTING: {"reason": str}
        """
        ...

    def on_command_output(self, line: str, stream: LogStream, process_name: str) -> None:
        """Handle STDOUT/STDERR output from external commands (openconnect.exe, route.exe).

        Args:
            line: Raw output line from command
            stream: Whether this came from STDOUT or STDERR
            process_name: Name of the process binary (e.g., "openconnect", "route")
        """
        ...

    def on_service_log(self, level: int, message: str, logger_name: str) -> None:
        """Handle normal Python logging from the service.

        Args:
            level: Python logging level (DEBUG=10, INFO=20, WARNING=30, ERROR=40, CRITICAL=50)
            message: The log message
            logger_name: Name of the logger that emitted this message
        """
        ...

    def on_error(self, error_message: str, error_code: VpnErrorCode, details: Optional[str] = None) -> None:
        """Handle error conditions.

        Args:
            error_message: Human-readable error description
            error_code: Standard error code for programmatic handling
            details: Optional additional error details/context
        """
        ...


@runtime_checkable
class VpnConnectManager(Protocol):
    """Asynchronous interface for VPN connection management"""

    def connect(self, profile: VPNProfile, cookie: str) -> None:
        """Connect to the VPN.

        Args:
            profile: VPN profile containing URL and routes
            cookie: Session cookie for authentication
        """
        ...

    def disconnect(self) -> None:
        """Disconnect from the VPN."""
        ...

    def query_status(self) -> None:
        """Query VPN connection status.

        The response will be sent via the configured callback as a on_status_message() call.
        """
        ...

