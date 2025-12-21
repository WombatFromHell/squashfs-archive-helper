"""
Core module for the SquashFS Archive Helper.

This module serves as a facade for all other modules,
providing a unified interface for all functionality.
"""

from typing import Optional

from .build import BuildManager
from .checksum import ChecksumManager
from .config import SquishFSConfig
from .dependencies import check_all_dependencies
from .extract import ExtractManager
from .list import ListManager
from .logging import get_logger
from .mounting import MountManager


class SquashFSManager:
    """
    Main manager for squashfs operations.

    This class serves as a facade that coordinates functionality
    across multiple specialized modules.
    """

    def __init__(self, config: Optional[SquishFSConfig] = None):
        self.config = config if config else SquishFSConfig()
        self.logger = get_logger(self.config.verbose)
        check_all_dependencies(self.config, self.logger)

        # Initialize specialized managers
        self.mount_manager = MountManager(self.config)
        self.checksum_manager = ChecksumManager(self.config)
        self.build_manager = BuildManager(self.config)
        self.list_manager = ListManager(self.config)
        self.extract_manager = ExtractManager(self.config)

    def mount(self, file_path: str, mount_point: Optional[str] = None) -> None:
        """Mount a squashfs file."""
        self.mount_manager.mount(file_path, mount_point)

    def unmount(self, file_path: str, mount_point: Optional[str] = None) -> None:
        """Unmount a squashfs file."""
        self.mount_manager.unmount(file_path, mount_point)

    def verify_checksum(self, file_path: str) -> None:
        """Verify checksum of a file."""
        self.checksum_manager.verify_checksum(file_path)

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
        progress: bool = False,
        progress_service=None,
    ) -> None:
        """Build a SquashFS archive."""
        self.build_manager.build_squashfs(
            source,
            output,
            excludes,
            exclude_file,
            wildcards,
            regex,
            compression,
            block_size,
            processors,
            progress,
            progress_service,
        )

    def list_squashfs(self, archive: str) -> None:
        """List contents of a SquashFS archive."""
        self.list_manager.list_squashfs(archive)

    def extract_squashfs(self, archive: str, output_dir: Optional[str] = None) -> None:
        """Extract contents of a SquashFS archive."""
        self.extract_manager.extract_squashfs(archive, output_dir)
