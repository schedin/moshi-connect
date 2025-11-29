import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from config.constants import VPN_PROFILES_FILE

logger = logging.getLogger(__name__)

class DestinationNetwork:
    def __init__(self, destination_ip: str, netmask: str):
        self.destination_ip = destination_ip
        self.netmask = netmask

    @staticmethod
    def from_cidr(line: str) -> 'DestinationNetwork':
        network, prefix = line.split('/')
        prefix_len = int(prefix)
        if not (0 <= prefix_len <= 32):
            raise ValueError("Invalid prefix length")
        # Basic IP validation (simplified)
        parts = network.split('.')
        if len(parts) != 4:
            raise ValueError("Invalid IP format")
        for part in parts:
            if not (0 <= int(part) <= 255):
                raise ValueError("Invalid IP octet")
        # Convert CIDR to subnet mask
        mask_bits = (0xffffffff >> (32 - prefix_len)) << (32 - prefix_len)
        netmask = f"{(mask_bits >> 24) & 0xff}.{(mask_bits >> 16) & 0xff}.{(mask_bits >> 8) & 0xff}.{mask_bits & 0xff}"
        return DestinationNetwork(destination_ip=network, netmask=netmask)

    def to_cidr(self) -> str:
        mask_bits = sum(bin(int(x)).count('1') for x in self.netmask.split('.'))
        return f"{self.destination_ip}/{mask_bits}"
    
    def __repr__(self) -> str:
        return self.to_cidr()


class VPNProfile:
    """Represents a VPN profile with connection details and routing configuration"""

    def __init__(self, name: str, url: str, routes: List[DestinationNetwork]):
        self.name = name
        self.url = url
        self.routes = routes

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'url': self.url,
            'routes': [route.to_cidr() for route in self.routes]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VPNProfile':
        return cls(
            name=data['name'],
            url=data['url'],
            routes=[DestinationNetwork.from_cidr(route) for route in data.get('routes', [])]
        )

    def __str__(self) -> str:
        return self.name


class VPNProfileManager:
    """Manages VPN profiles - loading, saving, and CRUD operations"""

    def __init__(self, config_dir: Path):
        self.profiles_file = config_dir / VPN_PROFILES_FILE
        self.profiles: Dict[str, VPNProfile] = {}
        self.load_profiles()

    def load_profiles(self) -> None:
        """Load profiles from YAML file"""
        try:
            if self.profiles_file.exists():
                with open(self.profiles_file, 'r') as f:
                    data = yaml.safe_load(f) or {}
                    self.profiles = {
                        name: VPNProfile.from_dict(profile_data)
                        for name, profile_data in data.items()
                    }
                logger.info(f"Loaded {len(self.profiles)} VPN profiles")
            else:
                logger.info("No existing profiles file found, starting with empty profiles")
        except Exception as e:
            logger.error(f"Error loading profiles: {e}")
            self.profiles = {}

    def save_profiles(self) -> None:
        """Save profiles to YAML file"""
        try:
            data = {name: profile.to_dict() for name, profile in self.profiles.items()}
            with open(self.profiles_file, 'w') as f:
                yaml.safe_dump(data, f, indent=2, default_flow_style=False)
            logger.info(f"Saved {len(self.profiles)} VPN profiles")
        except Exception as e:
            logger.error(f"Error saving profiles: {e}")

    def get_profile(self, name: str) -> Optional[VPNProfile]:
        """Get a profile by name"""
        return self.profiles.get(name)

    def add_profile(self, profile: VPNProfile) -> None:
        """Add or update a profile"""
        self.profiles[profile.name] = profile
        self.save_profiles()
        logger.info(f"Added/updated profile: {profile.name}")

    def remove_profile(self, name: str) -> bool:
        """Remove a profile by name"""
        if name in self.profiles:
            del self.profiles[name]
            self.save_profiles()
            logger.info(f"Removed profile: {name}")
            return True
        return False

    def get_profile_names(self) -> List[str]:
        """Get list of all profile names"""
        return list(self.profiles.keys())

    def is_valid_server_name(self, text: str) -> bool:
        """
        Check if the text looks like a valid VPN server name.

        Args:
            text: The text to validate

        Returns:
            bool: True if it looks like a server name
        """
        if not text or not text.strip():
            return False

        text = text.strip()

        # If it's already an existing profile, it's not a new server name
        if text in self.profiles:
            return False

        # If it starts with http/https, it's a URL
        if text.startswith(('http://', 'https://')):
            return True

        # Check if it looks like a domain name (contains dots and valid characters)
        # Simple validation: contains at least one dot and only valid domain characters
        if '.' in text and all(c.isalnum() or c in '.-' for c in text):
            # Must not start or end with dot or dash
            if not text.startswith(('.', '-')) and not text.endswith(('.', '-')):
                # Must have at least one letter (not just numbers and dots)
                if any(c.isalpha() for c in text):
                    return True

        return False


# def parse_routes_string(routes_str: str) -> List[str]:
#     """Parse a comma-separated string of routes into a list"""
#     if not routes_str.strip():
#         return []
    
#     routes = []
#     for route in routes_str.split(','):
#         route = route.strip()
#         if route:
#             routes.append(route)
    
#     return routes


# def routes_list_to_string(routes: List[str]) -> str:
#     """Convert a list of routes to a comma-separated string"""
#     return ', '.join(routes)
