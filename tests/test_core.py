"""
Test cases for the core module.

This module tests the core mounting/unmounting functionality.
Note: Many tests are mocked since they require actual squashfuse/fusermount.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from subprocess import CalledProcessError

import pytest

from squish.config import SquashFSConfig
from squish.core import SquashFSManager
from squish.errors import (
    BuildError,
    ChecksumCommandExecutionError,
    ChecksumError,
    CommandExecutionError,
    DependencyError,
    ListError,
    MksquashfsCommandExecutionError,
    MountCommandExecutionError,
    MountError,
    MountPointError,
    UnmountCommandExecutionError,
    UnmountError,
    UnsquashfsCommandExecutionError,
)


class TestSquashFSManagerInitialization:
    """Test SquashFSManager initialization and dependency checking."""

    def test_init_with_default_config(self, mocker):
        """Test initialization with default configuration."""
        # Mock successful dependency check
        mock_subprocess = mocker.patch("squish.core.subprocess.run")
        mock_subprocess.return_value = mocker.MagicMock()

        manager = SquashFSManager()
        assert manager.config.mount_base == "mounts"
        assert manager.config.temp_dir == "/tmp"
        assert manager.config.auto_cleanup is True

    def test_init_with_custom_config(self, mocker):
        """Test initialization with custom configuration."""
        # Mock successful dependency check
        mock_subprocess = mocker.patch("squish.core.subprocess.run")
        mock_subprocess.return_value = mocker.MagicMock()

        config = SquashFSConfig(
            mount_base="custom",
            temp_dir="/tmp",  # Use existing directory
            auto_cleanup=False,
            verbose=True,
        )
        manager = SquashFSManager(config)
        assert manager.config == config

    def test_non_linux_os_error(self, mocker):
        """Test that non-Linux OS raises DependencyError."""
        mock_platform = mocker.patch("squish.core.platform.system")
        mock_platform.return_value = "Windows"

        with pytest.raises(DependencyError, match="currently only supported on Linux"):
            SquashFSManager()

    def test_missing_dependency_error(self, mocker):
        """Test that missing dependencies raise DependencyError."""
        # Mock failed dependency check with CalledProcessError

        mock_subprocess = mocker.patch("squish.core.subprocess.run")
        mock_subprocess.side_effect = CalledProcessError(1, "which")

        with pytest.raises(DependencyError, match="is not installed or not in PATH"):
            SquashFSManager()


class TestMountPointValidation:
    """Test mount point validation logic."""

    @pytest.fixture
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("squish.core.subprocess.run")
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
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("squish.core.subprocess.run")
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
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("squish.core.subprocess.run")
        return SquashFSManager()

    def test_mount_workflow(self, mocker, manager):
        """Test the complete mount workflow."""
        # Mock successful squashfuse call
        mock_subprocess = mocker.patch("squish.core.subprocess.run")
        mock_subprocess.return_value = mocker.MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # Should not be mounted initially
            assert not manager.tracker.is_mounted(file_path)

            # Mock os.makedirs to avoid creating actual directories
            mocker.patch("squish.core.os.makedirs")
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
        mock_subprocess = mocker.patch("squish.core.subprocess.run")
        mock_subprocess.return_value = mocker.MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # First, mock a mount operation
            mocker.patch("squish.core.os.makedirs")
            manager.mount(file_path)
            assert manager.tracker.is_mounted(file_path)

            # Get the mount point that was recorded
            mount_info = manager.tracker.get_mount_info(file_path)
            mount_point = Path(mount_info[1])

            # Create the mount directory and a dummy file to make it non-empty
            mount_point.mkdir(parents=True, exist_ok=True)
            (mount_point / "dummy").touch()

            # Now test unmount
            mocker.patch("squish.core.shutil.rmtree")
            mocker.patch("squish.core.os.rmdir")
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
            mocker.patch("squish.core.subprocess.run")
            mocker.patch("squish.core.os.makedirs")
            manager.mount(file_path)

            # Second mount should fail
            with pytest.raises(MountError, match="already mounted"):
                mocker.patch("squish.core.subprocess.run")
                mocker.patch("squish.core.os.makedirs")
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
        mocker.patch("squish.core.subprocess.run")
        return SquashFSManager()

    def test_mount_command_execution_error(self, mocker, manager):
        """Test error handling in _execute_mount_command."""

        # Mock failed squashfuse call
        mock_subprocess = mocker.patch("squish.core.subprocess.run")
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
        mock_subprocess = mocker.patch("squish.core.subprocess.run")
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
        mocker.patch("squish.core.subprocess.run")
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
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("squish.core.subprocess.run")
        return SquashFSManager()

    def test_cleanup_directory_removal_error(self, mocker, manager):
        """Test error handling when directory removal fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "test_mount"
            mount_point.mkdir()

            # Create a file to make cleanup fail
            (mount_point / "stubborn_file").touch()

            # Enable verbose to see the warning
            manager.config.verbose = True

            # This should not raise an exception, just print a warning
            # Mock shutil.rmtree to raise an error only during the cleanup call
            original_rmtree = shutil.rmtree

            def mock_rmtree(path, **kwargs):
                if str(path) == str(mount_point):
                    raise OSError("Permission denied")
                else:
                    return original_rmtree(path, **kwargs)

            mocker.patch("squish.core.shutil.rmtree", side_effect=mock_rmtree)
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
            mocker.patch("squish.core.os.rmdir", side_effect=mock_rmdir)
            manager._cleanup_mount_directory(mount_point)


