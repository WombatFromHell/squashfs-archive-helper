"""
Build logic for the SquashFS Archive Helper.

This module contains functionality for creating SquashFS archives
with various options and configurations.
"""

import subprocess
from pathlib import Path
from typing import Optional

from .config import SquishFSConfig
from .errors import (
    BuildError,
    DependencyError,
    MksquashfsCommandExecutionError,
)
from .logging import get_logger



class BuildManager:
    """
    Manager for squashfs build operations.

    This class handles creation of squashfs archives with various
    configurations, exclude patterns, and progress tracking.
    """

    def __init__(self, config: Optional[SquishFSConfig] = None):
        self.config = config if config else SquishFSConfig()
        self.logger = get_logger(self.config.verbose)

    def _build_exclude_arguments(
        self,
        excludes: list[str] | None = None,
        exclude_file: str | None = None,
        wildcards: bool = False,
        regex: bool = False,
    ) -> list[str]:
        """Build exclude arguments for mksquashfs command."""
        exclude_args = []

        if wildcards:
            exclude_args.append("-wildcards")
        if regex:
            exclude_args.append("-regex")

        if excludes:
            for pattern in excludes:
                exclude_args.extend(["-e", pattern])

        if exclude_file:
            exclude_args.extend(["-ef", exclude_file])

        return exclude_args

    def _execute_mksquashfs_command(
        self,
        source: str,
        output: str,
        excludes: list[str],
        compression: str,
        block_size: str,
        processors: int,
        progress_service=None,  # For dependency injection in tests
    ) -> None:
        """Execute mksquashfs command to create archive."""
        command = [
            "mksquashfs",
            source,
            output,
            "-comp",
            compression,
            "-b",
            block_size,
            "-processors",
            str(processors),
        ] + excludes

        if self.config.verbose:
            self.logger.log_command_execution(" ".join(command))

        # Run mksquashfs normally
        try:
            subprocess.run(command, check=True)
            if self.config.verbose:
                self.logger.log_command_execution(" ".join(command), success=True)
        except subprocess.CalledProcessError as e:
            self.logger.log_command_execution(
                " ".join(command), e.returncode, success=False
            )
            raise MksquashfsCommandExecutionError(
                "mksquashfs", e.returncode, f"Failed to create archive: {e.stderr}"
            )



    def build_squashfs(
        self,
        source: str,
        output: str,
        excludes: list[str] | None = None,
        exclude_file: str | None = None,
        wildcards: bool = False,
        regex: bool = False,
        compression: str = "zstd",
        block_size: str = "1M",
        processors: int | None = None,
        progress_service=None,  # For dependency injection in tests
    ) -> None:
        """Build a SquashFS archive with optional excludes."""
        source_path = Path(source)
        output_path = Path(output)

        # Validate source exists
        if not source_path.exists():
            self.logger.logger.error(f"Source not found: {source}")
            raise BuildError(f"Source not found: {source}")

        # Validate output doesn't exist
        if output_path.exists():
            self.logger.logger.error(f"Output exists: {output}")
            raise BuildError(f"Output exists: {output}")

        # Check build dependencies
        self._check_build_dependencies()



        # Determine processors if not specified
        if processors is None:
            try:
                nproc_result = subprocess.run(
                    ["nproc"], capture_output=True, text=True, check=True
                )
                processors = int(nproc_result.stdout.strip())
            except subprocess.CalledProcessError:
                processors = 1  # Fallback to single processor

        # Build exclude arguments
        exclude_args = self._build_exclude_arguments(
            excludes, exclude_file, wildcards, regex
        )

        # Execute mksquashfs command
        self._execute_mksquashfs_command(
            source,
            output,
            exclude_args,
            compression,
            block_size,
            processors,
            progress_service,
        )

        # Generate checksum after successful build
        self._generate_checksum(output)

        self.logger.logger.info(f"Created: {output}")

    def _generate_checksum(self, file_path: str) -> None:
        """Generate SHA256 checksum for created archive."""
        import subprocess

        from .errors import ChecksumCommandExecutionError
        from .logging import get_logger

        logger = get_logger(self.config.verbose)
        checksum_file = file_path + ".sha256"
        command = ["sha256sum", file_path]

        if self.config.verbose:
            logger.log_command_execution(" ".join(command))

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            with open(checksum_file, "w") as f:
                f.write(result.stdout.strip())

            if self.config.verbose:
                logger.log_command_execution(" ".join(command), success=True)
                logger.logger.info(f"Wrote checksum: {checksum_file}")

        except subprocess.CalledProcessError as e:
            logger.log_command_execution(" ".join(command), e.returncode, success=False)
            raise ChecksumCommandExecutionError(
                "sha256sum", e.returncode, f"Failed to generate checksum: {e.stderr}"
            )

    def _check_build_dependencies(self) -> None:
        """Check for build-specific dependencies."""
        import subprocess

        from .errors import DependencyError
        from .logging import get_logger

        logger = get_logger(self.config.verbose)

        commands = ["mksquashfs", "unsquashfs", "nproc"]
        for cmd in commands:
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
