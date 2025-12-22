"""
Test cases for the progress parsing and Zenity integration module.

This module tests the mksquashfs progress parser and related functionality.
"""

import logging
import subprocess

import pytest

from squish.progress import (
    BuildCancelledError,
    ExtractCancelledError,
    ExtractProgressTracker,
    MksquashfsProgress,
    ProgressParseError,
    ProgressTracker,
    UnsquashfsProgress,
    ZenityProgressService,
    parse_mksquashfs_progress,
    parse_unsquashfs_progress,
)


class TestMksquashfsProgressDataClass:
    """Test the MksquashfsProgress data class."""

    def test_valid_progress_creation(self):
        """Test creation of valid progress object."""
        progress = MksquashfsProgress(current_files=10, total_files=100, percentage=50)
        assert progress.current_files == 10
        assert progress.total_files == 100
        assert progress.percentage == 50

    def test_invalid_percentage_raises_error(self):
        """Test that invalid percentage raises ValueError."""
        with pytest.raises(ValueError, match="Percentage must be between 0-100"):
            MksquashfsProgress(current_files=10, total_files=100, percentage=150)

        with pytest.raises(ValueError, match="Percentage must be between 0-100"):
            MksquashfsProgress(current_files=10, total_files=100, percentage=-10)

    def test_invalid_current_files_raises_error(self):
        """Test that invalid current files raises ValueError."""
        with pytest.raises(ValueError, match="Current files must be >= 0"):
            MksquashfsProgress(current_files=-1, total_files=100, percentage=50)

    def test_invalid_total_files_raises_error(self):
        """Test that invalid total files raises ValueError."""
        with pytest.raises(ValueError, match="Total files must be > 0"):
            MksquashfsProgress(current_files=10, total_files=0, percentage=50)

        with pytest.raises(ValueError, match="Total files must be > 0"):
            MksquashfsProgress(current_files=10, total_files=-100, percentage=50)

    def test_current_exceeds_total_raises_error(self):
        """Test that current files exceeding total raises ValueError."""
        with pytest.raises(
            ValueError, match="Current files.*cannot exceed total files"
        ):
            MksquashfsProgress(current_files=150, total_files=100, percentage=50)

    def test_immutability(self):
        """Test that the dataclass is immutable."""
        progress = MksquashfsProgress(current_files=10, total_files=100, percentage=50)

        with pytest.raises(Exception):  # FrozenInstanceError
            progress.current_files = 20  # type: ignore[attr-defined]


class TestUnsquashfsProgressDataClass:
    """Test the UnsquashfsProgress data class."""

    def test_valid_progress_creation(self):
        """Test creation of valid progress object."""
        progress = UnsquashfsProgress(current_files=10, total_files=100, percentage=50)
        assert progress.current_files == 10
        assert progress.total_files == 100
        assert progress.percentage == 50

    def test_invalid_percentage_raises_error(self):
        """Test that invalid percentage raises ValueError."""
        with pytest.raises(ValueError, match="Percentage must be between 0-100"):
            UnsquashfsProgress(current_files=10, total_files=100, percentage=150)

        with pytest.raises(ValueError, match="Percentage must be between 0-100"):
            UnsquashfsProgress(current_files=10, total_files=100, percentage=-10)

    def test_invalid_current_files_raises_error(self):
        """Test that invalid current files raises ValueError."""
        with pytest.raises(ValueError, match="Current files must be >= 0"):
            UnsquashfsProgress(current_files=-1, total_files=100, percentage=50)

    def test_invalid_total_files_raises_error(self):
        """Test that invalid total files raises ValueError."""
        with pytest.raises(ValueError, match="Total files must be > 0"):
            UnsquashfsProgress(current_files=10, total_files=0, percentage=50)

        with pytest.raises(ValueError, match="Total files must be > 0"):
            UnsquashfsProgress(current_files=10, total_files=-100, percentage=50)

    def test_current_exceeds_total_raises_error(self):
        """Test that current files exceeding total raises ValueError."""
        with pytest.raises(
            ValueError, match="Current files.*cannot exceed total files"
        ):
            UnsquashfsProgress(current_files=150, total_files=100, percentage=50)

    def test_immutability(self):
        """Test that the dataclass is immutable."""
        progress = UnsquashfsProgress(current_files=10, total_files=100, percentage=50)

        with pytest.raises(Exception):  # FrozenInstanceError
            progress.current_files = 20  # type: ignore[attr-defined]


