#!/usr/bin/env python3
"""
Build Distribution Script

This script uses PyInstaller to create executable files for:
1. main.py - The GUI application
2. standalone_service.py - The service-only application

The script will:
- Build executables using PyInstaller
- Copy runtime dependencies (images, openconnect) to distribution
- Create a complete, ready-to-package distribution folder
"""

import sys
import os
import shutil
from pathlib import Path
import PyInstaller.__main__


def get_project_root():
    """Get the project root directory (parent of scripts/)"""
    script_dir = Path(__file__).parent.absolute()
    return script_dir.parent


def ensure_directory(path):
    """Ensure a directory exists, create if it doesn't"""
    path = Path(path)
    if not path.exists():
        print(f"Creating directory: {path}")
        path.mkdir(parents=True, exist_ok=True)
    return path


def run_pyinstaller_with_spec(spec_file, project_root, build_dir, dist_dir):
    """
    Run PyInstaller using a custom spec file

    Args:
        spec_file: Path to the PyInstaller spec file
        project_root: Root directory of the project
        build_dir: Directory for temporary build files
        dist_dir: Directory for final distribution files

    Returns:
        True if successful, False otherwise
    """
    # Ensure directories exist
    ensure_directory(build_dir)
    ensure_directory(dist_dir)

    # Construct PyInstaller arguments
    args = [
        str(spec_file),
        "--workpath", str(build_dir / "work"),
        "--distpath", str(dist_dir),
        # Clean build without confirmation prompt
        "--clean",
        "--noconfirm",
    ]

    print(f"\n{'='*70}")
    print(f"Building with custom spec file")
    print(f"Spec file: {spec_file}")
    print(f"Arguments: {' '.join(args)}")
    print(f"{'='*70}\n")

    # Change to project root directory
    original_cwd = os.getcwd()
    os.chdir(str(project_root))
    try:
        PyInstaller.__main__.run(args)

        print(f"\n✓ Successfully built bundle using spec file")
        return True

    except Exception as e:
        print(f"\n✗ Failed to build using spec file")
        print(f"Error: {e}")
        return False
    finally:
        # Restore original working directory
        os.chdir(original_cwd)


def create_logs_directory(dist_bundle_dir):
    """
    Create the logs subdirectory in the distribution folder.

    Args:
        dist_bundle_dir: Distribution bundle directory (e.g., build/dist/moshi-connect)

    Returns:
        True if successful, False otherwise
    """
    logs_dir = dist_bundle_dir / "logs"
    try:
        logs_dir.mkdir(exist_ok=True)
        print(f"✓ Created logs directory: {logs_dir}")
        return True
    except Exception as e:
        print(f"✗ Failed to create logs directory: {e}")
        return False