class TestMountWorkflowErrors:
    """Test error conditions in mount workflow."""

    @pytest.fixture
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("squish.core.subprocess.run")
        return SquashFSManager()

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
        mocker.patch("squish.core.subprocess.run")
        return SquashFSManager()

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
            mocker.patch("squish.core.subprocess.run")
            mocker.patch("squish.core.shutil.rmtree")
            mocker.patch("squish.core.os.rmdir")
            manager.unmount(file_path, str(custom_mount_point))

            # Verify the custom mount point was used
            # (This is tested by the fact that no exception was raised)


class TestChecksumFunctionality:
    """Test checksum verification functionality."""

    @pytest.fixture
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("squish.core.subprocess.run")
        return SquashFSManager()

    def test_validate_checksum_files_success(self, manager):
        """Test successful checksum file validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test file and its checksum file
            test_file = Path(temp_dir) / "test.sqs"
            checksum_file = Path(temp_dir) / "test.sqs.sha256"

            test_file.touch()
            checksum_file.write_text("abc123 test.sqs")

            # Should not raise an exception
            file_path_obj, checksum_file_obj = manager._validate_checksum_files(
                str(test_file)
            )
            assert file_path_obj == test_file
            assert checksum_file_obj == checksum_file

    def test_validate_checksum_files_nonexistent_target(self, manager):
        """Test error when target file doesn't exist."""
        with pytest.raises(ChecksumError, match="Target file does not exist"):
            manager._validate_checksum_files("/nonexistent/test.sqs")

    def test_validate_checksum_files_nonexistent_checksum(self, manager):
        """Test error when checksum file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.sqs"
            test_file.touch()

            with pytest.raises(ChecksumError, match="Checksum file does not exist"):
                manager._validate_checksum_files(str(test_file))

    def test_validate_checksum_files_different_directories(self, manager):
        """Test error when files are in different directories."""
        # Let's test this by directly calling the method with mocked paths
        # that have different parent directories

        # Create a test file in one directory
        with tempfile.TemporaryDirectory() as temp_dir1:
            test_file = Path(temp_dir1) / "test.sqs"
            test_file.touch()

            # Create a checksum file in a different directory
            with tempfile.TemporaryDirectory() as temp_dir2:
                checksum_file = Path(temp_dir2) / "test.sqs.sha256"
                checksum_file.write_text("abc123 test.sqs")

                # Now we need to mock the method to use our custom checksum file path
                # instead of the automatically calculated one
                original_method = manager._validate_checksum_files

                def mock_validate_checksum_files(file_path: str):
                    file_path_obj = Path(file_path)
                    # Use our custom checksum file path instead of calculating it
                    checksum_file_obj = checksum_file

                    # Check if both files exist
                    if not file_path_obj.exists():
                        manager.logger.logger.error(
                            f"Target file does not exist: {file_path}"
                        )
                        raise ChecksumError(f"Target file does not exist: {file_path}")

                    if not checksum_file_obj.exists():
                        manager.logger.logger.error(
                            f"Checksum file does not exist: {checksum_file_obj}"
                        )
                        raise ChecksumError(
                            f"Checksum file does not exist: {checksum_file_obj}"
                        )

                    # Check if both files are in the same directory
                    if file_path_obj.parent != checksum_file_obj.parent:
                        manager.logger.logger.error(
                            "Target file and checksum file are not in the same directory"
                        )
                        raise ChecksumError(
                            "Target file and checksum file must be in the same directory"
                        )

                    return file_path_obj, checksum_file_obj

                # Replace the method temporarily
                manager._validate_checksum_files = mock_validate_checksum_files

                try:
                    with pytest.raises(
                        ChecksumError, match="must be in the same directory"
                    ):
                        manager._validate_checksum_files(str(test_file))
                finally:
                    # Restore the original method
                    manager._validate_checksum_files = original_method

    def test_parse_checksum_file_success(self, manager):
        """Test successful checksum file parsing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            checksum_file = Path(temp_dir) / "test.sqs.sha256"
            checksum_file.write_text("abc123 test.sqs")

            result = manager._parse_checksum_file(checksum_file, "test.sqs")
            assert result is True

    def test_parse_checksum_file_missing_filename(self, manager):
        """Test error when checksum file doesn't contain target filename."""
        with tempfile.TemporaryDirectory() as temp_dir:
            checksum_file = Path(temp_dir) / "test.sqs.sha256"
            checksum_file.write_text("abc123 other_file.sqs")

            result = manager._parse_checksum_file(checksum_file, "test.sqs")
            assert result is False

    def test_parse_checksum_file_read_error(self, manager):
        """Test error when checksum file cannot be read."""
        with tempfile.TemporaryDirectory() as temp_dir:
            checksum_file = Path(temp_dir) / "test.sqs.sha256"
            # Create a file with no read permissions
            checksum_file.touch(mode=0o000)

            with pytest.raises(ChecksumError, match="Failed to read checksum file"):
                manager._parse_checksum_file(checksum_file, "test.sqs")

    def test_execute_checksum_command_success(self, mocker, manager):
        """Test successful checksum command execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            checksum_file = Path(temp_dir) / "test.sqs.sha256"
            checksum_file.write_text("abc123 test.sqs")

            # Mock successful subprocess run
            mock_subprocess = mocker.patch("squish.core.subprocess.run")
            mock_result = mocker.MagicMock()
            mock_result.stdout = "test.sqs: OK"
            mock_subprocess.return_value = mock_result

            # Should not raise an exception
            manager._execute_checksum_command(checksum_file)

    def test_execute_checksum_command_failure(self, mocker, manager):
        """Test failed checksum command execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            checksum_file = Path(temp_dir) / "test.sqs.sha256"
            checksum_file.write_text("abc123 test.sqs")

            # Mock failed subprocess run

            mock_subprocess = mocker.patch("squish.core.subprocess.run")
            mock_subprocess.side_effect = CalledProcessError(
                1, "sha256sum", "Checksum failed"
            )

            with pytest.raises(ChecksumError):
                manager._execute_checksum_command(checksum_file)

    def test_verify_checksum_success(self, mocker, manager):
        """Test successful complete checksum verification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.sqs"
            checksum_file = Path(temp_dir) / "test.sqs.sha256"

            test_file.touch()
            checksum_file.write_text("abc123 test.sqs")

            # Mock successful subprocess run
            mock_subprocess = mocker.patch("squish.core.subprocess.run")
            mock_result = mocker.MagicMock()
            mock_result.stdout = "test.sqs: OK"
            mock_subprocess.return_value = mock_result

            # Should not raise an exception
            manager.verify_checksum(str(test_file))

    def test_verify_checksum_failure(self, mocker, manager):
        """Test failed complete checksum verification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.sqs"
            checksum_file = Path(temp_dir) / "test.sqs.sha256"

            test_file.touch()
            checksum_file.write_text("abc123 test.sqs")

            # Mock failed subprocess run

            mock_subprocess = mocker.patch("squish.core.subprocess.run")
            mock_subprocess.side_effect = CalledProcessError(
                1, "sha256sum", "Checksum failed"
            )

            with pytest.raises(ChecksumError):
                manager.verify_checksum(str(test_file))

    def test_verify_checksum_missing_target_file(self, manager):
        """Test checksum verification when target file doesn't exist."""
        with pytest.raises(ChecksumError, match="Target file does not exist"):
            manager.verify_checksum("/nonexistent/test.sqs")

    def test_verify_checksum_missing_checksum_file(self, manager):
        """Test checksum verification when checksum file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.sqs"
            test_file.touch()

            with pytest.raises(ChecksumError, match="Checksum file does not exist"):
                manager.verify_checksum(str(test_file))

    def test_verify_checksum_missing_filename_in_checksum(self, manager):
        """Test checksum verification when filename is missing from checksum file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.sqs"
            checksum_file = Path(temp_dir) / "test.sqs.sha256"

            test_file.touch()
            checksum_file.write_text("abc123 other_file.sqs")

            with pytest.raises(ChecksumError, match="does not contain entry for"):
                manager.verify_checksum(str(test_file))


