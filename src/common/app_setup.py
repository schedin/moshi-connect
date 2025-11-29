"""
Common application setup functionality

This module provides shared functionality for setting up the application,
including dependency checking, directory initialization, and logging configuration.
"""

import sys
import os
import logging
from pathlib import Path
from typing import Optional

import config.constants as constants
from _version import __version__
from common.logging_config import setup_logging_for_service, setup_logging_for_gui

logger = logging.getLogger(__name__)


def get_config_dir() -> Path:
    """Get the roaming AppData directory for settings and profiles"""
    roaming_base = Path(os.environ["APPDATA"])  # e.g. C:\Users\<you>\AppData\Roaming
    app_roaming = roaming_base / constants.APP_DIR
    app_roaming.mkdir(exist_ok=True)
    return app_roaming


def get_log_dir() -> Path:
    """Get the local AppData directory for logs and temporary data"""
    local_base = Path(os.environ["LOCALAPPDATA"])  # e.g. C:\Users\<you>\AppData\Local
    app_local = local_base / constants.APP_DIR
    app_local.mkdir(exist_ok=True)
    return app_local


def setup_logging(log_dir: Path, app_name: str) -> None:
    """Setup application logging (deprecated - use setup_logging_for_gui or setup_logging_for_service)

    Args:
        log_dir: Directory for log files
        app_name: Name of the application for logging messages
    """
    # Create logs directory in user's local AppData
    log_file = log_dir / constants.LOG_FILE

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger.info(f"{app_name} {__version__} starting...")
    logger.info(f"Log file: {log_file}")


def check_dependencies(check_gui_deps: bool = True) -> bool:
    """Check if required dependencies are available

    Args:
        check_gui_deps: Whether to check GUI-specific dependencies (PySide6, pystray)
    """
    missing_deps = []

    if check_gui_deps:
        try:
            import PySide6
        except ImportError:
            missing_deps.append("PySide6")

        try:
            import pystray
        except ImportError:
            missing_deps.append("pystray")

    try:
        import lz4
    except ImportError:
        missing_deps.append("lz4")

    if missing_deps:
        print("Missing required dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nPlease install them using pip or your package manager")
        return False

    return True


def initialize_app_environment(app_name: str, is_service: bool = False) -> tuple[Path, Path] | None:
    """Initialize the application environment (directories, logging, dependencies)

    Args:
        app_name: Name of the application for logging messages
        is_service: Whether this is a service application (uses different logging strategy)

    Returns:
        tuple: (config_dir, log_dir) if successful, None if failed
    """
    if not check_dependencies(check_gui_deps=not is_service):
        return None

    config_dir = get_config_dir()
    log_dir = get_log_dir()

    if is_service:
        setup_logging_for_service(app_name)
    else:
        setup_logging_for_gui(app_name)

    return config_dir, log_dir
