#!/usr/bin/env python3
"""
OpenConnect GUI Release Downloader

Downloads the official OpenConnect GUI release from infradead.org
and extracts it to the build directory.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add the scripts directory to the path so we can import common modules
sys.path.insert(0, str(Path(__file__).parent))

from common.http_downloader import HttpDownloader
from common.windows_installer_extractor import WindowsInstallerExtractor

# Download configuration
DOWNLOAD_URL = "https://www.infradead.org/openconnect-gui/download/openconnect-gui-1.6.2-win64.exe"
INSTALLER_NAME = "openconnect-gui-1.6.2-win64.exe"

# Default directories (relative to project root)
DEFAULT_INSTALLER_DIR = "build"
DEFAULT_EXTRACT_DIR = "build/openconnect"

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
        description="Download and extract OpenConnect GUI release from infradead.org",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/download_openconnect_gui_release.py
  python scripts/download_openconnect_gui_release.py --installer-dir ./installers --extract-dir ./bin --force
  python scripts/download_openconnect_gui_release.py --quiet
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

    logger.info(f"OpenConnect GUI Release Downloader and Extractor")
    logger.info(f"Download URL: {DOWNLOAD_URL}")
    logger.info(f"Installer directory: {installer_dir}")
    logger.info(f"Extract directory: {extract_dir}")

    try:
        # Step 1: Download the installer
        downloader = HttpDownloader(
            download_dir=installer_dir,
            force=args.force
        )

        installer_path = downloader.download_file(DOWNLOAD_URL, INSTALLER_NAME)
        if not installer_path:
            logger.error("Failed to download installer")
            return 1

        logger.info(f"Downloaded installer to: {installer_path}")

        # Step 2: Extract files from installer
        extractor = WindowsInstallerExtractor(
            extract_dir=extract_dir,
            force=args.force
        )

        success = extractor.extract_files_from_installer(installer_path)
        if not success:
            logger.error("Failed to extract files from installer")
            return 1

        # Step 3: Look for important files
        openconnect_exe = None
        openconnect_gui_exe = None
        
        for file_path in extract_dir.rglob('*'):
            if file_path.is_file():
                if file_path.name.lower() == 'openconnect.exe':
                    openconnect_exe = file_path
                elif file_path.name.lower() == 'openconnect-gui.exe':
                    openconnect_gui_exe = file_path

        if openconnect_exe:
            logger.info(f"Found openconnect.exe at: {openconnect_exe}")
        else:
            logger.warning("openconnect.exe not found in extracted files")

        if openconnect_gui_exe:
            logger.info(f"Found openconnect-gui.exe at: {openconnect_gui_exe}")
        else:
            logger.warning("openconnect-gui.exe not found in extracted files")

        # Log summary of extracted files
        extracted_files = list(extract_dir.rglob('*'))
        files_only = [f for f in extracted_files if f.is_file()]
        
        exe_files = [f for f in files_only if f.suffix.lower() == '.exe']
        dll_files = [f for f in files_only if f.suffix.lower() == '.dll']
        
        logger.info(f"Extraction completed successfully!")
        logger.info(f"Total files extracted: {len(files_only)}")
        logger.info(f"Executable files: {len(exe_files)}")
        logger.info(f"DLL files: {len(dll_files)}")

        for exe_file in exe_files:
            logger.debug(f"  EXE: {exe_file.name}")

        return 0

    except Exception as e:
        logger.error(f"Failed to download and extract: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