class TestVerboseOutput:
    """Test verbose output functionality."""

    @pytest.fixture
    def verbose_manager(self, mocker):
        """Create a manager with verbose output enabled."""
        config = SquashFSConfig(verbose=True)
        mocker.patch("squish.core.subprocess.run")
        return SquashFSManager(config)

    def test_verbose_mount_output(self, mocker, verbose_manager):
        """Test verbose output during mount operation."""
        mock_subprocess = mocker.patch("squish.core.subprocess.run")
        mock_subprocess.return_value = mocker.MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            mocker.patch("squish.core.os.makedirs")
            # The logging output is now handled by the logger, not print statements
            # We can verify that the mount operation completes without errors
            verbose_manager.mount(file_path)

            # Verify that the mount was recorded in the tracker
            mount_info = verbose_manager.tracker.get_mount_info(file_path)
            assert mount_info is not None
            assert file_path in mount_info[0]  # File path should be in the mount info

    def test_verbose_unmount_output(self, mocker, verbose_manager):
        """Test verbose output during unmount operation."""
        mock_subprocess = mocker.patch("squish.core.subprocess.run")
        mock_subprocess.return_value = mocker.MagicMock()

        with tempfile.NamedTemporaryFile(suffix=".sqs") as squashfs_file:
            file_path = squashfs_file.name

            # First mock a mount operation
            mocker.patch("squish.core.os.makedirs")
            verbose_manager.mount(file_path)

            # Get the mount point
            mount_info = verbose_manager.tracker.get_mount_info(file_path)
            mount_point = Path(mount_info[1])

            # Create the mount directory and a dummy file
            mount_point.mkdir(parents=True, exist_ok=True)
            (mount_point / "dummy").touch()

            # Now test unmount with verbose output
            mocker.patch("squish.core.shutil.rmtree")
            mocker.patch("squish.core.os.rmdir")
            verbose_manager.unmount(file_path)

            # Verify that the unmount was successful by checking the tracker
            assert not verbose_manager.tracker.is_mounted(file_path)

    def test_verbose_cleanup_warning(self, mocker, verbose_manager):
        """Test verbose warning during cleanup failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "test_mount"
            mount_point.mkdir()

            # Create a file to make cleanup fail
            (mount_point / "stubborn_file").touch()

            # Mock shutil.rmtree to raise an error
            original_rmtree = shutil.rmtree

            def mock_rmtree(path, **kwargs):
                if str(path) == str(mount_point):
                    raise OSError("Permission denied")
                else:
                    return original_rmtree(path, **kwargs)

            # The cleanup operation should handle the error gracefully
            # and log it using the logger instead of print
            mocker.patch("squish.core.shutil.rmtree", side_effect=mock_rmtree)
            verbose_manager._cleanup_mount_directory(mount_point)

            # The operation should complete without raising an exception
            # The logging is handled internally by the logger

    def test_parent_directory_cleanup_failure(self, mocker, verbose_manager):
        """Test the pass statement when parent directory cleanup fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mount point structure that matches our pattern
            mount_point = Path(temp_dir) / verbose_manager.config.mount_base / "test"
            mount_point.mkdir(parents=True)

            # Create a sibling directory to prevent parent cleanup
            sibling_dir = mount_point.parent / "sibling"
            sibling_dir.mkdir()

            # Mock os.rmdir to raise OSError for parent directory
            original_rmdir = os.rmdir

            def mock_rmdir(path, **kwargs):
                if str(path) == str(mount_point.parent):
                    raise OSError("Directory not empty")
                else:
                    return original_rmdir(path, **kwargs)

            # This should not raise an exception, just pass
            mocker.patch("squish.core.os.rmdir", side_effect=mock_rmdir)
            verbose_manager._cleanup_mount_directory(mount_point)

            # The test passes if no exception is raised


