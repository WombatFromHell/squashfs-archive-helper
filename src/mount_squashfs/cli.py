"""
Command-line interface for the Mount-SquashFS application.

This module handles argument parsing and provides the main entry point
for the command-line interface.
"""

import argparse
import os
import sys
from typing import Optional

from .config import SquashFSConfig
from .core import SquashFSManager
from .errors import SquashFSError


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Mount/unmount .sqs or .squashfs files"
    )
    parser.add_argument(
        "-u", "--unmount", action="store_true", help="Unmount the squashfs file"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument("file", help="Path to the .sqs or .squashfs file")
    parser.add_argument(
        "mount_point", nargs="?", default=None, help="Path to mount the squashfs file"
    )
    return parser.parse_args()


def get_config_from_args(args: argparse.Namespace) -> SquashFSConfig:
    """Get configuration based on command line arguments."""
    config = SquashFSConfig()
    if args.verbose:
        config.verbose = True
    return config


def handle_mount_operation(
    manager: SquashFSManager, file_path: str, mount_point: Optional[str]
) -> None:
    """Handle the mount operation."""
    try:
        manager.mount(file_path, mount_point)
    except SquashFSError as e:
        print(f"Mount failed: {e}")
        sys.exit(1)


def handle_unmount_operation(
    manager: SquashFSManager, file_path: str, mount_point: Optional[str]
) -> None:
    """Handle the unmount operation."""
    try:
        manager.unmount(file_path, mount_point)
    except SquashFSError as e:
        print(f"Unmount failed: {e}")
        sys.exit(1)


def validate_file_exists(file_path: str, unmounting: bool = False) -> None:
    """Validate that the file exists."""
    if not unmounting and not os.path.isfile(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    try:
        args = parse_args()

        # Validate file exists (unless unmounting)
        validate_file_exists(args.file, args.unmount)

        # Get configuration
        config = get_config_from_args(args)

        # Create manager
        manager = SquashFSManager(config)

        # Perform operation
        if args.unmount:
            handle_unmount_operation(manager, args.file, args.mount_point)
        else:
            handle_mount_operation(manager, args.file, args.mount_point)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