def copy_runtime_dependencies(project_root, dist_bundle_dir):
    """
    Copy runtime dependencies to the distribution folder.

    Args:
        project_root: Root directory of the project
        dist_bundle_dir: Distribution bundle directory (e.g., build/dist/moshi-connect)

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*70}")
    print("COPYING RUNTIME DEPENDENCIES")
    print(f"{'='*70}\n")

    success = True

    # Copy images directory
    images_src = project_root / "images"
    images_dst = dist_bundle_dir / "images"

    if images_src.exists():
        print(f"Copying images: {images_src} -> {images_dst}")
        try:
            if images_dst.exists():
                shutil.rmtree(images_dst)
            shutil.copytree(images_src, images_dst)
            print(f"✓ Copied images directory")
        except Exception as e:
            print(f"✗ Failed to copy images: {e}")
            success = False
    else:
        print(f"⚠ Warning: Images directory not found: {images_src}")

    # Copy openconnect directory
    openconnect_src = project_root / "build" / "openconnect"
    openconnect_dst = dist_bundle_dir / "openconnect"

    if openconnect_src.exists():
        print(f"Copying openconnect: {openconnect_src} -> {openconnect_dst}")
        try:
            if openconnect_dst.exists():
                shutil.rmtree(openconnect_dst)
            shutil.copytree(openconnect_src, openconnect_dst)
            print(f"✓ Copied openconnect directory")

            # Count files
            file_count = sum(1 for _ in openconnect_dst.rglob('*') if _.is_file())
            print(f"  ({file_count} files)")
        except Exception as e:
            print(f"✗ Failed to copy openconnect: {e}")
            success = False
    else:
        print(f"⚠ Warning: OpenConnect directory not found: {openconnect_src}")
        print(f"  Run download_openconnect.py or download_openconnect_gui.py first")

    print()
    return success


def main():
    print("Build Distribution Script")
    print(f"Platform: {sys.platform}")
    print(f"Python: {sys.version}")
    
    # Get project paths
    project_root = get_project_root()
    print(f"Project root: {project_root}")
    
    # Define build directories
    build_dir = project_root / "build"
    dist_dir = project_root / "build" / "dist"
    
    # Define spec file and source files
    spec_file = project_root / "moshi-connect-bundle.spec"
    main_entry = project_root / "src" / "main.py"
    service_entry = project_root / "src" / "standalone_service.py"

    # Verify files exist
    if not spec_file.exists():
        print(f"✗ Error: Spec file not found: {spec_file}")
        return 1

    if not main_entry.exists():
        print(f"✗ Error: Entry point not found: {main_entry}")
        return 1

    if not service_entry.exists():
        print(f"✗ Error: Entry point not found: {service_entry}")
        return 1
    
    ensure_directory(build_dir)
    ensure_directory(dist_dir)
    
    # Build both applications using custom spec file
    print("\n" + "="*70)
    print("BUILDING BUNDLE")
    print("="*70)

    success = run_pyinstaller_with_spec(
        spec_file=spec_file,
        project_root=project_root,
        build_dir=build_dir,
        dist_dir=dist_dir
    )

    # Copy runtime dependencies to the distribution
    if success:
        dist_bundle_dir = dist_dir / "moshi-connect"
        if dist_bundle_dir.exists():
            # Create logs directory
            logs_success = create_logs_directory(dist_bundle_dir)
            success = success and logs_success

            # Copy runtime dependencies
            deps_success = copy_runtime_dependencies(project_root, dist_bundle_dir)
            success = success and deps_success
        else:
            print(f"✗ Error: Distribution bundle directory not found: {dist_bundle_dir}")
            success = False

    # Summary
    print("\n" + "="*70)
    print("BUILD SUMMARY")
    print("="*70)

    if success:
        print("✓ Bundle: SUCCESS")
        print("  - GUI Application")
        print("  - Service Application")
    else:
        print("✗ Bundle: FAILED")
    
    print(f"\nOutput directory: {dist_dir}")
    print(f"Build files: {build_dir}")
    
    if dist_dir.exists():
        print("\nGenerated files:")
        for item in sorted(dist_dir.iterdir()):
            if item.is_dir():
                print(f"  📁 {item.name}/")
                # List executables in the directory
                for exe in sorted(item.iterdir()):
                    if exe.is_file():
                        size_mb = exe.stat().st_size / (1024 * 1024)
                        print(f"     - {exe.name} ({size_mb:.2f} MB)")
            else:
                size_mb = item.stat().st_size / (1024 * 1024)
                print(f"  📄 {item.name} ({size_mb:.2f} MB)")
    
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("1. Test the executables in build/dist/moshi-connect/")
    print("2. The distribution includes:")
    print("   - moshi-connect.exe (GUI)")
    print("   - moshi-connect-service.exe (Service)")
    print("   - images/ (runtime icons)")
    print("   - openconnect/ (VPN binaries)")
    print("3. The build/dist/moshi-connect/ folder is ready for packaging")
    print("4. Create a Windows installer that packages this entire folder")

    # Return exit code
    if success:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())

