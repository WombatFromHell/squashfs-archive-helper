"""
Test cases for the mounting module.

This module tests the mounting functionality separately.
Note: Many tests are mocked since they require actual squashfuse/fusermount.
"""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from subprocess import CalledProcessError

import pytest

from squish.config import SquishFSConfig
from squish.errors import (
    MountCommandExecutionError,
    MountError,
    MountPointError,
    UnmountCommandExecutionError,
    UnmountError,
)
from squish.mounting import MountManager


class TestMountManagerInitialization:
    """Test MountManager initialization."""

    def test_init_with_default_config(self, mocker):
        """Test initialization with default configuration."""
        # Mock successful dependency check (if there are any)
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value = mocker.MagicMock()

        manager = MountManager()
        assert manager.config.mount_base == "mounts"
        assert manager.config.temp_dir == "/tmp"
        assert manager.config.auto_cleanup is True

    def test_init_with_custom_config(self, mocker):
        """Test initialization with custom configuration."""
        # Mock successful dependency check
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value = mocker.MagicMock()

        config = SquishFSConfig(
            mount_base="custom",
            temp_dir="/tmp",  # Use existing directory
            auto_cleanup=False,
            verbose=True,
        )
        manager = MountManager(config)
        assert manager.config == config


class TestMountPointValidation:
    """Test mount point validation logic."""

    @pytest.fixture
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("subprocess.run")
        return MountManager()

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
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("subprocess.run")
        return MountManager()

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
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("subprocess.run")
        return MountManager()

    def test_mount_workflow(self, mocker, manager):
        """Test the complete mount workflow."""
        # Mock successful squashfuse call
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value = mocker.MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # Should not be mounted initially
            assert not manager.tracker.is_mounted(file_path)

            # Mock os.makedirs to avoid creating actual directories
            mocker.patch("squish.mounting.os.makedirs")
            # Mock the mount operation
            manager.mount(file_path)

            # Should be mounted now
            assert manager.tracker.is_mounted(file_path)

            # Get mount info
            mount_info = manager.tracker.get_mount_info(file_path)
            assert mount_info is not None
            assert mount_info[0] == str(Path(file_path).resolve())

    def test_unmount_workflow(self, mocker, manager):
        """Test the complete unmount workflow."""
        # Mock successful fusermount call
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value = mocker.MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # First, mock a mount operation
            mocker.patch("squish.mounting.os.makedirs")
            manager.mount(file_path)
            assert manager.tracker.is_mounted(file_path)

            # Get the mount point that was recorded
            mount_info = manager.tracker.get_mount_info(file_path)
            mount_point = Path(mount_info[1])

            # Create the mount directory and a dummy file to make it non-empty
            mount_point.mkdir(parents=True, exist_ok=True)
            (mount_point / "dummy").touch()

            # Now test unmount
            mocker.patch("squish.mounting.shutil.rmtree")
            mocker.patch("squish.mounting.os.rmdir")
            manager.unmount(file_path)

            # Should not be mounted anymore
            assert not manager.tracker.is_mounted(file_path)

            # Clean up the mount directory we created
            if mount_point.exists():
                import shutil

                shutil.rmtree(mount_point, ignore_errors=True)

    def test_double_mount_error(self, mocker, manager):
        """Test that mounting twice raises MountError."""
        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # Mock first mount
            mocker.patch("subprocess.run")
            mocker.patch("squish.mounting.os.makedirs")
            manager.mount(file_path)

            # Second mount should fail
            with pytest.raises(MountError, match="already mounted"):
                mocker.patch("subprocess.run")
                mocker.patch("squish.mounting.os.makedirs")
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
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("subprocess.run")
        return MountManager()

    def test_mount_command_execution_error(self, mocker, manager):
        """Test error handling in _execute_mount_command."""

        # Mock failed squashfuse call
        mock_subprocess = mocker.patch("subprocess.run")
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

    def test_unmount_command_execution_error(self, mocker, manager):
        """Test error handling in _execute_unmount_command."""

        # Mock failed fusermount call
        mock_subprocess = mocker.patch("subprocess.run")
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
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("subprocess.run")
        return MountManager()

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
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("subprocess.run")
        return MountManager()

    def test_cleanup_directory_removal_error(self, mocker, manager):
        """Test error handling when directory removal fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "test_mount"
            mount_point.mkdir()

            # Create a file to make cleanup fail
            (mount_point / "stubborn_file").touch()

            # Enable verbose to see the warning
            object.__setattr__(manager.config, "verbose", True)

            # This should not raise an exception, just print a warning
            # Mock shutil.rmtree to raise an error only during the cleanup call
            original_rmtree = shutil.rmtree

            def mock_rmtree(path, **kwargs):
                if str(path) == str(mount_point):
                    raise OSError("Permission denied")
                else:
                    return original_rmtree(path, **kwargs)

            mocker.patch("squish.mounting.shutil.rmtree", side_effect=mock_rmtree)
            manager._cleanup_mount_directory(mount_point)

    def test_cleanup_parent_directory_removal_error(self, mocker, manager):
        """Test error handling when parent directory removal fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mount point in a custom location that matches mount_base
            mount_point = Path(temp_dir) / manager.config.mount_base / "test"
            mount_point.mkdir(parents=True)

            # Create another directory to prevent parent cleanup
            sibling_dir = mount_point.parent / "sibling"
            sibling_dir.mkdir()

            # Mock os.rmdir to raise an error for parent directory
            original_rmdir = os.rmdir

            def mock_rmdir(path, **kwargs):
                if str(path) == str(mount_point.parent):
                    raise OSError("Directory not empty")
                else:
                    return original_rmdir(path, **kwargs)

            # This should not raise an exception
            mocker.patch("squish.mounting.os.rmdir", side_effect=mock_rmdir)
            manager._cleanup_mount_directory(mount_point)


