"""
Mount tracking system for the Mount-SquashFS application.

This module handles tracking of mounted squashfs files using temporary files.
"""

from pathlib import Path
from typing import Optional, Tuple

from .config import SquashFSConfig
from .errors import SquashFSError


class MountTracker:
    """
    Track mounted squashfs files using temporary tracking files.

    This class handles the creation, reading, and removal of tracking files
    that store information about mounted squashfs files.
    """

    def __init__(self, config: SquashFSConfig):
        self.config = config

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
                        return (sqs_file, mount_point)
            except IOError as e:
                raise SquashFSError(f"Could not read mount info from {temp_file}: {e}")
        return None

    def _write_mount_info(self, file_path: str, mount_point: str) -> None:
        """Write mount information to the temporary file."""
        temp_file = self._get_temp_file_path(file_path)
        try:
            with open(temp_file, "w") as f:
                # Write each path on a separate line
                f.write(f"{Path(file_path).resolve()}\n")
                f.write(f"{Path(mount_point).resolve()}\n")
        except IOError as e:
            raise SquashFSError(f"Could not write mount info to {temp_file}: {e}")

    def _remove_mount_info(self, file_path: str) -> None:
        """Remove the temporary mount tracking file."""
        temp_file = self._get_temp_file_path(file_path)
        try:
            if temp_file.exists():
                temp_file.unlink()
        except OSError as e:
            raise SquashFSError(f"Could not remove mount info file {temp_file}: {e}")

    def is_mounted(self, file_path: str) -> bool:
        """Check if a file is currently mounted."""
        return self._get_temp_file_path(file_path).exists()

    def get_mount_info(self, file_path: str) -> Optional[Tuple[str, str]]:
        """Get mount information for a file if it's mounted."""
        return self._read_mount_info(file_path)

    def record_mount(self, file_path: str, mount_point: str) -> None:
        """Record a mount operation."""
        self._write_mount_info(file_path, mount_point)

    def record_unmount(self, file_path: str) -> None:
        """Record an unmount operation."""
        self._remove_mount_info(file_path)
