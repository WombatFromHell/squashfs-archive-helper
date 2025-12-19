"""
Checksum verification logic for the SquashFS Archive Helper.

This module contains functionality for validating and verifying
checksums of squashfs files to ensure integrity.
"""

import subprocess
from pathlib import Path
from typing import Optional

from .config import SquishFSConfig
from .errors import (
    ChecksumCommandExecutionError,
    ChecksumError,
)
from .logging import get_logger


class ChecksumManager:
    """
    Manager for checksum verification operations.

    This class handles checksum validation, file parsing,
    and integrity verification for squashfs files.
    """

    def __init__(self, config: Optional[SquishFSConfig] = None):
        self.config = config if config else SquishFSConfig()
        self.logger = get_logger(self.config.verbose)

    def _validate_checksum_files(self, file_path: str) -> tuple[Path, Path]:
        """Validate that checksum file exists and is in the same directory as target file."""
        file_path_obj = Path(file_path)
        checksum_file = file_path_obj.with_suffix(file_path_obj.suffix + ".sha256")

        # Check if both files exist
        if not file_path_obj.exists():
            raise ChecksumError(f"Target file does not exist: {file_path}")

        if not checksum_file.exists():
            raise ChecksumError(f"Checksum file does not exist: {checksum_file}")

        # Check if both files are in the same directory
        if file_path_obj.parent != checksum_file.parent:
            raise ChecksumError(
                "Target file and checksum file must be in the same directory"
            )

        return file_path_obj, checksum_file

    def _parse_checksum_file(self, checksum_file: Path, target_filename: str) -> bool:
        """Parse checksum file and check if it contains the target filename."""
        try:
            with open(checksum_file, "r") as f:
                content = f.read().strip()

            # Check if the target filename appears in the checksum file
            if target_filename not in content:
                self.logger.logger.error(
                    f"Checksum file does not contain target filename: {target_filename}"
                )
                return False

            return True
        except Exception as e:
            raise ChecksumError(f"Failed to read checksum file: {e}")

    def _execute_checksum_command(self, checksum_file: Path) -> None:
        """Execute sha256sum -c command to verify checksum."""
        command = ["sha256sum", "-c", str(checksum_file)]
        if self.config.verbose:
            self.logger.log_command_execution(" ".join(command))

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            if self.config.verbose:
                self.logger.log_command_execution(" ".join(command), success=True)

            # Check if the output indicates success
            if "OK" not in result.stdout and "FAILED" not in result.stdout:
                self.logger.logger.warning(
                    f"Unexpected checksum verification result: {result.stdout}"
                )
        except subprocess.CalledProcessError:
            raise ChecksumError("Checksum verification failed!")

    def _generate_checksum(self, file_path: str) -> None:
        """Generate SHA256 checksum for created archive."""
        checksum_file = file_path + ".sha256"
        command = ["sha256sum", file_path]

        if self.config.verbose:
            self.logger.log_command_execution(" ".join(command))

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            with open(checksum_file, "w") as f:
                f.write(result.stdout.strip())

            if self.config.verbose:
                self.logger.log_command_execution(" ".join(command), success=True)
                self.logger.logger.info(f"Wrote checksum: {checksum_file}")

        except subprocess.CalledProcessError as e:
            self.logger.log_command_execution(
                " ".join(command), e.returncode, success=False
            )
            raise ChecksumCommandExecutionError(
                "sha256sum", e.returncode, f"Failed to generate checksum: {e.stderr}"
            )

    def verify_checksum(self, file_path: str) -> None:
        """Verify checksum of a file using sha256sum -c."""
        # Checksum verification can take time, so provide start feedback
        self.logger.logger.info(f"Verifying checksum for: {file_path}")

        try:
            # Validate files exist and are in same directory
            file_path_obj, checksum_file = self._validate_checksum_files(file_path)

            # Parse checksum file to ensure it contains the target filename
            if not self._parse_checksum_file(checksum_file, file_path_obj.name):
                raise ChecksumError(
                    f"Checksum file does not contain entry for: {file_path_obj.name}"
                )

            # Execute checksum verification
            self._execute_checksum_command(checksum_file)

            # Checksum verification completed successfully - let CLI handle the final message
            # self.logger.logger.info(f"Checksum verification completed for: {file_path}")

        except ChecksumError:
            raise

    def generate_checksum(self, file_path: str) -> None:
        """Generate SHA256 checksum for a file."""
        self._generate_checksum(file_path)
