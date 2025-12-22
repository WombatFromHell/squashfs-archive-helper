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
from .errors import (
    BuildError,
    ExtractCancelledError,
    ExtractError,
    ListError,
    SquashFSError,
    XattrError,
)
from .logging import get_logger

# Command abbreviation system - keep only the most common single-letter aliases
COMMAND_ALIASES = {
    "m": "mount",
    "um": "unmount",
    "c": "check",
    "b": "build",
    "l": "ls",
    "ex": "extract",
}

ALL_COMMANDS = ["mount", "unmount", "check", "build", "extract", "ls"]


def parse_args() -> argparse.Namespace:
    """Parse command line arguments with subcommands."""
    parser = argparse.ArgumentParser(
        description="SquashFS archive management tool - mount, unmount, build, and list SquashFS archives",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Command abbreviations:
  mount    -> m
  unmount  -> um
  check    -> c
  build    -> b
  ls       -> l
  extract  -> ex

Prefix matching is supported for commands (minimum 2 characters).
For example: 'mou' -> 'mount', 'bu' -> 'build', 'lis' -> 'ls'""".strip(),
    )

    # Add global verbose flag
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Mount command
    mount_parser = subparsers.add_parser(
        "mount", help="Mount a SquashFS archive", aliases=["m"]
    )
    mount_parser.add_argument("file", help="Path to the .sqs or .squashfs file")
    mount_parser.add_argument(
        "mount_point", nargs="?", default=None, help="Path to mount the squashfs file"
    )

    # Unmount command
    unmount_parser = subparsers.add_parser(
        "unmount",
        help="Unmount a SquashFS archive",
        aliases=["um"],
    )
    unmount_parser.add_argument("file", help="Path to the .sqs or .squashfs file")
    unmount_parser.add_argument(
        "mount_point", nargs="?", default=None, help="Path to unmount"
    )

    # Check command
    check_parser = subparsers.add_parser(
        "check",
        help="Verify checksum of a SquashFS archive",
        aliases=["c"],
    )
    check_parser.add_argument("file", help="Path to the .sqs or .squashfs file")

    # Build command
    build_parser = subparsers.add_parser(
        "build", help="Create a SquashFS archive", aliases=["b"]
    )
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
    build_parser.add_argument(
        "-P", "--progress", action="store_true", help="Show progress dialog with Zenity"
    )

    # List command
    list_parser = subparsers.add_parser(
        "ls", help="List contents of a SquashFS archive", aliases=["l"]
    )
    list_parser.add_argument("archive", help="Path to the SquashFS archive")

    # Extract command
    extract_parser = subparsers.add_parser(
        "extract", help="Extract a SquashFS archive", aliases=["ex"]
    )
    extract_parser.add_argument("archive", help="Path to the SquashFS archive")
    extract_parser.add_argument(
        "-o",
        "--output",
        default=".",
        help="Output directory (default: current directory)",
    )
    extract_parser.add_argument(
        "-P",
        "--progress",
        action="store_true",
        help="Show progress dialog with Zenity (falls back to console if Zenity unavailable)",
    )

    return parser.parse_args()


def get_config_from_args(args: argparse.Namespace) -> SquishFSConfig:
    """Get configuration based on command line arguments."""
    config = SquishFSConfig()
    if args.verbose:
        config.verbose = True

    return config


def resolve_command(command: str) -> str:
    """Resolve command abbreviations to full command names using hybrid approach.

    1. First check explicit aliases
    2. Then check if it's already a full command name
    3. Finally try prefix matching for longer abbreviations (minimum 2 characters)

    Args:
        command: The command or abbreviation to resolve

    Returns:
        The resolved full command name

    Raises:
        ValueError: If command is ambiguous or unknown
    """
    # 1. Check explicit aliases first
    if command in COMMAND_ALIASES:
        return COMMAND_ALIASES[command]

    # 2. Check if it's already a full command name
    if command in ALL_COMMANDS:
        return command

    # 3. Try prefix matching for longer abbreviations (minimum 2 characters)
    if len(command) >= 2:
        matches = [cmd for cmd in ALL_COMMANDS if cmd.startswith(command)]

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            raise ValueError(
                f"Ambiguous command '{command}': could be {', '.join(matches)}"
            )

    # Provide helpful suggestions
    suggestions = []
    for full_cmd in ALL_COMMANDS:
        if command in full_cmd:  # contains the characters, not necessarily prefix
            suggestions.append(full_cmd)

    suggestion_msg = ""
    if suggestions:
        suggestion_msg = f" Did you mean: {', '.join(suggestions)}?"

    # Also suggest single-letter aliases if available
    alias_suggestions = []
    for alias, full_cmd in COMMAND_ALIASES.items():
        if command.startswith(alias) or alias.startswith(command):
            alias_suggestions.append(f"{alias} ({full_cmd})")

    if alias_suggestions:
        if suggestion_msg:
            suggestion_msg += f" Or try: {', '.join(alias_suggestions)}?"
        else:
            suggestion_msg = f" Did you mean: {', '.join(alias_suggestions)}?"

    raise ValueError(
        f"Unknown command '{command}'. Available commands: {', '.join(ALL_COMMANDS)}{suggestion_msg}"
    )


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
    progress: bool = False,
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
            progress=progress,
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


def handle_extract_operation(
    manager: SquashFSManager,
    archive: str,
    output_dir: str,
    progress: bool = False,
    logger=None,
) -> None:
    """Handle the extract operation."""
    try:
        manager.extract_squashfs(archive, output_dir, progress=progress)
    except ExtractCancelledError:
        if logger:
            logger.logger.info("Extract operation cancelled by user")
        else:
            print("Extract operation cancelled by user")
        sys.exit(0)  # Exit with 0 for user cancellation
    except XattrError as e:
        if logger:
            logger.logger.error(f"Extract operation failed: {e}")
        else:
            print(f"Extract operation failed: {e}")
        sys.exit(2)  # Use exit code 2 for xattr-specific errors
    except ExtractError as e:
        if logger:
            logger.logger.error(f"Extract operation failed: {e}")
        else:
            print(f"Extract operation failed: {e}")
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

        # Resolve command abbreviations
        try:
            resolved_command = resolve_command(args.command)
        except ValueError as e:
            if logger:
                logger.logger.error(f"Command resolution failed: {e}")
            else:
                print(f"Error: {e}")
            sys.exit(1)

        # Perform operation based on resolved command
        if resolved_command == "mount":
            validate_file_exists(args.file, "mount", logger)
            handle_mount_operation(manager, args.file, args.mount_point, logger)

        elif resolved_command == "unmount":
            validate_file_exists(args.file, "unmount", logger)
            handle_unmount_operation(manager, args.file, args.mount_point, logger)

        elif resolved_command == "check":
            validate_file_exists(args.file, "check", logger)
            handle_check_operation(manager, args.file, logger)

        elif resolved_command == "build":
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
                progress=args.progress,
                logger=logger,
            )

        elif resolved_command == "ls":
            validate_file_exists(args.archive, "list", logger)
            handle_list_operation(manager, args.archive, logger)

        elif resolved_command == "extract":
            validate_file_exists(args.archive, "extract", logger)
            handle_extract_operation(
                manager, args.archive, args.output, args.progress, logger
            )

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
