"""
Build logic for the SquashFS Archive Helper.

This module contains functionality for creating SquashFS archives
with various options and configurations.
"""

import datetime
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .command_executor import CommandExecutor
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
from .tool_adapters import (
    IMksquashfsAdapter,
    MksquashfsAdapter,
)


@dataclass
class BuildConfiguration:
    """Configuration object for SquashFS build operations."""

    source: str | list[str]
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

    source: str | list[str]
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

    def __init__(
        self,
        config: Optional[SquishFSConfig] = None,
        mksquashfs_adapter: Optional[IMksquashfsAdapter] = None,
    ):
        self.config = config if config else SquishFSConfig()
        self.logger = get_logger(self.config.verbose)
        self.mksquashfs_adapter = mksquashfs_adapter or MksquashfsAdapter(
            self._get_command_executor(), self.config
        )

    def _get_command_executor(self):
        """Get a command executor instance."""
        return CommandExecutor(self.config)

    def _get_base_name_from_source(self, source_path: Path) -> str:
        """Extract the base name from a file or directory source."""
        if source_path.is_file():
            # Remove all file extensions, not just the last one
            base_name = source_path.name
            # Iterate through suffixes in valid order to strip them
            # This handles cases like archive.tar.gz -> archive
            while source_path.suffixes:
                suffix = source_path.suffixes[-1]
                if base_name.endswith(suffix):
                    base_name = base_name[: -len(suffix)]
                # Remove the suffix from the path object for the next iteration
                source_path = source_path.with_suffix("")
            return base_name

        # If source is a directory, use its name
        return source_path.name

    def _find_next_available_filename(
        self, target_dir: Path, base_name: str, extension: str
    ) -> str:
        """Find the next available filename to avoid collisions."""
        # Check if the base file exists first
        output_filename = f"{base_name}{extension}"
        output_path = target_dir / output_filename

        if not output_path.exists():
            return str(output_path)

        # Fallback to the archive-(YYYYMMDD)-(nn).sqsh pattern if tailored name exists
        # Or if we want to use the numbered pattern for everything else
        return self._generate_numbered_archive_name(target_dir, extension)

    def _generate_numbered_archive_name(self, target_dir: Path, extension: str) -> str:
        """Generate a numbered archive name based on the current date."""
        # Generate date string
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        base_name_pattern = f"archive-{date_str}"

        # Find all existing numbers
        existing_numbers = set()
        for filename in os.listdir(target_dir):
            if filename.startswith(base_name_pattern) and filename.endswith(extension):
                try:
                    # Extract number part: "archive-20231222-01.sqsh" -> "01"
                    # Length of base_pattern + 1 (for dash)
                    start_idx = len(base_name_pattern) + 1
                    end_idx = -len(extension)
                    num_part = filename[start_idx:end_idx]
                    existing_numbers.add(int(num_part))
                except (ValueError, IndexError):
                    continue

        # Find next available number
        next_num = 1
        while next_num in existing_numbers:
            next_num += 1

        return str(target_dir / f"{base_name_pattern}-{next_num:02d}{extension}")

    def _generate_default_output_filename(self, source: str | list[str]) -> str:
        """Generate default output filename based on source name or archive-(YYYYMMDD)-(nn).sqsh"""
        target_dir = Path(".")
        extension = ".sqsh"

        # Strategy 1: For a single source, try to use its name
        if isinstance(source, str):
            source_path = Path(source)
            base_name = self._get_base_name_from_source(source_path)
            output_path = target_dir / f"{base_name}{extension}"

            if not output_path.exists():
                return str(output_path)

        # Strategy 2: For multiple sources or if single-source name exists, use numbered archive pattern
        return self._generate_numbered_archive_name(target_dir, extension)

    def _count_files_in_directory(self, directory: str | list[str]) -> int:
        """Count total files in directory for progress estimation."""
        import os

        total_files = 0

        # Handle both single directory and multiple sources
        if isinstance(directory, str):
            directories = [directory]
        else:
            directories = directory

        for dir_path in directories:
            for root, dirs, files in os.walk(dir_path):
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
        source: str | list[str],
        output: str,
        excludes: list[str],
        compression: str,
        block_size: str,
        processors: int,
        progress_service=None,  # For dependency injection in tests
    ) -> None:
        """Execute mksquashfs command to create archive using adapter."""
        # Handle both single source and multiple sources
        if isinstance(source, str):
            sources = [source]
        else:
            sources = source

        # Use the adapter to execute the build
        try:
            self.mksquashfs_adapter.build(
                sources=sources,
                output=output,
                excludes=excludes,
                compression=compression,
                block_size=block_size,
                processors=processors,
                progress_observer=progress_service,
            )
        except MksquashfsCommandExecutionError:
            raise
        except Exception as e:
            raise MksquashfsCommandExecutionError(
                "mksquashfs", getattr(e, "returncode", 1), str(e)
            )

    def _execute_mksquashfs_command_with_progress(
        self, config: CommandConfiguration
    ) -> None:
        """Execute mksquashfs command with progress tracking."""
        # Handle both single source and multiple sources
        if isinstance(config.source, str):
            sources = [config.source]
        else:
            sources = config.source

        command = (
            [
                "mksquashfs",
            ]
            + sources
            + [
                config.output,
                "-comp",
                config.compression,
                "-b",
                config.block_size,
                "-processors",
                str(config.processors),
                "-info",  # Show file processing for progress estimation
                "-keep-as-directory",  # Keep source directory structure intact
            ]
            + config.excludes
        )

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
            config.progress_service.start(
                f"Building {config.output}... (0/{total_files} files)"
            )

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

    def build_squashfs(self, config: BuildConfiguration) -> None:
        """Build a SquashFS archive using configuration object."""
        # Handle both single source and multiple sources
        if isinstance(config.source, str):
            sources = [config.source]
        else:
            sources = config.source

        # Generate default output filename if not provided
        if config.output is None:
            config.output = self._generate_default_output_filename(config.source)
            if self.config.verbose:
                self.logger.logger.info(
                    f"Generated default output filename: {config.output}"
                )

        output_path = Path(config.output)

        # Validate all sources exist
        for source in sources:
            source_path = Path(source)
            if not source_path.exists():
                self.logger.logger.error(f"Source not found: {source}")
                raise BuildError(f"Source not found: {source}")

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
                source=sources,  # Pass list of sources
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
                sources,  # Pass list of sources
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
