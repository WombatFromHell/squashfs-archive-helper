"""
Dependency checking logic for the SquashFS Archive Helper.

This module contains functionality for checking system dependencies
and command availability for various operations.
"""

import platform
from typing import Optional

from .command_executor import ICommandExecutor
from .config import SquishFSConfig
from .errors import DependencyError
from .logging import get_logger


def _check_single_command(cmd: str, executor: ICommandExecutor) -> bool:
    """Pure function to check a single command."""
    try:
        executor.execute(
            ["which", cmd],
            check=True,
            capture_output=True,
        )
        return True
    except Exception:
        return False


def _ensure_config_and_executor(config, executor):
    """Ensure config and executor are initialized."""
    if config is None:
        from .config import SquishFSConfig

        config = SquishFSConfig()

    if executor is None:
        from .command_executor import CommandExecutor

        executor = CommandExecutor(config)

    return config, executor


def check_commands(
    commands: list[str],
    config: Optional[SquishFSConfig] = None,
    executor: Optional[ICommandExecutor] = None,
) -> None:
    """Check if required commands are available using functional pattern."""
    config, executor = _ensure_config_and_executor(config, executor)
    logger = get_logger(config.verbose)

    # Use functional approach: find first missing command lazily
    missing_cmd = next(
        (cmd for cmd in commands if not _check_single_command(cmd, executor)),
        None,
    )

    if missing_cmd:
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
    config: Optional[SquishFSConfig] = None, executor: Optional[ICommandExecutor] = None
) -> None:
    """Check for Linux-specific dependencies."""
    check_commands(["squashfuse", "fusermount", "sha256sum"], config, executor)


def check_build_dependencies(
    config: Optional[SquishFSConfig] = None, executor: Optional[ICommandExecutor] = None
) -> None:
    """Check for build-specific dependencies."""
    check_commands(["mksquashfs", "unsquashfs", "nproc"], config, executor)


def check_all_dependencies(
    config: Optional[SquishFSConfig] = None, logger=None
) -> None:
    """Check system dependencies."""
    current_os = platform.system().lower()
    if current_os == "linux":
        check_linux_dependencies(config)  # Remove logger parameter
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
