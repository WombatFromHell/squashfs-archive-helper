"""
Configuration management for the Mount-SquashFS application.

This module handles configuration settings and validation for the
mount-squashfs functionality.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class SquishFSConfig:
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
        xattr_mode: Xattr handling mode for extract operations (auto-detected based on user privileges)
    """

    mount_base: str = "mounts"
    temp_dir: str = "/tmp"
    auto_cleanup: bool = True
    verbose: bool = False
    compression: str = "zstd"
    block_size: str = "1M"
    processors: Optional[int] = None
    xattr_mode: Optional[str] = None  # Will be auto-detected in __post_init__

    def __post_init__(self):
        """Validate configuration values after initialization."""
        if not self.mount_base:
            raise ValueError("mount_base cannot be empty")

        if not self.temp_dir:
            raise ValueError("temp_dir cannot be empty")

        # Auto-detect xattr_mode based on user privileges if not explicitly set
        if self.xattr_mode is None:
            if is_root_user():
                # Root users can handle all xattrs including security.selinux
                self.xattr_mode = "all"
            else:
                # Non-root users should avoid system xattrs to prevent permission errors
                self.xattr_mode = "user-only"

        # Validate xattr_mode
        valid_xattr_modes = ["all", "user-only", "none"]
        if self.xattr_mode not in valid_xattr_modes:
            raise ValueError(
                f"xattr_mode must be one of {valid_xattr_modes}, got: {self.xattr_mode}"
            )

        # Ensure paths are valid
        temp_path = Path(self.temp_dir)
        if not temp_path.exists():
            raise ValueError(f"temp_dir does not exist: {self.temp_dir}")

        if not temp_path.is_dir():
            raise ValueError(f"temp_dir is not a directory: {self.temp_dir}")


def is_root_user() -> bool:
    """Check if the current user has root privileges."""
    return os.geteuid() == 0


def get_default_config() -> SquishFSConfig:
    """Get the default configuration."""
    return SquishFSConfig()