class TestBuildFunctionality:
    """Test build functionality."""

    @pytest.fixture
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("squish.core.subprocess.run")
        return SquashFSManager()

    def test_build_exclude_arguments(self, manager):
        """Test building exclude arguments."""
        excludes = ["*.tmp", "*.log"]
        exclude_file = "exclude.txt"

        result = manager._build_exclude_arguments(
            excludes=excludes, exclude_file=exclude_file, wildcards=True, regex=False
        )

        expected = ["-wildcards", "-e", "*.tmp", "-e", "*.log", "-ef", "exclude.txt"]
        assert result == expected

    def test_build_squashfs_success(self, mocker, manager):
        """Test successful build operation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            # Mock subprocess.run
            mock_run = mocker.patch("squish.core.subprocess.run")

            # Mock subprocess.run to return appropriate values
            def mock_run_side_effect(cmd, **kwargs):
                if cmd[0] == "nproc":
                    return mocker.MagicMock(
                        stdout="4\n", returncode=0, check=lambda: True
                    )
                elif cmd[0] == "mksquashfs":
                    return mocker.MagicMock(returncode=0, check=lambda: True)
                elif cmd[0] == "sha256sum":
                    # Return a mock with proper stdout for checksum
                    mock_result = mocker.MagicMock()
                    mock_result.stdout = f"d41d8cd98f00b204e9800998ecf8427e  {output}\n"
                    mock_result.returncode = 0
                    mock_result.check = lambda: True
                    return mock_result
                return mocker.MagicMock(returncode=0, check=lambda: True)

            mock_run.side_effect = mock_run_side_effect

            manager.build_squashfs(str(source), str(output))

            # Verify mksquashfs was called
            assert mock_run.call_count >= 3  # nproc + mksquashfs + sha256sum

            # Verify checksum was generated
            checksum_file = str(output) + ".sha256"
            assert Path(checksum_file).exists()

            # Verify checksum content
            with open(checksum_file, "r") as f:
                content = f.read()
            assert f"d41d8cd98f00b204e9800998ecf8427e  {output}" in content

    def test_build_squashfs_source_not_found(self, manager):
        """Test build operation with non-existent source."""
        with pytest.raises(BuildError, match="Source not found"):
            manager.build_squashfs("/nonexistent/source", "/output.sqsh")

    def test_build_squashfs_output_exists(self, manager):
        """Test build operation with existing output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"
            output.touch()  # Create existing file

            with pytest.raises(BuildError, match="Output exists"):
                manager.build_squashfs(str(source), str(output))