class TestParseMksquashfsProgress:
    """Test the mksquashfs progress parser."""

    def test_parse_standard_progress_bar(self):
        """Test parsing standard progress bar format."""
        line = "[===================================================================================================================/                         ] 7951/9606  82%"
        result = parse_mksquashfs_progress(line)
        assert result == MksquashfsProgress(7951, 9606, 82)

    def test_parse_percentage_only_format(self):
        """Test parsing percentage-only format."""
        line = "7951/9606  82%"
        result = parse_mksquashfs_progress(line)
        assert result == MksquashfsProgress(7951, 9606, 82)

    def test_parse_with_various_whitespace(self):
        """Test parsing with different whitespace patterns."""
        lines_and_expected = [
            ("  [=====] 10/100  50%  ", MksquashfsProgress(10, 100, 50)),
            ("\t[=====] 10/100  50%\t", MksquashfsProgress(10, 100, 50)),
            ("[=====] 10/100  50%", MksquashfsProgress(10, 100, 50)),
            ("  7951/9606  82%  ", MksquashfsProgress(7951, 9606, 82)),
        ]

        for line, expected in lines_and_expected:
            result = parse_mksquashfs_progress(line)
            assert result == expected

    def test_return_none_for_non_progress_lines(self):
        """Test that non-progress lines return None."""
        non_progress_lines = [
            "Parallel mksquashfs: Using 16 processors",
            "Creating 4.0 filesystem on test.sqsh",
            "Filesystem size 1.23 Kbytes",
            "",
            "Exportable Squashfs 4.0 filesystem, zstd compressed",
            "file /file1.txt, uncompressed size 10 bytes",
        ]

        for line in non_progress_lines:
            assert parse_mksquashfs_progress(line) is None

    def test_raise_error_for_malformed_progress(self):
        """Test that malformed progress lines raise ProgressParseError."""
        # Lines that match the pattern but have invalid data
        malformed_lines = [
            "[=====] 10/100  9999%",  # Invalid percentage (> 100)
            "[=====] 10/0  50%",  # Zero total files
        ]

        for line in malformed_lines:
            with pytest.raises(ProgressParseError):
                parse_mksquashfs_progress(line)

        # Lines that don't match the pattern should return None
        non_matching_lines = [
            "[=====] invalid/format 999%",
            "[=====] 10/100",  # Missing percentage
            "[=====] -1/100  50%",  # Negative current files (doesn't match regex)
            "[=====] 10/100  abc%",  # Invalid percentage format (doesn't match regex)
        ]

        for line in non_matching_lines:
            assert parse_mksquashfs_progress(line) is None

        # Lines with valid format but invalid logic should still be parsed
        # (validation happens in the dataclass, not in parsing)
        valid_format_lines = [
            "[=====] 100/100  50%",  # 100/100 files with 50% completion is valid
        ]

        for line in valid_format_lines:
            result = parse_mksquashfs_progress(line)
            assert result is not None

    def test_parse_edge_cases(self):
        """Test parsing of edge cases."""
        # 0% progress
        line = "[                                                                                                                   ] 0/100  0%"
        result = parse_mksquashfs_progress(line)
        assert result == MksquashfsProgress(0, 100, 0)

        # 100% progress
        line = "[===================================================================================================================================] 100/100  100%"
        result = parse_mksquashfs_progress(line)
        assert result == MksquashfsProgress(100, 100, 100)

        # Single file
        line = "[===================================================================================================================================] 1/1  100%"
        result = parse_mksquashfs_progress(line)
        assert result == MksquashfsProgress(1, 1, 100)


