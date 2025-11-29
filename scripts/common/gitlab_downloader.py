#!/usr/bin/env python3
"""
GitLab Artifact Downloader

Common functionality for downloading artifacts from GitLab CI/CD pipelines.
This module provides a generic interface for downloading artifacts from GitLab projects.
"""

import os
import json
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .windows_installer_extractor import WindowsInstallerExtractor

logger = logging.getLogger(__name__)


class GitLabArtifactDownloader:
    """Downloads and extracts artifacts from GitLab CI/CD pipelines"""

    def __init__(self, project_id: int, installer_dir: Path, extract_dir: Path, force: bool = False):
        """
        Initialize the downloader

        Args:
            project_id: GitLab project ID
            installer_dir: Directory to save installer files
            extract_dir: Directory to extract files to
            force: Whether to overwrite existing files
        """
        self.project_id = project_id
        self.installer_dir = installer_dir
        self.extract_dir = extract_dir
        self.force = force
        self.session_headers = {
        }

        # Initialize Windows installer extractor
        self.extractor = WindowsInstallerExtractor(
            extract_dir=extract_dir,
            force=force
        )

        # GitLab API configuration
        self.gitlab_api_base = "https://gitlab.com/api/v4"
    
    def _make_request(self, url: str, headers: Optional[Dict[str, str]] = None) -> bytes:
        """Make HTTP request with error handling"""
        request_headers = self.session_headers.copy()
        if headers:
            request_headers.update(headers)
        
        req = Request(url, headers=request_headers)
        
        try:
            with urlopen(req) as response:
                return response.read()
        except HTTPError as e:
            logger.error(f"HTTP error {e.code} when requesting {url}: {e.reason}")
            raise
        except URLError as e:
            logger.error(f"URL error when requesting {url}: {e.reason}")
            raise
    
    def _search_artifacts(self, job_pattern: str, artifact_pattern: str) -> Optional[Tuple[int, str]]:
        """
        Search for artifacts by checking pipelines and their jobs

        Args:
            job_pattern: Pattern to match in job names
            artifact_pattern: Pattern to match in artifact filenames

        Returns:
            Tuple of (job_id, artifact_filename) if found, None otherwise
        """
        logger.info("Searching for artifacts in successful pipelines...")

        # Get successful pipelines (public API, no auth required)
        # Limit to reasonable number to avoid long search times
        url = f"{self.gitlab_api_base}/projects/{self.project_id}/pipelines"
        params = "?status=success&per_page=20"

        try:
            response_data = self._make_request(url + params)
            pipelines = json.loads(response_data.decode('utf-8'))

            if not pipelines:
                logger.error("No successful pipelines found")
                return None

            logger.info(f"Found {len(pipelines)} successful pipelines")

            # Search through pipelines for matching jobs with artifacts
            pipelines_checked = 0
            max_pipelines_to_check = 10  # Limit to avoid long search times

            for pipeline in pipelines:
                pipelines_checked += 1
                if pipelines_checked > max_pipelines_to_check:
                    logger.info(f"Reached maximum of {max_pipelines_to_check} pipelines to check")
                    break

                pipeline_id = pipeline['id']
                logger.debug(f"Checking pipeline {pipeline_id} (SHA: {pipeline['sha'][:8]}) [{pipelines_checked}/{max_pipelines_to_check}]")

                try:
                    # Get jobs for this pipeline (public API)
                    jobs_url = f"{self.gitlab_api_base}/projects/{self.project_id}/pipelines/{pipeline_id}/jobs"
                    jobs_data = self._make_request(jobs_url)
                    jobs = json.loads(jobs_data.decode('utf-8'))

                    # Find matching jobs - check all matching jobs regardless of artifacts_file flag
                    # because GitLab API may incorrectly report artifacts as unavailable
                    matching_jobs_in_pipeline = []
                    all_jobs_in_pipeline = []

                    for job in jobs:
                        job_name = job.get('name', '')
                        job_id = job.get('id')
                        status = job.get('status')
                        has_artifacts_flag = bool(job.get('artifacts_file'))

                        all_jobs_in_pipeline.append(f"{job_name} (ID: {job_id}, Status: {status}, API artifacts: {has_artifacts_flag})")

                        if job_pattern in job_name and status == 'success':
                            matching_jobs_in_pipeline.append(job)
                            logger.debug(f"Found matching job: {job_name} (ID: {job_id}) - Status: {status}, API artifacts flag: {has_artifacts_flag}")

                    logger.debug(f"Pipeline {pipeline_id} has {len(jobs)} jobs total:")
                    for job_info in all_jobs_in_pipeline:
                        logger.debug(f"  {job_info}")

                    if not matching_jobs_in_pipeline:
                        logger.debug(f"No matching jobs found in pipeline {pipeline_id}")
                        continue

                    logger.debug(f"Found {len(matching_jobs_in_pipeline)} matching jobs in pipeline {pipeline_id}, will check for artifacts...")

                    # Check each matching job for the artifact pattern
                    for job in matching_jobs_in_pipeline:
                        job_name = job.get('name', '')
                        job_id = job.get('id')

                        try:
                            # Try to download and check artifacts - ignore the artifacts_file flag
                            logger.debug(f"Attempting to download artifacts from job {job_name} (ID: {job_id})")
                            artifacts_url = f"{self.gitlab_api_base}/projects/{self.project_id}/jobs/{job_id}/artifacts"

                            try:
                                artifacts_data = self._make_request(artifacts_url)
                                logger.debug(f"Successfully downloaded {len(artifacts_data)} bytes of artifacts from job {job_id}")
                            except Exception as download_error:
                                logger.debug(f"Failed to download artifacts from job {job_id}: {download_error}")
                                continue

                            # Create temporary file to check contents
                            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
                                temp_file.write(artifacts_data)
                                temp_path = Path(temp_file.name)

                            try:
                                logger.debug(f"Checking contents of artifacts zip from job {job_id}")
                                with zipfile.ZipFile(temp_path, 'r') as zip_file:
                                    file_list = zip_file.namelist()
                                    logger.debug(f"Artifacts zip contains {len(file_list)} files:")
                                    for f in file_list[:10]:  # Show first 10 files
                                        logger.debug(f"  - {f}")
                                    if len(file_list) > 10:
                                        logger.debug(f"  ... and {len(file_list) - 10} more files")

                                    matching_files = [f for f in file_list if artifact_pattern in f and f.endswith('.exe')]
                                    logger.debug(f"Files matching pattern '{artifact_pattern}*.exe': {matching_files}")

                                    if matching_files:
                                        logger.info(f"SUCCESS: Found matching artifacts in job {job_name} (ID: {job_id}): {matching_files}")
                                        return job_id, matching_files[0]
                                    else:
                                        logger.debug(f"No files matching '{artifact_pattern}*.exe' found in job {job_name}")

                            except zipfile.BadZipFile as zip_error:
                                logger.debug(f"Downloaded file from job {job_id} is not a valid zip: {zip_error}")
                                continue
                            finally:
                                temp_path.unlink()

                        except Exception as e:
                            logger.debug(f"Error checking artifacts for job {job_id}: {e}")
                            continue

                except Exception as e:
                    logger.debug(f"Error checking pipeline {pipeline_id}: {e}")
                    continue

            logger.error(f"No artifacts matching '{artifact_pattern}' found in jobs matching '{job_pattern}' in {pipelines_checked} pipelines checked")
            logger.info("This may be due to GitLab removing artifacts from recent CI jobs.")
            logger.info("You may need to wait for new builds with artifacts to become available.")
            return None

        except Exception as e:
            logger.error(f"Error searching for artifacts: {e}")
            return None
    
    def _download_artifacts(self, job_id: int) -> Path:
        """Download job artifacts to a temporary file"""
        url = f"{self.gitlab_api_base}/projects/{self.project_id}/jobs/{job_id}/artifacts"
        
        logger.info(f"Downloading artifacts from job {job_id}...")
        
        # Create temporary file for download
        temp_fd, temp_path = tempfile.mkstemp(suffix='.zip', prefix='artifacts_')
        temp_file = Path(temp_path)
        
        try:
            response_data = self._make_request(url)
            
            # Write to temporary file
            with os.fdopen(temp_fd, 'wb') as f:
                f.write(response_data)
            
            logger.info(f"Downloaded {len(response_data)} bytes to {temp_file}")
            return temp_file
            
        except Exception:
            # Clean up temp file on error
            try:
                os.close(temp_fd)
                temp_file.unlink()
            except:
                pass
            raise
    
    def _extract_installer_from_zip(self, zip_path: Path, installer_pattern: str) -> Optional[Path]:
        """Extract installer from the artifacts zip file"""
        logger.info(f"Extracting installer matching '{installer_pattern}' from {zip_path}...")

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                # List all files to find the installer
                file_list = zip_file.namelist()
                installer_files = [f for f in file_list if installer_pattern in f and f.endswith('.exe')]

                if not installer_files:
                    logger.error(f"No installer matching '{installer_pattern}*.exe' found in artifacts")
                    logger.debug(f"Available files: {file_list}")
                    return None

                # Use the first matching installer
                installer_file_path = installer_files[0]
                logger.info(f"Found installer: {installer_file_path}")

                # Create temporary file for the installer
                temp_fd, temp_installer_path = tempfile.mkstemp(suffix='.exe', prefix='installer_')
                temp_installer = Path(temp_installer_path)

                try:
                    # Extract the installer file to temporary location
                    with zip_file.open(installer_file_path) as source:
                        with os.fdopen(temp_fd, 'wb') as target:
                            target.write(source.read())

                    logger.info(f"Extracted installer to temporary file: {temp_installer}")
                    return temp_installer

                except Exception:
                    # Clean up temp file on error
                    try:
                        os.close(temp_fd)
                        temp_installer.unlink()
                    except:
                        pass
                    raise

        except zipfile.BadZipFile:
            logger.error(f"Invalid zip file: {zip_path}")
            return None
        except Exception as e:
            logger.error(f"Error extracting from zip: {e}")
            return None

    def _save_installer(self, installer_path: Path, installer_name: str) -> Path:
        """Save installer to the installer directory"""
        # Create installer directory
        self.installer_dir.mkdir(parents=True, exist_ok=True)

        saved_installer_path = self.installer_dir / installer_name

        # Copy installer to installer directory
        if not saved_installer_path.exists() or self.force:
            with open(installer_path, 'rb') as src, open(saved_installer_path, 'wb') as dst:
                dst.write(src.read())
            logger.info(f"Saved installer as: {saved_installer_path}")
        else:
            logger.info(f"Installer already exists: {saved_installer_path}")

        return saved_installer_path


    def download_and_extract(self, job_pattern: str, artifact_pattern: str,
                           installer_name: str, file_filter: Optional[List[str]] = None) -> bool:
        """
        Main download and extraction process

        Args:
            job_pattern: Pattern to match in job names
            artifact_pattern: Pattern to match in artifact filenames
            installer_name: Name to save the installer as
            file_filter: Optional list of file patterns to extract

        Returns:
            True if successful, False otherwise
        """
        try:
            # Step 1: Search for artifacts
            result = self._search_artifacts(job_pattern, artifact_pattern)
            if not result:
                return False

            job_id, artifact_filename = result
            logger.info(f"Using job {job_id} with artifact: {artifact_filename}")

            # Step 2: Download artifacts
            artifacts_zip = self._download_artifacts(job_id)

            try:
                # Step 3: Extract installer from zip
                installer_path = self._extract_installer_from_zip(artifacts_zip, artifact_pattern)
                if not installer_path:
                    return False

                try:
                    # Step 4: Save installer
                    saved_installer = self._save_installer(installer_path, installer_name)

                    # Step 5: Extract files from installer
                    success = self.extractor.extract_files_from_installer(saved_installer, file_filter)
                    if not success:
                        return False

                    logger.info(f"Successfully downloaded and extracted to {self.extract_dir}")
                    return True

                finally:
                    # Clean up temporary installer file
                    try:
                        installer_path.unlink()
                    except:
                        pass

            finally:
                # Clean up temporary artifacts zip
                try:
                    artifacts_zip.unlink()
                except:
                    pass

        except Exception as e:
            logger.error(f"Download and extraction failed: {e}")
            return False
