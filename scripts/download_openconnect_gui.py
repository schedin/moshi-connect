#!/usr/bin/env python3
"""
OpenConnect Downloader (from the openconnect-gui project)
"""

import argparse
import logging
import sys
from pathlib import Path

# Add the scripts directory to the path so we can import common modules
sys.path.insert(0, str(Path(__file__).parent))

from common.gitlab_downloader import GitLabArtifactDownloader

# GitLab project configuration
PROJECT_ID = 12274423  # openconnect/openconnect-gui project ID
JOB_PATTERN = "WindowsNative"  # Job name pattern to search for
ARTIFACT_PATTERN = "openconnect-gui"  # Installer filename pattern
INSTALLER_NAME = "openconnect-gui-installer.exe"

# Default directories (relative to project root)
DEFAULT_INSTALLER_DIR = "build"
DEFAULT_EXTRACT_DIR = "build/openconnect"

# Files needed for openconnect.exe runtime (based on build_deps_mingw@msys2.sh)
OPENCONNECT_RUNTIME_FILES = [
    # Core executable
    "openconnect.exe",

    # VPN script and driver
    "vpnc-script-win.js",
    "wintun.dll",

    # Required DLL dependencies (from build_deps_mingw@msys2.sh packaging section)
    "libgcc_s_seh-1.dll",
    "libgmp-10.dll",
    "libgnutls.dll",
    "libgnutls-30.dll",
    "libhogweed-6.dll",
    "libintl-8.dll",
    "libnettle-8.dll",
    "libp11-kit-0.dll",
    "libtasn1-6.dll",
    "libwinpthread-1.dll",
    "libxml2-2.dll",
    "zlib1.dll",
    "libstoken-1.dll",
    "liblz4.dll",
    "libopenconnect-5.dll",
    "libbrotlicommon.dll",
    "libbrotlidec.dll",
    "libbrotlienc.dll",
    "libzstd.dll",

    # Additional dependencies that may be needed
    "iconv.dll",      # Character encoding (alternative to libiconv-2.dll)
    "libiconv-2.dll", # Character encoding (newer version)
]

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = True) -> None:
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def get_project_root() -> Path:
    """Get the project root directory"""
    return Path(__file__).parent.parent


def main() -> int:
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Download and extract OpenConnect-GUI installer from GitLab CI artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/download_openconnect_gui.py
  python scripts/download_openconnect_gui.py --installer-dir ./installers --extract-dir ./bin --force
  python scripts/download_openconnect_gui.py --quiet
        """
    )

    parser.add_argument(
        '--installer-dir', '-i',
        type=Path,
        help=f'Directory to save installer files (default: {DEFAULT_INSTALLER_DIR})'
    )
    parser.add_argument(
        '--extract-dir', '-e',
        type=Path,
        help=f'Directory to extract OpenConnect files (default: {DEFAULT_EXTRACT_DIR})'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Overwrite existing files'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Disable debug logging (use INFO level instead)'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(not args.quiet)

    # Determine directories
    project_root = get_project_root()

    if args.installer_dir:
        installer_dir = args.installer_dir.resolve()
    else:
        installer_dir = project_root / DEFAULT_INSTALLER_DIR

    if args.extract_dir:
        extract_dir = args.extract_dir.resolve()
    else:
        extract_dir = project_root / DEFAULT_EXTRACT_DIR

    logger.info(f"OpenConnect-GUI Installer Downloader and Extractor")
    logger.info(f"Installer directory: {installer_dir}")
    logger.info(f"Extract directory: {extract_dir}")
    file_filter = OPENCONNECT_RUNTIME_FILES

    # Create downloader and run
    try:
        downloader = GitLabArtifactDownloader(
            project_id=PROJECT_ID,
            installer_dir=installer_dir,
            extract_dir=extract_dir,
            force=args.force
        )

        success = downloader.download_and_extract(
            job_pattern=JOB_PATTERN,
            artifact_pattern=ARTIFACT_PATTERN,
            installer_name=INSTALLER_NAME,
            file_filter=file_filter
        )

        if success:
            # Look for openconnect.exe specifically
            openconnect_exe = None
            for file_path in extract_dir.rglob('*'):
                if file_path.is_file() and file_path.name.lower() == 'openconnect.exe':
                    openconnect_exe = file_path
                    break

            if openconnect_exe:
                logger.info(f"Found openconnect.exe at: {openconnect_exe}")
            else:
                logger.warning("openconnect.exe not found in extracted files")

            extracted_files = list(extract_dir.rglob('*.dll'))
            logger.info(f"Extracted {len(extracted_files)} files")
            for extracted_file in extracted_files:
                logger.debug(f"  - {extracted_file.name}")

        return 0 if success else 1

    except Exception as e:
        logger.error(f"Failed to initialize downloader: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