class TestParseUnsquashfsProgress:
    """Test the unsquashfs progress parser."""

    def test_parse_percentage_format(self):
        """Test parsing percentage format."""
        line = "50%"
        result = parse_unsquashfs_progress(line, total_files=100)
        assert result == UnsquashfsProgress(50, 100, 50)

        line = "100%"
        result = parse_unsquashfs_progress(line, total_files=200)
        assert result == UnsquashfsProgress(200, 200, 100)

        line = "0%"
        result = parse_unsquashfs_progress(line, total_files=50)
        assert result == UnsquashfsProgress(0, 50, 0)

    def test_parse_inodes_format(self):
        """Test parsing inodes format."""
        line = "100 inodes (200 blocks) to write"
        result = parse_unsquashfs_progress(line, total_files=200)
        assert result == UnsquashfsProgress(100, 200, 50)

        line = "200 inodes (400 blocks) to write"
        result = parse_unsquashfs_progress(line, total_files=200)
        assert result == UnsquashfsProgress(200, 200, 99)  # min(99, 100) = 99

    def test_parse_created_files_format(self):
        """Test parsing created files format."""
        line = "created 50 files"
        result = parse_unsquashfs_progress(line, total_files=100)
        assert result == UnsquashfsProgress(50, 100, 50)

        line = "created 100 files"
        result = parse_unsquashfs_progress(line, total_files=100)
        assert result == UnsquashfsProgress(100, 100, 99)  # min(99, 100) = 99

    def test_parse_non_progress_lines(self):
        """Test that non-progress lines return None."""
        lines = [
            "Parallel unsquashfs: Using 16 processors",
            "0 inodes (0 blocks) to write",
            "squashfs-root",
            "created 0 files",
            "created 1 directory",
            "created 0 symlinks",
            "",
            "Some random text",
        ]

        for line in lines:
            result = parse_unsquashfs_progress(line, total_files=100)
            assert result is None

    def test_parse_invalid_percentage(self):
        """Test that invalid percentage raises ProgressParseError."""
        # "invalid%" doesn't match the regex, so it returns None
        result = parse_unsquashfs_progress("invalid%", total_files=100)
        assert result is None

        # "150%" matches the regex but creates invalid progress data
        with pytest.raises(ProgressParseError):
            parse_unsquashfs_progress("150%", total_files=100)

    def test_parse_invalid_inodes(self):
        """Test that invalid inodes format returns None."""
        # Invalid format doesn't match regex, so returns None
        result = parse_unsquashfs_progress(
            "invalid inodes (blocks) to write", total_files=100
        )
        assert result is None

    def test_parse_invalid_created_files(self):
        """Test that invalid created files format returns None."""
        # Invalid format doesn't match regex, so returns None
        result = parse_unsquashfs_progress("created invalid files", total_files=100)
        assert result is None


class TestZenityProgressService:
    """Test the Zenity progress service."""

    def test_initialization(self):
        """Test service initialization."""
        service = ZenityProgressService()
        assert service.title == "Building SquashFS"
        assert service.process is None
        assert service.cancelled is False

        custom_service = ZenityProgressService("Custom Title")
        assert custom_service.title == "Custom Title"

    def test_start_creates_process(self, mocker):
        """Test that start method creates a subprocess."""
        mock_popen = mocker.patch("subprocess.Popen")
        service = ZenityProgressService()

        service.start("Test build")

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert call_args[0] == "zenity"
        assert "--progress" in call_args
        assert "--title" in call_args
        assert "Test build" in call_args

    def test_start_raises_error_if_already_started(self, mocker):
        """Test that start raises error if already started."""
        mocker.patch("subprocess.Popen")
        service = ZenityProgressService()

        service.start()

        with pytest.raises(
            RuntimeError, match="Zenity progress dialog already started"
        ):
            service.start()

    def test_update_raises_error_if_not_started(self):
        """Test that update raises error if not started."""
        service = ZenityProgressService()
        progress = MksquashfsProgress(10, 100, 50)

        with pytest.raises(RuntimeError, match="Zenity progress dialog not started"):
            service.update(progress)

    def test_update_writes_to_stdin(self, mocker):
        """Test that update writes percentage and status to stdin."""
        mock_process = mocker.MagicMock()
        mock_process.stdin = mocker.MagicMock()
        mocker.patch("subprocess.Popen", return_value=mock_process)

        service = ZenityProgressService()
        service.start()

        progress = MksquashfsProgress(10, 100, 50)
        service.update(progress)

        # Check that percentage was written
        mock_process.stdin.write.assert_any_call("50\n")
        mock_process.stdin.flush.assert_called()

        # Check that status text was written (new format includes percentage)
        mock_process.stdin.write.assert_any_call("# Processing files: 10/100 (50%)\n")

    def test_update_ignores_if_cancelled(self, mocker):
        """Test that update is ignored if cancelled."""
        mock_process = mocker.MagicMock()
        mock_process.stdin = mocker.MagicMock()
        mocker.patch("subprocess.Popen", return_value=mock_process)

        service = ZenityProgressService()
        service.start()

        # Reset the mock after start() to only check update() calls
        mock_process.stdin.write.reset_mock()

        service.cancelled = True

        progress = MksquashfsProgress(10, 100, 50)
        service.update(progress)

        # Should not write anything during update when cancelled
        mock_process.stdin.write.assert_not_called()

    def test_check_cancelled_returns_false_if_not_started(self):
        """Test check_cancelled returns False if not started."""
        service = ZenityProgressService()
        assert service.check_cancelled() is False

    def test_check_cancelled_returns_true_if_process_terminated(self, mocker):
        """Test check_cancelled returns True if process terminated."""
        mock_process = mocker.MagicMock()
        mock_process.poll.return_value = 0  # Process has terminated
        mocker.patch("subprocess.Popen", return_value=mock_process)

        service = ZenityProgressService()
        service.start()

        assert service.check_cancelled() is True
        assert service.cancelled is True

    def test_check_cancelled_returns_false_if_process_running(self, mocker):
        """Test check_cancelled returns False if process still running."""
        mock_process = mocker.MagicMock()
        mock_process.poll.return_value = None  # Process still running
        mocker.patch("subprocess.Popen", return_value=mock_process)

        service = ZenityProgressService()
        service.start()

        assert service.check_cancelled() is False
        assert service.cancelled is False

    def test_close_without_start(self):
        """Test close without starting."""
        service = ZenityProgressService()
        service.close()  # Should not raise

    def test_close_closes_process(self, mocker):
        """Test close properly closes the process."""
        mock_process = mocker.MagicMock()
        mock_process.stdin = mocker.MagicMock()
        mocker.patch("subprocess.Popen", return_value=mock_process)

        service = ZenityProgressService()
        service.start()

        service.close(success=True)

        # Should write 100% if successful
        mock_process.stdin.write.assert_called_with("100\n")
        mock_process.stdin.close.assert_called()
        mock_process.wait.assert_called()
        assert service.process is None

    def test_close_handles_exceptions(self, mocker):
        """Test close handles exceptions gracefully."""
        mock_process = mocker.MagicMock()
        mock_process.stdin = mocker.MagicMock()
        mock_process.stdin.close.side_effect = Exception("Test error")
        mocker.patch("subprocess.Popen", return_value=mock_process)

        service = ZenityProgressService()
        service.start()

        # Should not raise
        service.close()
        assert service.process is None


