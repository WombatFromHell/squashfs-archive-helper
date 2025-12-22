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


class CommandNotFound(Exception):
    """Exception raised when a command is not found."""

    pass


class AmbiguousCommand(Exception):
    """Exception raised when a command is ambiguous."""

    pass


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
    build_parser.add_argument(
        "sources", nargs="+", help="Source directories/files to archive"
    )
    build_parser.add_argument(
        "-o",
        "--output",
        help="Output archive file (optional, auto-detected from last arg)",
    )
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
        # Create new config with verbose=True since config is immutable
        config = SquishFSConfig(
            mount_base=config.mount_base,
            temp_dir=config.temp_dir,
            auto_cleanup=config.auto_cleanup,
            verbose=True,
            compression=config.compression,
            block_size=config.block_size,
            processors=config.processors,
            xattr_mode=config.xattr_mode,
            exclude=config.exclude,
        )

    return config


def _resolve_via_aliases(command: str) -> str:
    """Pure function - resolve via aliases."""
    if command in COMMAND_ALIASES:
        return COMMAND_ALIASES[command]
    raise CommandNotFound(command)


def _resolve_via_exact_match(command: str) -> str:
    """Pure function - resolve via exact match."""
    if command in ALL_COMMANDS:
        return command
    raise CommandNotFound(command)


def _resolve_via_prefix_matching(command: str) -> str:
    """Pure function - resolve via prefix matching."""
    if len(command) < 2:
        raise CommandNotFound(command)

    matches = [cmd for cmd in ALL_COMMANDS if cmd.startswith(command)]

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        raise AmbiguousCommand(command, matches)

    raise CommandNotFound(command)


def _generate_suggestions(command: str) -> list[str]:
    """Pure function - generate suggestions without side effects."""
    suggestions = []

    # Find commands containing the input
    suggestions.extend(cmd for cmd in ALL_COMMANDS if command in cmd)

    # Find matching aliases
    suggestions.extend(
        f"{alias} ({full_cmd})"
        for alias, full_cmd in COMMAND_ALIASES.items()
        if command.startswith(alias) or alias.startswith(command)
    )

    return suggestions


# Command resolution strategies in order of priority
COMMAND_RESOLUTION_STRATEGIES = [
    _resolve_via_aliases,
    _resolve_via_exact_match,
    _resolve_via_prefix_matching,
]


def resolve_command(command: str) -> str:
    """Resolve command using multiple strategies with clear error handling.

    Uses a strategy pattern to try different resolution methods in order:
    1. Aliases
    2. Exact matches
    3. Prefix matching

    Args:
        command: The command or abbreviation to resolve

    Returns:
        The resolved full command name

    Raises:
        ValueError: If command is ambiguous or unknown with helpful suggestions
    """
    for strategy in COMMAND_RESOLUTION_STRATEGIES:
        try:
            return strategy(command)
        except CommandNotFound:
            continue
        except AmbiguousCommand as e:
            # Re-raise ambiguous commands immediately with better formatting
            raise ValueError(
                f"Ambiguous command '{command}': could be {', '.join(e.args[1])}"
            )

    # Provide suggestions only if all strategies fail
    suggestions = _generate_suggestions(command)
    suggestion_msg = ""
    if suggestions:
        suggestion_msg = f" Did you mean: {', '.join(suggestions)}?"

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
    sources: list[str],
    output: str | None = None,
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
        # Auto-detect output if not explicitly provided
        if output is None and len(sources) > 1:
            # Check if the last argument looks like an output file
            last_source = sources[-1]
            if last_source.endswith((".sqsh", ".sqs", ".squashfs")):
                # Last argument is likely the output
                output = last_source
                sources = sources[:-1]  # Remove output from sources
            else:
                # Use the first source for naming
                output = None

        # Import BuildConfiguration for both single and multiple source cases
        from .build import BuildConfiguration

        # Handle multiple sources by passing them directly to mksquashfs
        if len(sources) > 1:
            # mksquashfs supports multiple source arguments natively
            # For multiple sources with no output specified, use generic naming
            if output is None:
                import datetime
                from pathlib import Path

                today = datetime.datetime.now().strftime("%Y%m%d")
                # Find the next available number
                output_path = Path(".") / f"archive-{today}-01.sqsh"
                counter = 1
                while output_path.exists():
                    counter += 1
                    output_path = Path(".") / f"archive-{today}-{counter:02d}.sqsh"
                output = str(output_path)

            config = BuildConfiguration(
                source=sources,  # Pass the list of sources directly
                output=output,
                excludes=excludes if excludes else [],
                exclude_file=exclude_file,
                wildcards=wildcards,
                regex=regex,
                compression=compression,
                block_size=block_size,
                processors=processors,
                progress=progress,
            )
            manager.build_manager.build_squashfs(config)
        else:
            # Single source case - also use BuildConfiguration for consistency
            config = BuildConfiguration(
                source=sources[0],
                output=output,
                excludes=excludes if excludes else [],
                exclude_file=exclude_file,
                wildcards=wildcards,
                regex=regex,
                compression=compression,
                block_size=block_size,
                processors=processors,
                progress=progress,
            )
            manager.build_manager.build_squashfs(config)
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


def _get_command_handler(resolved_command: str, manager, args, logger):
    """Pure function to get the appropriate command handler."""
    command_handlers = {
        "mount": lambda: (
            validate_file_exists(args.file, "mount", logger),
            handle_mount_operation(manager, args.file, args.mount_point, logger),
        ),
        "unmount": lambda: (
            validate_file_exists(args.file, "unmount", logger),
            handle_unmount_operation(manager, args.file, args.mount_point, logger),
        ),
        "check": lambda: (
            validate_file_exists(args.file, "check", logger),
            handle_check_operation(manager, args.file, logger),
        ),
        "build": lambda: (
            # Validate all sources exist
            all(
                [
                    validate_directory_exists(source, "build", logger)
                    if os.path.isdir(source)
                    else validate_file_exists(source, "build", logger)
                    for source in args.sources
                ]
            ),
            handle_build_operation(
                manager,
                args.sources,
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
            ),
        ),
        "ls": lambda: (
            validate_file_exists(args.archive, "list", logger),
            handle_list_operation(manager, args.archive, logger),
        ),
        "extract": lambda: (
            validate_file_exists(args.archive, "extract", logger),
            handle_extract_operation(
                manager, args.archive, args.output, args.progress, logger
            ),
        ),
    }

    return command_handlers.get(resolved_command)


def _log_error(logger, message: str) -> None:
    """Pure function for error logging."""
    if logger:
        logger.logger.error(message)
    else:
        print(message)


def main() -> None:
    """Main entry point for the CLI with improved functional structure."""
    logger = None
    try:
        # Setup phase - pure operations
        args = parse_args()
        logger = get_logger_from_args(args)
        config = get_config_from_args(args)
        manager = SquashFSManager(config)

        # Command resolution phase
        try:
            resolved_command = resolve_command(args.command)
        except ValueError as e:
            _log_error(logger, f"Command resolution failed: {e}")
            sys.exit(1)

        # Command execution phase
        handler = _get_command_handler(resolved_command, manager, args, logger)
        if handler:
            handler()
        else:
            _log_error(logger, f"Unknown command: {resolved_command}")
            sys.exit(1)

    except KeyboardInterrupt:
        if logger:
            logger.logger.info("Operation cancelled by user")
        else:
            print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        _log_error(logger, f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
