#!/usr/bin/env python3
"""
Build script for OpenConnect using MSYS2/MINGW64 toolchain.

This script clones/updates OpenConnect from GitLab, builds it using MSYS2/MINGW64,
and copies the result to the build directory.
"""

import os
import sys
import subprocess
import shutil
import logging
import argparse
import urllib.request
from pathlib import Path

# Configuration
#OPENCONNECT_VERSION = "v9.12"
OPENCONNECT_VERSION = "60bcf52dfc74cb9d9c63c8881c5ea89e119a8604" # Last good commit before bad
#OPENCONNECT_VERSION = "c6bbd46208ad231cc9fff21a937f615e0ddd3287" # Bad commit, causing "WaitForMultipleObjects failed: The handle is invalid. Failed to read from TAP device: The handle is invalid."

OPENCONNECT_REPO_URL = "https://gitlab.com/openconnect/openconnect.git"
MSYS2_ROOT = "C:\\msys64"
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
BUILD_DIR = PROJECT_ROOT / "build"
OPENCONNECT_GIT_DIR = BUILD_DIR / "openconnect.git"
OPENCONNECT_BUILD_DIR = BUILD_DIR / "openconnect"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def setup_msys2_environment():
    """Setup MSYS2 environment variables for subprocess calls."""
    env = os.environ.copy()
    env.update({
        "MSYSTEM": "MINGW64",
        "CHERE_INVOKING": "1",
        "PATH": f"{MSYS2_ROOT}\\mingw64\\bin;{MSYS2_ROOT}\\usr\\bin;{env.get('PATH', '')}"
    })
    return env


def run_msys2_command(command, cwd=None, shell_script=None):
    """Run a command in MSYS2 MINGW64 environment."""
    env = setup_msys2_environment()

    if shell_script:
        # Use relative path from cwd to shell_script
        if isinstance(shell_script, Path) and cwd:
            try:
                # Calculate relative path from cwd to shell_script
                relative_script = os.path.relpath(shell_script, cwd)
                shell_script_str = relative_script.replace('\\', '/')
            except ValueError:
                # If relative path calculation fails, use basename
                shell_script_str = shell_script.name
        else:
            shell_script_str = str(shell_script)

        # Run a shell script
        bash_exe = f"{MSYS2_ROOT}\\usr\\bin\\bash.exe"
        cmd = [bash_exe, "--login", "-i", "-c", f"./{shell_script_str}"]
    else:
        # Run a direct command
        bash_exe = f"{MSYS2_ROOT}\\usr\\bin\\bash.exe"
        cmd = [bash_exe, "--login", "-i", "-c", command]

    logger.info(f"Running MSYS2 command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            check=True
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        raise


def ensure_directories():
    """Create necessary directories."""
    BUILD_DIR.mkdir(exist_ok=True)
    logger.info(f"Created build directory: {BUILD_DIR}")


def check_git_available():
    """Check if git is available in MSYS2 environment."""
    try:
        run_msys2_command("git --version")
        return True
    except subprocess.CalledProcessError:
        return False


def clone_or_update_openconnect():
    """Clone or update OpenConnect repository."""
    # Check if git is available
    if not check_git_available():
        logger.warning("Git not found in MSYS2 environment, installing dependencies first...")
        install_dependencies()

    if OPENCONNECT_GIT_DIR.exists():
        logger.info(f"Updating existing OpenConnect repository at {OPENCONNECT_GIT_DIR}")
        run_msys2_command(f"git fetch origin", cwd=OPENCONNECT_GIT_DIR)
    else:
        logger.info(f"Cloning OpenConnect repository to {OPENCONNECT_GIT_DIR}")
        run_msys2_command(f"git clone {OPENCONNECT_REPO_URL} {OPENCONNECT_GIT_DIR.name}", cwd=BUILD_DIR)

    # Checkout the specified version
    logger.info(f"Checking out version {OPENCONNECT_VERSION}")
    run_msys2_command(f"git checkout {OPENCONNECT_VERSION}", cwd=OPENCONNECT_GIT_DIR)


def install_dependencies():
    """Install build dependencies using the shell script."""
    logger.info("Installing OpenConnect build dependencies")
    run_msys2_command(None, cwd=SCRIPT_DIR, shell_script=SCRIPT_DIR / "install_openconnect_deps.sh")


def download_vpnc_script(output_dir: Path):
    vpnc_script_url = "https://gitlab.com/openconnect/vpnc-scripts/-/raw/master/vpnc-script-win.js"
    vpnc_script_path = output_dir / "vpnc-script-win.js"

    logger.info("Downloading vpnc-script-win.js...")
    try:
        urllib.request.urlretrieve(vpnc_script_url, vpnc_script_path)
        logger.info(f"Downloaded vpnc-script-win.js to {vpnc_script_path}")
    except Exception as e:
        logger.error(f"Failed to download vpnc-script-win.js: {e}")
        raise


def build_openconnect():
    """Build OpenConnect using the simplified build script."""
    logger.info("Building OpenConnect")
    run_msys2_command(None, cwd=OPENCONNECT_GIT_DIR, shell_script=SCRIPT_DIR / "build_openconnect.sh")


def extract_wintun():
    """Extract wintun driver files to the build directory."""
    import zipfile

    wintun_zip = PROJECT_ROOT / "wintun" / "wintun-0.14.1.zip"
    if not wintun_zip.exists():
        logger.warning(f"Wintun zip file not found at {wintun_zip}")
        return

    logger.info("Extracting wintun driver...")

    # Extract wintun.dll for x64
    with zipfile.ZipFile(wintun_zip, 'r') as zip_ref:
        # Extract the x64 wintun.dll
        try:
            zip_ref.extract("wintun/bin/amd64/wintun.dll", OPENCONNECT_BUILD_DIR)
            # Move it to the root of the build directory
            wintun_src = OPENCONNECT_BUILD_DIR / "wintun" / "bin" / "amd64" / "wintun.dll"
            wintun_dst = OPENCONNECT_BUILD_DIR / "wintun.dll"
            shutil.move(str(wintun_src), str(wintun_dst))

            # Clean up extracted directory structure
            shutil.rmtree(OPENCONNECT_BUILD_DIR / "wintun")

            logger.info(f"Extracted wintun.dll to {wintun_dst}")
        except KeyError:
            logger.warning("Could not find wintun/bin/amd64/wintun.dll in zip file")


def copy_build_results():
    """Copy build results to the build directory with flat structure."""
    # Remove existing build directory
    if OPENCONNECT_BUILD_DIR.exists():
        shutil.rmtree(OPENCONNECT_BUILD_DIR)

    # Create new build directory
    OPENCONNECT_BUILD_DIR.mkdir(exist_ok=True)

    # Copy from flat directory (created by build script)
    flat_dir = OPENCONNECT_GIT_DIR / "install" / "flat"
    if flat_dir.exists():
        logger.info(f"Copying build results from {flat_dir} to {OPENCONNECT_BUILD_DIR}")

        # Copy all files from flat directory to build root
        for item in flat_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, OPENCONNECT_BUILD_DIR)
                logger.info(f"Copied {item.name}")

        # Extract wintun driver
        extract_wintun()

        # Log final contents
        logger.info("Final build directory contents:")
        for file in sorted(OPENCONNECT_BUILD_DIR.iterdir()):
            if file.is_file():
                logger.info(f"  {file.name}")
    else:
        logger.error(f"Flat directory not found at {flat_dir}")
        logger.error("Build may have failed or used different install location")
        raise FileNotFoundError(f"No build results found at {flat_dir}")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Build OpenConnect for Windows using MSYS2/MINGW64")
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Force installation of build dependencies"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean existing build directories before building"
    )
    return parser.parse_args()