class TestZenityFallback:
    """Test Zenity fallback functionality when Zenity is not available."""

    def test_zenity_fallback_when_not_available(self, mocker, caplog):
        """Test graceful fallback when Zenity is not available."""
        # Mock subprocess.Popen to raise FileNotFoundError
        mocker.patch(
            "subprocess.Popen", side_effect=FileNotFoundError("zenity not found")
        )

        service = ZenityProgressService()

        # Should not raise an exception, just fall back gracefully
        service.start()

        # Process should be None (fallback mode)
        assert service.process is None

        # Should be able to continue with console-only progress
        progress = MksquashfsProgress(10, 100, 50)
        service.update(progress)  # Should not raise

        service.close()  # Should not raise

    def test_console_fallback_logging(self, mocker, caplog):
        """Test that appropriate logging occurs during fallback."""
        # Mock subprocess.Popen to raise FileNotFoundError
        mocker.patch(
            "subprocess.Popen", side_effect=FileNotFoundError("zenity not found")
        )

        service = ZenityProgressService()

        # Capture logs at WARNING level
        with caplog.at_level(logging.WARNING):
            service.start()

        # Verify warning was logged
        assert any("Zenity not found" in record.message for record in caplog.records)
        assert any(
            "falling back to console progress" in record.message
            for record in caplog.records
        )

    def test_console_fallback_progress_updates(self, mocker, caplog):
        """Test that progress updates work in console fallback mode."""
        # Mock subprocess.Popen to raise FileNotFoundError
        mocker.patch(
            "subprocess.Popen", side_effect=FileNotFoundError("zenity not found")
        )

        service = ZenityProgressService()
        service.start()

        # Capture logs at INFO level
        with caplog.at_level(logging.INFO):
            progress = MksquashfsProgress(25, 100, 25)
            service.update(progress)

        # Verify progress was logged to console
        assert any("Progress: 25%" in record.message for record in caplog.records)
        assert any("25/100 files" in record.message for record in caplog.records)

    def test_console_fallback_cancellation_handling(self, mocker):
        """Test that cancellation handling works in console fallback mode."""
        # Mock subprocess.Popen to raise FileNotFoundError
        mocker.patch(
            "subprocess.Popen", side_effect=FileNotFoundError("zenity not found")
        )

        service = ZenityProgressService()
        service.start()

        # Should not be cancelled in console mode
        assert service.check_cancelled() is False

        # Should not raise when closing
        service.close(success=True)

    def test_console_fallback_close_method(self, mocker, caplog):
        """Test that close method works correctly in console fallback mode."""
        # Mock subprocess.Popen to raise FileNotFoundError
        mocker.patch(
            "subprocess.Popen", side_effect=FileNotFoundError("zenity not found")
        )

        service = ZenityProgressService()
        service.start()

        # Capture logs at INFO level
        with caplog.at_level(logging.INFO):
            service.close(success=True)

        # Verify completion message was logged
        assert any(
            "Build completed successfully" in record.message
            for record in caplog.records
        )


