"""
Test cases for the list module.

This module tests the list functionality separately.
"""

import tempfile
from subprocess import CalledProcessError

import pytest

from squish.config import SquishFSConfig
from squish.errors import ListError, UnsquashfsCommandExecutionError
from squish.list import ListManager


class TestListManagerInitialization:
    """Test ListManager initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        manager = ListManager()
        assert manager.config.mount_base == "mounts"
        assert manager.config.temp_dir == "/tmp"
        assert manager.config.auto_cleanup is True

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = SquishFSConfig(
            mount_base="custom",
            temp_dir="/tmp",  # Use existing directory
            auto_cleanup=False,
            verbose=True,
        )
        manager = ListManager(config)
        assert manager.config == config


class TestListSquashFS:
    """Test list squashfs functionality."""

    @pytest.fixture
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        return ListManager()

    def test_list_squashfs_success(self, mocker, manager):
        """Test successful list operation."""
        with tempfile.NamedTemporaryFile(suffix=".sqsh") as archive_file:
            mock_run = mocker.patch("squish.list.subprocess.run")

            # Mock successful unsquashfs output
            def mock_run_side_effect(cmd, **kwargs):
                if cmd[0] in ["which", "mksquashfs", "unsquashfs", "nproc"]:
                    # Dependency checks - return successful mocks
                    return mocker.MagicMock(returncode=0, check=lambda: True)
                elif cmd[0] == "unsquashfs" and "-llc" in cmd:
                    # Actual list command
                    mock_result = mocker.MagicMock()
                    mock_result.stdout = "drwxr-xr-x root/root 0 2023-01-01 00:00 dir/\n-rw-r--r-- root/root 100 2023-01-01 00:00 file.txt\n"
                    mock_result.returncode = 0
                    mock_result.check = lambda: True
                    return mock_result
                return mocker.MagicMock(returncode=0, check=lambda: True)

            mock_run.side_effect = mock_run_side_effect

            manager.list_squashfs(archive_file.name)

            # Verify unsquashfs was called with correct arguments
            # Check that the last call was the actual list command
            last_call = mock_run.call_args_list[-1]
            call_args = last_call[0][0]
            assert call_args[0] == "unsquashfs"
            assert "-llc" in call_args
            assert archive_file.name in call_args

    def test_list_squashfs_archive_not_found(self, manager):
        """Test list operation with non-existent archive."""
        with pytest.raises(ListError, match="Archive not found"):
            manager.list_squashfs("/nonexistent/archive.sqsh")


class TestListCommandExecution:
    """Test list command execution errors."""

    def test_unsquashfs_command_execution_error(self, mocker):
        """Test UnsquashfsCommandExecutionError."""
        config = SquishFSConfig()
        manager = ListManager(config)

        # Mock subprocess to fail
        mock_run = mocker.patch("squish.list.subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "unsquashfs", "Test error")

        with tempfile.NamedTemporaryFile(suffix=".sqsh") as archive_file:
            with pytest.raises(UnsquashfsCommandExecutionError) as exc_info:
                manager._execute_unsquashfs_list(archive_file.name)

            assert exc_info.value.command == "unsquashfs"
            assert exc_info.value.return_code == 1
            assert "Failed to list archive contents" in exc_info.value.message
            assert isinstance(exc_info.value, ListError)


class TestListDependencyChecking:
    """Test list dependency checking functionality."""

    def test_check_build_dependencies_success(self, mocker):
        """Test successful build dependency checking for list."""
        config = SquishFSConfig()
        manager = ListManager(config)

        # Mock successful subprocess.run for unsquashfs check
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock()

        # This should not raise an exception
        manager._check_build_dependencies()

    def test_check_build_dependencies_failure(self, mocker):
        """Test failed build dependency checking for list."""
        from squish.errors import DependencyError

        config = SquishFSConfig()
        manager = ListManager(config)

        # Mock failed subprocess.run for "which unsquashfs"
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "which")

        with tempfile.NamedTemporaryFile(suffix=".sqsh") as archive_file:
            with pytest.raises(DependencyError, match="unsquashfs is not installed"):
                manager.list_squashfs(archive_file.name)
