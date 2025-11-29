import json
import lz4.block
import configparser
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_default_firefox_profile_dir() -> Optional[Path]:
    """Get the default Firefox profile path using profiles.ini"""
    profiles_ini = Path.home() / "AppData/Roaming/Mozilla/Firefox/profiles.ini"

    if not profiles_ini.exists():
        logger.warning(f"Firefox profiles.ini not found at: {profiles_ini}")
        return None

    logger.debug(f"Reading Firefox profiles from: {profiles_ini}")
    config = configparser.RawConfigParser()
    config.read(profiles_ini)

    # First try to find Install sections (newer Firefox versions)
    install_sections = [s for s in config.sections() if s.startswith("Install")]
    if install_sections:
        path = config[install_sections[0]]["Default"]
        logger.debug(f"Found default profile in Install section: {path}")
    else:
        # Fallback if no Install section (older Firefox versions)
        default_profile_path = None
        for section in config.sections():
            if config.has_option(section, "Default") and config[section]["Default"] == "1":
                default_profile_path = config[section]["Path"]
                logger.debug(f"Found default profile in legacy section: {path}")
                break

        if default_profile_path:
            path = default_profile_path
        else:
            logger.warning("No default profile found in profiles.ini")
            return None

    return Path.home() / "AppData/Roaming/Mozilla/Firefox" / path

def extract_cookies_from_recovery_file() -> Optional[list[dict[str, str]]]:
    """Extract cookies from Firefox recovery.jsonlz4 file"""
    profile_dir = get_default_firefox_profile_dir()
    if not profile_dir:
        return None

    recovery_file = profile_dir / 'sessionstore-backups' / 'recovery.jsonlz4'

    if not recovery_file.exists():
        logger.warning(f"Recovery file not found: {recovery_file}")
        return None

    logger.debug(f"Reading recovery file: {recovery_file}")

    try:
        with open(recovery_file, 'rb') as f:
            # Skip the first 8 bytes (mozLz40\0 header)
            header = f.read(8)
            assert header == b'mozLz40\0', f"Invalid header: {header.decode('utf-8', errors='replace')}"
            logger.debug("Successfully validated mozLz40 header")

            # Read the rest of the file
            compressed_data = f.read()
            logger.debug(f"Read {len(compressed_data)} bytes of compressed data")

            # Decompress using LZ4
            decompressed_data = lz4.block.decompress(compressed_data)
            logger.debug(f"Decompressed to {len(decompressed_data)} bytes")

            # Parse as JSON
            session_data = json.loads(decompressed_data.decode('utf-8'))
            logger.debug("Successfully parsed session data as JSON")

            # Extract cookies from session data
            cookies = []
            if 'cookies' in session_data:
                cookies.extend(session_data['cookies'])

            logger.debug(f"Successfully extracted {len(cookies)} total cookies")
            return cookies

    except Exception as e:
        logger.error(f"Error extracting cookies: {e}")
        return None


def get_webvpn_cookies(host: Optional[str] = None) -> list[str]:
    cookies = extract_cookies_from_recovery_file()
    if cookies is None:
        return []
    webvpn_cookies = [cookie for cookie in cookies if cookie.get('name') == 'webvpn']
    if host:
        webvpn_cookies = [cookie for cookie in webvpn_cookies if cookie.get('host') == host]
    return [cookie['value'] for cookie in webvpn_cookies]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    print(get_webvpn_cookies())

if __name__ == "__main__":
    main()
