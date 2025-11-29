"""
Logging configuration for different application contexts.

This module provides logging setup for:
- Service (standalone_service.py, windows_service.py): Uses server.log with rotating handlers
- GUI application (main.py): Uses application.log with rotating handlers

The logging strategy differs based on whether the application is running as a service
or as a GUI application, and whether it's running from a build distribution or installed location.
"""

import sys
import os
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

import config.constants as constants
from _version import __version__

logger = logging.getLogger(__name__)


def get_executable_dir() -> Path:
    """Get the directory where the running executable is located.

    Returns:
        Path to the directory containing the running executable
    """
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle
        return Path(sys.executable).parent
    else:
        # Running as a script
        return Path(sys.executable).parent


def find_log_dir_for_service() -> Optional[Path]:
    r"""Find the log directory for the service (no directory creation).

    Checks in this order:
    1. If a 'logs' subdirectory exists relative to the executable's directory, use it
    2. If %LOCALAPPDATA%\moshi-connect directory exists, use it
    3. Otherwise, return None (no file logging)

    Returns:
        Path to log directory, or None if no suitable directory found
    """
    # Check 1: logs subdirectory relative to executable
    exe_dir = get_executable_dir()
    logs_dir = exe_dir / "logs"
    if logs_dir.exists():
        return logs_dir

    # Check 2: LOCALAPPDATA\moshi-connect
    try:
        local_base = Path(os.environ["LOCALAPPDATA"])
        app_local = local_base / constants.APP_DIR
        if app_local.exists():
            return app_local
    except (KeyError, OSError):
        pass

    return None


def find_log_dir_for_gui() -> Optional[Path]:
    r"""Find the log directory for the GUI application (with directory creation).

    Checks in this order:
    1. If a 'logs' subdirectory exists relative to the executable's directory, use it
    2. Otherwise, attempt to create %LOCALAPPDATA%\moshi-connect and use it
    3. If directory creation fails, return None (no file logging)

    Returns:
        Path to log directory, or None if no suitable directory found
    """
    # Check 1: logs subdirectory relative to executable
    exe_dir = get_executable_dir()
    logs_dir = exe_dir / "logs"
    if logs_dir.exists():
        return logs_dir

    # Check 2: Create LOCALAPPDATA\moshi-connect if needed
    try:
        local_base = Path(os.environ["LOCALAPPDATA"])
        app_local = local_base / constants.APP_DIR
        app_local.mkdir(parents=True, exist_ok=True)
        return app_local
    except (KeyError, OSError):
        pass

    return None


def setup_logging_for_service(app_name: str) -> None:
    """Setup logging for the service application.
    
    Uses server.log with rotating file handler.
    
    Args:
        app_name: Name of the application for logging messages
    """
    log_dir = find_log_dir_for_service()
    
    # Configure logging
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_dir:
        log_file = log_dir / constants.SERVER_LOG_FILE
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5
            )
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            )
            handlers.append(file_handler)
        except (OSError, IOError) as e:
            print(f"Warning: Could not create log file handler: {e}", file=sys.stderr)
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    logger.info(f"{app_name} {__version__} starting...")
    if log_dir:
        logger.info(f"Log file: {log_dir / constants.SERVER_LOG_FILE}")


def setup_logging_for_gui(app_name: str) -> None:
    """Setup logging for the GUI application.

    Uses application.log with rotating file handler. Attempts to create directories if needed.

    Args:
        app_name: Name of the application for logging messages
    """
    log_dir = find_log_dir_for_gui()
    
    # Configure logging
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_dir:
        log_file = log_dir / constants.LOG_FILE
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5
            )
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            )
            handlers.append(file_handler)
        except (OSError, IOError) as e:
            print(f"Warning: Could not create log file handler: {e}", file=sys.stderr)
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    logger.info(f"{app_name} {__version__} starting...")
    if log_dir:
        logger.info(f"Log file: {log_dir / constants.LOG_FILE}")

