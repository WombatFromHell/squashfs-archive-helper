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
    XattrError,
)
from .logging import get_logger
from .progress import (
    ExtractCancelledError,
    ExtractProgressTracker,
    ZenityProgressService,
)


class ExtractManager:
    """
    Manager for squashfs extract operations.

    This class handles extraction of archive contents to
    specified directories using the unsquashfs command.
    """

    def __init__(self, config: Optional[SquishFSConfig] = None):
        self.config = config if config else SquishFSConfig()
        self.logger = get_logger(self.config.verbose)

    def _get_xattr_flags(self) -> list[str]:
        """Get unsquashfs flags based on xattr_mode configuration."""
        if self.config.xattr_mode == "all":
            # Extract all xattrs (default behavior)
            return ["-xattrs"]
        elif self.config.xattr_mode == "user-only":
            # Only extract user xattrs, exclude security.selinux and other system xattrs
            return ["-xattrs-include", "^user."]
        elif self.config.xattr_mode == "none":
            # Disable xattr extraction entirely
            return ["-no-xattrs"]
        else:
            # Fallback to user-only if unknown mode (shouldn't happen due to validation)
            return ["-xattrs-include", "^user."]

    def _is_xattr_error(self, error_output: str) -> bool:
        """Check if the error output indicates an xattr-related error."""
        xattr_error_patterns = [
            "write_xattr",
            "xattr",
            "security.selinux",
            "not superuser",
            "XATTR",
        ]
        return any(pattern in error_output for pattern in xattr_error_patterns)

    def _count_files_in_archive(self, archive: str) -> int:
        """Count total files in archive for progress estimation."""
        command = ["unsquashfs", "-llc", archive]

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            # Count non-empty lines (each line represents a file/directory)
            # Filter out directory entries and count only files
            lines = result.stdout.strip().split("\n")
            file_count = 0
            for line in lines:
                if line.strip() and not line.strip().endswith("/"):
                    # This is a file, not a directory
                    file_count += 1
            return file_count
        except subprocess.CalledProcessError as e:
            self.logger.logger.warning(
                f"Failed to count files in archive {archive}: {e.stderr}"
            )
            return 0  # Fallback to 0 if we can't count files

    def _execute_unsquashfs_extract(
        self, archive: str, output_dir: str, resolved_output_path: str
    ) -> None:
        """Execute unsquashfs command to extract archive contents."""
        # Get xattr flags based on configuration
        xattr_flags = self._get_xattr_flags()

        if output_dir == ".":
            # Use default extraction location (squashfs-root) when extracting to current directory
            command = ["unsquashfs", "-i"] + xattr_flags + [archive]
        else:
            command = ["unsquashfs", "-i", "-d", output_dir] + xattr_flags + [archive]

        if self.config.verbose:
            self.logger.log_command_execution(" ".join(command))

        try:
            # Don't capture output - let users see the unsquashfs -i output
            subprocess.run(command, check=True, text=True)

            if self.config.verbose:
                self.logger.log_command_execution(" ".join(command), success=True)

            # Print extraction summary
            print(f"Successfully extracted {archive} to {resolved_output_path}")

        except subprocess.CalledProcessError as e:
            self.logger.log_command_execution(
                " ".join(command), e.returncode, success=False
            )

            # Handle cases where stderr might be None
            error_output = e.stderr if e.stderr else "Unknown error"
            error_message = f"Failed to extract archive contents: {error_output}"

            # Check if this is an xattr-related error (only if stderr is not None)
            if e.stderr and self._is_xattr_error(e.stderr):
                from .errors import XattrError

                # Provide helpful guidance for xattr errors
                if self.config.xattr_mode == "all":
                    suggestion = (
                        "Try using --xattr-mode user-only to exclude system xattrs, "
                        "--xattr-mode none to disable xattrs entirely, or run as superuser."
                    )
                else:
                    suggestion = (
                        "Xattr extraction failed. You can try --xattr-mode none to "
                        "disable xattrs entirely or run as superuser."
                    )

                error_message = f"{error_message}\n\nXattr Error: {suggestion}"
                raise XattrError(error_message)

            raise UnsquashfsExtractCommandExecutionError(
                "unsquashfs",
                e.returncode,
                error_message,
            )

    def _build_extraction_command(
        self, archive: str, output_dir: str, xattr_flags: list[str]
    ) -> list[str]:
        """Pure function for building extraction command."""
        if output_dir == ".":
            return ["unsquashfs", "-percentage"] + xattr_flags + [archive]
        return ["unsquashfs", "-d", output_dir, "-percentage"] + xattr_flags + [archive]

    def _should_display_line(self, line: str) -> bool:
        """Pure function to determine if line should be displayed."""
        stripped_line = line.strip()
        return bool(stripped_line and not stripped_line.isdigit())

    def _process_extraction_output(
        self, process, progress_tracker, progress_service, archive
    ) -> tuple[list[str], bool]:
        """Process extraction output with clean separation of concerns."""
        all_output = []
        cancelled = False

        if process.stdout:
            for line in process.stdout:
                all_output.append(line)

                # Display informative output
                if self._should_display_line(line):
                    print(line.strip(), flush=True)

                # Update progress
                progress_tracker.process_output_line(line)

                # Check cancellation
                if progress_tracker.zenity_service.check_cancelled():
                    process.terminate()
                    progress_service.close(success=False)
                    cancelled = True
                    break

        return all_output, cancelled

    def _handle_extraction_errors(
        self, all_output: list[str], process, progress_service, archive: str
    ) -> None:
        """Centralize error detection and handling."""
        error_output = " ".join(all_output) if all_output else "Unknown error"
        progress_service.close(success=False)
        progress_service.process = None

        error_message = f"Failed to extract archive contents: {error_output}"

        # Check if this is an xattr-related error
        if self._is_xattr_error(error_output):
            # Provide helpful guidance for xattr errors
            if self.config.xattr_mode == "all":
                suggestion = (
                    "Try using --xattr-mode user-only to exclude system xattrs, "
                    "--xattr-mode none to disable xattrs entirely, or run as superuser."
                )
            else:
                suggestion = (
                    "Xattr extraction failed. You can try --xattr-mode none to "
                    "disable xattrs entirely or run as superuser."
                )

            error_message = f"{error_message}\n\nXattr Error: {suggestion}"
            raise XattrError(error_message)

        raise UnsquashfsExtractCommandExecutionError(
            "unsquashfs",
            process.returncode,
            error_message,
        )

    def _initialize_extraction_process(
        self, archive: str, output_dir: str, progress_service=None
    ) -> tuple[subprocess.Popen, ZenityProgressService, ExtractProgressTracker, int]:
        """Initialize extraction process with progress tracking."""
        # Get xattr flags based on configuration
        xattr_flags = self._get_xattr_flags()

        # Pure command construction
        command = self._build_extraction_command(archive, output_dir, xattr_flags)

        if self.config.verbose:
            self.logger.log_command_execution(" ".join(command))

        # Start extraction process
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        # Create progress service if not provided
        if progress_service is None:
            progress_service = ZenityProgressService(title="Extracting SquashFS")

        # Count total files for progress estimation
        total_files = self._count_files_in_archive(archive)

        # Initialize progress tracker
        progress_tracker = ExtractProgressTracker(progress_service)
        progress_tracker.set_total_files(total_files)

        # Start progress service
        initial_text = f"Extracting {archive}... (0/{total_files} files)"
        progress_service.start(initial_text)

        return process, progress_service, progress_tracker, total_files

    def _finalize_extraction_success(
        self,
        progress_service: ZenityProgressService,
        archive: str,
        resolved_output_path: str,
    ) -> None:
        """Finalize successful extraction."""
        progress_service.close(success=True)
        progress_service.process = None
        print(f"Successfully extracted {archive} to {resolved_output_path}")

    def _finalize_extraction_failure(
        self, progress_service: ZenityProgressService, exception: Exception
    ) -> None:
        """Finalize failed extraction with proper cleanup."""
        if (
            progress_service
            and hasattr(progress_service, "process")
            and progress_service.process
        ):
            progress_service.close(success=False)
            progress_service.process = None

    def _handle_extraction_exception(
        self, e: Exception, progress_service: ZenityProgressService, archive: str
    ) -> None:
        """Handle extraction exceptions with appropriate error conversion."""
        if isinstance(e, ExtractCancelledError):
            # Let cancellation errors pass through unchanged
            raise
        elif isinstance(e, XattrError):
            # Let XattrError pass through unchanged
            raise
        elif isinstance(e, UnsquashfsExtractCommandExecutionError):
            # Check if this is an xattr-related error and re-raise as XattrError if so
            if self._is_xattr_error(str(e)):
                # Provide helpful guidance for xattr errors
                if self.config.xattr_mode == "all":
                    suggestion = (
                        "Try using --xattr-mode user-only to exclude system xattrs, "
                        "--xattr-mode none to disable xattrs entirely, or run as superuser."
                    )
                else:
                    suggestion = (
                        "Xattr extraction failed. You can try --xattr-mode none to "
                        "disable xattrs entirely or run as superuser."
                    )

                error_message = f"{e}\n\nXattr Error: {suggestion}"
                raise XattrError(error_message)
            raise
        else:
            # Handle unexpected exceptions
            raise UnsquashfsExtractCommandExecutionError(
                "unsquashfs",
                getattr(e, "returncode", 1),
                f"Failed to extract archive contents: {str(e)}",
            )

    def _execute_unsquashfs_extract_with_progress(
        self,
        archive: str,
        output_dir: str,
        resolved_output_path: str,
        progress_service=None,  # For dependency injection in tests
    ) -> None:
        """Execute unsquashfs command with progress tracking."""
        try:
            # Initialize extraction process
            process, progress_service, progress_tracker, total_files = (
                self._initialize_extraction_process(
                    archive, output_dir, progress_service
                )
            )

            # Process output with clean separation
            all_output, cancelled = self._process_extraction_output(
                process, progress_tracker, progress_service, archive
            )

            process.wait()

            if cancelled:
                raise ExtractCancelledError("Extract cancelled by user")

            if process.returncode != 0:
                self._handle_extraction_errors(
                    all_output, process, progress_service, archive
                )

            # Finalize successful extraction
            self._finalize_extraction_success(
                progress_service, archive, resolved_output_path
            )

        except Exception as e:
            # Handle extraction exceptions
            if progress_service:
                self._handle_extraction_exception(e, progress_service, archive)
                # Finalize extraction failure
                self._finalize_extraction_failure(progress_service, e)

    def _validate_archive(self, archive_path: Path, archive: str) -> None:
        """Validate archive file exists and is valid."""
        if not archive_path.exists():
            self.logger.logger.error(f"Archive not found: {archive}")
            raise ExtractError(f"Archive not found: {archive}")

        if not archive_path.is_file():
            self.logger.logger.error(f"Archive path is not a file: {archive}")
            raise ExtractError(f"Archive path is not a file: {archive}")

    def _resolve_output_path(self, output_dir: str) -> tuple[str, Path]:
        """Resolve output path based on output directory."""
        output_path = Path(output_dir)

        # Resolve output path to absolute path for better user feedback
        if output_dir == ".":
            # When extracting to current directory, unsquashfs -i extracts to squashfs-root/
            resolved_output_path = Path.cwd() / "squashfs-root"
        else:
            resolved_output_path = output_path.resolve()

        return output_dir, resolved_output_path

    def _create_output_directory(self, output_dir: str, output_path: Path) -> None:
        """Create output directory if needed."""
        # Create output directory if it doesn't exist and we're using a custom location
        # (not the default "." which uses squashfs-root)
        if output_dir != "." and not output_path.exists():
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

    def _validate_output_directory(self, output_dir: str, output_path: Path) -> None:
        """Validate output directory is writable."""
        # Validate output directory is writable (only if we're using a custom location)
        if output_dir != "." and not os.access(str(output_path), os.W_OK):
            self.logger.logger.error(f"Output directory is not writable: {output_dir}")
            raise ExtractError(f"Output directory is not writable: {output_dir}")

    def _execute_extraction(
        self,
        archive: str,
        output_dir: str,
        resolved_output_path: str,
        progress: bool,
        progress_service=None,
    ) -> None:
        """Execute the appropriate extraction method based on progress flag."""
        if progress:
            self._execute_unsquashfs_extract_with_progress(
                archive, output_dir, resolved_output_path, progress_service
            )
        else:
            self._execute_unsquashfs_extract(archive, output_dir, resolved_output_path)

    def extract_squashfs(
        self,
        archive: str,
        output_dir: Optional[str] = None,
        progress: bool = False,
        progress_service=None,  # For dependency injection in tests
    ) -> None:
        """Extract contents of a SquashFS archive to a directory.

        Args:
            archive: Path to the SquashFS archive file
            output_dir: Output directory path (defaults to current directory)
            progress: Whether to show progress dialog
            progress_service: Optional progress service for testing
        """
        archive_path = Path(archive)

        # Set default output directory to current directory
        if output_dir is None:
            output_dir = "."

        # Validate archive
        self._validate_archive(archive_path, archive)

        # Check extract dependencies (for unsquashfs)
        self._check_extract_dependencies()

        # Resolve output paths
        output_dir, resolved_output_path = self._resolve_output_path(output_dir)

        # Create output directory if needed
        self._create_output_directory(output_dir, resolved_output_path)

        # Validate output directory
        self._validate_output_directory(output_dir, resolved_output_path)

        # Execute extraction
        self._execute_extraction(
            archive, output_dir, str(resolved_output_path), progress, progress_service
        )

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
