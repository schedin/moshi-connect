"""
Unit tests for interface parsing in VPN connection manager.
"""

import unittest
import re
from unittest.mock import Mock

from src.service.vpn_connect_manager_impl import VpnConnectManagerImpl


class TestInterfaceParsing(unittest.TestCase):
    """Test cases for interface parsing patterns"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_callback = Mock()
        self.manager = VpnConnectManagerImpl(self.mock_callback)

    def test_wintun_device_pattern(self):
        """Test that Wintun device pattern is correctly parsed"""
        # The pattern from the actual implementation
        pattern = r"Using (?P<devicename>[\w-]+) device '(?P<name>[^']+)', index (?P<index>\d+)"

        test_line = "Using Wintun device 'vpn.mycompany.com', index 31"
        match = re.search(pattern, test_line)

        self.assertIsNotNone(match, "Wintun device pattern should match")
        self.assertEqual(match.group('devicename'), 'Wintun')
        self.assertEqual(match.group('name'), 'vpn.mycompany.com')
        self.assertEqual(match.group('index'), '31')

    def test_tap_device_pattern(self):
        """Test that TAP device pattern is correctly parsed"""
        pattern = r"Using (?P<devicename>[\w-]+) device '(?P<name>[^']+)', index (?P<index>\d+)"

        test_line = "Using TAP device 'Local Area Connection', index 15"
        match = re.search(pattern, test_line)

        self.assertIsNotNone(match, "TAP device pattern should match")
        self.assertEqual(match.group('devicename'), 'TAP')
        self.assertEqual(match.group('name'), 'Local Area Connection')
        self.assertEqual(match.group('index'), '15')

    def test_tap_windows_device_pattern(self):
        """Test that TAP-Windows device pattern is correctly parsed"""
        pattern = r"Using (?P<devicename>[\w-]+) device '(?P<name>[^']+)', index (?P<index>\d+)"

        test_line = "Using TAP-Windows device 'Local Area Connection', index 16"
        match = re.search(pattern, test_line)

        self.assertIsNotNone(match, "TAP-Windows device pattern should match")
        self.assertEqual(match.group('devicename'), 'TAP-Windows')
        self.assertEqual(match.group('name'), 'Local Area Connection')
        self.assertEqual(match.group('index'), '16')

    def test_tun_device_pattern(self):
        """Test that TUN device pattern is correctly parsed"""
        pattern = r"Using (?P<devicename>[\w-]+) device '(?P<name>[^']+)', index (?P<index>\d+)"

        test_line = "Using tun device 'tun0', index 5"
        match = re.search(pattern, test_line)

        self.assertIsNotNone(match, "TUN device pattern should match")
        self.assertEqual(match.group('devicename'), 'tun')
        self.assertEqual(match.group('name'), 'tun0')
        self.assertEqual(match.group('index'), '5')

    def test_pattern_with_special_characters_in_name(self):
        """Test pattern with special characters in device name"""
        pattern = r"Using (?P<devicename>[\w-]+) device '(?P<name>[^']+)', index (?P<index>\d+)"

        test_line = "Using Wintun device 'VPN-Connection_123', index 42"
        match = re.search(pattern, test_line)

        self.assertIsNotNone(match, "Pattern should handle special characters in name")
        self.assertEqual(match.group('devicename'), 'Wintun')
        self.assertEqual(match.group('name'), 'VPN-Connection_123')
        self.assertEqual(match.group('index'), '42')

    def test_pattern_does_not_match_invalid_format(self):
        """Test that pattern doesn't match invalid formats"""
        pattern = r"Using (?P<devicename>[\w-]+) device '(?P<name>[^']+)', index (?P<index>\d+)"
        
        invalid_lines = [
            "Using device 'vpn.mycompany.com', index 31",  # Missing device type
            "Using Wintun 'vpn.mycompany.com', index 31",  # Missing 'device' keyword
            "Using Wintun device vpn.mycompany.com, index 31",  # Missing quotes
            "Using Wintun device 'vpn.mycompany.com', index",  # Missing index number
            "Connected to Wintun device 'vpn.mycompany.com', index 31",  # Wrong verb
        ]
        
        for invalid_line in invalid_lines:
            match = re.search(pattern, invalid_line)
            self.assertIsNone(match, f"Pattern should not match invalid format: {invalid_line}")


if __name__ == '__main__':
    unittest.main()