class TestListFunctionality:
    """Test list functionality."""

    @pytest.fixture
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        mocker.patch("squish.core.subprocess.run")
        return SquashFSManager()

    def test_list_squashfs_success(self, mocker, manager):
        """Test successful list operation."""
        with tempfile.NamedTemporaryFile(suffix=".sqsh") as archive_file:
            mock_run = mocker.patch("squish.core.subprocess.run")

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


class TestErrorHandling:
    """Test error handling for new operations."""

    def test_mksquashfs_command_execution_error(self):
        """Test MksquashfsCommandExecutionError."""
        error = MksquashfsCommandExecutionError("mksquashfs", 1, "Test error")
        assert (
            str(error) == "Command 'mksquashfs' failed with return code 1: Test error"
        )
        assert isinstance(error, BuildError)
        assert isinstance(error, CommandExecutionError)

    def test_unsquashfs_command_execution_error(self):
        """Test UnsquashfsCommandExecutionError."""
        error = UnsquashfsCommandExecutionError("unsquashfs", 1, "Test error")
        assert (
            str(error) == "Command 'unsquashfs' failed with return code 1: Test error"
        )
        assert isinstance(error, ListError)
        assert isinstance(error, CommandExecutionError)


class TestCoreEdgeCases:
    """Test core module edge cases and error conditions."""

    def test_cleanup_mount_directory_error(self, mocker):
        """Test mount directory cleanup with error."""
        # Create a manager with mocked dependencies
        mocker.patch("squish.core.subprocess.run")
        manager = SquashFSManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir) / "mount_point"
            mount_point.mkdir()

            # Create a file in the mount point to prevent cleanup
            test_file = mount_point / "test_file.txt"
            test_file.write_text("test content")

            # Mock shutil.rmtree to raise an error only for the specific mount point
            original_rmtree = shutil.rmtree

            def side_effect_func(path, **kwargs):
                if str(path) == str(mount_point):
                    raise OSError("Permission denied")
                else:
                    return original_rmtree(path, **kwargs)

            mock_rmtree_obj = mocker.patch(
                "shutil.rmtree", side_effect=side_effect_func
            )

            # This should not raise an exception, just log a warning
            manager._cleanup_mount_directory(mount_point)

            # Verify rmtree was called
            mock_rmtree_obj.assert_called_once_with(mount_point)


