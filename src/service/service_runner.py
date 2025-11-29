"""
Service Runner - Manages VPN Service Lifecycle

This module provides a runner for the VPN service that can be started
in a separate thread or process.
"""

import logging
import threading
import time

from service.service_impl import ServiceImpl, SERVICE_NAME

logger = logging.getLogger(__name__)


class ServiceRunner:
    """Runs the background IPC service in a separate thread"""

    def __init__(self) -> None:
        self.service: ServiceImpl
        self.service_thread: threading.Thread
        self.is_running = False
    
    def start_service(self) -> bool:
        """Start the VPN service in a separate thread"""
        if self.is_running:
            logger.warning("Service is already running")
            return True
        
        try:
            # Create service instance
            self.service = ServiceImpl()

            # Start service in background thread
            self.service_thread = threading.Thread(target=self._run_service, daemon=True)
            self.service_thread.start()

            # Wait a bit for service to start
            time.sleep(0.1)

            logger.info(f"Starting {SERVICE_NAME} thread...")
            return True

        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            return False

    def _run_service(self) -> None:
        """Run the service in background thread"""
        try:
            if self.service.start_service():
                self.is_running = True
                logger.info("VPN service started successfully")
                # Keep service running
                while self.is_running:
                    time.sleep(0.1)
            else:
                logger.error(f"Failed to start {SERVICE_NAME}")
        except Exception as e:
            logger.error(f"Error in service thread: {e}")
        finally:
            if self.service:
                self.service.stop_service()
            self.is_running = False
    
    def stop_service(self) -> None:
        """Stop the VPN service and thread"""
        if not self.is_running:
            return

        logger.info(f"Stopping {SERVICE_NAME}...")

        try:
            self.is_running = False

            if self.service:
                self.service.stop_service()

            if self.service_thread and self.service_thread.is_alive():
                self.service_thread.join(timeout=5.0)
                if self.service_thread.is_alive():
                    logger.warning("Service thread did not stop gracefully")

        except Exception as e:
            logger.error(f"Error stopping service: {e}")
