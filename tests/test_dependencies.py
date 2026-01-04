"""
Test cases for the dependencies module.

This module tests the dependency checking functionality separately.
"""

from subprocess import CalledProcessError

import pytest

from squish.command_executor import MockCommandExecutor
from squish.config import SquishFSConfig
from squish.dependencies import (
    check_all_dependencies,
    check_build_dependencies,
    check_commands,
    check_linux_dependencies,
)
from squish.errors import DependencyError


class TestDependencyChecking:
    """Test dependency checking functions."""

    def test_check_commands_success(self, mocker):
        """Test successful command checking."""
        config = SquishFSConfig()
        executor = MockCommandExecutor()
        executor.set_available_commands(["ls", "echo"])

        # This should not raise an exception
        check_commands(["ls", "echo"], config, executor)

    def test_check_commands_failure(self, mocker):
        """Test failed command checking."""
        config = SquishFSConfig()
        executor = MockCommandExecutor()

        with pytest.raises(DependencyError, match="is not installed or not in PATH"):
            check_commands(["nonexistent_command"], config, executor)

    def test_check_linux_dependencies(self, mocker):
        """Test Linux dependency checking."""
        config = SquishFSConfig()
        executor = MockCommandExecutor()
        executor.set_available_commands(["squashfuse", "fusermount", "sha256sum"])

        # This should not raise an exception
        check_linux_dependencies(config, executor)

    def test_check_build_dependencies(self, mocker):
        """Test build dependency checking."""
        config = SquishFSConfig()
        executor = MockCommandExecutor()
        executor.set_available_commands(["mksquashfs", "unsquashfs", "nproc"])

        # This should not raise an exception
        check_build_dependencies(config, executor)

    def test_check_all_dependencies_linux_success(self, mocker):
        """Test all dependency checking for Linux."""
        config = SquishFSConfig()
        executor = MockCommandExecutor()
        executor.set_available_commands(["squashfuse", "fusermount", "sha256sum"])

        # Mock platform check
        mock_platform = mocker.patch("platform.system")
        mock_platform.return_value = "Linux"

        # This should not raise an exception
        check_all_dependencies(config, executor)

    def test_check_all_dependencies_non_linux_error(self, mocker):
        """Test all dependency checking for non-Linux OS."""
        config = SquishFSConfig()
        executor = MockCommandExecutor()

        # Mock platform check
        mock_platform = mocker.patch("platform.system")
        mock_platform.return_value = "Windows"

        with pytest.raises(DependencyError, match="currently only supported on Linux"):
            check_all_dependencies(config, executor)


class TestDependencyCheckingCoverageGaps:
    """Test coverage gap scenarios for dependency checking functions."""

    def test_check_commands_defaults(self, mocker):
        """Test check_commands with default parameters (None)."""
        # Just test that calling with None parameters doesn't crash
        # Mock imports and subprocess run
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock()

        # Call without config and logger (should use defaults)
        check_commands(["ls"])

        # If we reached this point, the function handled the default case properly

    def test_check_commands_defaults_with_which_failure(self, mocker):
        """Test check_commands with default parameters when 'which' fails."""
        # Mock subprocess run to fail
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "which")

        # Call without config and logger (should use defaults)
        with pytest.raises(DependencyError, match="is not installed or not in PATH"):
            check_commands(["nonexistent_command"])

    def test_check_all_dependencies_non_linux_error_defaults(self, mocker):
        """Test all dependency checking for non-Linux OS with default logger."""
        # Mock platform check
        mock_platform = mocker.patch("platform.system")
        mock_platform.return_value = "Windows"

        with pytest.raises(DependencyError, match="currently only supported on Linux"):
            check_all_dependencies()  # No config or logger provided

    def test_check_all_dependencies_linux_calls_check_linux_dependencies_correctly(
        self, mocker
    ):
        """Test that check_all_dependencies calls check_linux_dependencies with correct parameters."""
        # Mock platform check to return Linux
        mock_platform = mocker.patch("platform.system")
        mock_platform.return_value = "Linux"

        # Mock check_linux_dependencies to verify it's called correctly
        mock_check_linux = mocker.patch("squish.dependencies.check_linux_dependencies")

        # Create a test config
        from squish.config import SquishFSConfig

        config = SquishFSConfig()

        # Call check_all_dependencies
        check_all_dependencies(config)

        # Verify check_linux_dependencies was called with config only (no logger parameter)
        mock_check_linux.assert_called_once_with(config)
