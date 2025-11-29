# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file. This spec file creates two executables in a single build:
1. The main GUI application
2. The service
"""

from PyInstaller.building.build_main import Analysis
from PyInstaller.building.api import PYZ, EXE, COLLECT

import os
import sys

DISTRIBUTION_NAME = "moshi-connect"
GUI_EXE_NAME = DISTRIBUTION_NAME
SERVICE_EXE_NAME = f"{GUI_EXE_NAME}-service"

# Collect hidden imports for packages that use dynamic imports
hidden_imports = []

# Common pathex (source directories)
pathex = [os.path.join(os.getcwd(), 'src')]

# Analysis for GUI application
a_gui = Analysis(
    ['src/main.py'],
    pathex=pathex,
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Analysis for Service application
a_service = Analysis(
    ['src/windows_service.py'],
    pathex=pathex,
    binaries=[],
    datas=[],
    hiddenimports=[
       'win32timezone',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    noarchive=False,
    optimize=0,
)

# Create PYZ archives
pyz_gui = PYZ(a_gui.pure)
pyz_service = PYZ(a_service.pure)

# Determine platform-specific settings
if sys.platform == "win32":
    # Windows settings
    gui_console = False  # No console for GUI on Windows
    service_console = True  # Keep console for service (for logging)
else:
    # Linux/Mac settings
    gui_console = True  # Keep console for debugging
    service_console = True

gui_icon = 'images/moshi-connect.ico'
service_icon = 'images/moshi-connect.ico'

# Create GUI executable
exe_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    [],
    exclude_binaries=True,
    name=GUI_EXE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=gui_console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=gui_icon,
)

# Create Service executable
exe_service = EXE(
    pyz_service,
    a_service.scripts,
    [],
    exclude_binaries=True,
    name=SERVICE_EXE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=service_console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=service_icon,
)

# Collect everything into a single distribution
coll = COLLECT(
    exe_gui,
    a_gui.binaries,
    a_gui.datas,
    exe_service,
    a_service.binaries,
    a_service.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=DISTRIBUTION_NAME,
)
