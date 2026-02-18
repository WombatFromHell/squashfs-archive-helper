"""
Command-line interface for the SquashFS management tool.

This module handles argument parsing and provides the main entry point
for the command-line interface with subcommands for different operations.
"""

import argparse
import os
import sys
from typing import Optional

from .config import SquishFSConfig, get_merged_config
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
from .version import get_version


class CommandNotFound(Exception):
    """Exception raised when a command is not found."""

    pass


class AmbiguousCommand(Exception):
    """Exception raised when a command is ambiguous."""

    pass


# All available full commands
ALL_COMMANDS = ["mount", "unmount", "check", "build", "extract", "ls"]


def parse_args() -> argparse.Namespace:
    """Parse command line arguments with subcommands."""
    parser = argparse.ArgumentParser(
        prog="squish.pyz",
        description=f"SquashFS archive management tool {get_version()} - mount, unmount, build, and list SquashFS archives",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Unique prefix matching is supported for all commands.
For example: 'm' -> 'mount', 'bu' -> 'build', 'ext' -> 'extract', 'l' -> 'ls'.
Ambiguous abbreviations will result in an error with suggestions.""".strip(),
    )

    # Add global verbose flag
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    # Add version flag
    parser.add_argument(
        "-V", "--version", action="version", version=f"%(prog)s {get_version()}"
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
    unmount_parser = subparsers.add_parser(
        "unmount",
        help="Unmount a SquashFS archive",
    )
    unmount_parser.add_argument("file", help="Path to the .sqs or .squashfs file")
    unmount_parser.add_argument(
        "mount_point", nargs="?", default=None, help="Path to unmount"
    )

    # Check command
    check_parser = subparsers.add_parser(
        "check",
        help="Verify checksum of a SquashFS archive",
    )
    check_parser.add_argument("file", help="Path to the .sqs or .squashfs file")

    # Build command
    build_parser = subparsers.add_parser("build", help="Create a SquashFS archive")
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
        "ls", help="List contents of a SquashFS archive"
    )
    list_parser.add_argument("archive", help="Path to the SquashFS archive")

    # Extract command
    extract_parser = subparsers.add_parser("extract", help="Extract a SquashFS archive")
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
    """Get configuration based on command line arguments and other sources.

    Merges configuration from multiple sources with proper precedence:
    1. CLI arguments (highest priority)
    2. Environment variables
    3. Configuration file
    4. Default values (lowest priority)
    """
    # Convert CLI arguments to dictionary for merging
    cli_config = {}

    # Map CLI arguments to config keys (only include valid, non-mock values)
    # Use getattr with default to handle missing attributes gracefully
    verbose_val = getattr(args, "verbose", False)
    if verbose_val and not hasattr(verbose_val, "__mock__"):
        cli_config["verbose"] = verbose_val

    compression_val = getattr(args, "compression", None)
    if compression_val and not hasattr(compression_val, "__mock__"):
        cli_config["compression"] = compression_val

    block_size_val = getattr(args, "block_size", None)
    if block_size_val and not hasattr(block_size_val, "__mock__"):
        cli_config["block_size"] = block_size_val

    processors_val = getattr(args, "processors", None)
    if processors_val is not None and not hasattr(processors_val, "__mock__"):
        cli_config["processors"] = processors_val

    exclude_val = getattr(args, "exclude", None)
    if exclude_val and not hasattr(exclude_val, "__mock__"):
        cli_config["exclude"] = exclude_val

    xattr_mode_val = getattr(args, "xattr_mode", None)
    if xattr_mode_val and not hasattr(xattr_mode_val, "__mock__"):
        cli_config["xattr_mode"] = xattr_mode_val

    # Get merged configuration from all sources
    return get_merged_config(cli_config)


def resolve_command(command: str) -> str:
    """Resolve command using unique prefix matching.

    Matches the input string against all available commands.
    If exactly one command starts with the input, it is returned.

    Args:
        command: The command or abbreviation to resolve

    Returns:
        The resolved full command name

    Raises:
        ValueError: If command is ambiguous or unknown
    """
    if not command:
        raise ValueError("No command provided")

    # Exact match first
    if command in ALL_COMMANDS:
        return command

    # Prefix matching
    matches = [cmd for cmd in ALL_COMMANDS if cmd.startswith(command)]

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        raise ValueError(
            f"Ambiguous command '{command}': could be {', '.join(matches)}"
        )

    # If no matches, suggest commands that contain the string
    suggestions = [cmd for cmd in ALL_COMMANDS if command in cmd]
    suggestion_msg = ""
    if suggestions:
        suggestion_msg = f" Did you mean: {', '.join(suggestions)}?"

    raise ValueError(
        f"Unknown command '{command}'. Available commands: {', '.join(ALL_COMMANDS)}{suggestion_msg}"
    )


def resolve_command_line_args(argv: list[str]) -> list[str]:
    """Resolve command abbreviations in command line arguments.

    This function looks for the subcommand in the argument list and
    resolves any abbreviations to their full command names.

    Args:
        argv: The list of command line arguments (e.g. sys.argv)

    Returns:
        The updated list of arguments with resolved command names
    """
    new_argv = list(argv)

    # Find the command in argv
    # It's the first argument that doesn't start with '-' and isn't the script itself
    command_idx = -1
    for i, arg in enumerate(new_argv[1:], 1):
        if not arg.startswith("-"):
            command_idx = i
            break

    if command_idx != -1:
        raw_command = new_argv[command_idx]
        try:
            resolved_command = resolve_command(raw_command)
            # Replace the abbreviation with the full command name
            new_argv[command_idx] = resolved_command
        except ValueError:
            # If resolution fails, we leave it as is so argparse can handle it
            # and show the standard "invalid choice" error if appropriate,
            # or it might be a valid command we don't know about yet?
            # Actually, our resolve_command is authoritative for ALL_COMMANDS.
            pass

    return new_argv


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


def _resolve_build_sources_and_output(
    sources: list[str], output: Optional[str]
) -> tuple[list[str], Optional[str]]:
    """Resolve sources and output path, handling implicit output in arguments."""
    # If explicit output provided via -o, use it
    if output is not None:
        return sources, output

    # Check for implicit output (last argument ending in archive extension)
    # Only if there's more than one argument total (e.g. "squish b src output.sqsh")
    if len(sources) > 1:
        last_arg = sources[-1]
        if last_arg.lower().endswith((".sqsh", ".sqs", ".squashfs")):
            return sources[:-1], last_arg

    return sources, None


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
        # Import BuildConfiguration locally to avoid circular imports if any
        from .build import BuildConfiguration

        # Resolve sources and output (handle implicit output arg)
        sources, output = _resolve_build_sources_and_output(sources, output)

        config = BuildConfiguration(
            source=sources[0] if len(sources) == 1 else sources,
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
        # Before parsing with argparse, we need to resolve the command
        # This allows arbitrary abbreviations like 'bu' for 'build' to work
        # from the command line, which argparse subparsers don't support natively.
        sys.argv = resolve_command_line_args(sys.argv)

        # Setup phase - pure operations
        args = parse_args()
        logger = get_logger_from_args(args)
        config = get_config_from_args(args)
        manager = SquashFSManager(config)

        # Command execution phase
        handler = _get_command_handler(args.command, manager, args, logger)
        if handler:
            handler()
        else:
            _log_error(logger, f"Unknown command: {args.command}")
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
