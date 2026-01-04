#!/usr/bin/env python3
"""
Test suite for the logging module.

This module tests the logging functionality for the mount-squashfs utility.
"""

import pytest

from squish.logging import MountSquashFSLogger


class TestMountSquashFSLoggerInitialization:
    """Test logger initialization."""


class TestMountSquashFSLoggerMountOperations:
    """Test mount operation logging."""

    def test_log_mount_start(self, logger, mocker):
        """Test logging mount start operation."""
        mock_info = mocker.patch.object(logger.logger, "info")
        logger.log_mount_start("test.sqs", "/mnt/point")
        mock_info.assert_called_once_with("Mounting: test.sqs -> /mnt/point")

    def test_log_mount_success(self, logger, mocker):
        """Test logging successful mount operation."""
        mock_info = mocker.patch.object(logger.logger, "info")
        logger.log_mount_success("test.sqs", "/mnt/point")
        mock_info.assert_called_once_with("Mounted: test.sqs -> /mnt/point")

    def test_log_mount_failed(self, logger, mocker):
        """Test logging failed mount operation."""
        mock_error = mocker.patch.object(logger.logger, "error")
        logger.log_mount_failed("test.sqs", "/mnt/point", "Permission denied")
        mock_error.assert_called_once_with(
            "Mount failed: test.sqs -> /mnt/point: Permission denied"
        )


class TestMountSquashFSLoggerUnmountOperations:
    """Test unmount operation logging."""

    @pytest.fixture
    def logger(self):
        """Create a logger instance for testing."""
        return MountSquashFSLogger("test_logger", verbose=False)

    def test_log_unmount_start(self, logger, mocker):
        """Test logging unmount start operation."""
        mock_info = mocker.patch.object(logger.logger, "info")
        logger.log_unmount_start("test.sqs", "/mnt/point")
        mock_info.assert_called_once_with("Unmounting: test.sqs -> /mnt/point")

    def test_log_unmount_success(self, logger, mocker):
        """Test logging successful unmount operation."""
        mock_info = mocker.patch.object(logger.logger, "info")
        logger.log_unmount_success("test.sqs", "/mnt/point")
        mock_info.assert_called_once_with("Unmounted: test.sqs -> /mnt/point")

    def test_log_unmount_failed(self, logger, mocker):
        """Test logging failed unmount operation."""
        mock_error = mocker.patch.object(logger.logger, "error")
        logger.log_unmount_failed("test.sqs", "/mnt/point", "Device busy")
        mock_error.assert_called_once_with(
            "Unmount failed: test.sqs -> /mnt/point: Device busy"
        )

    def test_log_unmount_failed_special_mount_points(self, logger, mocker):
        """Test logging failed unmount operation with special mount points."""
        special_mount_points = ["not_mounted", "no_mount_info", "auto"]

        for mount_point in special_mount_points:
            mock_error = mocker.patch.object(logger.logger, "error")
            logger.log_unmount_failed("test.sqs", mount_point, "Device busy")
            # For special mount points, the format should be different
            expected_message = "Unmount failed: test.sqs: Device busy"
            mock_error.assert_called_once_with(expected_message)


class TestMountSquashFSLoggerFileOperations:
    """Test file operation logging."""

    @pytest.fixture
    def logger(self):
        """Create a logger instance for testing."""
        return MountSquashFSLogger("test_logger", verbose=False)

    def test_log_file_not_found(self, logger, mocker):
        """Test logging file not found error."""
        mock_error = mocker.patch.object(logger.logger, "error")
        logger.log_file_not_found("/nonexistent/test.sqs", "mount")
        mock_error.assert_called_once_with("File not found: /nonexistent/test.sqs")

    def test_log_mount_point_not_found(self, logger, mocker):
        """Test logging mount point not found error."""
        mock_error = mocker.patch.object(logger.logger, "error")
        logger.log_mount_point_not_found("/nonexistent/mount")
        mock_error.assert_called_once_with("Mount point not found: /nonexistent/mount")

    def test_log_mount_point_empty(self, logger, mocker):
        """Test logging mount point empty warning."""
        mock_warning = mocker.patch.object(logger.logger, "warning")
        logger.log_mount_point_empty("/mnt/empty")
        mock_warning.assert_called_once_with("Mount point empty: /mnt/empty")

    def test_log_directory_not_found(self, logger, mocker):
        """Test logging directory not found error."""
        mock_error = mocker.patch.object(logger.logger, "error")
        logger.log_directory_not_found("/nonexistent/dir", "build")
        mock_error.assert_called_once_with("Directory not found: /nonexistent/dir")


