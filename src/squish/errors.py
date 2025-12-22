"""
Error handling for the Mount-SquashFS application.

This module defines custom exceptions and error handling utilities
for the mount-squashfs functionality.
"""

# Functional error handling patterns
from typing import Any, Callable, Generic, TypeVar, Union


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


class ExtractCancelledError(SquashFSError):
    """Exception raised when extract operation is cancelled by user."""

    pass


class XattrError(ExtractError):
    """Exception raised when xattr-related operations fail."""

    pass


T = TypeVar("T")
E = TypeVar("E", bound=Exception)
U = TypeVar("U")  # For mapped results
F = TypeVar("F", bound=Exception)  # For mapped errors


class Result(Generic[T, E]):
    """Functional result type for error handling."""

    def __init__(
        self, success: bool, value: Union[T, None] = None, error: Union[E, None] = None
    ):
        self.success = success
        self.value = value
        self.error = error

    @classmethod
    def ok(cls, value: T) -> "Result[T, E]":
        """Create a successful result."""
        return cls(True, value=value)

    @classmethod
    def err(cls, error: E) -> "Result[T, E]":
        """Create an error result."""
        return cls(False, error=error)

    def is_ok(self) -> bool:
        """Check if result is successful."""
        return self.success

    def is_err(self) -> bool:
        """Check if result is an error."""
        return not self.success

    def unwrap(self) -> T:
        """Get the value or raise the error."""
        if self.success:
            if self.value is None:
                raise ValueError("Result is successful but has no value")
            return self.value
        if self.error is None:
            raise ValueError("Result is an error but has no error value")
        raise self.error

    def unwrap_or(self, default: T) -> T:
        """Get the value or return default."""
        return self.value if self.success and self.value is not None else default

    def map(self, fn: Callable[[T], U]) -> "Result[U, E]":
        """Apply function to successful result."""
        if self.success and self.value is not None:
            return Result.ok(fn(self.value))
        return self  # type: ignore

    def map_err(self, fn: Callable[[E], F]) -> "Result[T, F]":
        """Apply function to error result."""
        if not self.success and self.error is not None:
            return Result.err(fn(self.error))
        return self  # type: ignore


def safe_operation(fn, *args, **kwargs) -> "Result[Any, Exception]":
    """Wrap a function call in a Result for functional error handling."""
    try:
        result = fn(*args, **kwargs)
        return Result.ok(result)
    except Exception as e:
        return Result.err(e)
