"""
Test cases for the core module.

This module tests the core mounting/unmounting functionality.
Note: Many tests are mocked since they require actual squashfuse/fusermount.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mount_squashfs.config import SquashFSConfig
from mount_squashfs.core import SquashFSManager
from mount_squashfs.errors import (
    DependencyError,
    MountCommandExecutionError,
    MountError,
    MountPointError,
    UnmountCommandExecutionError,
    UnmountError,
)


class TestSquashFSManagerInitialization:
    """Test SquashFSManager initialization and dependency checking."""

    @patch("mount_squashfs.core.subprocess.run")
    def test_init_with_default_config(self, mock_subprocess):
        """Test initialization with default configuration."""
        # Mock successful dependency check
        mock_subprocess.return_value = MagicMock()

        manager = SquashFSManager()
        assert manager.config.mount_base == "mounts"
        assert manager.config.temp_dir == "/tmp"
        assert manager.config.auto_cleanup is True

    @patch("mount_squashfs.core.subprocess.run")
    def test_init_with_custom_config(self, mock_subprocess):
        """Test initialization with custom configuration."""
        # Mock successful dependency check
        mock_subprocess.return_value = MagicMock()

        config = SquashFSConfig(
            mount_base="custom",
            temp_dir="/tmp",  # Use existing directory
            auto_cleanup=False,
            verbose=True,
        )
        manager = SquashFSManager(config)
        assert manager.config == config

    @patch("mount_squashfs.core.platform.system")
    def test_non_linux_os_error(self, mock_platform):
        """Test that non-Linux OS raises DependencyError."""
        mock_platform.return_value = "Windows"

        with pytest.raises(DependencyError, match="currently only supported on Linux"):
            SquashFSManager()

    @patch("mount_squashfs.core.subprocess.run")
    def test_missing_dependency_error(self, mock_subprocess):
        """Test that missing dependencies raise DependencyError."""
        # Mock failed dependency check with CalledProcessError
        from subprocess import CalledProcessError

        mock_subprocess.side_effect = CalledProcessError(1, "which")

        with pytest.raises(DependencyError, match="is not installed or not in PATH"):
            SquashFSManager()


class TestMountPointValidation:
    """Test mount point validation logic."""

    @pytest.fixture
    def manager(self):
        """Create a manager with mocked dependencies."""
        with patch("mount_squashfs.core.subprocess.run"):
            return SquashFSManager()

    def test_valid_mount_point(self, manager):
        """Test that valid mount points pass validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "test"
            mount_point.mkdir()

            # Create a dummy file to make it non-empty
            (mount_point / "dummy").touch()

            # Should not raise an exception
            assert manager._is_mount_point_valid(mount_point) is True

    def test_nonexistent_mount_point(self, manager):
        """Test that nonexistent mount points raise MountPointError."""
        mount_point = Path("/nonexistent/mount/point")

        with pytest.raises(MountPointError, match="Mount point does not exist"):
            manager._is_mount_point_valid(mount_point)

    def test_empty_mount_point(self, manager):
        """Test that empty mount points raise MountPointError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "empty"
            mount_point.mkdir()

            with pytest.raises(MountPointError, match="Mount point is empty"):
                manager._is_mount_point_valid(mount_point)


class TestMountDetermination:
    """Test mount point determination logic."""

    @pytest.fixture
    def manager(self):
        """Create a manager with mocked dependencies."""
        with patch("mount_squashfs.core.subprocess.run"):
            return SquashFSManager()

    def test_default_mount_point(self, manager):
        """Test default mount point determination."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory for testing
            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                mount_point = manager._determine_mount_point("test.sqs")
                expected = Path(temp_dir) / "mounts" / "test"
                assert mount_point == expected
            finally:
                os.chdir(original_cwd)

    def test_custom_mount_point(self, manager):
        """Test custom mount point determination."""
        mount_point = manager._determine_mount_point("test.sqs", "/custom/mount")
        assert mount_point == Path("/custom/mount")


