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
    Result,
    SquashFSError,
    UnmountError,
    safe_operation,
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


class TestResultClass:
    """Test the Result class for functional error handling."""

    def test_result_ok_creation(self):
        """Test creating a successful result."""
        result = Result.ok(42)
        assert result.is_ok()
        assert not result.is_err()
        assert result.unwrap() == 42

    def test_result_err_creation(self):
        """Test creating an error result."""
        error = ValueError("test error")
        result = Result.err(error)
        assert result.is_err()
        assert not result.is_ok()

    def test_result_unwrap_success(self):
        """Test unwrap on successful result."""
        result = Result.ok("success")
        assert result.unwrap() == "success"

    def test_result_unwrap_error(self):
        """Test unwrap on error result."""
        error = RuntimeError("test error")
        result = Result.err(error)
        try:
            result.unwrap()
            assert False, "Should have raised an exception"
        except RuntimeError as e:
            assert str(e) == "test error"

    def test_result_unwrap_or_success(self):
        """Test unwrap_or on successful result."""
        result = Result.ok(42)
        assert result.unwrap_or(0) == 42

    def test_result_unwrap_or_error(self):
        """Test unwrap_or on error result."""
        result = Result.err(ValueError("error"))
        assert result.unwrap_or(0) == 0

    def test_result_map_success(self):
        """Test map on successful result."""
        result = Result.ok(5)
        mapped = result.map(lambda x: x * 2)
        assert mapped.unwrap() == 10

    def test_result_map_error(self):
        """Test map on error result."""
        result = Result.err(ValueError("error"))
        mapped = result.map(lambda x: x * 2)
        assert mapped.is_err()

    def test_result_map_err_success(self):
        """Test map_err on error result."""
        result = Result.err(ValueError("original"))
        mapped = result.map_err(lambda e: RuntimeError(str(e) + " modified"))
        assert mapped.is_err()

    def test_result_map_err_on_success(self):
        """Test map_err on successful result."""
        result = Result.ok(42)
        mapped = result.map_err(lambda e: RuntimeError(str(e) + " modified"))
        assert mapped.is_ok()
        assert mapped.unwrap() == 42

    def test_result_with_none_value(self):
        """Test result with None value."""
        result = Result.ok(None)
        assert result.is_ok()
        assert result.unwrap_or("default") == "default"

    def test_result_unwrap_none_value_error(self):
        """Test unwrap with None value raises ValueError."""
        result = Result.ok(None)
        try:
            result.unwrap()
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert str(e) == "Result is successful but has no value"

    def test_result_unwrap_none_error_error(self):
        """Test unwrap with None error raises ValueError."""
        result = Result.err(None)  # type: ignore
        try:
            result.unwrap()
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert str(e) == "Result is an error but has no error value"

    def test_result_with_none_error(self):
        """Test result with None error."""
        result = Result.err(None)  # type: ignore
        assert result.is_err()

    def test_safe_operation_success(self):
        """Test safe_operation with successful function."""

        def success_func():
            return "success"

        result = safe_operation(success_func)
        assert result.is_ok()
        assert result.unwrap() == "success"

    def test_safe_operation_failure(self):
        """Test safe_operation with failing function."""

        def fail_func():
            raise ValueError("test error")

        result = safe_operation(fail_func)
        assert result.is_err()
        try:
            result.unwrap()
            assert False, "Should have raised an exception"
        except ValueError as e:
            assert str(e) == "test error"

    def test_result_chaining(self):
        """Test chaining multiple result operations."""
        result = Result.ok(5)
        transformed = result.map(lambda x: x * 2).map(lambda x: str(x))
        assert transformed.unwrap() == "10"

    def test_result_error_chaining(self):
        """Test chaining with error handling."""
        result = Result.err(ValueError("original"))
        transformed = result.map_err(lambda e: RuntimeError(str(e) + " wrapped"))
        assert transformed.is_err()
