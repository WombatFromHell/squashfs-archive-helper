"""
Test cases for the dependencies module.

This module tests the dependency checking functionality separately.
"""

from subprocess import CalledProcessError

import pytest

from squish.config import SquishFSConfig
from squish.dependencies import (
    check_all_dependencies,
    check_build_dependencies,
    check_commands,
    check_linux_dependencies,
)
from squish.errors import DependencyError
from squish.logging import get_logger


class TestDependencyChecking:
    """Test dependency checking functions."""

    def test_check_commands_success(self, mocker):
        """Test successful command checking."""
        config = SquishFSConfig()
        logger = get_logger(config.verbose)

        # Mock successful subprocess run
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock()

        # This should not raise an exception
        check_commands(["ls", "echo"], config, logger)

    def test_check_commands_failure(self, mocker):
        """Test failed command checking."""
        config = SquishFSConfig()
        logger = get_logger(config.verbose)

        # Mock failed subprocess run
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "which")

        with pytest.raises(DependencyError, match="is not installed or not in PATH"):
            check_commands(["nonexistent_command"], config, logger)

    def test_check_linux_dependencies(self, mocker):
        """Test Linux dependency checking."""
        config = SquishFSConfig()
        logger = get_logger(config.verbose)

        # Mock successful subprocess run
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock()

        # This should not raise an exception
        check_linux_dependencies(config, logger)

    def test_check_build_dependencies(self, mocker):
        """Test build dependency checking."""
        config = SquishFSConfig()
        logger = get_logger(config.verbose)

        # Mock successful subprocess run
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock()

        # This should not raise an exception
        check_build_dependencies(config, logger)

    def test_check_all_dependencies_linux_success(self, mocker):
        """Test all dependency checking for Linux."""
        config = SquishFSConfig()
        logger = get_logger(config.verbose)

        # Mock successful subprocess run and platform check
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock()
        mock_platform = mocker.patch("platform.system")
        mock_platform.return_value = "Linux"

        # This should not raise an exception
        check_all_dependencies(config, logger)

    def test_check_all_dependencies_non_linux_error(self, mocker):
        """Test all dependency checking for non-Linux OS."""
        config = SquishFSConfig()
        logger = get_logger(config.verbose)

        # Mock platform check
        mock_platform = mocker.patch("platform.system")
        mock_platform.return_value = "Windows"

        with pytest.raises(DependencyError, match="currently only supported on Linux"):
            check_all_dependencies(config, logger)


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
