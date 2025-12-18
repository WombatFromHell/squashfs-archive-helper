"""
Mount tracking system for the Mount-SquashFS application.

This module handles tracking of mounted squashfs files using temporary files.
"""

from pathlib import Path
from typing import Optional, Tuple

from .config import SquashFSConfig
from .errors import SquashFSError
from .logging import get_logger


class MountTracker:
    """
    Track mounted squashfs files using temporary tracking files.

    This class handles the creation, reading, and removal of tracking files
    that store information about mounted squashfs files.
    """

    def __init__(self, config: SquashFSConfig):
        self.config = config
        self.logger = get_logger(self.config.verbose)

    def _get_temp_file_path(self, file_path: str) -> Path:
        """Get the path to the temporary tracking file."""
        file_path_obj = Path(file_path)
        return Path(self.config.temp_dir) / f"{file_path_obj.stem}.mounted"

    def _read_mount_info(self, file_path: str) -> Optional[Tuple[str, str]]:
        """Read mount information from the temporary file."""
        temp_file = self._get_temp_file_path(file_path)
        if temp_file.exists():
            try:
                with open(temp_file, "r") as f:
                    # Read both lines - first line is sqs file, second is mount point
                    sqs_file = f.readline().strip()
                    mount_point = f.readline().strip()
                    if sqs_file and mount_point:
                        # Validate that the stored path matches the requested file
                        requested_path = str(Path(file_path).resolve())
                        if sqs_file == requested_path:
                            # Tracking read operations are internal - only log failures
                            # self.logger.log_tracking_operation(file_path, "read", success=True)
                            return (sqs_file, mount_point)
                        else:
                            # Path conflict: tracking file exists but is for a different file
                            self.logger.logger.error(
                                f"Tracking file conflict: {temp_file} exists for {sqs_file}, "
                                f"but requested operation on {requested_path}. "
                                f"These appear to be different files with the same name."
                            )
                            raise SquashFSError(
                                f"Tracking file conflict: {temp_file} exists for {sqs_file}, "
                                f"but requested operation on {requested_path}. "
                                f"These appear to be different files with the same name."
                            )
            except IOError as e:
                self.logger.logger.error(
                    f"Could not read mount info from {temp_file}: {e}"
                )
                raise SquashFSError(f"Could not read mount info from {temp_file}: {e}")
        else:
            # This is a normal condition when file is not mounted, log at debug level
            self.logger.logger.debug(f"Tracking file not found for: {file_path}")
        return None

    def _write_mount_info(self, file_path: str, mount_point: str) -> None:
        """Write mount information to the temporary file."""
        temp_file = self._get_temp_file_path(file_path)
        try:
            with open(temp_file, "w") as f:
                # Write each path on a separate line
                f.write(f"{Path(file_path).resolve()}\n")
                f.write(f"{Path(mount_point).resolve()}\n")
            # Tracking write operations are internal - only log failures
            # self.logger.log_tracking_operation(file_path, "write", success=True)
        except IOError as e:
            self.logger.log_tracking_operation(file_path, "write", success=False)
            raise SquashFSError(f"Could not write mount info to {temp_file}: {e}")

    def _remove_mount_info(self, file_path: str) -> None:
        """Remove the temporary mount tracking file."""
        temp_file = self._get_temp_file_path(file_path)
        try:
            if temp_file.exists():
                temp_file.unlink()
                # Tracking remove operations are internal - only log failures
                # self.logger.log_tracking_operation(file_path, "remove", success=True)
            else:
                self.logger.log_tracking_operation(file_path, "remove", success=False)
        except OSError as e:
            self.logger.log_tracking_operation(file_path, "remove", success=False)
            raise SquashFSError(f"Could not remove mount info file {temp_file}: {e}")

    def is_mounted(self, file_path: str) -> bool:
        """Check if a file is currently mounted."""
        try:
            # Check if tracking file exists AND contains the correct path
            mount_info = self.get_mount_info(file_path)
            return mount_info is not None
        except SquashFSError:
            # If there's a conflict or other error, the file is not properly mounted
            return False

    def get_mount_info(self, file_path: str) -> Optional[Tuple[str, str]]:
        """Get mount information for a file if it's mounted."""
        return self._read_mount_info(file_path)

    def record_mount(self, file_path: str, mount_point: str) -> None:
        """Record a mount operation."""
        self._write_mount_info(file_path, mount_point)

    def record_unmount(self, file_path: str) -> None:
        """Record an unmount operation."""
        self._remove_mount_info(file_path)