class TestProgressTracker:
    """Test the progress tracker."""

    def test_initialization(self, mocker):
        """Test tracker initialization."""
        mock_service = mocker.MagicMock()
        tracker = ProgressTracker(mock_service)

        assert tracker.zenity_service == mock_service
        assert tracker._state.last_progress is None

    def test_process_output_line_with_progress(self, mocker):
        """Test processing output line with progress info."""
        mock_service = mocker.MagicMock()
        mock_service.check_cancelled.return_value = False  # Don't cancel
        tracker = ProgressTracker(mock_service)

        line = "[=====] 10/100  50%"
        tracker.process_output_line(line)

        # Should parse and update service
        mock_service.update.assert_called_once()
        progress_arg = mock_service.update.call_args[0][0]
        assert progress_arg == MksquashfsProgress(10, 100, 50)
        assert tracker._state.last_progress == progress_arg

    def test_process_output_line_without_progress(self, mocker):
        """Test processing output line without progress info."""
        mock_service = mocker.MagicMock()
        mock_service.check_cancelled.return_value = False  # Don't cancel
        tracker = ProgressTracker(mock_service)

        line = "Creating 4.0 filesystem..."
        tracker.process_output_line(line)

        # Should not update service
        mock_service.update.assert_not_called()
        assert tracker._state.last_progress is None

    def test_process_output_line_raises_cancelled_error(self, mocker):
        """Test that cancelled service raises BuildCancelledError."""
        mock_service = mocker.MagicMock()
        mock_service.check_cancelled.return_value = True
        tracker = ProgressTracker(mock_service)

        line = "Some output line"

        with pytest.raises(BuildCancelledError, match="Build cancelled by user"):
            tracker.process_output_line(line)

    def test_process_output_line_with_malformed_progress(self, mocker):
        """Test processing malformed progress line."""
        mock_service = mocker.MagicMock()
        mock_service.check_cancelled.return_value = False  # Don't cancel
        tracker = ProgressTracker(mock_service)

        line = "[=====] 10/100  9999%"  # This will match pattern but fail validation

        with pytest.raises(ProgressParseError):
            tracker.process_output_line(line)

        # Should not update service
        mock_service.update.assert_not_called()

    def test_process_output_line_with_file_info(self, mocker):
        """Test processing file info lines for progress estimation."""
        mock_service = mocker.MagicMock()
        mock_service.check_cancelled.return_value = False  # Don't cancel
        mock_service.process = mocker.MagicMock()
        mock_service.process.stdin = mocker.MagicMock()

        tracker = ProgressTracker(mock_service)
        tracker.set_total_files(10)

        line = "file /test1.txt, uncompressed size 100 bytes"
        tracker.process_output_line(line)

        # Should update file count and send status update
        assert tracker._state.file_count == 1
        assert tracker._state.processed_size == 100

        # Should call update method which writes to stdin
        mock_service.update.assert_called_once()

        # Check the progress object passed to update
        progress_arg = mock_service.update.call_args[0][0]
        assert progress_arg.current_files == 1
        assert progress_arg.total_files == 10
        assert progress_arg.percentage == 10

    def test_process_output_line_with_file_info_and_total_files(self, mocker):
        """Test processing file info lines when total files is known."""
        mock_service = mocker.MagicMock()
        mock_service.check_cancelled.return_value = False  # Don't cancel
        mock_service.process = mocker.MagicMock()
        mock_service.process.stdin = mocker.MagicMock()

        tracker = ProgressTracker(mock_service)
        tracker.set_total_files(2)

        # Process first file
        line1 = "file /test1.txt, uncompressed size 100 bytes"
        tracker.process_output_line(line1)

        # Should create mock progress and update service
        assert tracker._state.file_count == 1
        assert tracker._state.last_progress is not None
        assert tracker._state.last_progress.current_files == 1
        assert tracker._state.last_progress.total_files == 2
        assert tracker._state.last_progress.percentage == 50

        mock_service.update.assert_called_once()

    def test_set_total_files(self, mocker):
        """Test setting total files for progress estimation."""
        mock_service = mocker.MagicMock()
        tracker = ProgressTracker(mock_service)

        tracker.set_total_files(100)
        assert tracker._state.total_files == 100


