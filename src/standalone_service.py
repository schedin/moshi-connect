#!/usr/bin/env python3
"""
Service-only entry point.
"""

import sys
import logging
import argparse
import threading
import time

from service.service_impl import ServiceImpl, SERVICE_NAME
from common.app_setup import initialize_app_environment

logger = logging.getLogger(__name__)


class StandaloneService:
    """Run the service as a standalone application.
    It should only be used when the service is running without a GUI.
    """
    def __init__(self) -> None:
        app_env = initialize_app_environment("Moshi Connect Service", is_service=True)
        if app_env is None:
            raise RuntimeError("Failed to initialize application environment")
        config_dir, log_dir = app_env
        logger.info("Starting Moshi Connect Service")
        self._stop_event = threading.Event()

    def exec(self) -> int:
        self.service = ServiceImpl()
        if not self.service.start_service():
            logger.error(f"Failed to start {SERVICE_NAME}")
            return 1

        try:
            self._stop_event.wait()
            return 0
        finally:
            self.service.stop_service()

    def stop(self) -> None:
        self._stop_event.set()


def main() -> int:
    parser = argparse.ArgumentParser(description="Moshi Connect Service")
    parser.parse_args()

    standalone_service = StandaloneService()
    service_thread = threading.Thread(target=standalone_service.exec, daemon=False)

    try:
        service_thread.start()
        logger.info(f"{SERVICE_NAME} running. Press Ctrl+C to stop.")
        while service_thread.is_alive():
            # Using sleep (instead of thread.join()) to allow KeyboardInterrupt in Windows
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
        standalone_service.stop()
        service_thread.join(timeout=5)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
