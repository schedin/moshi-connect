#!/usr/bin/env python3
"""
Main entry point for the the application. May start either only the GUI or the GUI + service.
"""

import sys
import os
import logging
import signal
import argparse
from pathlib import Path
from types import FrameType

import ui.gui_main as gui_main
from service.service_runner import ServiceRunner
from common.app_setup import initialize_app_environment

logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Moshi Connect")
    parser.add_argument(
        "--start-service",
        action="store_true",
        default=False,
        help="Start the VPN service (default: False)"
    )
    return parser.parse_args()


def main() -> None:
    """Main application entry point"""

    # Parse command line arguments
    args = parse_arguments()

    app_env = initialize_app_environment("Moshi Connect", is_service=False)
    if app_env is None:
        sys.exit(1)

    config_dir, log_dir = app_env

    service_runner = None
    if args.start_service:
        # Use ServiceRunner for co-located GUI+service operation
        # This runs the service in a separate thread alongside the GUI
        service_runner = ServiceRunner()
        if not service_runner.start_service():
            logger.error("Failed to start VPN service")
            sys.exit(1)

    window, app = gui_main.init_gui(config_dir, log_dir)

    signal_count = 0
    def signal_handler(signum: int, frame: FrameType | None) -> None:
        """Handle SIGINT (Ctrl+C) signals for graceful shutdown"""
        nonlocal signal_count
        signal_count += 1
        signal_names: dict[int, str] = {
            signal.SIGINT: "SIGINT (Ctrl+C)",
            signal.SIGTERM: "SIGTERM"
        }
        signal_name = signal_names.get(signum, f"signal {signum}")

        logger.error(f"Received signal!")
        if signal_count == 1:
            logger.info(f"Received {signal_name}, initiating graceful shutdown...")
            logger.debug("Shutting down main window and disconnecting VPN if connected...")
            try:
                window.quit_application(force_quit=True)
                if service_runner is not None:
                    service_runner.stop_service()
            except Exception as e:
                logger.error(f"Error during graceful shutdown: {e}")
                sys.exit(1)
        else:
            logger.warning(f"Received second {signal_name}, forcing immediate exit!")
            sys.exit(1)

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    # SIGTERM is also supported on Windows for termination requests
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        gui_main.start_gui(window, app)
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        if service_runner is not None:
            service_runner.stop_service()


if __name__ == "__main__":
    main()
