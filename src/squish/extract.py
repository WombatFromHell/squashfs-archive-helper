"""
Extract logic for the SquashFS Archive Helper.

This module contains functionality for extracting contents
from SquashFS archives using the unsquashfs command.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from .config import SquishFSConfig
from .errors import (
    ExtractError,
    UnsquashfsExtractCommandExecutionError,
)
from .logging import get_logger


class ExtractManager:
    """
    Manager for squashfs extract operations.

    This class handles extraction of archive contents to
    specified directories using the unsquashfs command.
    """

    def __init__(self, config: Optional[SquishFSConfig] = None):
        self.config = config if config else SquishFSConfig()
        self.logger = get_logger(self.config.verbose)

    def _execute_unsquashfs_extract(self, archive: str, output_dir: str) -> None:
        """Execute unsquashfs command to extract archive contents."""
        command = ["unsquashfs", "-d", output_dir, archive]

        if self.config.verbose:
            self.logger.log_command_execution(" ".join(command))

        try:
            subprocess.run(command, check=True, capture_output=True, text=True)

            if self.config.verbose:
                self.logger.log_command_execution(" ".join(command), success=True)

            # Print extraction summary
            print(f"Successfully extracted {archive} to {output_dir}")

        except subprocess.CalledProcessError as e:
            self.logger.log_command_execution(
                " ".join(command), e.returncode, success=False
            )
            raise UnsquashfsExtractCommandExecutionError(
                "unsquashfs",
                e.returncode,
                f"Failed to extract archive contents: {e.stderr}",
            )

    def extract_squashfs(self, archive: str, output_dir: Optional[str] = None) -> None:
        """Extract contents of a SquashFS archive to a directory.

        Args:
            archive: Path to the SquashFS archive file
            output_dir: Output directory path (defaults to current directory)
        """
        archive_path = Path(archive)

        # Set default output directory to current directory
        if output_dir is None:
            output_dir = "."

        output_path = Path(output_dir)

        # Validate archive exists
        if not archive_path.exists():
            self.logger.logger.error(f"Archive not found: {archive}")
            raise ExtractError(f"Archive not found: {archive}")

        # Validate archive is a file
        if not archive_path.is_file():
            self.logger.logger.error(f"Archive path is not a file: {archive}")
            raise ExtractError(f"Archive path is not a file: {archive}")

        # Check extract dependencies (for unsquashfs)
        self._check_extract_dependencies()

        # Create output directory if it doesn't exist
        if not output_path.exists():
            try:
                output_path.mkdir(parents=True, exist_ok=True)
                if self.config.verbose:
                    self.logger.logger.info(f"Created output directory: {output_dir}")
            except OSError as e:
                self.logger.logger.error(
                    f"Failed to create output directory {output_dir}: {e}"
                )
                raise ExtractError(
                    f"Failed to create output directory {output_dir}: {e}"
                )

        # Validate output directory is writable
        if not os.access(str(output_path), os.W_OK):
            self.logger.logger.error(f"Output directory is not writable: {output_dir}")
            raise ExtractError(f"Output directory is not writable: {output_dir}")

        # Execute unsquashfs extract command
        self._execute_unsquashfs_extract(archive, output_dir)

    def _check_extract_dependencies(self) -> None:
        """Check for extract-specific dependencies."""
        import subprocess

        from .errors import DependencyError
        from .logging import get_logger

        logger = get_logger(self.config.verbose)
        cmd = "unsquashfs"

        try:
            # Only log on success if verbose mode is enabled
            if self.config.verbose:
                logger.log_dependency_check(cmd, "available")
            subprocess.run(
                ["which", cmd],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError:
            logger.log_dependency_check(cmd, "missing")
            raise DependencyError(
                f"{cmd} is not installed or not in PATH. "
                f"Please install {cmd} to use this script."
            )