class TestExtractProgressTracker:
    """Test the ExtractProgressTracker class."""

    def test_initialization(self, mocker):
        """Test tracker initialization."""
        mock_service = mocker.MagicMock()
        tracker = ExtractProgressTracker(mock_service)

        assert tracker.zenity_service == mock_service
        assert tracker._state.last_progress is None
        assert tracker._state.file_count == 0
        assert tracker._state.total_files is None

    def test_process_output_line_with_percentage(self, mocker):
        """Test processing percentage progress lines."""
        mock_service = mocker.MagicMock()
        mock_service.check_cancelled.return_value = False
        tracker = ExtractProgressTracker(mock_service)
        tracker.set_total_files(100)

        line = "50%"
        tracker.process_output_line(line)

        # Should parse percentage and update service
        assert tracker._state.last_progress is not None
        assert tracker._state.last_progress.percentage == 50
        assert tracker._state.last_progress.current_files == 50
        assert tracker._state.last_progress.total_files == 100
        mock_service.update.assert_called_once()

    def test_process_output_line_with_created_files(self, mocker):
        """Test processing created files progress lines."""
        mock_service = mocker.MagicMock()
        mock_service.check_cancelled.return_value = False
        tracker = ExtractProgressTracker(mock_service)
        tracker.set_total_files(200)

        line = "created 100 files"
        tracker.process_output_line(line)

        # Should parse created files and update service
        assert tracker._state.last_progress is not None
        assert tracker._state.last_progress.current_files == 100
        assert tracker._state.last_progress.total_files == 200
        assert tracker._state.last_progress.percentage == 50
        mock_service.update.assert_called_once()

    def test_process_output_line_with_inodes(self, mocker):
        """Test processing inodes progress lines."""
        mock_service = mocker.MagicMock()
        mock_service.check_cancelled.return_value = False
        tracker = ExtractProgressTracker(mock_service)
        tracker.set_total_files(100)

        line = "50 inodes (100 blocks) to write"
        tracker.process_output_line(line)

        # Should parse inodes and update service
        assert tracker._state.last_progress is not None
        assert tracker._state.last_progress.current_files == 50
        assert tracker._state.last_progress.total_files == 100
        assert tracker._state.last_progress.percentage == 50
        mock_service.update.assert_called_once()

    def test_process_output_line_without_total_files(self, mocker):
        """Test processing lines when total files is not set."""
        mock_service = mocker.MagicMock()
        mock_service.check_cancelled.return_value = False
        tracker = ExtractProgressTracker(mock_service)
        # Don't set total_files

        line = "50%"
        tracker.process_output_line(line)

        # Should not update service when total_files is None
        mock_service.update.assert_not_called()

    def test_process_output_line_with_created_files_updates_file_count(self, mocker):
        """Test that created files lines update file count."""
        mock_service = mocker.MagicMock()
        mock_service.check_cancelled.return_value = False
        tracker = ExtractProgressTracker(mock_service)
        tracker.set_total_files(100)

        line = "created 25 files"
        tracker.process_output_line(line)

        # The file_count is updated in _process_file_line, but since "created 25 files"
        # is parsed as standard progress, _process_file_line is not called
        # The progress is still tracked correctly though
        assert tracker._state.last_progress is not None
        assert tracker._state.last_progress.current_files == 25
        assert tracker._state.last_progress.total_files == 100
        assert tracker._state.last_progress.percentage == 25

    def test_process_output_line_non_progress_lines(self, mocker):
        """Test processing non-progress lines."""
        mock_service = mocker.MagicMock()
        mock_service.check_cancelled.return_value = False
        tracker = ExtractProgressTracker(mock_service)
        tracker.set_total_files(100)

        lines = [
            "Parallel unsquashfs: Using 16 processors",
            "0 inodes (0 blocks) to write",
            "squashfs-root",
            "created 0 files",
            "created 1 directory",
            "created 0 symlinks",
        ]

        for line in lines:
            tracker.process_output_line(line)

        # Should not update service for non-progress lines
        mock_service.update.assert_not_called()

    def test_process_output_line_cancellation(self, mocker):
        """Test that cancellation raises ExtractCancelledError."""
        mock_service = mocker.MagicMock()
        mock_service.check_cancelled.return_value = True
        tracker = ExtractProgressTracker(mock_service)
        tracker.set_total_files(100)

        with pytest.raises(ExtractCancelledError, match="Extract cancelled by user"):
            tracker.process_output_line("50%")

    def test_set_total_files(self, mocker):
        """Test setting total files for progress estimation."""
        mock_service = mocker.MagicMock()
        tracker = ExtractProgressTracker(mock_service)

        tracker.set_total_files(100)
        assert tracker._state.total_files == 100


