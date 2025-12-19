"""
List logic for the SquashFS Archive Helper.

This module contains functionality for listing contents
of SquashFS archives.
"""

import subprocess
from pathlib import Path
from typing import Optional

from .config import SquishFSConfig
from .errors import (
    ListError,
    UnsquashfsCommandExecutionError,
)
from .logging import get_logger


class ListManager:
    """
    Manager for squashfs list operations.

    This class handles listing of archive contents and
    display options for SquashFS archives.
    """

    def __init__(self, config: Optional[SquishFSConfig] = None):
        self.config = config if config else SquishFSConfig()
        self.logger = get_logger(self.config.verbose)

    def _execute_unsquashfs_list(self, archive: str) -> None:
        """Execute unsquashfs command to list archive contents."""
        command = ["unsquashfs", "-llc", archive]

        if self.config.verbose:
            self.logger.log_command_execution(" ".join(command))

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            print(result.stdout)  # Direct output to console for listing

            if self.config.verbose:
                self.logger.log_command_execution(" ".join(command), success=True)

        except subprocess.CalledProcessError as e:
            self.logger.log_command_execution(
                " ".join(command), e.returncode, success=False
            )
            raise UnsquashfsCommandExecutionError(
                "unsquashfs",
                e.returncode,
                f"Failed to list archive contents: {e.stderr}",
            )

    def list_squashfs(self, archive: str) -> None:
        """List contents of a SquashFS archive."""
        archive_path = Path(archive)

        # Validate archive exists
        if not archive_path.exists():
            self.logger.logger.error(f"Archive not found: {archive}")
            raise ListError(f"Archive not found: {archive}")

        # Check build dependencies (for unsquashfs)
        self._check_build_dependencies()

        # Execute unsquashfs list command
        self._execute_unsquashfs_list(archive)

    def _check_build_dependencies(self) -> None:
        """Check for build-specific dependencies."""
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
