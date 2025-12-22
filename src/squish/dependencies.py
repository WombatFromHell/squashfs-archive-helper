"""
Dependency checking logic for the SquashFS Archive Helper.

This module contains functionality for checking system dependencies
and command availability for various operations.
"""

import platform
import subprocess
from typing import Optional

from .config import SquishFSConfig
from .errors import DependencyError


def _check_single_command(cmd: str, config, logger) -> bool:
    """Pure function to check a single command."""
    try:
        subprocess.run(
            ["which", cmd],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def check_commands(
    commands: list[str], config: Optional[SquishFSConfig] = None, logger=None
) -> None:
    """Check if required commands are available using functional pattern."""
    if config is None:
        from .config import SquishFSConfig

        config = SquishFSConfig()

    if logger is None:
        from .logging import get_logger

        logger = get_logger(config.verbose)

    # Use functional approach: find first missing command
    missing_commands = [
        cmd for cmd in commands if not _check_single_command(cmd, config, logger)
    ]

    if missing_commands:
        missing_cmd = missing_commands[0]  # Take first missing command
        logger.log_dependency_check(missing_cmd, "missing")
        raise DependencyError(
            f"{missing_cmd} is not installed or not in PATH. "
            f"Please install {missing_cmd} to use this script."
        )

    # Log all available commands if verbose
    if config.verbose:
        for cmd in commands:
            logger.log_dependency_check(cmd, "available")


def check_linux_dependencies(
    config: Optional[SquishFSConfig] = None, logger=None
) -> None:
    """Check for Linux-specific dependencies."""
    check_commands(["squashfuse", "fusermount", "sha256sum"], config, logger)


def check_build_dependencies(
    config: Optional[SquishFSConfig] = None, logger=None
) -> None:
    """Check for build-specific dependencies."""
    check_commands(["mksquashfs", "unsquashfs", "nproc"], config, logger)


def check_all_dependencies(
    config: Optional[SquishFSConfig] = None, logger=None
) -> None:
    """Check system dependencies."""
    current_os = platform.system().lower()
    if current_os == "linux":
        check_linux_dependencies(config, logger)
    else:
        # Create a temporary logger if none provided
        if logger is None:
            if config is None:
                from .config import SquishFSConfig

                config = SquishFSConfig()
            from .logging import get_logger

            logger = get_logger(config.verbose)

        raise DependencyError(
            f"This script is currently only supported on Linux. "
            f"Detected OS: {current_os}"
        )
