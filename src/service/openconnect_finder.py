"""
Locates the OpenConnect executable
"""
import sys
from pathlib import Path
import subprocess
from typing import Optional


def find_openconnect() -> Optional[Path]:
    """
    Find OpenConnect executable

    Returns:
        Path to openconnect.exe if found, None otherwise
    """

    if getattr(sys, "frozen", False):
        # When frozen, we're running as a bundled executable
        base_dir = Path(sys.executable).resolve().parent
    else:
        # When not frozen, we're running from source
        base_dir = Path(__file__).resolve().parent.parent.parent

    # Typically running as an executable in a bundled folder
    exe = base_dir / "openconnect" / "openconnect.exe"
    if exe.exists():
        return exe

    # Typically running from source using build artifacts
    exe = base_dir / "build" / "openconnect" / "openconnect.exe"
    if exe.exists():
        return exe

    # Search PATH
    try:
        result = subprocess.check_output(["where", "openconnect.exe"], text=True).strip()
        openconnect_path = result.split("\n")[0]
        return Path(openconnect_path)
    except Exception:
        return None