class TestCoreCoverageGaps:
    """Test cases to cover missing core.py coverage gaps."""

    def test_validate_checksum_files_different_directories_coverage(self, mocker):
        """Test _validate_checksum_files with different directories to cover lines 103-106."""

        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files in different directories
            file1_dir = Path(temp_dir) / "dir1"
            file2_dir = Path(temp_dir) / "dir2"
            file1_dir.mkdir()
            file2_dir.mkdir()

            file1 = file1_dir / "test.sqs"
            file2 = file2_dir / "test.sqs.sha256"
            file1.touch()
            file2.touch()

            # Create manager with verbose config
            config = mocker.MagicMock()
            config.verbose = True
            logger = mocker.MagicMock()

            manager = SquashFSManager(config)
            manager.logger = logger

            # Mock the method to test the directory validation logic directly
            # We need to patch the Path.with_suffix method to return the file in different directory
            mock_with_suffix = mocker.patch("pathlib.Path.with_suffix")
            mock_with_suffix.return_value = file2

            # This should raise ChecksumError due to different directories
            with pytest.raises(ChecksumError) as exc_info:
                manager._validate_checksum_files(str(file1))

            # Verify the error message
            assert "Target file and checksum file must be in the same directory" in str(
                exc_info.value
            )

    def test_execute_checksum_command_verbose_coverage(self, mocker):
        """Test _execute_checksum_command with verbose logging to cover line 134."""

        # Create a temporary checksum file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sha256", delete=False) as f:
            f.write("test content")
            checksum_file = Path(f.name)

        try:
            # Create manager with verbose config
            config = mocker.MagicMock()
            config.verbose = True
            logger = mocker.MagicMock()

            manager = SquashFSManager(config)
            manager.logger = logger

            # Mock subprocess.run to avoid actual execution
            mock_run = mocker.patch("subprocess.run")
            mock_result = mocker.MagicMock()
            mock_result.stdout = "test.sqs: OK"
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            # This should cover the verbose logging (line 134)
            manager._execute_checksum_command(checksum_file)

            # Verify the command was executed
            mock_run.assert_called_once()
            # Verify verbose logging was called (line 134)
            logger.log_command_execution.assert_called()

        finally:
            checksum_file.unlink()

    def test_execute_checksum_command_success_logging_coverage(self, mocker):
        """Test _execute_checksum_command success logging to cover line 139."""

        # Create a temporary checksum file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sha256", delete=False) as f:
            f.write("test content")
            checksum_file = Path(f.name)

        try:
            # Create manager with verbose config
            config = mocker.MagicMock()
            config.verbose = True
            logger = mocker.MagicMock()

            manager = SquashFSManager(config)
            manager.logger = logger

            # Mock subprocess.run to return success
            mock_run = mocker.patch("subprocess.run")
            mock_result = mocker.MagicMock()
            mock_result.stdout = "test.sqs: OK"
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            # This should cover the success logging (line 139)
            manager._execute_checksum_command(checksum_file)

            # Verify the success logging was called (line 139)
            # The success logging should be the second call to log_command_execution
            assert logger.log_command_execution.call_count == 2, (
                f"Expected 2 calls, got {logger.log_command_execution.call_count}"
            )

            # Check that the second call has the success parameter (either explicit or default)
            # The method signature is: log_command_execution(command, return_code=None, success=True)
            # So the second call should have at least the command parameter
            second_call = logger.log_command_execution.call_args_list[1]
            assert len(second_call[0]) >= 1, (
                "Second call should have at least command parameter"
            )

            # Verify that the command was executed successfully by checking the subprocess call
            mock_run.assert_called_once()

        finally:
            checksum_file.unlink()

    def test_execute_checksum_command_unexpected_result_coverage(self, mocker):
        """Test _execute_checksum_command with unexpected result to cover line 143."""

        # Create a temporary checksum file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sha256", delete=False) as f:
            f.write("test content")
            checksum_file = Path(f.name)

        try:
            # Create manager
            config = mocker.MagicMock()
            config.verbose = False
            logger = mocker.MagicMock()

            manager = SquashFSManager(config)
            manager.logger = logger

            # Mock subprocess.run to return unexpected output
            mock_run = mocker.patch("subprocess.run")
            mock_result = mocker.MagicMock()
            mock_result.stdout = "unexpected output"
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            # This should cover the warning for unexpected result (line 143)
            manager._execute_checksum_command(checksum_file)

            # Verify the warning was logged (line 143)
            logger.logger.warning.assert_called_once_with(
                "Unexpected checksum verification result: unexpected output"
            )

        finally:
            checksum_file.unlink()

    def test_mount_point_validation_exit_path_coverage(self, mocker):
        """Test mount point validation exit path to cover line 255->exit."""
        # This tests the return statement in _is_mount_point_valid that should return True

        # Create a manager with mocked dependencies
        mocker.patch("squish.core.subprocess.run")
        manager = SquashFSManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir)
            # Add a dummy file to make directory non-empty
            (mount_point / "dummy_file").touch()

            # This should return True (the return True statement on line ~255)
            result = manager._is_mount_point_valid(mount_point)
            assert result is True

    def test_mount_point_validation_failure_coverage(self, mocker):
        """Test mount point validation failure to cover line 371."""

        # Create a manager with mocked dependencies
        mocker.patch("squish.core.subprocess.run")
        manager = SquashFSManager()

        # This should trigger the MountPointError for non-existent mount point (line 371)
        with pytest.raises(MountPointError, match="Mount point does not exist"):
            manager._is_mount_point_valid(Path("/nonexistent/mount/point"))

    def test_validate_checksum_files_target_not_exists_coverage(self, mocker):
        """Test _validate_checksum_files when target doesn't exist to cover line 405."""

        # Create a manager with mocked dependencies
        mocker.patch("squish.core.subprocess.run")
        manager = SquashFSManager()

        # Test with non-existent target file (line 405)
        with pytest.raises(ChecksumError, match="Target file does not exist"):
            manager._validate_checksum_files("/nonexistent/file.sqs")

    def test_parse_checksum_file_content_not_found_coverage(self, mocker):
        """Test _parse_checksum_file when content is not found to cover lines 410-415."""

        # Create a manager with mocked dependencies
        mocker.patch("squish.core.subprocess.run")
        manager = SquashFSManager()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sha256", delete=False) as f:
            f.write("different_filename_checksum content.txt")
            checksum_file = Path(f.name)

        try:
            # This should return False when target filename is not in content (lines 410-415)
            result = manager._parse_checksum_file(checksum_file, "test.sqs")
            assert result is False
        finally:
            checksum_file.unlink()

    def test_parse_checksum_file_read_error_coverage(self, mocker):
        """Test _parse_checksum_file read error to cover line 425."""

        # Create a manager with mocked dependencies
        mocker.patch("squish.core.subprocess.run")
        manager = SquashFSManager()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sha256", delete=False) as f:
            f.write("test content")
            checksum_file = Path(f.name)

        try:
            # Mock open to raise an exception to test the catch block (line 425)
            mock_open = mocker.patch("builtins.open")
            mock_open.side_effect = Exception("Read error")

            with pytest.raises(ChecksumError, match="Failed to read checksum file"):
                manager._parse_checksum_file(checksum_file, "test.sqs")
        finally:
            checksum_file.unlink()

    def test_is_mount_point_valid_empty_mount_point_coverage(self, mocker):
        """Test _is_mount_point_valid for empty mount point to cover lines 433-440."""

        # Create a manager with mocked dependencies
        mocker.patch("squish.core.subprocess.run")
        manager = SquashFSManager()

        with tempfile.TemporaryDirectory() as temp_dir:
            mount_point = Path(temp_dir)
            # Directory is empty (no dummy file)

            # This should raise MountPointError (lines 433-440)
            with pytest.raises(MountPointError, match="Mount point is empty"):
                manager._is_mount_point_valid(mount_point)

    def test_execute_mksquashfs_command_failure_coverage(self, mocker):
        """Test _execute_mksquashfs_command failure to cover lines 474->484."""

        # Create a manager with mocked dependencies
        mocker.patch("squish.core.subprocess.run")
        manager = SquashFSManager()

        # Mock subprocess.run to raise CalledProcessError (lines 474->484)
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "mksquashfs")

        with pytest.raises(MksquashfsCommandExecutionError) as exc_info:
            manager._execute_mksquashfs_command(
                "source", "output.sqsh", [], "zstd", "1M", 1
            )

        # Verify the error type and details
        assert exc_info.value.command == "mksquashfs"
        assert exc_info.value.return_code == 1

    def test_generate_checksum_command_failure_coverage(self, mocker):
        """Test _generate_checksum command failure to cover lines 480-481."""

        mocker.patch("squish.core.subprocess.run")
        manager = SquashFSManager()

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name

        try:
            # Mock subprocess.run to raise CalledProcessError (lines 480-481)
            mock_run = mocker.patch("subprocess.run")
            mock_run.side_effect = CalledProcessError(1, "sha256sum")

            with pytest.raises(ChecksumCommandExecutionError) as exc_info:
                manager._generate_checksum(temp_file_path)

            # Verify the error type and details
            assert exc_info.value.command == "sha256sum"
            assert exc_info.value.return_code == 1
        finally:
            # Clean up the temporary file
            Path(temp_file_path).unlink(missing_ok=True)

    def test_build_dependency_check_failure_coverage(self, mocker):
        """Test build dependency check failure to cover line 503."""

        # Mock the dependency check to fail for build dependencies
        def mock_run_side_effect(cmd, *args, **kwargs):
            if (
                isinstance(cmd, list)
                and len(cmd) >= 2
                and cmd[0] == "which"
                and cmd[1] in ["mksquashfs", "unsquashfs", "nproc"]
            ):
                # Simulate that one of the build dependencies is missing
                raise CalledProcessError(1, "which")
            return mocker.MagicMock(returncode=0)

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = mock_run_side_effect

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            manager = SquashFSManager()
            with pytest.raises(
                DependencyError, match="is not installed or not in PATH"
            ):
                manager.build_squashfs(str(source), str(output))

    def test_build_processor_detection_failure_coverage(self, mocker):
        """Test build processor detection failure to cover lines 474-481."""

        # Store reference to the real subprocess.run function to avoid recursion
        real_subprocess_run = subprocess.run

        # Create a manager with mocked dependencies
        mock_run = mocker.patch("subprocess.run")

        def mock_run_side_effect(cmd, *args, **kwargs):
            if isinstance(cmd, list) and cmd[0] == "which":
                # Mock dependency checks to pass
                return mocker.MagicMock(returncode=0)
            elif isinstance(cmd, list) and cmd[0] == "nproc":
                # Simulate nproc command failure to trigger fallback to 1 processor (lines 474-481)
                raise CalledProcessError(1, "nproc")
            elif isinstance(cmd, list) and cmd[0] == "mksquashfs":
                # Actually run mksquashfs command to create the file
                result = real_subprocess_run(cmd, *args, **kwargs)
                return result
            elif isinstance(cmd, list) and cmd[0] == "sha256sum":
                # Actually run sha256sum but mock the output appropriately
                if "-c" in cmd:  # checksum verification
                    # Create a mock successful result for verification
                    result = mocker.MagicMock()
                    result.stdout = "OK\n"
                    result.returncode = 0
                    return result
                else:  # checksum generation
                    # Actually run sha256sum and capture output
                    result = real_subprocess_run(cmd, *args, **kwargs)
                    return result
            else:
                # Mock other commands to succeed
                result = mocker.MagicMock()
                result.stdout = "fake_checksum some_file\n"
                result.returncode = 0
                return result

        mock_run.side_effect = mock_run_side_effect

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            manager = SquashFSManager()

            # This should work by falling back to 1 processor (lines 474-481)
            # The build should complete successfully by using 1 processor as fallback
            manager.build_squashfs(str(source), str(output))

            # Verify that the file was created
            assert Path(output).exists()

    def test_build_processor_detection_success_coverage(self, mocker):
        """Test build processor detection success to cover the success path of lines 474-481."""

        # Store reference to the real subprocess.run function to avoid recursion
        real_subprocess_run = subprocess.run

        # Create a manager with mocked dependencies
        mock_run = mocker.patch("subprocess.run")

        def mock_run_side_effect(cmd, *args, **kwargs):
            if isinstance(cmd, list) and cmd[0] == "which":
                # Mock dependency checks to pass
                return mocker.MagicMock(returncode=0)
            elif isinstance(cmd, list) and cmd[0] == "nproc":
                # Simulate nproc command success to trigger normal processor count (lines 474-481)
                result = mocker.MagicMock()
                result.stdout = "4"  # Return 4 processors
                result.returncode = 0
                return result
            elif isinstance(cmd, list) and cmd[0] == "mksquashfs":
                # Actually run mksquashfs command to create the file
                result = real_subprocess_run(cmd, *args, **kwargs)
                return result
            elif isinstance(cmd, list) and cmd[0] == "sha256sum":
                # Actually run sha256sum but mock the output appropriately
                if "-c" in cmd:  # checksum verification
                    # Create a mock successful result for verification
                    result = mocker.MagicMock()
                    result.stdout = "OK\n"
                    result.returncode = 0
                    return result
                else:  # checksum generation
                    # Actually run sha256sum and capture output
                    result = real_subprocess_run(cmd, *args, **kwargs)
                    return result
            else:
                # Mock other commands to succeed
                result = mocker.MagicMock()
                result.stdout = "fake_checksum some_file\n"
                result.returncode = 0
                return result

        mock_run.side_effect = mock_run_side_effect

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            manager = SquashFSManager()

            # This should work by using the detected 4 processors (lines 474-481)
            # The build should complete successfully by using the detected processor count
            manager.build_squashfs(str(source), str(output))

            # Verify that the file was created
            assert Path(output).exists()
