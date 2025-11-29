#!/usr/bin/env python3
"""
Windows Installer Extractor

Common functionality for extracting files from Windows installer executables.
This module provides a generic interface for extracting contents from Windows
installer files using 7z.

Requirements:
    - 7z command-line tool (install with: sudo apt install p7zip-full)
"""

import logging
import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def check_7z_available() -> Optional[str]:
    """
    Check if 7z is available and return its path
    
    Returns:
        Path to 7z executable if available, None otherwise
    """

    possible_paths = [
        "7z",      # In PATH
        "7za",     # Standalone version
        "7zz",     # Linux version 
        r"C:\Program Files\7-Zip\7z.exe",     # Windows default installation
        r"C:\Program Files\7-Zip\7za.exe",    # Windows standalone version
    ]
    for cmd in possible_paths:
        try:
            result = subprocess.run([cmd, '--help'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
            if result.returncode == 0:
                logger.debug(f"Found 7z at: {cmd}")
                return cmd
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    
    logger.debug("7z not found in PATH")
    return None


class WindowsInstallerExtractor:
    """
    Extractor for Windows installer files using 7z
    """
    
    def __init__(self, extract_dir: Path, force: bool = False):
        """
        Initialize the extractor
        
        Args:
            extract_dir: Directory to extract files to
            force: Whether to overwrite existing files
        """
        self.extract_dir = extract_dir
        self.force = force
        
        # Check for 7z availability
        self.sevenzip_path = check_7z_available()
        
        if not self.sevenzip_path:
            raise RuntimeError(
                "7z is required but not found. "
                "Linux: curl -sL  https://www.7-zip.org/a/7z2501-linux-x64.tar.xz | sudo tar -xJ -C /usr/local/bin 7zz"
            )
    
    def extract_files_from_installer(self, installer_path: Path, 
                                   file_filter: Optional[List[str]] = None) -> bool:
        """
        Extract files from Windows installer
        
        Args:
            installer_path: Path to the installer file
            file_filter: Optional list of file patterns to extract
            
        Returns:
            True if extraction successful, False otherwise
        """
        if not installer_path.exists():
            logger.error(f"Installer file not found: {installer_path}")
            return False
        
        logger.info(f"Extracting files from installer: {installer_path}")
        
        try:
            # Create output directory
            self.extract_dir.mkdir(parents=True, exist_ok=True)
            
            # Check if directory already has files and force flag
            if any(self.extract_dir.iterdir()) and not self.force:
                logger.warning(f"{self.extract_dir} already contains files. Use --force to overwrite.")
                return True
            
            # Extract using 7z
            logger.debug("Extracting with 7z")
            if self._extract_with_7z(installer_path, file_filter):
                self._log_extracted_files()
                return True
            else:
                logger.error("7z extraction failed")
                return False
                
        except Exception as e:
            logger.error(f"Error extracting files from installer: {e}")
            return False
    
    def _extract_with_7z(self, installer_path: Path, file_filter: Optional[List[str]] = None) -> bool:
        """Extract using 7z command"""
        try:
            if file_filter:
                # For filtered extraction, we need to extract all first, then filter
                temp_extract_dir = self.extract_dir / "temp_extract"
                temp_extract_dir.mkdir(exist_ok=True)
                
                # Extract all files to temp directory
                cmd = [
                    self.sevenzip_path,
                    "x",  # Extract with full paths
                    str(installer_path),
                    f"-o{temp_extract_dir}",
                    "-y"  # Yes to all prompts
                ]
                
                logger.debug(f"7z: Extracting all files to temp directory: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                if result.returncode != 0:
                    logger.debug(f"7z extraction failed: {result.stderr}")
                    return False
                
                # Copy filtered files to final destination
                self._copy_filtered_files(temp_extract_dir, file_filter)
                
                # Clean up temp directory
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
                
            else:
                # Extract all files directly
                cmd = [
                    self.sevenzip_path,
                    "x",  # Extract with full paths
                    str(installer_path),
                    f"-o{self.extract_dir}",
                    "-y"  # Yes to all prompts
                ]
                
                logger.debug(f"7z: Extracting all files: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                if result.returncode != 0:
                    logger.debug(f"7z extraction failed: {result.stderr}")
                    return False
            
            return True
            
        except Exception as e:
            logger.debug(f"7z extraction failed: {e}")
            return False
    
    def _copy_filtered_files(self, temp_extract_dir: Path, file_filter: List[str]) -> None:
        """Copy files matching the filter from temp directory to final destination"""
        logger.debug(f"Filtering files with patterns: {file_filter}")

        # Get list of all extracted files
        all_files = []
        for file_path in temp_extract_dir.rglob('*'):
            if file_path.is_file():
                rel_path = file_path.relative_to(temp_extract_dir)
                all_files.append(str(rel_path))

        # Filter files using the same logic as GitLab downloader
        files_to_extract = self._filter_files(all_files, file_filter)

        copied_files = []
        for file_path_str in files_to_extract:
            src = temp_extract_dir / file_path_str
            # Flatten structure - put all files in root of extract_dir
            dest_path = self.extract_dir / Path(file_path_str).name

            if src.exists():
                # Create parent directories if needed
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Copy file
                shutil.copy2(src, dest_path)
                copied_files.append(dest_path)
                logger.debug(f"Copied: {src.name} -> {dest_path}")

        if not copied_files:
            logger.warning(f"No files matched the filter patterns: {file_filter}")
        else:
            logger.info(f"Copied {len(copied_files)} filtered files")

    def _filter_files(self, all_files: List[str], file_filter: Optional[List[str]]) -> List[str]:
        """Filter files based on patterns"""
        if not file_filter:
            return all_files

        # Define specific DLLs we want (OpenConnect runtime dependencies)
        wanted_dlls = {
            'libffi-8.dll', 'libgcc_s_seh-1.dll', 'libgcc_s_dw2-1.dll',
            'libgmp-10.dll', 'libgnutls-30.dll', 'libhogweed-6.dll',
            'libintl-8.dll', 'libnettle-8.dll', 'libp11-kit-0.dll',
            'libtasn1-6.dll', 'libwinpthread-1.dll', 'libxml2-2.dll',
            'zlib1.dll', 'libstoken-1.dll', 'liblz4.dll', 'libiconv-2.dll',
            'libunistring-5.dll', 'libidn2-0.dll', 'liblzma-5.dll',
            'libbrotlicommon.dll', 'libbrotlidec.dll', 'libzstd.dll',
            'libbrotlienc.dll', 'libopenconnect-5.dll', 'wintun.dll'
        }

        files_to_extract = []

        for pattern in file_filter:
            if pattern == "*.dll":
                # Only extract specific OpenConnect runtime DLLs
                matching = [f for f in all_files
                          if f.lower().endswith('.dll') and
                          Path(f).name.lower() in wanted_dlls]
            elif pattern == "*.exe":
                matching = [f for f in all_files if f.lower().endswith('.exe')]
            elif pattern in ["openconnect.exe", "vpnc-script-win.js", "wintun.dll"]:
                matching = [f for f in all_files if Path(f).name.lower() == pattern.lower()]
            else:
                # Exact filename match
                matching = [f for f in all_files if Path(f).name.lower() == pattern.lower()]

            files_to_extract.extend(matching)
            logger.debug(f"Pattern '{pattern}' matched {len(matching)} files: {[Path(f).name for f in matching]}")

        # Remove duplicates
        files_to_extract = list(set(files_to_extract))
        logger.info(f"Filtering resulted in {len(files_to_extract)} files to extract")

        return files_to_extract
    
    def _log_extracted_files(self) -> None:
        """Log information about extracted files"""
        try:
            all_files = list(self.extract_dir.rglob('*'))
            files_only = [f for f in all_files if f.is_file()]
            
            logger.info(f"Extraction completed. Found {len(files_only)} files in {self.extract_dir}")
            
            # Log some details about what was extracted
            exe_files = [f for f in files_only if f.suffix.lower() == '.exe']
            dll_files = [f for f in files_only if f.suffix.lower() == '.dll']
            
            if exe_files:
                logger.info(f"Executable files: {len(exe_files)}")
                for exe_file in exe_files:
                    logger.debug(f"  - {exe_file.name}")
            
            if dll_files:
                logger.info(f"DLL files: {len(dll_files)}")
                for dll_file in dll_files[:10]:  # Limit to first 10 to avoid spam
                    logger.debug(f"  - {dll_file.name}")
                if len(dll_files) > 10:
                    logger.debug(f"  ... and {len(dll_files) - 10} more DLL files")
                    
        except Exception as e:
            logger.debug(f"Error logging extracted files: {e}")
