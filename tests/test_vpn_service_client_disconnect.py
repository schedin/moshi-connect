"""
Unit tests for VPN service client disconnect handling.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import threading
import time

import sys
import os
# Add src to path so we can import using the same relative imports as the service
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from service.service_impl import ServiceImpl, ClientConnection
from ipc.vpn_connect_interface import VpnStatus
from service.vpn_connect_manager_impl import VpnConnectManagerImpl


class TestVpnServiceClientDisconnect(unittest.TestCase):
    """Test cases for VPN service client disconnect handling"""

    def setUp(self):
        """Set up test fixtures"""
        self.service = ServiceImpl()

        # Create a real VPN manager instance but mock its methods
        mock_callback = Mock()
        self.real_vpn_manager = VpnConnectManagerImpl(mock_callback)

        # Mock the disconnect method
        self.real_vpn_manager.disconnect = Mock()

        # Set default status
        self.real_vpn_manager.current_status = VpnStatus.DISCONNECTED
        self.service.vpn_manager = self.real_vpn_manager

    def test_remove_client_with_remaining_clients(self):
        """Test that OpenConnect is not terminated when other clients remain"""
        # Create mock clients
        client1 = Mock(spec=ClientConnection)
        client1.address = "client1"
        client2 = Mock(spec=ClientConnection)
        client2.address = "client2"
        
        # Add clients to service
        self.service.clients = [client1, client2]
        
        # Set VPN as connected
        self.real_vpn_manager.current_status = VpnStatus.CONNECTED

        # Remove one client
        self.service._remove_client(client1)

        # Verify disconnect was not called
        self.real_vpn_manager.disconnect.assert_not_called()
        
        # Verify client was removed
        self.assertNotIn(client1, self.service.clients)
        self.assertIn(client2, self.service.clients)

    def test_remove_last_client_with_active_connection(self):
        """Test that OpenConnect is terminated when last client disconnects with active VPN"""
        # Create mock client
        client = Mock(spec=ClientConnection)
        client.address = "test_client"
        
        # Add client to service
        self.service.clients = [client]
        
        # Set VPN as connected
        self.real_vpn_manager.current_status = VpnStatus.CONNECTED

        # Remove the last client
        self.service._remove_client(client)

        # Verify disconnect was called
        self.real_vpn_manager.disconnect.assert_called_once()
        
        # Verify client was removed
        self.assertNotIn(client, self.service.clients)

    def test_remove_last_client_with_disconnected_vpn(self):
        """Test that disconnect is not called when VPN is already disconnected"""
        # Create mock client
        client = Mock(spec=ClientConnection)
        client.address = "test_client"

        # Add client to service
        self.service.clients = [client]

        # Set VPN as disconnected
        self.real_vpn_manager.current_status = VpnStatus.DISCONNECTED

        # Remove the last client
        self.service._remove_client(client)

        # Verify disconnect was not called
        self.real_vpn_manager.disconnect.assert_not_called()

    def test_remove_last_client_with_disconnecting_vpn(self):
        """Test that disconnect is not called when VPN is already disconnecting"""
        # Create mock client
        client = Mock(spec=ClientConnection)
        client.address = "test_client"
        
        # Add client to service
        self.service.clients = [client]
        
        # Set VPN as disconnecting
        self.real_vpn_manager.current_status = VpnStatus.DISCONNECTING

        # Remove the last client
        self.service._remove_client(client)

        # Verify disconnect was not called
        self.real_vpn_manager.disconnect.assert_not_called()

    def test_remove_last_client_with_connecting_vpn(self):
        """Test that disconnect is called when VPN is connecting"""
        # Create mock client
        client = Mock(spec=ClientConnection)
        client.address = "test_client"
        
        # Add client to service
        self.service.clients = [client]
        
        # Set VPN as connecting
        self.real_vpn_manager.current_status = VpnStatus.CONNECTING

        # Remove the last client
        self.service._remove_client(client)

        # Verify disconnect was called
        self.real_vpn_manager.disconnect.assert_called_once()

    def test_handle_last_client_disconnect_without_status_attribute(self):
        """Test handling when VPN manager doesn't have current_status attribute"""
        # Create mock client
        client = Mock(spec=ClientConnection)
        client.address = "test_client"
        
        # Add client to service
        self.service.clients = [client]
        
        # Create VPN manager without current_status attribute
        self.service.vpn_manager = Mock(spec=[])  # Empty spec means no attributes
        
        # Remove the last client - should not raise exception
        self.service._remove_client(client)
        
        # Verify no disconnect was attempted
        self.assertFalse(hasattr(self.service.vpn_manager, 'disconnect'))

    @patch('service.vpn_service.logging')
    def test_handle_last_client_disconnect_exception_handling(self, mock_logging):
        """Test that exceptions in last client disconnect handling are logged"""
        # Create mock client
        client = Mock(spec=ClientConnection)
        client.address = "test_client"
        
        # Add client to service
        self.service.clients = [client]
        
        # Make disconnect raise an exception
        self.real_vpn_manager.disconnect.side_effect = Exception("Test exception")
        self.real_vpn_manager.current_status = VpnStatus.CONNECTED
        
        # Remove the last client - should not raise exception
        self.service._remove_client(client)
        
        # Verify error was logged
        mock_logging.error.assert_called()
        error_call_args = mock_logging.error.call_args[0][0]
        self.assertIn("Error handling last client disconnect", error_call_args)


if __name__ == '__main__':
    unittest.main()