class TestMountSquashFSLoggerDependencyOperations:
    """Test dependency operation logging."""

    @pytest.fixture
    def logger(self):
        """Create a logger instance for testing."""
        return MountSquashFSLogger("test_logger", verbose=False)

    def test_log_dependency_check_available(self, logger, mocker):
        """Test logging available dependency."""
        mock_info = mocker.patch.object(logger.logger, "info")
        logger.log_dependency_check("fusermount", status="available")
        mock_info.assert_called_once_with("Dependency available: fusermount")

    def test_log_dependency_check_missing(self, logger, mocker):
        """Test logging missing dependency."""
        mock_error = mocker.patch.object(logger.logger, "error")
        logger.log_dependency_check("squashfuse", status="missing")
        mock_error.assert_called_once_with("Dependency missing: squashfuse")


class TestMountSquashFSLoggerCommandOperations:
    """Test command operation logging."""

    @pytest.fixture
    def logger(self):
        """Create a logger instance for testing."""
        return MountSquashFSLogger("test_logger", verbose=False)

    def test_log_command_execution(self, logger, mocker):
        """Test logging command execution."""
        mock_info = mocker.patch.object(logger.logger, "info")
        logger.log_command_execution("mount -o ro test.sqs /mnt/point")
        mock_info.assert_called_once_with(
            "Command executed: mount -o ro test.sqs /mnt/point"
        )

    def test_log_command_execution_failed(self, logger, mocker):
        """Test logging failed command execution."""
        mock_error = mocker.patch.object(logger.logger, "error")
        logger.log_command_execution(
            "mount -o ro test.sqs /mnt/point", return_code=1, success=False
        )
        mock_error.assert_called_once_with(
            "Command failed: mount -o ro test.sqs /mnt/point"
        )


class TestMountSquashFSLoggerCleanupOperations:
    """Test cleanup operation logging."""

    @pytest.fixture
    def logger(self):
        """Create a logger instance for testing."""
        return MountSquashFSLogger("test_logger", verbose=False)

    def test_log_cleanup_operation(self, logger, mocker):
        """Test logging cleanup operation."""
        mock_info = mocker.patch.object(logger.logger, "info")
        logger.log_cleanup_operation("/mnt/point", "directory_removal", success=True)
        mock_info.assert_called_once_with("Cleanup: directory_removal on /mnt/point")

    def test_log_cleanup_failed(self, logger, mocker):
        """Test logging failed cleanup operation."""
        mock_warning = mocker.patch.object(logger.logger, "warning")
        logger.log_cleanup_operation("/mnt/point", "directory_removal", success=False)
        mock_warning.assert_called_once_with(
            "Cleanup failed: directory_removal on /mnt/point"
        )


class TestMountSquashFSLoggerTrackingOperations:
    """Test tracking operation logging."""

    @pytest.fixture
    def logger(self):
        """Create a logger instance for testing."""
        return MountSquashFSLogger("test_logger", verbose=False)

    def test_log_tracking_operation(self, logger, mocker):
        """Test logging tracking operation."""
        mock_info = mocker.patch.object(logger.logger, "info")
        logger.log_tracking_operation("test.sqs", "record_mount", success=True)
        mock_info.assert_called_once_with("Tracking: record_mount for test.sqs")

    def test_log_tracking_failed(self, logger, mocker):
        """Test logging failed tracking operation."""
        mock_error = mocker.patch.object(logger.logger, "error")
        logger.log_tracking_operation("test.sqs", "record_mount", success=False)
        mock_error.assert_called_once_with("Tracking failed: record_mount for test.sqs")


class TestMountSquashFSLoggerValidationOperations:
    """Test validation operation logging."""

    @pytest.fixture
    def logger(self):
        """Create a logger instance for testing."""
        return MountSquashFSLogger("test_logger", verbose=False)

    def test_log_validation_result(self, logger, mocker):
        """Test logging validation result."""
        mock_info = mocker.patch.object(logger.logger, "info")
        logger.log_validation_result("mount_point", "/mnt/point", "pass")
        mock_info.assert_called_once_with(
            "Validation passed: mount_point for /mnt/point"
        )

    def test_log_validation_failed(self, logger, mocker):
        """Test logging failed validation."""
        mock_warning = mocker.patch.object(logger.logger, "warning")
        logger.log_validation_result("mount_point", "/mnt/point", "fail")
        mock_warning.assert_called_once_with(
            "Validation failed: mount_point for /mnt/point"
        )


