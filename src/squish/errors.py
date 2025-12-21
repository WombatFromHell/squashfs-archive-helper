"""
Error handling for the Mount-SquashFS application.

This module defines custom exceptions and error handling utilities
for the mount-squashfs functionality.
"""


class SquashFSError(Exception):
    """Base exception for all mount-squashfs related errors."""

    pass


class DependencyError(SquashFSError):
    """Exception raised when required dependencies are missing."""

    pass


class MountError(SquashFSError):
    """Exception raised when mounting operations fail."""

    pass


class UnmountError(SquashFSError):
    """Exception raised when unmounting operations fail."""

    pass


class ConfigError(SquashFSError):
    """Exception raised when configuration is invalid."""

    pass


class MountPointError(SquashFSError):
    """Exception raised when mount point validation fails."""

    pass


class CommandExecutionError(SquashFSError):
    """Exception raised when command execution fails."""

    def __init__(self, command: str, return_code: int, message: str = ""):
        self.command = command
        self.return_code = return_code
        self.message = message
        super().__init__(
            f"Command '{command}' failed with return code {return_code}: {message}"
        )


class MountCommandExecutionError(CommandExecutionError, MountError):
    """Exception raised when mount command execution fails."""

    pass


class UnmountCommandExecutionError(CommandExecutionError, UnmountError):
    """Exception raised when unmount command execution fails."""

    pass


class ChecksumError(SquashFSError):
    """Exception raised when checksum verification fails."""

    pass


class ChecksumCommandExecutionError(CommandExecutionError, ChecksumError):
    """Exception raised when checksum command execution fails."""

    pass


class BuildError(SquashFSError):
    """Exception raised when build operations fail."""

    pass


class ListError(SquashFSError):
    """Exception raised when list operations fail."""

    pass


class ExtractError(SquashFSError):
    """Exception raised when extract operations fail."""

    pass


class MksquashfsCommandExecutionError(CommandExecutionError, BuildError):
    """Exception raised when mksquashfs command execution fails."""

    pass


class UnsquashfsCommandExecutionError(CommandExecutionError, ListError):
    """Exception raised when unsquashfs command execution fails."""

    pass


class UnsquashfsExtractCommandExecutionError(CommandExecutionError, ExtractError):
    """Exception raised when unsquashfs extract command execution fails."""

    pass
