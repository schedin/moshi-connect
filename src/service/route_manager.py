"""
Route manager, to override the VPN provider default routing..
"""

import sys
import subprocess
import logging
from config.vpn_profiles import DestinationNetwork

logger = logging.getLogger(__name__)


class RouteManager:
    def __init__(self, routes: list[DestinationNetwork]):
        self.routes = routes

    def apply_routes(self, device_index: str) -> None:
        self.device_index = device_index

        if not self.routes:
            return

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        route_deletemd = ["route", "delete", "0.0.0.0", "mask", "0.0.0.0", "IF", device_index]
        logger.info(f"Executing: {' '.join(route_deletemd)}")
        subprocess.run(route_deletemd, creationflags=creationflags)

        DUMMY_GATEWAY = "0.0.0.0"
        gateway = DUMMY_GATEWAY
        for route in self.routes:
            route_cmd = ["route", "add", route.destination_ip, "mask", route.netmask, gateway, "IF", device_index]
            logger.info(f"Executing: {' '.join(route_cmd)}")
            subprocess.run(route_cmd, creationflags=creationflags)

    def cleanup_routes(self) -> None:  
        if self.routes:
            pass