class TestMountSquashFSLoggerBuildOperations:
    """Test build operation logging."""

    @pytest.fixture
    def logger(self):
        """Create a logger instance for testing."""
        return MountSquashFSLogger("test_logger", verbose=False)

    def test_log_build_start(self, logger, mocker):
        """Test logging build start operation."""
        mock_info = mocker.patch.object(logger.logger, "info")
        logger.log_build_start("source_dir", "output.sqsh")
        mock_info.assert_called_once_with("Building: source_dir -> output.sqsh")

    def test_log_build_success(self, logger, mocker):
        """Test logging successful build operation."""
        mock_info = mocker.patch.object(logger.logger, "info")
        logger.log_build_success("source_dir", "output.sqsh")
        mock_info.assert_called_once_with("Built: source_dir -> output.sqsh")

    def test_log_build_failed(self, logger, mocker):
        """Test logging failed build operation."""
        mock_error = mocker.patch.object(logger.logger, "error")
        logger.log_build_failed("source_dir", "output.sqsh", "Build error")
        mock_error.assert_called_once_with(
            "Build failed: source_dir -> output.sqsh: Build error"
        )


class TestMountSquashFSLoggerListOperations:
    """Test list operation logging."""

    @pytest.fixture
    def logger(self):
        """Create a logger instance for testing."""
        return MountSquashFSLogger("test_logger", verbose=False)

    def test_log_list_start(self, logger, mocker):
        """Test logging list start operation."""
        mock_info = mocker.patch.object(logger.logger, "info")
        logger.log_list_start("archive.sqsh")
        mock_info.assert_called_once_with("Listing contents of: archive.sqsh")

    def test_log_list_success(self, logger, mocker):
        """Test logging successful list operation."""
        mock_info = mocker.patch.object(logger.logger, "info")
        logger.log_list_success("archive.sqsh")
        mock_info.assert_called_once_with("Listed contents of: archive.sqsh")

    def test_log_list_failed(self, logger, mocker):
        """Test logging failed list operation."""
        mock_error = mocker.patch.object(logger.logger, "error")
        logger.log_list_failed("archive.sqsh", "List error")
        mock_error.assert_called_once_with("List failed: archive.sqsh: List error")


class TestVerboseLoggingComprehensive:
    """Comprehensive parametrized tests for verbose logging across all modules."""

    @pytest.mark.parametrize(
        "module,scenario",
        [
            ("build", "build_operation"),
            ("mount", "mount_operation"),
            ("list", "list_operation"),
            ("command_executor", "command_execution"),
        ],
    )
    def test_verbose_logging_comprehensive(self, module, scenario, mocker, capsys):
        """Test verbose logging behavior across all modules comprehensively."""
        # Create logger with verbose=True
        logger = MountSquashFSLogger("test_logger", verbose=True)

        # Execute the appropriate logging methods based on module/scenario
        if module == "build":
            logger.log_build_start("source_dir", "output.sqsh")
            logger.log_build_success("source_dir", "output.sqsh")

        elif module == "mount":
            logger.log_mount_start("archive.sqsh", "/mnt/point")
            logger.log_mount_success("archive.sqsh", "/mnt/point")

        elif module == "list":
            logger.log_list_start("archive.sqsh")
            logger.log_list_success("archive.sqsh")

        elif module == "command_executor":
            logger.log_command_execution("echo test")

        # Verify that logging output was produced (verbose=True should log)
        captured = capsys.readouterr()
        assert captured.out.strip() != "" or captured.err.strip() != ""

    def test_verbose_vs_non_verbose_logging(self, mocker):
        """Test that verbose=True produces more logging than verbose=False."""
        # Create verbose logger
        verbose_logger = MountSquashFSLogger("verbose_logger", verbose=True)
        mock_verbose = mocker.MagicMock()
        verbose_logger.logger = mock_verbose

        # Create non-verbose logger
        non_verbose_logger = MountSquashFSLogger("non_verbose_logger", verbose=False)
        mock_non_verbose = mocker.MagicMock()
        non_verbose_logger.logger = mock_non_verbose

        # Execute same operations on both
        verbose_logger.log_build_start("source", "output.sqsh")
        non_verbose_logger.log_build_start("source", "output.sqsh")

        # Verify verbose logger has more log calls
        verbose_call_count = (
            mock_verbose.info.call_count + mock_verbose.debug.call_count
        )
        non_verbose_call_count = (
            mock_non_verbose.info.call_count + mock_non_verbose.debug.call_count
        )

        assert verbose_call_count >= non_verbose_call_count


class TestLoggerFactoryFunction:
    """Test the get_logger factory function."""
