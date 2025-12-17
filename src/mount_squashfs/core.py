"""
Core mounting/unmounting logic for the Mount-SquashFS application.

This module contains the main functionality for mounting and unmounting
squashfs files, including dependency checking and safety validation.
"""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .config import SquashFSConfig
from .errors import (
    DependencyError,
    MountCommandExecutionError,
    MountError,
    MountPointError,
    UnmountCommandExecutionError,
    UnmountError,
)
from .tracking import MountTracker


class SquashFSManager:
    """
    Main manager for squashfs mounting/unmounting operations.

    This class handles all core operations including dependency checking,
    mount point validation, and the actual mounting/unmounting processes.
    """

    def __init__(self, config: Optional[SquashFSConfig] = None):
        self.config = config if config else SquashFSConfig()
        self.tracker = MountTracker(self.config)
        self._check_dependencies()

    def _check_commands(self, commands: list[str]) -> None:
        """Check if required commands are available."""
        for cmd in commands:
            try:
                subprocess.run(
                    ["which", cmd],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError:
                raise DependencyError(
                    f"{cmd} is not installed or not in PATH. "
                    f"Please install {cmd} to use this script."
                )

    def _check_linux_dependencies(self) -> None:
        """Check for Linux-specific dependencies."""
        self._check_commands(["squashfuse", "fusermount"])

    def _check_dependencies(self) -> None:
        """Check system dependencies."""
        current_os = platform.system().lower()
        if current_os == "linux":
            self._check_linux_dependencies()
        else:
            raise DependencyError(
                f"This script is currently only supported on Linux. "
                f"Detected OS: {current_os}"
            )

    def _is_mount_point_valid(self, mount_point: Path) -> bool:
        """Check if the mount point exists and is not empty."""
        if not mount_point.exists():
            raise MountPointError(f"Mount point does not exist: {mount_point}")

        if not any(mount_point.iterdir()):
            raise MountPointError(
                f"Mount point is empty, nothing to unmount: {mount_point}"
            )

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
            raise MountError(f"Mount point {mount_point} is not empty")

    def _execute_mount_command(self, file_path: str, mount_point: Path) -> None:
        """Execute the squashfuse mount command."""
        try:
            subprocess.run(["squashfuse", str(file_path), str(mount_point)], check=True)
        except subprocess.CalledProcessError as e:
            raise MountCommandExecutionError(
                "squashfuse",
                e.returncode,
                f"Failed to mount {file_path} to {mount_point}",
            )

    def _execute_unmount_command(self, mount_point: Path) -> None:
        """Execute the fusermount unmount command."""
        try:
            subprocess.run(["fusermount", "-u", str(mount_point)], check=True)
        except subprocess.CalledProcessError as e:
            raise UnmountCommandExecutionError(
                "fusermount", e.returncode, f"Failed to unmount from {mount_point}"
            )

    def _cleanup_mount_directory(self, mount_point: Path) -> None:
        """Clean up the mount directory after unmounting."""
        if self.config.auto_cleanup:
            try:
                shutil.rmtree(mount_point)

                # Clean up parent directory if empty and it's our mount base
                mounts_dir = mount_point.parent
                if mounts_dir.name == self.config.mount_base:
                    try:
                        os.rmdir(mounts_dir)
                    except OSError:
                        pass  # Parent directory not empty, that's fine
            except OSError as e:
                if self.config.verbose:
                    print(f"Warning: Could not remove directory {mount_point}: {e}")

    def mount(self, file_path: str, mount_point: Optional[str] = None) -> None:
        """Mount a squashfs file, with safety checks to prevent duplicate mounting."""

        # Check if already mounted
        if self.tracker.is_mounted(file_path):
            raise MountError(f"{file_path} is already mounted")

        # Determine mount point
        mount_point_obj = self._determine_mount_point(file_path, mount_point)

        # Validate mount point availability
        self._validate_mount_point_available(mount_point_obj)

        # Create mount directory
        self._create_mount_directory(mount_point_obj)

        # Perform the mount
        self._execute_mount_command(file_path, mount_point_obj)

        if self.config.verbose:
            print(f"Mounted {file_path} to {mount_point_obj}")

        # Record the mount with absolute paths
        self.tracker.record_mount(file_path, str(mount_point_obj.resolve()))

    def unmount(self, file_path: str, mount_point: Optional[str] = None) -> None:
        """Unmount a squashfs file, with safety checks to prevent duplicate unmounting."""
        file_path_obj = Path(file_path)

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

        # Verify mount point exists and is not empty
        self._is_mount_point_valid(mount_point_obj)

        # Perform the unmount
        self._execute_unmount_command(mount_point_obj)

        if self.config.verbose:
            print(f"Unmounted {file_path_obj.stem} from {mount_point_obj}")

        # Clean up mount directory
        self._cleanup_mount_directory(mount_point_obj)

        # Remove tracking file
        self.tracker.record_unmount(file_path)
