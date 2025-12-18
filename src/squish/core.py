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
    BuildError,
    ChecksumCommandExecutionError,
    ChecksumError,
    DependencyError,
    ListError,
    MksquashfsCommandExecutionError,
    MountCommandExecutionError,
    MountError,
    MountPointError,
    UnmountCommandExecutionError,
    UnmountError,
    UnsquashfsCommandExecutionError,
)
from .logging import get_logger
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
        self.logger = get_logger(self.config.verbose)
        self._check_dependencies()

    def _check_commands(self, commands: list[str]) -> None:
        """Check if required commands are available."""
        for cmd in commands:
            try:
                # Only log on success if verbose mode is enabled
                if self.config.verbose:
                    self.logger.log_dependency_check(cmd, "available")
                subprocess.run(
                    ["which", cmd],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError:
                self.logger.log_dependency_check(cmd, "missing")
                raise DependencyError(
                    f"{cmd} is not installed or not in PATH. "
                    f"Please install {cmd} to use this script."
                )

    def _check_linux_dependencies(self) -> None:
        """Check for Linux-specific dependencies."""
        self._check_commands(["squashfuse", "fusermount", "sha256sum"])

    def _check_build_dependencies(self) -> None:
        """Check for build-specific dependencies."""
        self._check_commands(["mksquashfs", "unsquashfs", "nproc"])

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
            source, output, exclude_args, compression, block_size, processors
        )

        # Generate checksum
        self._generate_checksum(output)

        self.logger.logger.info(f"Created: {output}")

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
