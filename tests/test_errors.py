"""
Test cases for the errors module.

This module tests the custom exception classes.
"""

from squish.errors import (
    BuildCancelledError,
    BuildError,
    CommandExecutionError,
    ConfigError,
    DependencyError,
    ErrorHandler,
    ExtractError,
    MountError,
    MountPointError,
    OperationResult,
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
        result = Result.err(None)
        try:
            result.unwrap()
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert str(e) == "Result is an error but has no error value"

    def test_result_with_none_error(self):
        """Test result with None error."""
        result = Result.err(None)
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


class TestOperationResult:
    """Test the OperationResult class."""

    def test_operation_result_success(self):
        """Test creating a successful operation result."""
        result = OperationResult.success()
        assert result.is_success()
        assert not result.is_failure()
        assert result.error is None
        assert result.error_type is None
        assert not result.can_retry
        assert result.recovery_suggestion is None

    def test_operation_result_failure(self):
        """Test creating a failed operation result."""
        error = ValueError("test error")
        result = OperationResult.failure(
            error,
            error_type="validation_error",
            can_retry=True,
            recovery_suggestion="Check input parameters",
        )
        assert result.is_failure()
        assert not result.is_success()
        assert result.error == error
        assert result.error_type == "validation_error"
        assert result.can_retry
        assert result.recovery_suggestion == "Check input parameters"

    def test_operation_result_get_error_message(self):
        """Test getting error message from operation result."""
        error = RuntimeError("operation failed")
        result = OperationResult.failure(error)
        assert result.get_error_message() == "operation failed"

    def test_operation_result_get_error_message_no_error(self):
        """Test getting error message when no error is present."""
        result = OperationResult.success()
        assert result.get_error_message() == "Unknown error"

    def test_operation_result_get_error_details(self):
        """Test getting detailed error information."""
        error = IOError("file not found")
        result = OperationResult.failure(
            error,
            error_type="file_system_error",
            can_retry=True,
            recovery_suggestion="Verify file paths",
        )
        details = result.get_error_details()
        assert details["error_type"] == "file_system_error"
        assert details["error_message"] == "file not found"
        assert details["can_retry"] is True
        assert details["recovery_suggestion"] == "Verify file paths"


class TestErrorHandler:
    """Test the ErrorHandler class."""

    def test_error_handler_handle_error(self, mocker):
        """Test handling an error with classification and recovery."""
        mock_logger = mocker.MagicMock()
        handler = ErrorHandler(mock_logger)

        error = DependencyError("missing dependency")
        result = handler.handle_error(error, "build operation")

        assert result.is_failure()
        assert result.error == error
        assert result.error_type == "dependency_error"
        assert result.can_retry
        assert (
            result.recovery_suggestion
            == "Please install the required dependency: missing dependency"
        )

        # Verify logging calls
        mock_logger.log_error.assert_called()

    def test_error_handler_classify_errors(self, mocker):
        """Test error classification for different error types."""
        mock_logger = mocker.MagicMock()
        handler = ErrorHandler(mock_logger)

        # Test various error types
        test_cases = [
            (DependencyError("missing"), "dependency_error"),
            (CommandExecutionError("cmd", 1), "command_execution_error"),
            (BuildError("build failed"), "operation_error"),
            (ExtractError("extract failed"), "operation_error"),
            (BuildCancelledError("cancelled"), "cancellation_error"),
            (FileNotFoundError("not found"), "file_system_error"),
            (ValueError("invalid"), "validation_error"),
            (RuntimeError("unknown"), "unknown_error"),
        ]

        for error, expected_type in test_cases:
            result = handler._classify_error(error)
            assert result == expected_type

    def test_error_handler_get_recovery_info(self, mocker):
        """Test getting recovery information for different error types."""
        mock_logger = mocker.MagicMock()
        handler = ErrorHandler(mock_logger)

        # Test various error types and their recovery info
        test_cases = [
            (
                DependencyError("missing"),
                (True, "Please install the required dependency: missing"),
            ),
            (
                CommandExecutionError("cmd", 1),
                (False, "Check command execution permissions and try again"),
            ),
            (
                BuildError("build failed"),
                (True, "Check source files and try the operation again"),
            ),
            (
                MountError("mount failed"),
                (False, "Check mount point permissions and filesystem state"),
            ),
            (
                FileNotFoundError("not found"),
                (True, "Verify file paths and permissions"),
            ),
            (
                ValueError("invalid"),
                (False, "Check input parameters and configuration"),
            ),
            (RuntimeError("unknown"), (False, None)),
        ]

        for error, expected_recovery in test_cases:
            result = handler._get_recovery_info(error, "test context")
            assert result == expected_recovery

    def test_error_handler_handle_success(self, mocker):
        """Test handling a successful operation."""
        mock_logger = mocker.MagicMock()
        handler = ErrorHandler(mock_logger)

        result = handler.handle_success("test operation")
        assert result.is_success()

        # Verify success logging
        mock_logger.log_success.assert_called_with(
            "test operation completed successfully"
        )


class TestErrorCoverageGaps:
    """Test specific coverage gaps in the errors module."""

    def test_operation_result_edge_cases(self):
        """Test OperationResult edge cases."""
        # Test with None error
        result = OperationResult.failure(None, "unknown_error")  # type: ignore
        assert result.is_failure()
        assert result.error is None
        assert result.get_error_message() == "Unknown error"

        # Test with empty recovery suggestion
        result = OperationResult.failure(
            ValueError("test"), "validation_error", recovery_suggestion=""
        )
        details = result.get_error_details()
        assert details["recovery_suggestion"] == ""

    def test_error_handler_edge_cases(self, mocker):
        """Test ErrorHandler edge cases."""
        mock_logger = mocker.MagicMock()
        handler = ErrorHandler(mock_logger)

        # Test with None error
        result = handler.handle_error(None, "test context")  # type: ignore
        assert result.is_failure()
        assert result.error is None
        assert result.get_error_message() == "Unknown error"

    def test_result_comprehensive_coverage(self):
        """Test comprehensive Result class coverage."""
        # Test all Result methods
        success_result = Result.ok(42)
        assert success_result.is_ok()
        assert not success_result.is_err()
        assert success_result.unwrap() == 42
        assert success_result.unwrap_or(0) == 42

        error_result = Result.err(ValueError("test"))
        assert error_result.is_err()
        assert not error_result.is_ok()

        # Test mapping functions
        mapped_success = success_result.map(lambda x: x * 2)
        assert mapped_success.unwrap() == 84

        mapped_error = error_result.map_err(lambda e: RuntimeError(str(e)))
        assert mapped_error.is_err()
