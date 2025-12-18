"""
Logging functionality for the Mount-SquashFS application.

This module provides centralized logging configuration and utilities
for consistent logging throughout the application.
"""

import logging
import sys


class MountSquashFSLogger:
    """
    Custom logger for Mount-SquashFS operations.

    This class provides structured logging with timestamps, log levels,
    and contextual information for mount/unmount operations.
    """

    def __init__(self, name: str = "mount_squashfs", verbose: bool = False):
        """Initialize the logger.

        Args:
            name: Name of the logger
            verbose: Enable verbose logging mode
        """
        self.logger = logging.getLogger(name)
        self.verbose = verbose

        # Set up logging format
        self._configure_logging()

    def _configure_logging(self) -> None:
        """Configure logging format and handlers."""
        # Clear any existing handlers to avoid duplicate logs
        self.logger.handlers.clear()

        # Set log level based on verbose mode
        log_level = logging.DEBUG if self.verbose else logging.INFO
        self.logger.setLevel(log_level)

        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)

        # Create formatter with message only for clean output
        formatter = logging.Formatter("%(message)s")
        console_handler.setFormatter(formatter)

        # Add handler to logger
        self.logger.addHandler(console_handler)

    def log_mount_start(self, file_path: str, mount_point: str) -> None:
        """Log the start of a mount operation.

        Args:
            file_path: Path to the squashfs file
            mount_point: Target mount point
        """
        self.logger.info(f"Mounting: {file_path} -> {mount_point}")

    def log_mount_success(self, file_path: str, mount_point: str) -> None:
        """Log successful mount operation.

        Args:
            file_path: Path to the squashfs file
            mount_point: Target mount point
        """
        self.logger.info(f"Mounted: {file_path} -> {mount_point}")

    def log_mount_failed(self, file_path: str, mount_point: str, error: str) -> None:
        """Log failed mount operation.

        Args:
            file_path: Path to the squashfs file
            mount_point: Target mount point
            error: Error message
        """
        self.logger.error(f"Mount failed: {file_path} -> {mount_point}: {error}")

    def log_unmount_start(self, file_path: str, mount_point: str) -> None:
        """Log the start of an unmount operation.

        Args:
            file_path: Path to the squashfs file
            mount_point: Target mount point
        """
        self.logger.info(f"Unmounting: {file_path} -> {mount_point}")

    def log_unmount_success(self, file_path: str, mount_point: str) -> None:
        """Log successful unmount operation.

        Args:
            file_path: Path to the squashfs file
            mount_point: Target mount point
        """
        self.logger.info(f"Unmounted: {file_path} -> {mount_point}")

    def log_unmount_failed(self, file_path: str, mount_point: str, error: str) -> None:
        """Log failed unmount operation.

        Args:
            file_path: Path to the squashfs file
            mount_point: Target mount point (or special marker)
            error: Error message
        """
        # Handle special cases where mount_point is not a real path
        if mount_point in ["not_mounted", "no_mount_info", "auto"]:
            self.logger.error(f"Unmount failed: {file_path}: {error}")
        else:
            self.logger.error(f"Unmount failed: {file_path} -> {mount_point}: {error}")

    def log_file_not_found(self, file_path: str, context: str = "mount") -> None:
        """Log file not found error.

        Args:
            file_path: Path to the missing file
            context: Context where the file was expected (mount/unmount)
        """
        self.logger.error(f"File not found: {file_path}")

    def log_mount_point_not_found(
        self, mount_point: str, context: str = "unmount"
    ) -> None:
        """Log mount point not found error.

        Args:
            mount_point: Path to the missing mount point
            context: Context where the mount point was expected
        """
        self.logger.error(f"Mount point not found: {mount_point}")

    def log_mount_point_empty(self, mount_point: str) -> None:
        """Log empty mount point warning.

        Args:
            mount_point: Path to the empty mount point
        """
        self.logger.warning(f"Mount point empty: {mount_point}")

    def log_dependency_check(self, dependency: str, status: str = "available") -> None:
        """Log dependency check result.

        Args:
            dependency: Name of the dependency being checked
            status: Status of the dependency (available/missing)
        """
        if status == "available":
            self.logger.info(f"Dependency available: {dependency}")
        else:
            self.logger.error(f"Dependency missing: {dependency}")

    def log_command_execution(
        self, command: str, return_code: int | None = None, success: bool = True
    ) -> None:
        """Log command execution.

        Args:
            command: Command being executed
            return_code: Return code from command execution
            success: Whether the command was successful
        """
        if success:
            self.logger.info(f"Command executed: {command}")
        else:
            self.logger.error(f"Command failed: {command}")

    def log_cleanup_operation(
        self, path: str, operation: str, success: bool = True
    ) -> None:
        """Log cleanup operation.

        Args:
            path: Path being cleaned up
            operation: Type of cleanup operation
            success: Whether the operation was successful
        """
        if success:
            self.logger.info(f"Cleanup: {operation} on {path}")
        else:
            self.logger.warning(f"Cleanup failed: {operation} on {path}")

    def log_tracking_operation(
        self, file_path: str, operation: str, success: bool = True
    ) -> None:
        """Log mount tracking operation.

        Args:
            file_path: Path to the squashfs file
            operation: Type of tracking operation (record/remove/read)
            success: Whether the operation was successful
        """
        if success:
            self.logger.info(f"Tracking: {operation} for {file_path}")
        else:
            self.logger.error(f"Tracking failed: {operation} for {file_path}")

    def log_validation_result(
        self, validation_type: str, path: str, result: str
    ) -> None:
        """Log validation result.

        Args:
            validation_type: Type of validation being performed
            path: Path being validated
            result: Result of validation (pass/fail)
        """
        if result == "pass":
            self.logger.info(f"Validation passed: {validation_type} for {path}")
        else:
            self.logger.warning(f"Validation failed: {validation_type} for {path}")

    def log_build_start(self, source: str, output: str) -> None:
        """Log the start of a build operation.

        Args:
            source: Source directory to archive
            output: Output archive file
        """
        self.logger.info(f"Building: {source} -> {output}")

    def log_build_success(self, source: str, output: str) -> None:
        """Log successful build operation.

        Args:
            source: Source directory archived
            output: Output archive file created
        """
        self.logger.info(f"Built: {source} -> {output}")

    def log_build_failed(self, source: str, output: str, error: str) -> None:
        """Log failed build operation.

        Args:
            source: Source directory
            output: Output archive file
            error: Error message
        """
        self.logger.error(f"Build failed: {source} -> {output}: {error}")

    def log_list_start(self, archive: str) -> None:
        """Log the start of a list operation.

        Args:
            archive: Path to the SquashFS archive
        """
        self.logger.info(f"Listing contents of: {archive}")

    def log_list_success(self, archive: str) -> None:
        """Log successful list operation.

        Args:
            archive: Path to the SquashFS archive
        """
        self.logger.info(f"Listed contents of: {archive}")

    def log_list_failed(self, archive: str, error: str) -> None:
        """Log failed list operation.

        Args:
            archive: Path to the SquashFS archive
            error: Error message
        """
        self.logger.error(f"List failed: {archive}: {error}")


def get_logger(verbose: bool = False) -> MountSquashFSLogger:
    """Get a configured logger instance.

    Args:
        verbose: Enable verbose logging mode

    Returns:
        Configured MountSquashFSLogger instance
    """
    return MountSquashFSLogger(verbose=verbose)
