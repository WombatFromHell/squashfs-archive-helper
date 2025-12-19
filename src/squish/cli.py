"""
Command-line interface for the SquashFS management tool.

This module handles argument parsing and provides the main entry point
for the command-line interface with subcommands for different operations.
"""

import argparse
import os
import sys
from typing import Optional

from .config import SquishFSConfig
from .core import SquashFSManager
from .errors import BuildError, ListError, SquashFSError
from .logging import get_logger


def parse_args() -> argparse.Namespace:
    """Parse command line arguments with subcommands."""
    parser = argparse.ArgumentParser(
        description="SquashFS archive management tool - mount, unmount, build, and list SquashFS archives"
    )

    # Add global verbose flag
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Mount command
    mount_parser = subparsers.add_parser("mount", help="Mount a SquashFS archive")
    mount_parser.add_argument("file", help="Path to the .sqs or .squashfs file")
    mount_parser.add_argument(
        "mount_point", nargs="?", default=None, help="Path to mount the squashfs file"
    )

    # Unmount command
    unmount_parser = subparsers.add_parser("unmount", help="Unmount a SquashFS archive")
    unmount_parser.add_argument("file", help="Path to the .sqs or .squashfs file")
    unmount_parser.add_argument(
        "mount_point", nargs="?", default=None, help="Path to unmount"
    )

    # Check command
    check_parser = subparsers.add_parser(
        "check", help="Verify checksum of a SquashFS archive"
    )
    check_parser.add_argument("file", help="Path to the .sqs or .squashfs file")

    # Build command
    build_parser = subparsers.add_parser("build", help="Create a SquashFS archive")
    build_parser.add_argument("source", help="Source directory to archive")
    build_parser.add_argument("output", help="Output archive file")
    build_parser.add_argument(
        "-e", "--exclude", action="append", help="Exclude pattern"
    )
    build_parser.add_argument("-f", "--exclude-file", help="File with exclude patterns")
    build_parser.add_argument(
        "-w", "--wildcards", action="store_true", help="Enable wildcard matching"
    )
    build_parser.add_argument(
        "-r", "--regex", action="store_true", help="Enable regex matching"
    )
    build_parser.add_argument(
        "-c",
        "--compression",
        default="zstd",
        help="Compression algorithm (default: zstd)",
    )
    build_parser.add_argument(
        "-b", "--block-size", default="1M", help="Block size (default: 1M)"
    )
    build_parser.add_argument(
        "-p", "--processors", type=int, help="Number of processors (default: auto)"
    )

    # List command
    list_parser = subparsers.add_parser(
        "ls", help="List contents of a SquashFS archive"
    )
    list_parser.add_argument("archive", help="Path to the SquashFS archive")

    return parser.parse_args()


def get_config_from_args(args: argparse.Namespace) -> SquishFSConfig:
    """Get configuration based on command line arguments."""
    config = SquishFSConfig()
    if args.verbose:
        config.verbose = True
    return config


def get_logger_from_args(args: argparse.Namespace):
    """Get logger based on command line arguments."""
    return get_logger(args.verbose)


def validate_file_exists(file_path: str, operation: str = "mount", logger=None) -> None:
    """Validate that the file exists."""
    if not os.path.isfile(file_path):
        if logger:
            logger.log_file_not_found(file_path, operation)
        else:
            print(f"File not found: {file_path}")
        sys.exit(1)


def validate_directory_exists(
    dir_path: str, operation: str = "build", logger=None
) -> None:
    """Validate that the directory exists."""
    if not os.path.isdir(dir_path):
        if logger:
            logger.log_directory_not_found(
                dir_path, operation
            )  # Use the appropriate logging method
        else:
            print(f"Directory not found: {dir_path}")
        sys.exit(1)


def handle_mount_operation(
    manager: SquashFSManager, file_path: str, mount_point: Optional[str], logger=None
) -> None:
    """Handle the mount operation."""
    try:
        manager.mount(file_path, mount_point)
    except SquashFSError as e:
        if logger:
            logger.log_mount_failed(
                file_path, str(mount_point) if mount_point else "auto", str(e)
            )
        else:
            print(f"Mount failed: {e}")
        sys.exit(1)


def handle_unmount_operation(
    manager: SquashFSManager, file_path: str, mount_point: Optional[str], logger=None
) -> None:
    """Handle the unmount operation."""
    try:
        manager.unmount(file_path, mount_point)
    except SquashFSError as e:
        if logger:
            logger.log_unmount_failed(
                file_path, str(mount_point) if mount_point else "auto", str(e)
            )
        else:
            print(f"Unmount failed: {e}")
        sys.exit(1)


def handle_check_operation(
    manager: SquashFSManager, file_path: str, logger=None
) -> None:
    """Handle the checksum verification operation."""
    try:
        manager.verify_checksum(file_path)
        if logger:
            logger.logger.info(f"Image checksum verified successfully: {file_path}")
        else:
            print(f"Checksum verification successful for: {file_path}")
    except SquashFSError as e:
        if logger:
            logger.logger.error(f"{e}")
        else:
            print(f"{e}")
        sys.exit(1)


def handle_build_operation(
    manager: SquashFSManager,
    source: str,
    output: str,
    excludes: list[str] | None = None,
    exclude_file: str | None = None,
    wildcards: bool = False,
    regex: bool = False,
    compression: str = "zstd",
    block_size: str = "1M",
    processors: int | None = None,
    logger=None,
) -> None:
    """Handle the build operation."""
    try:
        manager.build_squashfs(
            source,
            output,
            excludes=excludes if excludes else [],
            exclude_file=exclude_file,
            wildcards=wildcards,
            regex=regex,
            compression=compression,
            block_size=block_size,
            processors=processors,
        )
    except BuildError as e:
        if logger:
            logger.logger.error(f"Build failed: {e}")
        else:
            print(f"Build failed: {e}")
        sys.exit(1)


def handle_list_operation(manager: SquashFSManager, archive: str, logger=None) -> None:
    """Handle the list operation."""
    try:
        manager.list_squashfs(archive)
    except ListError as e:
        if logger:
            logger.logger.error(f"List operation failed: {e}")
        else:
            print(f"List operation failed: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    logger = None
    try:
        args = parse_args()

        # Get logger first so we can use it for all operations
        logger = get_logger_from_args(args)

        # Get configuration
        config = get_config_from_args(args)

        # Create manager
        manager = SquashFSManager(config)

        # Perform operation based on command
        if args.command == "mount":
            validate_file_exists(args.file, "mount", logger)
            handle_mount_operation(manager, args.file, args.mount_point, logger)

        elif args.command == "unmount":
            validate_file_exists(args.file, "unmount", logger)
            handle_unmount_operation(manager, args.file, args.mount_point, logger)

        elif args.command == "check":
            validate_file_exists(args.file, "check", logger)
            handle_check_operation(manager, args.file, logger)

        elif args.command == "build":
            validate_directory_exists(args.source, "build", logger)
            handle_build_operation(
                manager,
                args.source,
                args.output,
                excludes=args.exclude,
                exclude_file=args.exclude_file,
                wildcards=args.wildcards,
                regex=args.regex,
                compression=args.compression,
                block_size=args.block_size,
                processors=args.processors,
                logger=logger,
            )

        elif args.command == "ls":
            validate_file_exists(args.archive, "list", logger)
            handle_list_operation(manager, args.archive, logger)

    except KeyboardInterrupt:
        if logger:
            logger.logger.info("Operation cancelled by user")
        else:
            print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        if logger:
            logger.logger.error(f"Unexpected error: {e}")
        else:
            print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
