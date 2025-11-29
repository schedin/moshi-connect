
"""
Windows Service wrapper for Moshi Connect Service

This module provides a Windows service implementation that wraps the StandaloneService
class to run as a proper Windows service that can be installed, started, and stopped
using Windows Service Control Manager.
"""

import sys
import win32serviceutil
import servicemanager

from standalone_service import StandaloneService, SERVICE_NAME


class MoshiConnectWindowsService(win32serviceutil.ServiceFramework):
    """Windows Service wrapper for Moshi Connect Service"""

    _svc_name_ = "MoshiConnectSvc"
    _svc_display_name_ = SERVICE_NAME
    _svc_description_ = f"Provider of VPN connectivity for the Moshi Connect application"

    def __init__(self, args) -> None:
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.standalone_service = StandaloneService()

    def SvcStop(self) -> None:
        self.standalone_service.stop()

    def SvcDoRun(self) -> None:
        self.standalone_service.exec()


def main() -> None:
    if len(sys.argv) == 1:
        # Executed by Windows Service Control Manager as a service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(MoshiConnectWindowsService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        # Executed as a normal application (with argument start/stop/install/remove/debug)
        win32serviceutil.HandleCommandLine(MoshiConnectWindowsService)

if __name__ == '__main__':
    main()