class TestMountWorkflowErrors:
    """Test error conditions in mount workflow."""

    @pytest.fixture
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("subprocess.run")
        return MountManager()

    def test_mount_already_mounted_error(self, mocker, manager):
        """Test error when trying to mount an already mounted file."""
        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # Mock the tracker to indicate file is already mounted
            mocker.patch.object(manager.tracker, "is_mounted", return_value=True)
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
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("subprocess.run")
        return MountManager()

    def test_unmount_no_mount_info_error(self, mocker, manager):
        """Test error when mount info cannot be retrieved."""
        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # Mock the tracker to indicate file is mounted but return no mount info
            mocker.patch.object(manager.tracker, "is_mounted", return_value=True)
            mocker.patch.object(manager.tracker, "get_mount_info", return_value=None)
            with pytest.raises(UnmountError, match="Could not determine mount point"):
                manager.unmount(file_path)

    def test_unmount_with_custom_mount_point(self, mocker, manager):
        """Test unmount with custom mount point provided."""
        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # Mock the tracker to indicate file is mounted
            mocker.patch.object(manager.tracker, "is_mounted", return_value=True)
            mocker.patch.object(
                manager.tracker,
                "get_mount_info",
                return_value=(file_path, "/some/mount"),
            )
            custom_mount_point = Path(tempfile.mkdtemp())

            # Create a dummy file to make it non-empty
            (custom_mount_point / "dummy").touch()

            # Mock the unmount command and cleanup
            mocker.patch("subprocess.run")
            mocker.patch("squish.mounting.shutil.rmtree")
            mocker.patch("squish.mounting.os.rmdir")
            manager.unmount(file_path, str(custom_mount_point))

            # Verify the custom mount point was used
            # (This is tested by the fact that no exception was raised)


