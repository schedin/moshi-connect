#!/usr/bin/env python3
"""
HTTP File Downloader

Common functionality for downloading files from HTTP/HTTPS URLs.
This module provides a generic interface for downloading files with progress logging.
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)


class HttpDownloader:
    """
    Generic HTTP file downloader
    """
    
    def __init__(self, download_dir: Path, force: bool = False):
        """
        Initialize the downloader
        
        Args:
            download_dir: Directory to save downloaded files
            force: Whether to overwrite existing files
        """
        self.download_dir = download_dir
        self.force = force
        self.session_headers = {
        }
    
    def download_file(self, url: str, filename: str) -> Optional[Path]:
        """
        Download a file from URL
        
        Args:
            url: URL to download from
            filename: Name to save the file as
            
        Returns:
            Path to downloaded file if successful, None otherwise
        """
        logger.info(f"Downloading file from: {url}")
        
        # Create download directory
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if file already exists
        file_path = self.download_dir / filename
        if file_path.exists() and not self.force:
            logger.info(f"File already exists: {file_path}")
            return file_path
        
        try:
            # Download to temporary file first
            temp_fd, temp_path = tempfile.mkstemp(suffix='.tmp', prefix='download_')
            temp_file = Path(temp_path)
            
            try:
                response_data = self._make_request(url)
                
                # Write to temporary file
                with open(temp_fd, 'wb') as f:
                    f.write(response_data)
                
                # Move to final location
                if file_path.exists():
                    file_path.unlink()  # Remove existing file
                
                temp_file.rename(file_path)
                
                logger.info(f"Downloaded {len(response_data)} bytes to {file_path}")
                return file_path
                
            except Exception:
                # Clean up temp file on error
                try:
                    temp_file.unlink()
                except:
                    pass
                raise
                
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            return None
    
    def _make_request(self, url: str) -> bytes:
        """
        Make HTTP request and return response data
        
        Args:
            url: URL to request
            
        Returns:
            Response data as bytes
            
        Raises:
            HTTPError: If HTTP request fails
            URLError: If URL is invalid or network error occurs
        """
        try:
            request = Request(url, headers=self.session_headers)
            
            with urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise HTTPError(url, response.status, f"HTTP {response.status}", 
                                  response.headers, None)
                
                # Get content length for progress logging
                content_length = response.headers.get('Content-Length')
                if content_length:
                    logger.debug(f"Content-Length: {int(content_length):,} bytes")
                
                # Read response data
                data = response.read()
                logger.debug(f"Downloaded {len(data):,} bytes")
                
                return data
                
        except HTTPError as e:
            logger.error(f"HTTP error {e.code}: {e.reason}")
            raise
        except URLError as e:
            logger.error(f"URL error: {e.reason}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
