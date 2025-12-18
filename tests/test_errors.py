"""
Test cases for the errors module.

This module tests the custom exception classes.
"""

from squish.errors import (
    CommandExecutionError,
    ConfigError,
    DependencyError,
    MountError,
    MountPointError,
    SquashFSError,
    UnmountError,
)


class TestErrorHierarchy:
    """Test the error class hierarchy."""

    def test_squashfs_error_base(self):
        """Test that SquashFSError is the base class."""
        error = SquashFSError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_dependency_error_inheritance(self):
        """Test that DependencyError inherits from SquashFSError."""
        error = DependencyError("dependency missing")
        assert isinstance(error, SquashFSError)
        assert isinstance(error, Exception)
        assert str(error) == "dependency missing"

    def test_mount_error_inheritance(self):
        """Test that MountError inherits from SquashFSError."""
        error = MountError("mount failed")
        assert isinstance(error, SquashFSError)
        assert str(error) == "mount failed"

    def test_unmount_error_inheritance(self):
        """Test that UnmountError inherits from SquashFSError."""
        error = UnmountError("unmount failed")
        assert isinstance(error, SquashFSError)
        assert str(error) == "unmount failed"

    def test_config_error_inheritance(self):
        """Test that ConfigError inherits from SquashFSError."""
        error = ConfigError("invalid config")
        assert isinstance(error, SquashFSError)
        assert str(error) == "invalid config"

    def test_mount_point_error_inheritance(self):
        """Test that MountPointError inherits from SquashFSError."""
        error = MountPointError("invalid mount point")
        assert isinstance(error, SquashFSError)
        assert str(error) == "invalid mount point"


class TestCommandExecutionError:
    """Test the CommandExecutionError class."""

    def test_command_execution_error_attributes(self):
        """Test that CommandExecutionError has the correct attributes."""
        error = CommandExecutionError("test_command", 1, "test message")
        assert error.command == "test_command"
        assert error.return_code == 1
        assert error.message == "test message"
        assert (
            str(error)
            == "Command 'test_command' failed with return code 1: test message"
        )

    def test_command_execution_error_default_message(self):
        """Test CommandExecutionError with default message."""
        error = CommandExecutionError("test_command", 1)
        assert error.command == "test_command"
        assert error.return_code == 1
        assert error.message == ""
        assert str(error) == "Command 'test_command' failed with return code 1: "

    def test_command_execution_error_inheritance(self):
        """Test that CommandExecutionError inherits from SquashFSError."""
        error = CommandExecutionError("test", 1, "message")
        assert isinstance(error, SquashFSError)
        assert isinstance(error, Exception)