class TestMountUnmountWorkflow:
    """Test mount/unmount workflow with mocked subprocess calls."""

    @pytest.fixture
    def manager(self):
        """Create a manager with mocked dependencies."""
        with patch("mount_squashfs.core.subprocess.run"):
            return SquashFSManager()

    @patch("mount_squashfs.core.subprocess.run")
    def test_mount_workflow(self, mock_subprocess, manager):
        """Test the complete mount workflow."""
        # Mock successful squashfuse call
        mock_subprocess.return_value = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # Should not be mounted initially
            assert not manager.tracker.is_mounted(file_path)

            # Mock os.makedirs to avoid creating actual directories
            with patch("mount_squashfs.core.os.makedirs"):
                # Mock the mount operation
                manager.mount(file_path)

                # Should be mounted now
                assert manager.tracker.is_mounted(file_path)

                # Get mount info
                mount_info = manager.tracker.get_mount_info(file_path)
                assert mount_info is not None
                assert mount_info[0] == str(Path(file_path).resolve())

    @patch("mount_squashfs.core.subprocess.run")
    def test_unmount_workflow(self, mock_subprocess, manager):
        """Test the complete unmount workflow."""
        # Mock successful fusermount call
        mock_subprocess.return_value = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # First, mock a mount operation
            with patch("mount_squashfs.core.os.makedirs"):
                manager.mount(file_path)
                assert manager.tracker.is_mounted(file_path)

            # Get the mount point that was recorded
            mount_info = manager.tracker.get_mount_info(file_path)
            mount_point = Path(mount_info[1])

            # Create the mount directory and a dummy file to make it non-empty
            mount_point.mkdir(parents=True, exist_ok=True)
            (mount_point / "dummy").touch()

            # Now test unmount
            with patch("mount_squashfs.core.shutil.rmtree"):
                with patch("mount_squashfs.core.os.rmdir"):
                    manager.unmount(file_path)

                    # Should not be mounted anymore
                    assert not manager.tracker.is_mounted(file_path)

                    # Clean up the mount directory we created
                    if mount_point.exists():
                        import shutil

                        shutil.rmtree(mount_point, ignore_errors=True)

    def test_double_mount_error(self, manager):
        """Test that mounting twice raises MountError."""
        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # Mock first mount
            with patch("mount_squashfs.core.subprocess.run"):
                with patch("mount_squashfs.core.os.makedirs"):
                    manager.mount(file_path)

            # Second mount should fail
            with pytest.raises(MountError, match="already mounted"):
                with patch("mount_squashfs.core.subprocess.run"):
                    with patch("mount_squashfs.core.os.makedirs"):
                        manager.mount(file_path)

    def test_unmount_not_mounted_error(self, manager):
        """Test that unmounting not mounted file raises UnmountError."""
        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # Should raise error since file is not mounted
            with pytest.raises(UnmountError, match="is not mounted"):
                manager.unmount(file_path)


class TestCommandExecutionErrors:
    """Test error handling in command execution."""

    @pytest.fixture
    def manager(self):
        """Create a manager with mocked dependencies."""
        with patch("mount_squashfs.core.subprocess.run"):
            return SquashFSManager()

    @patch("mount_squashfs.core.subprocess.run")
    def test_mount_command_execution_error(self, mock_subprocess, manager):
        """Test error handling in _execute_mount_command."""
        from subprocess import CalledProcessError

        # Mock failed squashfuse call
        mock_subprocess.side_effect = CalledProcessError(1, "squashfuse")

        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name
            mount_point = Path(tempfile.mkdtemp())

            with pytest.raises(MountCommandExecutionError) as exc_info:
                manager._execute_mount_command(file_path, mount_point)

            # Verify the error details
            assert exc_info.value.command == "squashfuse"
            assert exc_info.value.return_code == 1
            assert "Failed to mount" in exc_info.value.message
            # Also verify it's a MountError
            assert isinstance(exc_info.value, MountError)

    @patch("mount_squashfs.core.subprocess.run")
    def test_unmount_command_execution_error(self, mock_subprocess, manager):
        """Test error handling in _execute_unmount_command."""
        from subprocess import CalledProcessError

        # Mock failed fusermount call
        mock_subprocess.side_effect = CalledProcessError(1, "fusermount")

        mount_point = Path(tempfile.mkdtemp())

        with pytest.raises(UnmountCommandExecutionError) as exc_info:
            manager._execute_unmount_command(mount_point)

        # Verify the error details
        assert exc_info.value.command == "fusermount"
        assert exc_info.value.return_code == 1
        assert "Failed to unmount" in exc_info.value.message
        # Also verify it's an UnmountError
        assert isinstance(exc_info.value, UnmountError)