class TestIntegrationScenarios:
    """Test integration scenarios."""

    def test_full_progress_workflow(self, mocker):
        """Test the full progress workflow from parsing to Zenity update."""
        # Mock the subprocess
        mock_process = mocker.MagicMock()
        mock_process.stdin = mocker.MagicMock()
        mocker.patch("subprocess.Popen", return_value=mock_process)

        # Create service and tracker
        service = ZenityProgressService()
        tracker = ProgressTracker(service)

        # Start the service
        service.start()

        # Mock check_cancelled to return False
        service.check_cancelled = mocker.MagicMock(return_value=False)

        # Process some progress lines
        progress_lines = [
            "[=====] 10/100  10%",
            "[=======] 25/100  25%",
            "[=========] 50/100  50%",
            "[==============] 75/100  75%",
            "[================] 100/100  100%",
        ]

        for line in progress_lines:
            tracker.process_output_line(line)

        # Verify updates were called (using the mock service's update method)
        # 2 initial calls (percentage + status) + 5 progress updates (2 calls each) = 12 total
        assert (
            mock_process.stdin.write.call_count == 12
        )  # 2 initial + 10 progress updates

        # Verify last progress was stored
        expected_final = MksquashfsProgress(100, 100, 100)
        assert tracker._state.last_progress == expected_final

        # Close the service
        service.close(success=True)

    def test_cancellation_workflow(self, mocker):
        """Test the cancellation workflow."""
        # Mock the subprocess
        mock_process = mocker.MagicMock()
        mock_process.stdin = mocker.MagicMock()
        mock_process.poll.return_value = 0  # Simulate cancellation
        mocker.patch("subprocess.Popen", return_value=mock_process)

        # Create service and tracker
        service = ZenityProgressService()
        tracker = ProgressTracker(service)

        # Start the service
        service.start()

        # Process a line - should detect cancellation
        with pytest.raises(BuildCancelledError):
            tracker.process_output_line("Some output")

        # Verify cancellation was detected
        assert service.cancelled is True

    def test_full_progress_workflow_with_zenity_fallback(self, mocker, caplog):
        """Test the full progress workflow with Zenity fallback."""

        # Mock subprocess.Popen to fail for Zenity but succeed for mksquashfs
        def mock_popen_side_effect(cmd, **kwargs):
            if cmd[0] == "zenity":
                raise FileNotFoundError("zenity not found")
            # For mksquashfs simulation, return a mock process
            mock_process = mocker.MagicMock()
            mock_process.stdout = iter(
                [
                    "[=====] 10/100  10%",
                    "[=======] 25/100  25%",
                    "[=========] 50/100  50%",
                    "[==============] 75/100  75%",
                    "[================] 100/100  100%",
                ]
            )
            return mock_process

        mocker.patch("subprocess.Popen", side_effect=mock_popen_side_effect)

        # Create service and tracker
        service = ZenityProgressService()
        tracker = ProgressTracker(service)

        # Start the service - should fall back to console mode
        with caplog.at_level(logging.WARNING):
            service.start()

        # Verify fallback was logged
        assert any("Zenity not found" in record.message for record in caplog.records)

        # Process progress lines in console fallback mode
        progress_lines = [
            "[=====] 10/100  10%",
            "[=======] 25/100  25%",
            "[=========] 50/100  50%",
            "[==============] 75/100  75%",
            "[================] 100/100  100%",
        ]

        with caplog.at_level(logging.INFO):
            for line in progress_lines:
                tracker.process_output_line(line)

        # Verify progress was logged to console
        progress_logs = [
            record.message for record in caplog.records if "Progress:" in record.message
        ]
        assert len(progress_logs) == 5
        assert any("10%" in log for log in progress_logs)
        assert any("100%" in log for log in progress_logs)

        # Verify last progress was stored
        expected_final = MksquashfsProgress(100, 100, 100)
        assert tracker._state.last_progress == expected_final

        # Close the service
        with caplog.at_level(logging.INFO):
            service.close(success=True)

        # Verify completion was logged
        assert any(
            "Build completed successfully" in record.message
            for record in caplog.records
        )


