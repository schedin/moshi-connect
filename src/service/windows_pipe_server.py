"""
Windows Named Pipe Server with Cross-Privilege Access

This module provides a named pipe server that allows connections from processes
running at different privilege levels (e.g., admin service to user-level GUI).
"""

import sys
import typing
import logging
from typing import Optional, Any, Tuple, cast
from collections.abc import Buffer
from multiprocessing.connection import Connection, Listener

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    import win32pipe
    import win32file
    import win32security
    from multiprocessing.connection import PipeConnection
    if typing.TYPE_CHECKING:
        from _win32typing import PyHANDLE
        from _win32typing import PySECURITY_ATTRIBUTES
    else:
        # Runtime placeholders so annotations using these names are valid at runtime.
        # During type-checking the real types from _win32typing will be used.
        PyHANDLE = int
        PySECURITY_ATTRIBUTES = Any


class WindowsPipeConnection(Connection):
    """
    Wrapper around a Windows named pipe handle that provides a Connection-like interface.
    Uses multiprocessing.connection.PipeConnection for proper message framing.
    """

    def __init__(self, pipe_handle_obj: PyHANDLE, pipe_handle_int: int):
        """
        Initialize the connection wrapper.

        Args:
            pipe_handle_obj: pywin32 HANDLE object (kept alive during initialization)
            pipe_handle_int: Integer Windows pipe handle value
        """
        # Store the pywin32 object to keep it alive
        # This prevents it from being garbage collected and closing the handle
        # before PipeConnection takes ownership
        self._pywin32_handle = pipe_handle_obj

        # Create a PipeConnection using the integer handle
        # PipeConnection expects an integer handle on Windows and takes ownership
        self._pipe_conn = PipeConnection(pipe_handle_int)

        # Now that PipeConnection has taken ownership, we can release our reference
        # But we need to prevent the pywin32 object from closing the handle
        # We do this by calling Detach() if available
        try:
            self._pywin32_handle.Detach()
        except AttributeError:
            # If Detach() doesn't exist, just keep the reference
            # The handle is now owned by PipeConnection anyway
            pass

    def send(self, obj: Any) -> None:
        raise NotImplementedError("This function is unsafe due to pickle serialization, use send_bytes() instead.")

    def recv(self) -> None:
        raise NotImplementedError("This function is unsafe due to pickle serialization, use send_bytes() instead.")

    def send_bytes(self, buf: Buffer, offset: int = 0, size: Optional[int] = None) -> None:
        """Send raw bytes through the pipe."""
        return self._pipe_conn.send_bytes(buf, offset, size)

    def recv_bytes(self, maxlength: Optional[int] = None) -> bytes:
        """Receive raw bytes from the pipe."""
        return self._pipe_conn.recv_bytes(maxlength)

    def poll(self, timeout: Optional[float] = 0) -> bool:
        """Check if data is available."""
        return self._pipe_conn.poll(timeout)

    def close(self) -> None:
        """Close the pipe connection."""
        try:
            self._pipe_conn.close()
        except Exception as e:
            logger.error(f"Error closing pipe connection: {e}")

    def fileno(self) -> Any:
        """Return the file descriptor."""
        return self._pipe_conn.fileno()