class TestMountPointValidationErrors:
    """Test error handling in mount point validation."""

    @pytest.fixture
    def manager(self):
        """Create a manager with mocked dependencies."""
        with patch("mount_squashfs.core.subprocess.run"):
            return SquashFSManager()

    def test_validate_mount_point_not_empty_error(self, manager):
        """Test error when mount point is not empty."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "non_empty"
            mount_point.mkdir()

            # Create a file to make it non-empty
            (mount_point / "existing_file").touch()

            with pytest.raises(MountError, match="Mount point .* is not empty"):
                manager._validate_mount_point_available(mount_point)


class TestCleanupErrors:
    """Test error handling in cleanup operations."""

    @pytest.fixture
    def manager(self):
        """Create a manager with mocked dependencies."""
        with patch("mount_squashfs.core.subprocess.run"):
            return SquashFSManager()

    def test_cleanup_directory_removal_error(self, manager):
        """Test error handling when directory removal fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "test_mount"
            mount_point.mkdir()

            # Create a file to make cleanup fail
            (mount_point / "stubborn_file").touch()

            # Mock shutil.rmtree to raise an error
            with patch(
                "mount_squashfs.core.shutil.rmtree",
                side_effect=OSError("Permission denied"),
            ):
                # Enable verbose to see the warning
                manager.config.verbose = True

                # This should not raise an exception, just print a warning
                manager._cleanup_mount_directory(mount_point)

    def test_cleanup_parent_directory_removal_error(self, manager):
        """Test error handling when parent directory removal fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mount point in a custom location that matches mount_base
            mount_point = Path(temp_dir) / manager.config.mount_base / "test"
            mount_point.mkdir(parents=True)

            # Create another directory to prevent parent cleanup
            sibling_dir = mount_point.parent / "sibling"
            sibling_dir.mkdir()

            # Mock os.rmdir to raise an error for parent directory
            with patch(
                "mount_squashfs.core.os.rmdir",
                side_effect=OSError("Directory not empty"),
            ):
                # This should not raise an exception
                manager._cleanup_mount_directory(mount_point)


class TestMountWorkflowErrors:
    """Test error conditions in mount workflow."""

    @pytest.fixture
    def manager(self):
        """Create a manager with mocked dependencies."""
        with patch("mount_squashfs.core.subprocess.run"):
            return SquashFSManager()

    def test_mount_already_mounted_error(self, manager):
        """Test error when trying to mount an already mounted file."""
        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # Mock the tracker to indicate file is already mounted
            with patch.object(manager.tracker, "is_mounted", return_value=True):
                with pytest.raises(MountError, match="already mounted"):
                    manager.mount(file_path)

    def test_mount_nonexistent_mount_point_validation(self, manager):
        """Test error when mount point doesn't exist."""
        mount_point = Path("/nonexistent/mount/point")

        with pytest.raises(MountPointError, match="Mount point does not exist"):
            manager._is_mount_point_valid(mount_point)


