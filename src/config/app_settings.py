"""
Application settings management
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Optional, Any

from config.constants import APP_SETTINGS_FILE

logger = logging.getLogger(__name__)


class AppSettings:
    """Manages application settings and preferences"""
    
    def __init__(self, config_dir: Path):
        self.settings_file = config_dir / APP_SETTINGS_FILE
        self.settings: Dict[str, Any] = {}
        self.load_settings()

    def load_settings(self) -> None:
        """Load settings from YAML file"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    self.settings = yaml.safe_load(f) or {}
                logger.info("Loaded application settings")
            else:
                logger.info("No existing settings file found, starting with default settings")
                self.settings = {}
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self.settings = {}
    
    def save_settings(self) -> None:
        """Save settings to YAML file"""
        try:
            with open(self.settings_file, 'w') as f:
                yaml.safe_dump(self.settings, f, indent=2, default_flow_style=False)
            logger.debug("Saved application settings")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
    
    def get_last_selected_profile(self) -> Optional[str]:
        """Get the name of the last selected VPN profile"""
        return self.settings.get('last_selected_profile')
    
    def set_last_selected_profile(self, profile_name: str) -> None:
        """Set the name of the last selected VPN profile"""
        self.settings['last_selected_profile'] = profile_name
        self.save_settings()
        logger.debug(f"Saved last selected profile: {profile_name}")
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value by key"""
        return self.settings.get(key, default)
    
    def set_setting(self, key: str, value: Any) -> None:
        """Set a setting value by key"""
        self.settings[key] = value
        self.save_settings()
