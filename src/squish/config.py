"""
Configuration management for the Mount-SquashFS application.

This module handles configuration settings and validation for the
mount-squashfs functionality.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class SquashFSConfig:
    """
    Configuration for the SquashFS management system.

    Attributes:
        mount_base: Base directory name for mount points (default: "mounts")
        temp_dir: Directory for temporary tracking files (default: "/tmp")
        auto_cleanup: Automatically clean up mount directories (default: True)
        verbose: Enable verbose output (default: False)
        compression: Default compression algorithm for build operations (default: "zstd")
        block_size: Default block size for build operations (default: "1M")
        processors: Default number of processors for build operations (default: None for auto)
    """

    mount_base: str = "mounts"
    temp_dir: str = "/tmp"
    auto_cleanup: bool = True
    verbose: bool = False
    compression: str = "zstd"
    block_size: str = "1M"
    processors: Optional[int] = None

    def __post_init__(self):
        """Validate configuration values after initialization."""
        if not self.mount_base:
            raise ValueError("mount_base cannot be empty")

        if not self.temp_dir:
            raise ValueError("temp_dir cannot be empty")

        # Ensure paths are valid
        temp_path = Path(self.temp_dir)
        if not temp_path.exists():
            raise ValueError(f"temp_dir does not exist: {self.temp_dir}")

        if not temp_path.is_dir():
            raise ValueError(f"temp_dir is not a directory: {self.temp_dir}")


def get_default_config() -> SquashFSConfig:
    """Get the default configuration."""
    return SquashFSConfig()