class TestUnmountWorkflowErrors:
    """Test error conditions in unmount workflow."""

    @pytest.fixture
    def manager(self):
        """Create a manager with mocked dependencies."""
        with patch("mount_squashfs.core.subprocess.run"):
            return SquashFSManager()

    def test_unmount_no_mount_info_error(self, manager):
        """Test error when mount info cannot be retrieved."""
        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # Mock the tracker to indicate file is mounted but return no mount info
            with (
                patch.object(manager.tracker, "is_mounted", return_value=True),
                patch.object(manager.tracker, "get_mount_info", return_value=None),
            ):
                with pytest.raises(
                    UnmountError, match="Could not determine mount point"
                ):
                    manager.unmount(file_path)

    def test_unmount_with_custom_mount_point(self, manager):
        """Test unmount with custom mount point provided."""
        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # Mock the tracker to indicate file is mounted
            with (
                patch.object(manager.tracker, "is_mounted", return_value=True),
                patch.object(
                    manager.tracker,
                    "get_mount_info",
                    return_value=(file_path, "/some/mount"),
                ),
            ):
                custom_mount_point = Path(tempfile.mkdtemp())

                # Create a dummy file to make it non-empty
                (custom_mount_point / "dummy").touch()

                # Mock the unmount command and cleanup
                with (
                    patch("mount_squashfs.core.subprocess.run"),
                    patch("mount_squashfs.core.shutil.rmtree"),
                    patch("mount_squashfs.core.os.rmdir"),
                ):
                    manager.unmount(file_path, str(custom_mount_point))

                    # Verify the custom mount point was used
                    # (This is tested by the fact that no exception was raised)


class TestVerboseOutput:
    """Test verbose output functionality."""

    @pytest.fixture
    def verbose_manager(self):
        """Create a manager with verbose output enabled."""
        config = SquashFSConfig(verbose=True)
        with patch("mount_squashfs.core.subprocess.run"):
            return SquashFSManager(config)

    @patch("mount_squashfs.core.subprocess.run")
    def test_verbose_mount_output(self, mock_subprocess, verbose_manager):
        """Test verbose output during mount operation."""
        mock_subprocess.return_value = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            with (
                patch("mount_squashfs.core.os.makedirs"),
                patch("builtins.print") as mock_print,
            ):
                verbose_manager.mount(file_path)

                # Verify verbose output was printed
                mock_print.assert_called()
                call_args = str(mock_print.call_args)
                assert "Mounted" in call_args

    @patch("mount_squashfs.core.subprocess.run")
    def test_verbose_unmount_output(self, mock_subprocess, verbose_manager):
        """Test verbose output during unmount operation."""
        mock_subprocess.return_value = MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # First mock a mount operation
            with patch("mount_squashfs.core.os.makedirs"):
                verbose_manager.mount(file_path)

            # Get the mount point
            mount_info = verbose_manager.tracker.get_mount_info(file_path)
            mount_point = Path(mount_info[1])

            # Create the mount directory and a dummy file
            mount_point.mkdir(parents=True, exist_ok=True)
            (mount_point / "dummy").touch()

            # Now test unmount with verbose output
            with (
                patch("mount_squashfs.core.shutil.rmtree"),
                patch("mount_squashfs.core.os.rmdir"),
                patch("builtins.print") as mock_print,
            ):
                verbose_manager.unmount(file_path)

                # Verify verbose output was printed
                mock_print.assert_called()
                call_args = str(mock_print.call_args)
                assert "Unmounted" in call_args

    def test_verbose_cleanup_warning(self, verbose_manager):
        """Test verbose warning during cleanup failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "test_mount"
            mount_point.mkdir()

            # Create a file to make cleanup fail
            (mount_point / "stubborn_file").touch()

            # Mock shutil.rmtree to raise an error
            with (
                patch(
                    "mount_squashfs.core.shutil.rmtree",
                    side_effect=OSError("Permission denied"),
                ),
                patch("builtins.print") as mock_print,
            ):
                verbose_manager._cleanup_mount_directory(mount_point)

                # Verify warning was printed
                mock_print.assert_called()
                call_args = str(mock_print.call_args)
                assert "Warning" in call_args
                assert "Could not remove directory" in call_args

    def test_parent_directory_cleanup_failure(self, verbose_manager):
        """Test the pass statement when parent directory cleanup fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mount point structure that matches our pattern
            mount_point = Path(temp_dir) / verbose_manager.config.mount_base / "test"
            mount_point.mkdir(parents=True)

            # Create a sibling directory to prevent parent cleanup
            sibling_dir = mount_point.parent / "sibling"
            sibling_dir.mkdir()

            # Mock os.rmdir to raise OSError for parent directory
            with patch(
                "mount_squashfs.core.os.rmdir",
                side_effect=OSError("Directory not empty"),
            ):
                # This should not raise an exception, just pass
                verbose_manager._cleanup_mount_directory(mount_point)

                # The test passes if no exception is raised
