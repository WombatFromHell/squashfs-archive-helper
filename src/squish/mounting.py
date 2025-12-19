"""
Mounting/unmounting logic for the SquashFS Archive Helper.

This module contains functionality for mounting and unmounting
squashfs files, including mount point validation and safety checks.
"""

import os
import shutil
from pathlib import Path
from typing import Optional

from .config import SquishFSConfig
from .errors import (
    MountCommandExecutionError,
    MountError,
    MountPointError,
    UnmountCommandExecutionError,
    UnmountError,
)
from .logging import get_logger
from .tracking import MountTracker


class MountManager:
    """
    Manager for squashfs mounting/unmounting operations.

    This class handles mount and unmount operations including validation,
    mount point management, and safety checks.
    """

    def __init__(self, config: Optional[SquishFSConfig] = None):
        self.config = config if config else SquishFSConfig()
        self.tracker = MountTracker(self.config)
        self.logger = get_logger(self.config.verbose)

    def _is_mount_point_valid(self, mount_point: Path) -> bool:
        """Check if the mount point exists and is not empty."""
        if not mount_point.exists():
            self.logger.log_mount_point_not_found(str(mount_point), "validation")
            raise MountPointError(f"Mount point does not exist: {mount_point}")

        if not any(mount_point.iterdir()):
            self.logger.log_mount_point_empty(str(mount_point))
            raise MountPointError(
                f"Mount point is empty, nothing to unmount: {mount_point}"
            )

        if self.config.verbose:
            self.logger.log_validation_result("mount_point", str(mount_point), "pass")
        return True

    def _determine_mount_point(
        self, file_path: str, mount_point: Optional[str] = None
    ) -> Path:
        """Determine the mount point for a file."""
        file_path_obj = Path(file_path)

        if mount_point is None:
            mount_point_obj = (
                Path(os.getcwd()) / self.config.mount_base / file_path_obj.stem
            )
        else:
            mount_point_obj = Path(mount_point)

        return mount_point_obj

    def _create_mount_directory(self, mount_point: Path) -> None:
        """Create the mount directory if it doesn't exist."""
        os.makedirs(mount_point, exist_ok=True)

    def _validate_mount_point_available(self, mount_point: Path) -> None:
        """Validate that the mount point is available for mounting."""
        if mount_point.exists() and any(mount_point.iterdir()):
            self.logger.log_validation_result(
                "mount_point_availability", str(mount_point), "fail"
            )
            raise MountError(f"Mount point {mount_point} is not empty")

        if self.config.verbose:
            self.logger.log_validation_result(
                "mount_point_availability", str(mount_point), "pass"
            )

    def _execute_mount_command(self, file_path: str, mount_point: Path) -> None:
        """Execute the squashfuse mount command."""
        import subprocess

        command = ["squashfuse", str(file_path), str(mount_point)]
        if self.config.verbose:
            self.logger.log_command_execution(" ".join(command))

        try:
            subprocess.run(command, check=True)
            if self.config.verbose:
                self.logger.log_command_execution(" ".join(command), success=True)
        except subprocess.CalledProcessError as e:
            self.logger.log_command_execution(
                " ".join(command), e.returncode, success=False
            )
            raise MountCommandExecutionError(
                "squashfuse",
                e.returncode,
                f"Failed to mount {file_path} to {mount_point}",
            )

    def _execute_unmount_command(self, mount_point: Path) -> None:
        """Execute the fusermount unmount command."""
        import subprocess

        command = ["fusermount", "-u", str(mount_point)]
        if self.config.verbose:
            self.logger.log_command_execution(" ".join(command))

        try:
            subprocess.run(command, check=True)
            if self.config.verbose:
                self.logger.log_command_execution(" ".join(command), success=True)
        except subprocess.CalledProcessError as e:
            self.logger.log_command_execution(
                " ".join(command), e.returncode, success=False
            )
            raise UnmountCommandExecutionError(
                "fusermount", e.returncode, f"Failed to unmount from {mount_point}"
            )

    def _cleanup_mount_directory(self, mount_point: Path) -> None:
        """Clean up the mount directory after unmounting."""
        if self.config.auto_cleanup:
            try:
                shutil.rmtree(mount_point)
                if self.config.verbose:
                    self.logger.log_cleanup_operation(
                        str(mount_point), "directory_removal"
                    )

                # Clean up parent directory if empty and it's our mount base
                mounts_dir = mount_point.parent
                if mounts_dir.name == self.config.mount_base:
                    try:
                        os.rmdir(mounts_dir)
                        if self.config.verbose:
                            self.logger.log_cleanup_operation(
                                str(mounts_dir), "parent_directory_removal"
                            )
                    except OSError:
                        self.logger.log_cleanup_operation(
                            str(mounts_dir), "parent_directory_removal", success=False
                        )
                        pass  # Parent directory not empty, that's fine
            except OSError as e:
                self.logger.log_cleanup_operation(
                    str(mount_point), "directory_removal", success=False
                )
                self.logger.logger.warning(
                    f"Could not remove directory {mount_point}: {e}"
                )

    def mount(self, file_path: str, mount_point: Optional[str] = None) -> None:
        """Mount a squashfs file, with safety checks to prevent duplicate mounting."""

        # Check if already mounted
        if self.tracker.is_mounted(file_path):
            self.logger.log_mount_failed(
                file_path, "already_mounted", "File is already mounted"
            )
            raise MountError(f"{file_path} is already mounted")

        # Determine mount point
        mount_point_obj = self._determine_mount_point(file_path, mount_point)
        # Only log the final result, not intermediate steps
        # self.logger.log_mount_start(file_path, str(mount_point_obj))

        # Validate mount point availability
        self._validate_mount_point_available(mount_point_obj)

        # Create mount directory
        self._create_mount_directory(mount_point_obj)
        if self.config.verbose:
            self.logger.log_cleanup_operation(
                str(mount_point_obj), "directory_creation"
            )

        # Perform the mount
        self._execute_mount_command(file_path, mount_point_obj)

        self.logger.log_mount_success(file_path, str(mount_point_obj))

        # Record the mount with absolute paths
        self.tracker.record_mount(file_path, str(mount_point_obj.resolve()))
        if self.config.verbose:
            self.logger.log_tracking_operation(file_path, "record_mount")

    def unmount(self, file_path: str, mount_point: Optional[str] = None) -> None:
        """Unmount a squashfs file, with safety checks to prevent duplicate unmounting."""

        # Check if mounted
        if not self.tracker.is_mounted(file_path):
            raise UnmountError(f"{file_path} is not mounted")

        # Get mount info from tracking file
        mount_info = self.tracker.get_mount_info(file_path)
        if not mount_info:
            raise UnmountError(f"Could not determine mount point for {file_path}")

        # Use provided mount point or the one from tracking file
        if mount_point:
            mount_point_obj = Path(mount_point)
        else:
            # Get the mount point from our tracking file
            mount_point_obj = Path(mount_info[1])

        # Only log the final result, not intermediate steps
        # self.logger.log_unmount_start(file_path, str(mount_point_obj))

        # Verify mount point exists and is not empty
        self._is_mount_point_valid(mount_point_obj)

        # Perform the unmount
        self._execute_unmount_command(mount_point_obj)

        self.logger.log_unmount_success(file_path, str(mount_point_obj))

        # Clean up mount directory
        self._cleanup_mount_directory(mount_point_obj)

        # Remove tracking file
        self.tracker.record_unmount(file_path)
        if self.config.verbose:
            self.logger.log_tracking_operation(file_path, "record_unmount")
