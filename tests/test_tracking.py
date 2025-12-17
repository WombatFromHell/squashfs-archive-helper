"""
Test cases for the tracking module.

This module tests the mount tracking functionality.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mount_squashfs.errors import SquashFSError
from mount_squashfs.tracking import MountTracker


class TestMountTracker:
    """Test the MountTracker class."""

    @pytest.fixture
    def tracker(self, test_config):
        """Create a MountTracker instance for testing with isolated temp dir."""
        return MountTracker(test_config)

    def test_temp_file_path(self, tracker):
        """Test that temp file paths are generated correctly."""
        temp_file = tracker._get_temp_file_path("/path/to/test.sqs")
        assert temp_file.name == "test.mounted"
        # The parent should be the isolated temp directory, not /tmp
        assert temp_file.parent != Path("/tmp")
        assert temp_file.parent.exists()

    def test_is_mounted_no_file(self, tracker):
        """Test is_mounted when no tracking file exists."""
        assert not tracker.is_mounted("/path/to/test.sqs")

    def test_record_and_check_mount(self, tracker):
        """Test recording and checking mount status."""
        file_path = "/path/to/test.sqs"
        mount_point = "/path/to/mount"

        # Should not be mounted initially
        assert not tracker.is_mounted(file_path)

        # Record mount
        tracker.record_mount(file_path, mount_point)

        # Should be mounted now
        assert tracker.is_mounted(file_path)

        # Get mount info
        mount_info = tracker.get_mount_info(file_path)
        assert mount_info is not None
        assert mount_info[0] == str(Path(file_path).resolve())
        assert mount_info[1] == str(Path(mount_point).resolve())

    def test_record_unmount(self, tracker):
        """Test recording unmount."""
        file_path = "/path/to/test.sqs"
        mount_point = "/path/to/mount"

        # Record mount
        tracker.record_mount(file_path, mount_point)
        assert tracker.is_mounted(file_path)

        # Record unmount
        tracker.record_unmount(file_path)
        assert not tracker.is_mounted(file_path)

        # Mount info should be None after unmount
        assert tracker.get_mount_info(file_path) is None

    def test_read_nonexistent_mount_info(self, tracker):
        """Test reading mount info for non-existent file."""
        assert tracker.get_mount_info("/path/to/nonexistent.sqs") is None

    def test_multiple_files_tracking(self, tracker):
        """Test tracking multiple files independently."""
        file1 = "/path/to/test1.sqs"
        file2 = "/path/to/test2.sqs"
        mount1 = "/path/to/mount1"
        mount2 = "/path/to/mount2"

        # Record mounts for both files
        tracker.record_mount(file1, mount1)
        tracker.record_mount(file2, mount2)

        # Both should be mounted
        assert tracker.is_mounted(file1)
        assert tracker.is_mounted(file2)

        # Get mount info for both
        info1 = tracker.get_mount_info(file1)
        info2 = tracker.get_mount_info(file2)

        assert info1[0] == str(Path(file1).resolve())
        assert info1[1] == str(Path(mount1).resolve())
        assert info2[0] == str(Path(file2).resolve())
        assert info2[1] == str(Path(mount2).resolve())

        # Unmount one, the other should still be mounted
        tracker.record_unmount(file1)
        assert not tracker.is_mounted(file1)
        assert tracker.is_mounted(file2)


class TestMountTrackerErrorHandling:
    """Test error handling in MountTracker."""

    @pytest.fixture
    def tracker(self, test_config):
        """Create a MountTracker instance for testing with isolated temp dir."""
        return MountTracker(test_config)

    def test_read_corrupted_mount_info(self, tracker):
        """Test reading corrupted mount info file."""
        file_path = "/path/to/test.sqs"
        temp_file = tracker._get_temp_file_path(file_path)

        # Create a corrupted file (empty file should not raise error, just return None)
        with open(temp_file, "w") as f:
            f.write("corrupted content\n")  # Single line should return None

        # Should return None for corrupted content
        result = tracker.get_mount_info(file_path)
        assert result is None

        # Clean up
        if temp_file.exists():
            temp_file.unlink()

    def test_write_to_invalid_path(self, tracker):
        """Test writing mount info to invalid path."""
        # This should work normally, but we test the error handling
        file_path = "/path/to/test.sqs"
        mount_point = "/path/to/mount"

        # This should not raise an error
        tracker.record_mount(file_path, mount_point)

        # Verify it was recorded
        assert tracker.is_mounted(file_path)

        # Clean up
        temp_file = tracker._get_temp_file_path(file_path)
        if temp_file.exists():
            temp_file.unlink()


class TestMountTrackerIOErrors:
    """Test IO error handling in MountTracker."""

    @pytest.fixture
    def tracker(self, test_config):
        """Create a MountTracker instance for testing with isolated temp dir."""
        return MountTracker(test_config)

    def test_read_mount_info_io_error(self, tracker):
        """Test IOError handling in _read_mount_info."""
        file_path = "/path/to/test.sqs"
        temp_file = tracker._get_temp_file_path(file_path)

        # Create a file with no read permissions to simulate IOError
        try:
            with open(temp_file, "w") as f:
                f.write("test content")

            # Change permissions to make it unreadable
            os.chmod(temp_file, 0o000)

            # This should raise SquashFSError
            with pytest.raises(SquashFSError, match="Could not read mount info"):
                tracker._read_mount_info(file_path)

        finally:
            # Restore permissions and clean up
            try:
                os.chmod(temp_file, 0o644)
                temp_file.unlink()
            except Exception:
                pass

    def test_write_mount_info_io_error(self, tracker):
        """Test IOError handling in _write_mount_info."""
        file_path = "/path/to/test.sqs"
        mount_point = "/path/to/mount"
        temp_file = tracker._get_temp_file_path(file_path)

        # Create a directory with the same name to cause IOError
        if not temp_file.exists():
            temp_file.mkdir()

        try:
            # This should raise SquashFSError
            with pytest.raises(SquashFSError, match="Could not write mount info"):
                tracker._write_mount_info(file_path, mount_point)

        finally:
            # Clean up
            if temp_file.exists():
                if temp_file.is_dir():
                    temp_file.rmdir()
                else:
                    temp_file.unlink()

    def test_remove_mount_info_os_error(self, tracker):
        """Test OSError handling in _remove_mount_info."""
        file_path = "/path/to/test.sqs"
        temp_file = tracker._get_temp_file_path(file_path)

        # Create a file
        with open(temp_file, "w") as f:
            f.write("test content")

        # Mock os.unlink to raise OSError
        with patch(
            "mount_squashfs.tracking.Path.unlink",
            side_effect=OSError("Permission denied"),
        ):
            # This should raise SquashFSError
            with pytest.raises(SquashFSError, match="Could not remove mount info file"):
                tracker._remove_mount_info(file_path)

        # Clean up the actual file
        if temp_file.exists():
            temp_file.unlink()
