"""
Build logic for the SquashFS Archive Helper.

This module contains functionality for creating SquashFS archives
with various options and configurations.
"""

import datetime
import os
import subprocess
from pathlib import Path
from typing import Optional

from dataclasses import dataclass
from typing import Optional, List

from .config import SquishFSConfig
from .errors import (
    BuildError,
    DependencyError,
    MksquashfsCommandExecutionError,
)
from .logging import get_logger
from .progress import (
    BuildCancelledError,
    ProgressTracker,
    ZenityProgressService,
)


@dataclass
class BuildConfiguration:
    """Configuration object for SquashFS build operations."""
    source: str
    output: Optional[str] = None
    excludes: Optional[List[str]] = None
    exclude_file: Optional[str] = None
    wildcards: bool = False
    regex: bool = False
    compression: str = "zstd"
    block_size: str = "1M"
    processors: Optional[int] = None
    progress: bool = False
    progress_service: Optional[ZenityProgressService] = None


@dataclass
class CommandConfiguration:
    """Configuration object for mksquashfs command execution."""
    source: str
    output: str
    excludes: List[str]
    compression: str
    block_size: str
    processors: int
    progress_service: Optional[ZenityProgressService] = None


class BuildManager:
    """
    Manager for squashfs build operations.

    This class handles creation of squashfs archives with various
    configurations, exclude patterns, and progress tracking.
    """

    def __init__(self, config: Optional[SquishFSConfig] = None):
        self.config = config if config else SquishFSConfig()
        self.logger = get_logger(self.config.verbose)

    def _generate_default_output_filename(self, source: str) -> str:
        """Generate default output filename in format: archive-(YYYYMMDD)-(nn).sqsh"""
        # Get the directory containing the source
        source_path = Path(source)
        if source_path.is_file():
            # If source is a file, use its parent directory
            target_dir = source_path.parent
        else:
            # If source is a directory, use its parent directory
            target_dir = source_path.parent

        # Generate date string
        date_str = datetime.datetime.now().strftime("%Y%m%d")

        # Find the next available number
        base_name = f"archive-{date_str}"
        extension = ".sqsh"

        # Check for existing files with this pattern in the target directory
        existing_files = []
        for filename in os.listdir(target_dir):
            if filename.startswith(base_name) and filename.endswith(extension):
                try:
                    # Extract the number part
                    num_part = filename[
                        len(base_name) + 1 : -len(extension)
                    ]  # +1 for the dash
                    existing_files.append(int(num_part))
                except (ValueError, IndexError):
                    # Skip files that don't match the expected pattern
                    continue

        # Find the next available number
        next_num = 1
        while next_num in existing_files:
            next_num += 1

        # Return the full path to the output file
        return str(target_dir / f"{base_name}-{next_num:02d}{extension}")

    def _count_files_in_directory(self, directory: str) -> int:
        """Count total files in directory for progress estimation."""
        import os

        total_files = 0
        for root, dirs, files in os.walk(directory):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            total_files += len(files)
        return total_files

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
            "-info",  # Show file processing for progress estimation
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

    def _execute_mksquashfs_command_with_progress(
        self, config: CommandConfiguration
    ) -> None:
        """Execute mksquashfs command with progress tracking."""
        command = [
            "mksquashfs",
            config.source,
            config.output,
            "-comp",
            config.compression,
            "-b",
            config.block_size,
            "-processors",
            str(config.processors),
            "-info",  # Show file processing for progress estimation
        ] + config.excludes

        if self.config.verbose:
            self.logger.log_command_execution(" ".join(command))

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # Create progress service if not provided
            if config.progress_service is None:
                config.progress_service = ZenityProgressService()

            # Count total files for progress estimation
            total_files = self._count_files_in_directory(config.source)

            progress_tracker = ProgressTracker(config.progress_service)
            progress_tracker.set_total_files(total_files)
            config.progress_service.start(f"Building {config.output}... (0/{total_files} files)")

            if process.stdout:
                for line in process.stdout:
                    progress_tracker.process_output_line(line)

                    if progress_tracker.zenity_service.check_cancelled():
                        process.terminate()
                        config.progress_service.close(success=False)
                        raise BuildCancelledError("Build cancelled by user")

            process.wait()
            config.progress_service.close(success=True)

            if process.returncode != 0:
                raise MksquashfsCommandExecutionError(
                    "mksquashfs", process.returncode, "Failed to create archive"
                )

        except subprocess.CalledProcessError as e:
            if config.progress_service:
                config.progress_service.close(success=False)
            raise MksquashfsCommandExecutionError(
                "mksquashfs", e.returncode, f"Failed to create archive: {e.stderr}"
            )

    def build_squashfs(
        self, config: BuildConfiguration
    ) -> None:
        """Build a SquashFS archive using configuration object."""
        source_path = Path(config.source)

        # Generate default output filename if not provided
        if config.output is None:
            config.output = self._generate_default_output_filename(config.source)
            if self.config.verbose:
                self.logger.logger.info(f"Generated default output filename: {config.output}")

        output_path = Path(config.output)

        # Validate source exists
        if not source_path.exists():
            self.logger.logger.error(f"Source not found: {config.source}")
            raise BuildError(f"Source not found: {config.source}")

        # Validate output doesn't exist
        if output_path.exists():
            self.logger.logger.error(f"Output exists: {config.output}")
            raise BuildError(f"Output exists: {config.output}")

        # Check build dependencies
        self._check_build_dependencies()

        # Determine processors if not specified
        if config.processors is None:
            try:
                nproc_result = subprocess.run(
                    ["nproc"], capture_output=True, text=True, check=True
                )
                config.processors = int(nproc_result.stdout.strip())
            except subprocess.CalledProcessError:
                config.processors = 1  # Fallback to single processor

        # Build exclude arguments
        exclude_args = self._build_exclude_arguments(
            config.excludes, config.exclude_file, config.wildcards, config.regex
        )

        # Execute mksquashfs command with or without progress
        if config.progress:
            command_config = CommandConfiguration(
                source=config.source,
                output=config.output,
                excludes=exclude_args,
                compression=config.compression,
                block_size=config.block_size,
                processors=config.processors,
                progress_service=config.progress_service,
            )
            self._execute_mksquashfs_command_with_progress(command_config)
        else:
            self._execute_mksquashfs_command(
                config.source,
                config.output,
                exclude_args,
                config.compression,
                config.block_size,
                config.processors,
                config.progress_service,
            )

        # Generate checksum after successful build
        self._generate_checksum(config.output)

        self.logger.logger.info(f"Created: {config.output}")

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