class WindowsPipeListener(Listener):
    """
    Windows Named Pipe Server with security attributes that allow
    connections from lower-privilege processes.

    This class provides a Listener-compatible interface for accepting connections.
    """

    def __init__(self, pipe_path: str):
        """Initialize the Windows named pipe server."""
        self.pipe_path = pipe_path
        #self.pipe_path = f"\\\\.\\pipe\\{pipe_name}"

    def _create_security_attributes(self) -> PySECURITY_ATTRIBUTES:
        """
        Create security attributes that allow access from any integrity level.

        This creates a DACL (Discretionary Access Control List) that grants
        full access to Everyone, and sets a SACL (System Access Control List)
        that allows low integrity level access.
        """
        # Create a security descriptor
        security_descriptor = win32security.SECURITY_DESCRIPTOR()

        # Create a DACL that grants full access to Everyone
        dacl = win32security.ACL()
        everyone_sid = win32security.CreateWellKnownSid(win32security.WinWorldSid)

        # GENERIC_ALL = 0x10000000 (full access)
        GENERIC_ALL = 0x10000000

        dacl.AddAccessAllowedAce(
            win32security.ACL_REVISION,
            GENERIC_ALL,
            everyone_sid
        )

        # Set the DACL
        security_descriptor.SetSecurityDescriptorDacl(1, dacl, 0)

        # Create a SACL that allows low integrity level access
        # This is the key to allowing user-level processes to connect to admin-level service
        sacl = win32security.ACL()
        low_integrity_sid = win32security.CreateWellKnownSid(win32security.WinLowLabelSid)

        # SYSTEM_MANDATORY_LABEL_NO_WRITE_UP = 1
        # This constant is not always available in ntsecuritycon, so we use the numeric value
        SYSTEM_MANDATORY_LABEL_NO_WRITE_UP = 1

        sacl.AddMandatoryAce(
            win32security.ACL_REVISION,
            0,  # No flags
            SYSTEM_MANDATORY_LABEL_NO_WRITE_UP,
            low_integrity_sid
        )

        # Set the SACL
        security_descriptor.SetSecurityDescriptorSacl(1, sacl, 0)

        # Create security attributes
        security_attributes = win32security.SECURITY_ATTRIBUTES()
        security_attributes.SECURITY_DESCRIPTOR = security_descriptor

        return security_attributes

    def _create_pipe(self) -> Tuple[PyHANDLE, int]:
        """
        Create a named pipe with security attributes that allow cross-privilege access.

        Returns:
            Tuple of (pywin32 HANDLE object, integer handle value)
        """
        security_attributes = self._create_security_attributes()

        # Create the named pipe with FILE_FLAG_OVERLAPPED for PipeConnection compatibility
        # PipeConnection REQUIRES overlapped I/O and MESSAGE mode for ERROR_MORE_DATA handling
        pipe_handle = win32pipe.CreateNamedPipe(
            self.pipe_path,
            win32pipe.PIPE_ACCESS_DUPLEX | win32file.FILE_FLAG_OVERLAPPED,  # Read/write access with overlapped I/O
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
            win32pipe.PIPE_UNLIMITED_INSTANCES,  # Max instances
            1048576,  # output buffer size (1MB)
            1048576,  # Input buffer size (1MB)
            0,  # Default timeout
            security_attributes
        )

        logger.info(f"Created named pipe with cross-privilege access: {self.pipe_path}")

        # Return both the pywin32 object and the integer handle
        # The caller must keep the pywin32 object alive until ownership is transferred
        return cast(PyHANDLE, pipe_handle), int(pipe_handle)

    def wait_for_connection(self, pipe_handle_obj: PyHANDLE, pipe_handle_int: int) -> bool:
        """
        Wait for a client to connect to the pipe.

        Args:
            pipe_handle_obj: pywin32 HANDLE object (kept alive during the call)
            pipe_handle_int: Integer handle value

        Returns:
            True if a client connected, False otherwise
        """
        try:
            win32pipe.ConnectNamedPipe(pipe_handle_int, None)
            logger.info(f"Client connected to pipe: {self.pipe_path}")
            return True
        except Exception as e:
            logger.error(f"Error waiting for pipe connection: {e}")
            return False

    def accept(self) -> WindowsPipeConnection:
        """
        Accept a new connection (Listener-compatible interface).

        This method creates a new pipe instance and waits for a client to connect.

        Returns:
            WindowsPipeConnection object representing the client connection
        """
        # Create a new pipe instance for this connection
        pipe_handle_obj, pipe_handle_int = self._create_pipe()

        # Wait for a client to connect
        # Keep the pywin32 object alive during the wait
        if not self.wait_for_connection(pipe_handle_obj, pipe_handle_int):
            self.close_pipe(pipe_handle_int)
            raise ConnectionError("Failed to accept connection")

        # Return a Connection-like wrapper
        # The WindowsPipeConnection will take ownership via PipeConnection
        # We must keep pipe_handle_obj alive until PipeConnection takes ownership
        return WindowsPipeConnection(pipe_handle_obj, pipe_handle_int)

    def close(self) -> None:
        """Close the pipe server."""
        self.running = False
        logger.info(f"Closed pipe server: {self.pipe_path}")

    def close_pipe(self, pipe_handle: Optional[int]) -> None:
        """Close a pipe handle."""
        if pipe_handle:
            try:
                win32file.CloseHandle(pipe_handle)
            except Exception as e:
                logger.error(f"Error closing pipe handle: {e}")