class TestMountingCoverageGaps:
    """Test coverage gap scenarios for mounting operations."""

    def test_cleanup_mount_directory_os_error(self, mocker):
        """Test _cleanup_mount_directory with OSError during shutil.rmtree."""
        config = SquishFSConfig()
        manager = MountManager(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "test_mount"
            mount_point.mkdir()

            # Enable auto_cleanup to trigger the cleanup
            object.__setattr__(manager.config, "auto_cleanup", True)

            # Mock shutil.rmtree to raise an OSError only for specific path
            original_rmtree = shutil.rmtree

            def mock_rmtree(path, **kwargs):
                if str(path) == str(mount_point):
                    raise OSError("Test error")
                else:
                    return original_rmtree(path, **kwargs)

            mocker.patch("squish.mounting.shutil.rmtree", side_effect=mock_rmtree)

            # This should handle the OSError gracefully and log a warning
            manager._cleanup_mount_directory(mount_point)

    def test_validate_mount_point_available_non_empty(self, mocker):
        """Test _validate_mount_point_available with non-empty directory."""
        config = SquishFSConfig()
        manager = MountManager(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "non_empty"
            mount_point.mkdir()

            # Create a file to make it non-empty
            (mount_point / "existing_file").touch()

            with pytest.raises(MountError, match="Mount point .* is not empty"):
                manager._validate_mount_point_available(mount_point)

    def test_is_mount_point_valid_nonexistent(self, mocker):
        """Test _is_mount_point_valid with non-existent mount point."""
        config = SquishFSConfig()
        manager = MountManager(config)

        mount_point = Path("/nonexistent/mount/point")

        with pytest.raises(MountPointError, match="Mount point does not exist"):
            manager._is_mount_point_valid(mount_point)

    def test_is_mount_point_valid_empty(self, mocker):
        """Test _is_mount_point_valid with empty mount point."""
        config = SquishFSConfig()
        manager = MountManager(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "empty_mount"
            mount_point.mkdir()

            with pytest.raises(MountPointError, match="Mount point is empty"):
                manager._is_mount_point_valid(mount_point)

    def test_determine_mount_point_none_provided(self, mocker):
        """Test _determine_mount_point when mount_point is None."""

        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                # Create a config with a custom mount_base
                custom_config = SquishFSConfig(mount_base="custom_mounts")
                custom_manager = MountManager(custom_config)

                # Test with no mount point provided, should use default logic
                mount_point = custom_manager._determine_mount_point("test.squashfs")
                expected = Path(temp_dir) / "custom_mounts" / "test"
                assert mount_point == expected
            finally:
                os.chdir(original_cwd)

    def test_execute_mount_command_success(self, mocker):
        """Test _execute_mount_command with successful execution."""
        config = SquishFSConfig()
        manager = MountManager(config)

        with tempfile.NamedTemporaryFile(suffix=".squashfs") as squashfs_file:
            file_path = squashfs_file.name

            with tempfile.TemporaryDirectory() as temp_dir:
                mount_point = Path(temp_dir) / "mount_point"

                # Mock successful subprocess call
                mock_subprocess = mocker.patch("subprocess.run")
                mock_subprocess.return_value = mocker.MagicMock()

                # This should not raise an exception
                manager._execute_mount_command(file_path, mount_point)

                # Verify subprocess.run was called with correct arguments
                mock_subprocess.assert_called_once()
                args, kwargs = mock_subprocess.call_args
                command = args[0]
                assert command[0] == "squashfuse"
                assert file_path in command
                assert str(mount_point) in command

    def test_execute_unmount_command_success(self, mocker):
        """Test _execute_unmount_command with successful execution."""
        config = SquishFSConfig()
        manager = MountManager(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "mount_point"

            # Mock successful subprocess call
            mock_subprocess = mocker.patch("subprocess.run")
            mock_subprocess.return_value = mocker.MagicMock()

            # This should not raise an exception
            manager._execute_unmount_command(mount_point)

            # Verify subprocess.run was called with correct arguments
            mock_subprocess.assert_called_once()
            args, kwargs = mock_subprocess.call_args
            command = args[0]
            assert command[0] == "fusermount"
            assert "-u" in command
            assert str(mount_point) in command

    def test_determine_mount_point_with_mount_base(self, mocker):
        """Test _determine_mount_point with a specific mount base."""
        config = SquishFSConfig(mount_base="custom_mounts")
        manager = MountManager(config)

        # Mock os.getcwd to control the working directory
        mocker.patch("os.getcwd", return_value="/tmp/test_dir")

        mount_point = manager._determine_mount_point("test.squashfs")
        expected = Path("/tmp/test_dir") / "custom_mounts" / "test"
        assert mount_point == expected

    def test_cleanup_mount_directory_with_auto_cleanup_false(self, mocker):
        """Test _cleanup_mount_directory when auto_cleanup is False."""
        config = SquishFSConfig(auto_cleanup=False)
        manager = MountManager(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "test_mount"
            mount_point.mkdir()

            # Create a dummy file to make sure it exists
            (mount_point / "dummy").touch()

            # Mock shutil.rmtree to be sure it's not called when auto_cleanup is False
            mock_rmtree = mocker.patch("squish.mounting.shutil.rmtree")

            # This should not remove the directory
            manager._cleanup_mount_directory(mount_point)

            # Verify that rmtree was not called
            mock_rmtree.assert_not_called()

    def test_mount_with_preexisting_mount_point(self, mocker):
        """Test mount operation with pre-existing mount point."""
        config = SquishFSConfig()
        manager = MountManager(config)

        with tempfile.NamedTemporaryFile(suffix=".squashfs") as squashfs_file:
            file_path = squashfs_file.name

            with tempfile.TemporaryDirectory() as temp_dir:
                mount_point = Path(temp_dir) / "mount_point"

                # Mock the subprocess operations
                mocker.patch("subprocess.run", return_value=mocker.MagicMock())

                # Mock os.makedirs to make sure it's called properly
                mock_makedirs = mocker.patch("squish.mounting.os.makedirs")

                # Mock the tracker's is_mounted method to return False initially
                # This is tricky because we need to mock both the tracker's initial check
                # and allow it to work after the mount is recorded
                original_is_mounted = manager.tracker.is_mounted
                original_record_mount = manager.tracker.record_mount

                # Mock the tracker methods
                def mock_is_mounted(file_path):
                    # Return False to allow mounting to proceed
                    return False

                manager.tracker.is_mounted = mock_is_mounted  # type: ignore[assignment]

                # Track if mount was recorded
                mount_recorded = []

                def mock_record_mount(file_path, mount_point):
                    mount_recorded.append((file_path, mount_point))

                manager.tracker.record_mount = mock_record_mount  # type: ignore[assignment]

                # This should create the directory and mount
                manager.mount(file_path, str(mount_point))

                # Verify os.makedirs was called with exist_ok=True
                mock_makedirs.assert_called_with(mount_point, exist_ok=True)

                # Verify mount was recorded
                assert len(mount_recorded) == 1

                # Restore original methods
                manager.tracker.is_mounted = original_is_mounted  # type: ignore[assignment]
                manager.tracker.record_mount = original_record_mount  # type: ignore[assignment]

    def test_determine_mount_point_with_custom_mount_point(self, mocker, caplog):
        """Test _determine_mount_point when a custom mount point is provided."""
        config = SquishFSConfig()
        manager = MountManager(config)

        # Test when mount_point is provided (not None)
        result = manager._determine_mount_point("test.squashfs", "/custom/mount/point")
        expected = Path("/custom/mount/point")
        assert result == expected

        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "mount_point"

            # Mock successful subprocess call
            mock_subprocess = mocker.patch("subprocess.run")
            mock_subprocess.return_value = mocker.MagicMock()

            # This should not raise an exception and log command execution
            with caplog.at_level(logging.INFO):
                manager._execute_unmount_command(mount_point)

            # Verify subprocess.run was called with correct arguments
            mock_subprocess.assert_called_once()
            args, kwargs = mock_subprocess.call_args
            command = args[0]
            assert command[0] == "fusermount"
            assert "-u" in command
            assert str(mount_point) in command