def main():
    """Main build function."""
    args = parse_arguments()

    try:
        logger.info("Starting OpenConnect build process")
        logger.info(f"Building OpenConnect version: {OPENCONNECT_VERSION}")

        # Check if MSYS2 is available
        if not Path(MSYS2_ROOT).exists():
            logger.error(f"MSYS2 not found at {MSYS2_ROOT}")
            sys.exit(1)

        # Clean if requested
        if args.clean:
            logger.info("Cleaning existing build directories")
            if OPENCONNECT_GIT_DIR.exists():
                try:
                    # Try to clean git repository using git command first
                    run_msys2_command("git clean -fdx", cwd=OPENCONNECT_GIT_DIR)
                    run_msys2_command("git reset --hard", cwd=OPENCONNECT_GIT_DIR)
                except:
                    # If git commands fail, try to remove the directory
                    try:
                        shutil.rmtree(OPENCONNECT_GIT_DIR)
                    except PermissionError:
                        logger.warning(f"Could not remove {OPENCONNECT_GIT_DIR} due to permission issues")
                        logger.warning("You may need to manually delete this directory")
            if OPENCONNECT_BUILD_DIR.exists():
                try:
                    shutil.rmtree(OPENCONNECT_BUILD_DIR)
                except PermissionError:
                    logger.warning(f"Could not remove {OPENCONNECT_BUILD_DIR} due to permission issues")

        ensure_directories()

        # Install dependencies if requested
        if args.install_deps:
            logger.info("Force installing dependencies")
            install_dependencies()

        clone_or_update_openconnect()
        build_openconnect()
        copy_build_results()
        download_vpnc_script(OPENCONNECT_BUILD_DIR)

        logger.info("OpenConnect build completed successfully")
        logger.info(f"Build results available at: {OPENCONNECT_BUILD_DIR}")

    except Exception as e:
        logger.error(f"Build failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()