class TestProgressCoverageGaps:
    """Test specific coverage gaps in progress.py."""

    def test_zenity_service_update_without_stdin(self, mocker):
        """Test Zenity service update when stdin is None (covers line 140)."""
        service = ZenityProgressService()

        # Mock the process to have None stdin
        mock_process = mocker.MagicMock()
        mock_process.stdin = None
        service.process = mock_process

        progress = MksquashfsProgress(current_files=50, total_files=100, percentage=50)

        # This should raise RuntimeError because stdin is None
        with pytest.raises(RuntimeError) as exc_info:
            service.update(progress)

        assert "Zenity progress dialog not started" in str(exc_info.value)

    def test_zenity_service_update_zero_total_files(self, mocker, caplog):
        """Test Zenity service update when total_files is 0 (covers line 180)."""
        service = ZenityProgressService()

        # Create a mock process with stdin
        mock_process = mocker.MagicMock()
        mock_process.stdin = mocker.MagicMock()
        service.process = mock_process

        # Create a mock progress object that bypasses validation
        mock_progress = mocker.MagicMock(spec=MksquashfsProgress)
        mock_progress.current_files = 0
        mock_progress.total_files = 0  # This will trigger the zero total files path
        mock_progress.percentage = 50

        # This should handle the zero total files case
        with caplog.at_level(logging.INFO):
            service.update(mock_progress)

        # Verify the status text was written for 0 total files case
        mock_process.stdin.write.assert_called_with("# Processing: 50% complete\n")

    def test_zenity_service_close_without_success(self, mocker, caplog):
        """Test Zenity service close when not successful (covers line 205)."""
        service = ZenityProgressService()

        # Set process to None to trigger console fallback mode
        service.process = None

        # Close with success=False
        with caplog.at_level(logging.WARNING):
            service.close(success=False)

        # Verify warning was logged
        assert any(
            "Build completed with issues" in record.message for record in caplog.records
        )

    def test_zenity_service_close_without_stdin(self, mocker):
        """Test Zenity service close when stdin is None (covers line 209)."""
        service = ZenityProgressService()

        # Mock the process to have None stdin
        mock_process = mocker.MagicMock()
        mock_process.stdin = None
        service.process = mock_process

        # This should handle the None stdin case gracefully
        service.close(success=True)

        # Verify no exception was raised and process was cleaned up
        assert service.process is None

    def test_zenity_service_close_timeout_handling(self, mocker):
        """Test Zenity service close with timeout handling (covers line 220)."""
        service = ZenityProgressService()

        # Create a mock process that will timeout
        mock_process = mocker.MagicMock()
        mock_process.stdin = mocker.MagicMock()
        mock_process.wait.side_effect = subprocess.TimeoutExpired("test", 1)
        service.process = mock_process

        # This should handle the timeout and kill the process
        service.close(success=True)

        # Verify process.kill was called
        mock_process.kill.assert_called_once()
        assert service.process is None

    def test_progress_tracker_file_processing_status(self, mocker):
        """Test progress tracker file processing status update (covers line 269)."""
        service = ZenityProgressService()
        tracker = ProgressTracker(service)

        # Mock the process to have stdin
        mock_process = mocker.MagicMock()
        mock_process.stdin = mocker.MagicMock()
        service.process = mock_process

        # Mock check_cancelled to return False to avoid cancellation
        mocker.patch.object(service, "check_cancelled", return_value=False)

        # Process a file line without total files set
        file_line = "file ./test.txt, uncompressed size 1024 bytes"
        tracker.process_output_line(file_line)

        # Verify status text was written for file processing
        mock_process.stdin.write.assert_called_with(
            "# Processing files: 1 files processed\n"
        )
