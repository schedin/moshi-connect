"""
Unit tests for settings import/export functionality
"""

import unittest
import tempfile
import yaml
from pathlib import Path

from src.config.vpn_profiles import VPNProfileManager, VPNProfile, DestinationNetwork
from src.config.app_settings import AppSettings


class TestSettingsExport(unittest.TestCase):
    """Test cases for settings export"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.profile_manager = VPNProfileManager(self.test_dir)
        self.app_settings = AppSettings(self.test_dir)

    def test_export_data_structure(self):
        """Test that export creates correct data structure"""
        # Add test profile
        test_profile = VPNProfile(
            name='test_vpn',
            url='https://test.vpn.com',
            routes=[DestinationNetwork.from_cidr('192.168.1.0/24')]
        )
        self.profile_manager.add_profile(test_profile)
        
        # Add test settings
        self.app_settings.set_setting('test_key', 'test_value')
        
        # Create export data
        export_data = {
            'profiles': {
                name: profile.to_dict() 
                for name, profile in self.profile_manager.profiles.items()
            },
            'settings': self.app_settings.settings
        }
        
        # Verify structure
        self.assertIn('profiles', export_data)
        self.assertIn('settings', export_data)
        self.assertIn('test_vpn', export_data['profiles'])
        self.assertEqual(export_data['settings']['test_key'], 'test_value')

    def test_export_to_yaml(self):
        """Test that data can be exported to valid YAML"""
        # Add test data
        test_profile = VPNProfile(
            name='test_vpn',
            url='https://test.vpn.com',
            routes=[DestinationNetwork.from_cidr('192.168.1.0/24')]
        )
        self.profile_manager.add_profile(test_profile)
        self.app_settings.set_setting('test_key', 'test_value')
        
        # Create export data
        export_data = {
            'profiles': {
                name: profile.to_dict() 
                for name, profile in self.profile_manager.profiles.items()
            },
            'settings': self.app_settings.settings
        }
        
        # Convert to YAML
        yaml_str = yaml.safe_dump(export_data, indent=2, default_flow_style=False)
        
        # Verify it's valid YAML by parsing it back
        parsed_data = yaml.safe_load(yaml_str)
        self.assertEqual(parsed_data['profiles']['test_vpn']['name'], 'test_vpn')
        self.assertEqual(parsed_data['settings']['test_key'], 'test_value')


class TestSettingsImport(unittest.TestCase):
    """Test cases for settings import"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.profile_manager = VPNProfileManager(self.test_dir)
        self.app_settings = AppSettings(self.test_dir)

    def test_import_from_yaml(self):
        """Test that settings can be imported from YAML"""
        yaml_content = """
profiles:
  test_vpn:
    name: test_vpn
    url: https://test.vpn.com
    routes:
      - 192.168.1.0/24
settings:
  test_key: test_value
  last_selected_profile: test_vpn
"""
        
        # Parse YAML
        data = yaml.safe_load(yaml_content)
        
        # Import profiles
        self.profile_manager.profiles.clear()
        for name, profile_data in data['profiles'].items():
            profile = VPNProfile.from_dict(profile_data)
            self.profile_manager.profiles[profile.name] = profile
        
        # Import settings
        self.app_settings.settings = data['settings']
        
        # Verify import
        self.assertIn('test_vpn', self.profile_manager.profiles)
        profile = self.profile_manager.get_profile('test_vpn')
        self.assertIsNotNone(profile)
        self.assertEqual(profile.url, 'https://test.vpn.com')
        self.assertEqual(len(profile.routes), 1)
        self.assertEqual(profile.routes[0].to_cidr(), '192.168.1.0/24')
        
        self.assertEqual(self.app_settings.settings['test_key'], 'test_value')
        self.assertEqual(self.app_settings.settings['last_selected_profile'], 'test_vpn')

    def test_import_multiple_profiles(self):
        """Test importing multiple profiles"""
        yaml_content = """
profiles:
  vpn1:
    name: vpn1
    url: https://vpn1.com
    routes:
      - 10.0.0.0/8
  vpn2:
    name: vpn2
    url: https://vpn2.com
    routes:
      - 172.16.0.0/12
      - 192.168.0.0/16
settings:
  last_selected_profile: vpn2
"""
        
        data = yaml.safe_load(yaml_content)
        
        # Import profiles
        self.profile_manager.profiles.clear()
        for name, profile_data in data['profiles'].items():
            profile = VPNProfile.from_dict(profile_data)
            self.profile_manager.profiles[profile.name] = profile
        
        # Verify both profiles imported
        self.assertEqual(len(self.profile_manager.profiles), 2)
        self.assertIn('vpn1', self.profile_manager.profiles)
        self.assertIn('vpn2', self.profile_manager.profiles)
        
        vpn2 = self.profile_manager.get_profile('vpn2')
        self.assertEqual(len(vpn2.routes), 2)

    def test_import_empty_routes(self):
        """Test importing profile with no routes"""
        yaml_content = """
profiles:
  test_vpn:
    name: test_vpn
    url: https://test.vpn.com
    routes: []
settings: {}
"""
        
        data = yaml.safe_load(yaml_content)
        
        # Import profiles
        self.profile_manager.profiles.clear()
        for name, profile_data in data['profiles'].items():
            profile = VPNProfile.from_dict(profile_data)
            self.profile_manager.profiles[profile.name] = profile
        
        # Verify profile with empty routes
        profile = self.profile_manager.get_profile('test_vpn')
        self.assertIsNotNone(profile)
        self.assertEqual(len(profile.routes), 0)

    def test_import_invalid_yaml(self):
        """Test that invalid YAML raises appropriate error"""
        invalid_yaml = "this is not: valid: yaml: content:"
        
        with self.assertRaises(yaml.YAMLError):
            yaml.safe_load(invalid_yaml)


if __name__ == '__main__':
    unittest.main()
