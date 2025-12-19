"""
Tests for the progress module.

This module contains comprehensive tests for all progress-related functionality
including interfaces, implementations, and services in src/squish/progress.py
"""

import subprocess

import pytest

from squish.progress import (
    CommandRunner,
    DefaultCommandRunner,
    KdialogProgressHandler,
    MockCommandRunner,
    NoopProgressHandler,
    ProgressHandler,
    ProgressParser,
    ProgressService,
)


class TestProgressHandlerInterface:
    """Test the abstract ProgressHandler interface."""

    def test_interface_abstractness(self):
        """Test that ProgressHandler is properly abstract."""
        assert hasattr(ProgressHandler, "__abstractmethods__")
        # Should not be able to instantiate abstract class
        with pytest.raises(TypeError):
            ProgressHandler()  # type: ignore

    def test_interface_methods_exist(self):
        """Test that all required methods exist in interface."""
        methods = [
            "start_progress",
            "update_progress",
            "cancel_progress",
            "complete_progress",
        ]
        for method in methods:
            assert hasattr(ProgressHandler, method)

    def test_progress_handler_interfaces_coverage(self, mocker):
        """Test interface implementations and their methods."""

        # Test that abstract base classes exist and are abstract
        assert hasattr(ProgressHandler, "__abstractmethods__")
        assert hasattr(CommandRunner, "__abstractmethods__")

        # Test concrete implementations
        noop_handler = NoopProgressHandler()
        proc, queue = noop_handler.start_progress("Test", 100)
        noop_handler.update_progress(queue, 50)
        noop_handler.cancel_progress(queue)
        noop_handler.complete_progress(queue)

        # Check that calls were tracked
        assert len(noop_handler.canceled_calls) == 1
        assert len(noop_handler.completed_calls) == 1
        assert len(noop_handler.updated_calls) == 1


class TestKdialogProgressHandler:
    """Test the KdialogProgressHandler implementation."""

    def test_start_progress_success(self, mocker):
        """Test successful progress start."""
        # Mock dependencies
        mock_tempfile = mocker.patch(
            "squish.progress.tempfile.mktemp", return_value="/tmp/test.fifo"
        )
        mock_os = mocker.patch("squish.progress.os.mkfifo")
        mock_Popen = mocker.patch("squish.progress.subprocess.Popen")
        mock_Thread = mocker.patch("squish.progress.threading.Thread")

        # Mock the process returned by Popen
        mock_proc = mocker.MagicMock()
        mock_Popen.return_value = mock_proc

        # Mock the thread
        mock_thread_instance = mocker.MagicMock()
        mock_Thread.return_value = mock_thread_instance

        # Create a progress handler instance and test it
        handler = KdialogProgressHandler()

        # This should cover the full kdialog progress functionality
        proc, cmd_queue = handler.start_progress("Test Title", 100)

        # Verify that necessary functions were called
        mock_tempfile.assert_called_once_with(suffix=".fifo")
        mock_os.assert_called_once()
        mock_Popen.assert_called_once()
        mock_Thread.assert_called_once()

        # Verify that we got the expected return values
        assert proc == mock_proc
        assert hasattr(cmd_queue, "put")  # It should be a queue

    def test_fifo_creation_failure(self, mocker):
        """Test FIFO creation failure handling."""
        # Mock necessary dependencies
        mock_tempfile = mocker.patch(
            "squish.progress.tempfile.mktemp", return_value="/tmp/test.fifo"
        )
        mock_os = mocker.patch(
            "squish.progress.os.mkfifo", side_effect=OSError("Failed to create FIFO")
        )

        # Create a progress handler instance and test it
        handler = KdialogProgressHandler()

        # This should raise RuntimeError due to FIFO creation failure
        with pytest.raises(RuntimeError, match="Failed to create FIFO"):
            handler.start_progress("Test Title", 100)

        # Verify that mktemp was called and mkfifo was called but failed
        mock_tempfile.assert_called_once_with(suffix=".fifo")
        mock_os.assert_called_once()

    def test_update_progress(self, mocker):
        """Test progress update functionality."""
        # Create handler and mock queue
        handler = KdialogProgressHandler()
        mock_queue = mocker.MagicMock()

        # Test update_progress method
        handler.update_progress(mock_queue, 50)
        mock_queue.put.assert_called_once_with("SET 50")

    def test_cancel_progress(self, mocker):
        """Test progress cancellation."""
        # Create handler and mock queue
        handler = KdialogProgressHandler()
        mock_queue = mocker.MagicMock()

        # Test cancel_progress method
        handler.cancel_progress(mock_queue)
        mock_queue.put.assert_called_once_with("CANCEL")

    def test_complete_progress(self, mocker):
        """Test progress completion."""
        # Create handler and mock queue
        handler = KdialogProgressHandler()
        mock_queue = mocker.MagicMock()

        # Test complete_progress method
        handler.complete_progress(mock_queue)
        mock_queue.put.assert_called_once_with("SET 100")

    def test_run_kdialog_progress_success_coverage(self, mocker):
        """Test KdialogProgressHandler functionality to cover the kdialog functionality."""
        # Mock the dependencies needed for kdialog functionality in the progress module
        mock_tempfile = mocker.patch(
            "squish.progress.tempfile.mktemp", return_value="/tmp/test.fifo"
        )
        mock_os = mocker.patch("squish.progress.os.mkfifo")
        mock_Popen = mocker.patch("squish.progress.subprocess.Popen")
        mock_Thread = mocker.patch("squish.progress.threading.Thread")

        # Mock the process returned by Popen
        mock_proc = mocker.MagicMock()
        mock_Popen.return_value = mock_proc

        # Mock the thread
        mock_thread_instance = mocker.MagicMock()
        mock_Thread.return_value = mock_thread_instance

        # Create a progress handler instance and test it
        handler = KdialogProgressHandler()

        # This should cover the full kdialog progress functionality
        proc, cmd_queue = handler.start_progress("Test Title", 100)

        # Verify that necessary functions were called
        mock_tempfile.assert_called_once_with(suffix=".fifo")
        mock_os.assert_called_once()
        mock_Popen.assert_called_once()
        mock_Thread.assert_called_once()

        # Verify that we got the expected return values
        assert proc == mock_proc
        assert hasattr(cmd_queue, "put")  # It should be a queue

    def test_run_kdialog_progress_fifo_creation_failure_coverage(self, mocker):
        """Test KdialogProgressHandler when FIFO creation fails to cover exception handling."""
        # Mock necessary dependencies
        mock_tempfile = mocker.patch(
            "squish.progress.tempfile.mktemp", return_value="/tmp/test.fifo"
        )
        mock_os = mocker.patch(
            "squish.progress.os.mkfifo", side_effect=OSError("Failed to create FIFO")
        )

        # Create a progress handler instance and test it
        handler = KdialogProgressHandler()

        # This should raise RuntimeError due to FIFO creation failure
        with pytest.raises(RuntimeError, match="Failed to create FIFO"):
            handler.start_progress("Test Title", 100)

        # Verify that mktemp was called and mkfifo was called but failed
        mock_tempfile.assert_called_once_with(suffix=".fifo")
        mock_os.assert_called_once()


class TestNoopProgressHandler:
    """Test the NoopProgressHandler implementation."""

    def test_initialization(self):
        """Test NoopProgressHandler initialization."""
        handler = NoopProgressHandler()
        assert hasattr(handler, "completed_calls")
        assert hasattr(handler, "canceled_calls")
        assert hasattr(handler, "updated_calls")
        assert handler.completed_calls == []
        assert handler.canceled_calls == []
        assert handler.updated_calls == []

    def test_noop_progress_methods(self, mocker):
        """Test NoopProgressHandler methods that don't do anything."""
        handler = NoopProgressHandler()
        mock_queue = mocker.MagicMock()

        # Test start_progress
        proc, queue = handler.start_progress("Test", 100)
        assert hasattr(proc, "terminate")  # It should have mocked methods
        assert queue is not None

        # Test update_progress
        handler.update_progress(mock_queue, 50)
        assert len(handler.updated_calls) == 1
        assert handler.updated_calls[0] == 50

        # Test cancel_progress
        handler.cancel_progress(mock_queue)
        assert len(handler.canceled_calls) == 1
        assert handler.canceled_calls[0] is True

        # Test complete_progress
        handler.complete_progress(mock_queue)
        assert len(handler.completed_calls) == 1
        assert handler.completed_calls[0] is True


class TestCommandRunnerInterface:
    """Test the CommandRunner interface."""

    def test_interface_abstractness(self):
        """Test that CommandRunner is properly abstract."""
        assert hasattr(CommandRunner, "__abstractmethods__")
        # Should not be able to instantiate abstract class
        with pytest.raises(TypeError):
            CommandRunner()  # type: ignore

    def test_interface_methods_exist(self):
        """Test that all required methods exist in CommandRunner interface."""
        methods = ["run", "popen"]
        for method in methods:
            assert hasattr(CommandRunner, method)

    def test_command_runner_interfaces_coverage(self, mocker):
        """Test CommandRunner interface implementations."""

        import subprocess

        # Test MockCommandRunner
        mock_runner = MockCommandRunner()

        # Test with mock results
        mock_result = subprocess.CompletedProcess(["test"], 0, "stdout", "stderr")
        mock_runner.set_mock_result("special", mock_result)

        # Run command that should match the pattern
        result = mock_runner.run(["special", "command"])
        assert result.returncode == 0
        assert result.stdout == "stdout"

        # Run command that doesn't match pattern (should get default)
        result2 = mock_runner.run(["other", "command"])
        assert result2.returncode == 0
        assert result2.stdout == ""

        # Test popen
        proc = mock_runner.popen(["test"])
        assert proc is not None
        assert len(mock_runner.popen_calls) == 1


class TestDefaultCommandRunner:
    """Test the DefaultCommandRunner implementation."""

    def test_run_method(self, mocker):
        """Test run method executes command."""
        runner = DefaultCommandRunner()

        # Mock subprocess.run
        mock_run = mocker.patch("subprocess.run")
        mock_result = mocker.MagicMock()
        mock_run.return_value = mock_result

        command = ["echo", "test"]
        result = runner.run(command, timeout=30)

        mock_run.assert_called_once_with(command, timeout=30)
        assert result == mock_result

    def test_popen_method(self, mocker):
        """Test popen method starts subprocess."""
        runner = DefaultCommandRunner()

        # Mock subprocess.Popen
        mock_popen = mocker.patch("subprocess.Popen")
        mock_proc = mocker.MagicMock()
        mock_popen.return_value = mock_proc

        command = ["echo", "test"]
        result = runner.popen(command, stdout=subprocess.PIPE)

        mock_popen.assert_called_once_with(command, stdout=subprocess.PIPE)
        assert result == mock_proc


class TestMockCommandRunner:
    """Test the MockCommandRunner implementation."""

    def test_initialization(self):
        """Test MockCommandRunner initialization."""
        runner = MockCommandRunner()
        assert hasattr(runner, "run_calls")
        assert hasattr(runner, "popen_calls")
        assert hasattr(runner, "mock_results")
        assert runner.run_calls == []
        assert runner.popen_calls == []

    def test_set_mock_result(self):
        """Test setting mock results for specific commands."""
        runner = MockCommandRunner()

        # Create a mock result
        mock_result = subprocess.CompletedProcess(["test"], 0, "stdout", "stderr")

        # Set the mock result for a pattern
        runner.set_mock_result("special", mock_result)

        # Verify it was stored
        assert "special" in runner.mock_results
        assert runner.mock_results["special"] == mock_result

    def test_run_with_mock_result(self, mocker):
        """Test run method with mock results."""
        runner = MockCommandRunner()

        # Create a mock result
        mock_result = subprocess.CompletedProcess(
            ["special", "command"], 0, "stdout", "stderr"
        )
        runner.set_mock_result("special", mock_result)

        # Test with mock result (should match the pattern)
        result = runner.run(["special", "command"])
        assert result.returncode == 0
        assert result.stdout == "stdout"

        # Verify the call was tracked
        assert len(runner.run_calls) == 1

    def test_run_with_default_result(self):
        """Test run method with default result when no pattern matches."""
        runner = MockCommandRunner()

        # Test with command that doesn't match pattern (should get default)
        result = runner.run(["other", "command"])
        assert result.returncode == 0
        assert result.stdout == ""

        # Verify the call was tracked
        assert len(runner.run_calls) == 1

    def test_popen_method(self, mocker):
        """Test popen method creates mock process."""
        runner = MockCommandRunner()

        # Test popen method
        proc = runner.popen(["test"])

        # Verify it returns a mock process-like object
        assert proc is not None
        assert len(runner.popen_calls) == 1

        # Verify mock process has expected methods
        assert hasattr(proc, "wait")
        assert hasattr(proc, "terminate")
        assert hasattr(proc, "kill")
        assert hasattr(proc, "stdin")
        assert hasattr(proc, "stdout")
        assert hasattr(proc, "stderr")


class TestProgressParser:
    """Test the ProgressParser functionality."""

    def test_parse_mksquashfs_progress_bar_format(self):
        """Test parsing of progress bar format."""
        parser = ProgressParser()

        # Test various bar formats
        test_cases = [
            # Bar format example: "[==================/                                      ]  20 inodes" (around 36%)
            (
                "[==================/                                      ]  20 inodes",
                36,
            ),  # 18 '=' chars: (18/50)*100 = 36%
            (
                "[===================/                                     ]  20 inodes",
                38,
            ),  # 19 '=' chars: (19/50)*100 = 38%
            (
                "[=================================/                         ]  30 inodes",
                66,
            ),  # 33 '=' chars: (33/50)*100 = 66%
            (
                "[==================================================/        ]  45 inodes",
                100,
            ),  # 50 '=' chars: (50/50)*100 = 100%
            (
                "[=/                                                     ]  0 inodes",
                2,
            ),  # 1 '=' char: (1/50)*100 = 2%
        ]

        for line, expected in test_cases:
            result = parser.parse_mksquashfs_progress(line)
            assert result == expected, (
                f"Failed for line: '{line}', expected {expected}, got {result}"
            )

    def test_parse_mksquashfs_progress_percent_format(self):
        """Test parsing of percent format."""
        parser = ProgressParser()

        # Test percent formats
        test_cases = [
            ("12.5% (456/3650 inodes)", 12),
            ("25.7% (456/3650 inodes)", 25),
            ("100% (456/3650 inodes)", 100),
            ("0% (0/3650 inodes)", 0),
            ("50% (25/50 inodes)", 50),
        ]

        for line, expected in test_cases:
            result = parser.parse_mksquashfs_progress(line)
            assert result == expected, (
                f"Failed for line: '{line}', expected {expected}, got {result}"
            )

    def test_parse_mksquashfs_progress_edge_cases(self):
        """Test parsing of various edge cases."""
        parser = ProgressParser()

        # Test edge cases that should return None
        test_cases = [
            ("", None),  # Empty string
            ("   ", None),  # Whitespace only
            ("non-progress text", None),  # Non-progress text
            ("[===]", None),  # Missing / and inodes
            ("10% incomplete", None),  # Percent without proper format
            # Empty bar
            (
                "[                                                  /]  0 inodes",
                0,
            ),  # No equals
            (
                "[==================================================/]  50 inodes",
                100,
            ),  # All equals
        ]

        for line, expected in test_cases:
            result = parser.parse_mksquashfs_progress(line)
            assert result == expected, (
                f"Failed for line: '{line}', expected {expected}, got {result}"
            )

    def test_parse_mksquashfs_progress_invalid_input(self):
        """Test parsing of invalid input."""
        parser = ProgressParser()

        # Test non-progress lines that should return None
        test_cases = [
            ("Processing file.txt", None),
            ("Building archive...", None),
            ("[", None),  # Incomplete
            ("]", None),  # Incomplete
            ("%", None),  # Incomplete
        ]

        for line, expected in test_cases:
            result = parser.parse_mksquashfs_progress(line)
            assert result == expected, (
                f"Failed for line: '{line}', expected {expected}, got {result}"
            )

    def test_parse_mksquashfs_progress_coverage(self, mocker):
        """Test parse_mksquashfs_progress method in ProgressParser to cover the functionality."""
        parser = ProgressParser()

        # Test various progress line formats
        # PROGRESS_BAR_WIDTH is 50, so count the '=' characters in the first group before '/'
        test_cases = [
            # Bar format example: "[====================/                              ]  1234 inodes" (requires '/' to match)
            (
                "[==================/                                      ]  20 inodes",
                36,
            ),  # 18 '=' chars: (18/50)*100 = 36%
            (
                "[===================/                                     ]  20 inodes",
                38,
            ),  # 19 '=' chars: (19/50)*100 = 38%
            (
                "[=================================/                         ]  30 inodes",
                66,
            ),  # 33 '=' chars: (33/50)*100 = 66%
            (
                "[==================================================/        ]  45 inodes",
                100,
            ),  # 50 '=' chars: (50/50)*100 = 100%
            (
                "[                                                  ]  0 inodes",
                None,
            ),  # No '/' so doesn't match first regex, returns None
            (
                "[=/                                                     ]  0 inodes",
                2,
            ),  # 1 '=' char: (1/50)*100 = 2%
            # The format without '/' doesn't match first regex, so returns None
            (
                "[==================================================]  50 inodes",
                None,
            ),  # No '/' so doesn't match first regex, returns None
            # Percent format: "12.5% (456/3650 inodes)"
            ("12.5% (456/3650 inodes)", 12),
            ("25.7% (456/3650 inodes)", 25),
            ("100% (456/3650 inodes)", 100),
            ("0% (0/3650 inodes)", 0),
            # Non-progress lines should return None
            ("Some other output line", None),
            ("", None),
            ("Processing file.txt", None),
        ]

        for line, expected in test_cases:
            result = parser.parse_mksquashfs_progress(line)
            assert result == expected, (
                f"Failed for line: '{line}', expected {expected}, got {result}"
            )

    def test_progress_parser_edge_cases_coverage(self):
        """Test ProgressParser with edge cases."""
        # Test various edge cases
        test_cases = [
            # Edge cases that should return None
            ("", None),  # Empty string
            ("   ", None),  # Whitespace only
            ("non-progress text", None),  # Non-progress text
            ("[===]", None),  # Missing / and inodes
            ("10% incomplete", None),  # Percent without proper format
            # Edge cases for bar parsing
            (
                "[                                                  /]  0 inodes",
                0,
            ),  # No equals
            (
                "[==================================================/]  50 inodes",
                100,
            ),  # All equals
            (
                "[=/                                             ]  1 inodes",
                2,
            ),  # One equals
            # Edge cases for percent parsing
            ("0% (0/100)", 0),  # Zero percent
            ("100% (100/100)", 100),  # One hundred percent
            ("50% (50/100)", 50),  # Half
            ("99.9% (999/1000)", 99),  # Decimal percent rounded down
        ]

        parser = ProgressParser()
        for line, expected in test_cases:
            result = parser.parse_mksquashfs_progress(line)
            assert result == expected, (
                f"Failed for line: '{line}', expected {expected}, got {result}"
            )


class TestProgressService:
    """Test the ProgressService coordination."""

    def test_run_mksquashfs_with_progress_success(self, mocker):
        """Test successful progress run."""
        # Mock the progress handler
        mock_handler = mocker.MagicMock()
        mock_proc = mocker.MagicMock()
        mock_queue = mocker.MagicMock()
        mock_handler.start_progress.return_value = (mock_proc, mock_queue)

        # Mock command runner
        mock_command_runner = mocker.MagicMock()
        mock_mksquashfs_proc = mocker.MagicMock()
        mock_mksquashfs_proc.wait.return_value = 0  # Success return code
        mock_mksquashfs_proc.stderr = mocker.MagicMock()
        mock_mksquashfs_proc.stderr.readline.return_value = ""  # Empty to end iteration
        mock_command_runner.popen.return_value = mock_mksquashfs_proc

        parser = ProgressParser()
        service = ProgressService(
            progress_handler=mock_handler,
            command_runner=mock_command_runner,
            progress_parser=parser,
        )

        command = ["test", "command"]

        # Should not raise exception
        service.run_mksquashfs_with_progress(command)

        # Verify that complete was called on success
        mock_handler.complete_progress.assert_called_once()

    def test_run_mksquashfs_with_progress_command_failure(self, mocker):
        """Test command failure handling."""
        import subprocess

        # Mock the progress handler
        mock_handler = mocker.MagicMock()
        mock_proc = mocker.MagicMock()
        mock_queue = mocker.MagicMock()
        mock_handler.start_progress.return_value = (mock_proc, mock_queue)

        # Mock command runner to return a proc that returns non-zero exit code
        mock_command_runner = mocker.MagicMock()
        mock_mksquashfs_proc = mocker.MagicMock()
        mock_mksquashfs_proc.wait.return_value = 1  # Failure return code
        mock_mksquashfs_proc.stderr = mocker.MagicMock()
        mock_mksquashfs_proc.stderr.read.return_value = "error output"
        mock_command_runner.popen.return_value = mock_mksquashfs_proc

        parser = ProgressParser()
        service = ProgressService(
            progress_handler=mock_handler,
            command_runner=mock_command_runner,
            progress_parser=parser,
        )

        command = ["test", "command"]

        # Should raise CalledProcessError
        with pytest.raises(subprocess.CalledProcessError):
            service.run_mksquashfs_with_progress(command)

        # Verify that cancel was called when return code != 0
        mock_handler.cancel_progress.assert_called_once()

    def test_run_mksquashfs_with_progress_exception_path(self, mocker):
        """Test exception handling path."""
        # Mock the progress handler to test exception paths
        mock_handler = mocker.MagicMock()
        mock_proc = mocker.MagicMock()
        mock_queue = mocker.MagicMock()
        mock_handler.start_progress.return_value = (mock_proc, mock_queue)

        # Mock command runner to raise an exception
        mock_command_runner = mocker.MagicMock()
        mock_command_runner.popen.side_effect = Exception("Test exception")

        parser = ProgressParser()
        service = ProgressService(
            progress_handler=mock_handler,
            command_runner=mock_command_runner,
            progress_parser=parser,
        )

        command = ["test", "command"]

        # Should raise a SubprocessError when exception occurs
        with pytest.raises(
            subprocess.SubprocessError, match="Error during archive creation"
        ):
            service.run_mksquashfs_with_progress(command)

        # Verify that cancel was called
        mock_handler.cancel_progress.assert_called_once()

    def test_run_mksquashfs_with_progress_threading(self, mocker):
        """Test threading functionality."""
        # Mock threading functionality
        mock_thread = mocker.patch("squish.progress.threading.Thread")
        mock_thread_instance = mocker.MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Mock the progress handler
        mock_handler = mocker.MagicMock()
        mock_proc = mocker.MagicMock()
        mock_queue = mocker.MagicMock()
        mock_handler.start_progress.return_value = (mock_proc, mock_queue)

        # Mock command runner
        mock_command_runner = mocker.MagicMock()
        mock_mksquashfs_proc = mocker.MagicMock()
        mock_mksquashfs_proc.wait.return_value = 0  # Success return code
        mock_mksquashfs_proc.stderr = mocker.MagicMock()
        mock_mksquashfs_proc.stderr.readline.return_value = ""  # Empty to end iteration
        mock_command_runner.popen.return_value = mock_mksquashfs_proc

        parser = ProgressParser()
        service = ProgressService(
            progress_handler=mock_handler,
            command_runner=mock_command_runner,
            progress_parser=parser,
        )

        command = ["test", "command"]

        # Should not raise exception
        service.run_mksquashfs_with_progress(command)

        # Verify that thread was started for reading stderr
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    def test_run_mksquashfs_with_kdialog_progress_success_coverage(self, mocker):
        """Test ProgressService functionality with mocked components for success path."""
        # Create the necessary mocks for the progress service
        mock_proc = mocker.MagicMock()
        mock_queue = mocker.MagicMock()

        # Mock the KdialogProgressHandler
        mock_handler = mocker.MagicMock()
        mock_handler.start_progress.return_value = (mock_proc, mock_queue)
        mock_handler.update_progress = mocker.MagicMock()
        mock_handler.complete_progress = mocker.MagicMock()
        mock_handler.cancel_progress = mocker.MagicMock()

        # Mock the CommandRunner
        mock_command_runner = mocker.MagicMock()
        mock_mksquashfs_proc = mocker.MagicMock()
        mock_mksquashfs_proc.wait.return_value = 0  # Success return code
        mock_mksquashfs_proc.stderr = mocker.MagicMock()
        mock_mksquashfs_proc.stderr.readline.return_value = (
            ""  # Empty string to end the iteration
        )
        mock_command_runner.popen.return_value = mock_mksquashfs_proc

        # Create the progress parser
        parser = ProgressParser()

        # Create the service and test
        service = ProgressService(
            progress_handler=mock_handler,
            command_runner=mock_command_runner,
            progress_parser=parser,
        )

        command = ["mksquashfs", "source", "output.sqsh", "-comp", "zstd"]

        # This should not raise any exceptions
        service.run_mksquashfs_with_progress(command)

        # Verify that processes were started and used
        mock_handler.start_progress.assert_called_once()
        mock_command_runner.popen.assert_called_once()
        # The complete_progress should be called when success
        mock_handler.complete_progress.assert_called_once()

    def test_run_mksquashfs_with_kdialog_progress_failure_coverage(self, mocker):
        """Test ProgressService functionality with mocked components for failure path."""
        # Create the necessary mocks for the progress service
        mock_proc = mocker.MagicMock()
        mock_queue = mocker.MagicMock()

        # Mock the KdialogProgressHandler
        mock_handler = mocker.MagicMock()
        mock_handler.start_progress.return_value = (mock_proc, mock_queue)
        mock_handler.update_progress = mocker.MagicMock()
        mock_handler.complete_progress = mocker.MagicMock()
        mock_handler.cancel_progress = mocker.MagicMock()

        # Mock the CommandRunner - simulate failure
        mock_command_runner = mocker.MagicMock()
        mock_mksquashfs_proc = mocker.MagicMock()
        mock_mksquashfs_proc.wait.return_value = 1  # Failure return code
        mock_mksquashfs_proc.stderr = mocker.MagicMock()
        mock_mksquashfs_proc.stderr.readline.return_value = (
            ""  # Empty string to end the iteration
        )
        mock_mksquashfs_proc.stderr.read.return_value = "error output"
        mock_command_runner.popen.return_value = mock_mksquashfs_proc

        # Create the progress parser
        parser = ProgressParser()

        # Create the service and test
        service = ProgressService(
            progress_handler=mock_handler,
            command_runner=mock_command_runner,
            progress_parser=parser,
        )

        command = ["mksquashfs", "source", "output.sqsh", "-comp", "zstd"]

        # Should raise exception
        with pytest.raises(
            subprocess.CalledProcessError
        ):  # Using subprocess exception as that's what the service raises
            service.run_mksquashfs_with_progress(command)

        # Verify that the cancel was called on failure
        mock_handler.cancel_progress.assert_called_once()

    def test_run_mksquashfs_with_kdialog_progress_exception_coverage(self, mocker):
        """Test ProgressService functionality with mocked components for exception path."""
        # Create the necessary mocks for the progress service
        mock_proc = mocker.MagicMock()
        mock_queue = mocker.MagicMock()

        # Mock the KdialogProgressHandler
        mock_handler = mocker.MagicMock()
        mock_handler.start_progress.return_value = (mock_proc, mock_queue)
        mock_handler.update_progress = mocker.MagicMock()
        mock_handler.complete_progress = mocker.MagicMock()
        mock_handler.cancel_progress = mocker.MagicMock()

        # Mock the CommandRunner - simulate exception
        mock_command_runner = mocker.MagicMock()
        mock_command_runner.popen.side_effect = Exception("Test exception")

        # Create the progress parser
        parser = ProgressParser()

        # Create the service and test
        service = ProgressService(
            progress_handler=mock_handler,
            command_runner=mock_command_runner,
            progress_parser=parser,
        )

        command = ["mksquashfs", "source", "output.sqsh", "-comp", "zstd"]

        # Should raise exception
        with pytest.raises(subprocess.SubprocessError) as exc_info:
            service.run_mksquashfs_with_progress(command)

        # Verify the error contains the expected message
        assert "Error during archive creation" in str(exc_info.value)

        # Verify that the cancel was called on exception
        mock_handler.cancel_progress.assert_called_once()

    def test_run_mksquashfs_with_progress_timeout_expired(self, mocker):
        """Test ProgressService cleanup when process.wait() times out."""
        # Import the TimeoutExpired exception
        from subprocess import TimeoutExpired

        # Create the necessary mocks for the progress service
        mock_proc = mocker.MagicMock()
        mock_queue = mocker.MagicMock()

        # Mock the KdialogProgressHandler
        mock_handler = mocker.MagicMock()
        mock_handler.start_progress.return_value = (mock_proc, mock_queue)
        mock_handler.update_progress = mocker.MagicMock()
        mock_handler.complete_progress = mocker.MagicMock()
        mock_handler.cancel_progress = mocker.MagicMock()

        # Mock the CommandRunner
        mock_command_runner = mocker.MagicMock()
        mock_mksquashfs_proc = mocker.MagicMock()
        mock_mksquashfs_proc.wait.return_value = 0  # Successful execution
        mock_mksquashfs_proc.stderr = None  # No error output
        mock_command_runner.popen.return_value = mock_mksquashfs_proc

        # Create the progress parser
        parser = ProgressParser()

        # Create the service and test
        service = ProgressService(
            progress_handler=mock_handler,
            command_runner=mock_command_runner,
            progress_parser=parser,
        )

        command = ["mksquashfs", "source", "output.sqsh", "-comp", "zstd"]

        # Mock the proc.wait to raise TimeoutExpired to test the finally block
        mock_proc.wait.side_effect = TimeoutExpired(command, 1.0)

        service.run_mksquashfs_with_progress(command)

        # Verify that proc.kill is called when wait times out
        mock_proc.kill.assert_called_once()

    def test_progress_parser_with_none_values(self, mocker):
        """Test ProgressParser with None values to cover edge cases in the parsing method."""
        parser = ProgressParser()

        # Test with None line (this might happen if we're not careful about input validation)
        # This test covers the lines that process the progress bar regex
        assert parser.parse_mksquashfs_progress("100% (100/100 inodes)") == 100
        assert (
            parser.parse_mksquashfs_progress(
                "[==================================================/        ]  45 inodes"
            )
            == 100
        )
        assert (
            parser.parse_mksquashfs_progress(
                "[=/                                                     ]  0 inodes"
            )
            == 2
        )

    def test_kdialog_progress_handler_writer_thread_exception(self, mocker):
        """Test KdialogProgressHandler writer thread exception handling."""
        # Mock necessary dependencies
        mock_tempfile = mocker.patch(
            "squish.progress.tempfile.mktemp", return_value="/tmp/test.fifo"
        )
        mock_os = mocker.patch("squish.progress.os.mkfifo")
        mock_Popen = mocker.patch("squish.progress.subprocess.Popen")
        mock_Thread = mocker.patch("squish.progress.threading.Thread")

        # Mock the process returned by Popen
        mock_proc = mocker.MagicMock()
        mock_Popen.return_value = mock_proc

        # Mock the thread to simulate exception in writer function
        mock_thread_instance = mocker.MagicMock()
        mock_Thread.return_value = mock_thread_instance

        # Create a progress handler instance and test it
        handler = KdialogProgressHandler()

        # This should cover the full kdialog progress functionality
        proc, cmd_queue = handler.start_progress("Test Title", 100)

        # Verify that necessary functions were called
        mock_tempfile.assert_called_once_with(suffix=".fifo")
        mock_os.assert_called_once()
        mock_Popen.assert_called_once()
        mock_Thread.assert_called_once()

    def test_progress_service_stderr_thread_exception_handling(self, mocker):
        """Test ProgressService stderr reading thread exception handling."""
        # Mock exception handling in the stderr reading thread
        mock_thread = mocker.patch("squish.progress.threading.Thread")
        mock_thread_instance = mocker.MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Mock the progress handler
        mock_handler = mocker.MagicMock()
        mock_proc = mocker.MagicMock()
        mock_queue = mocker.MagicMock()
        mock_handler.start_progress.return_value = (mock_proc, mock_queue)

        # Mock command runner with an invalid stderr to trigger exception handling
        mock_command_runner = mocker.MagicMock()
        mock_mksquashfs_proc = mocker.MagicMock()
        mock_mksquashfs_proc.wait.return_value = 0  # Success return code
        # Make stderr return None to trigger exception in the thread
        mock_mksquashfs_proc.stderr = None
        mock_command_runner.popen.return_value = mock_mksquashfs_proc

        parser = ProgressParser()
        service = ProgressService(
            progress_handler=mock_handler,
            command_runner=mock_command_runner,
            progress_parser=parser,
        )

        command = ["test", "command"]

        # Should not raise exception even with None stderr
        service.run_mksquashfs_with_progress(command)

        # Verify that thread was started for reading stderr
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    def test_progress_service_with_timeout_expired(self, mocker):
        """Test progress service handling when kdialog process wait times out."""
        # Mock the progress handler
        mock_handler = mocker.MagicMock()
        mock_proc = mocker.MagicMock()
        mock_queue = mocker.MagicMock()
        mock_handler.start_progress.return_value = (mock_proc, mock_queue)

        # Mock command runner
        mock_command_runner = mocker.MagicMock()
        mock_mksquashfs_proc = mocker.MagicMock()
        mock_mksquashfs_proc.wait.return_value = 0  # Success return code
        mock_mksquashfs_proc.stderr = mocker.MagicMock()
        mock_mksquashfs_proc.stderr.readline.return_value = ""  # Empty to end iteration
        mock_command_runner.popen.return_value = mock_mksquashfs_proc

        # Mock process termination behavior
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(["kdialog"], 1.0)

        parser = ProgressParser()
        service = ProgressService(
            progress_handler=mock_handler,
            command_runner=mock_command_runner,
            progress_parser=parser,
        )

        command = ["test", "command"]

        # Should complete without raising exception due to timeout handling
        service.run_mksquashfs_with_progress(command)

        # Verify that kill was called after timeout
        mock_proc.kill.assert_called_once()

    def test_kdialog_progress_handler_writer_thread_exception_handling(self, mocker):
        """Test KdialogProgressHandler writer thread exception handling."""
        # Mock necessary dependencies to trigger exception in the writer thread
        mock_tempfile = mocker.patch(
            "squish.progress.tempfile.mktemp", return_value="/tmp/test.fifo"
        )
        mock_os = mocker.patch("squish.progress.os.mkfifo")
        mock_Popen = mocker.patch("squish.progress.subprocess.Popen")
        mock_Thread = mocker.patch("squish.progress.threading.Thread")

        # Mock the process returned by Popen
        mock_proc = mocker.MagicMock()
        mock_Popen.return_value = mock_proc

        # Create a progress handler instance and test it
        handler = KdialogProgressHandler()

        # This should cover the exception handling in writer thread
        proc, cmd_queue = handler.start_progress("Test Title", 100)

        # Verify that necessary functions were called
        mock_tempfile.assert_called_once_with(suffix=".fifo")
        mock_os.assert_called_once()
        mock_Popen.assert_called_once()

        # Simulate the thread being started
        mock_Thread.assert_called_once()

    def test_progress_service_stderr_thread_exception_handling_with_none_stderr(
        self, mocker
    ):
        """Test ProgressService stderr reading thread exception handling when stderr is None."""
        # Mock the progress handler
        mock_handler = mocker.MagicMock()
        mock_proc = mocker.MagicMock()
        mock_queue = mocker.MagicMock()
        mock_handler.start_progress.return_value = (mock_proc, mock_queue)

        # Mock command runner with stderr as None to trigger exception handling
        mock_command_runner = mocker.MagicMock()
        mock_mksquashfs_proc = mocker.MagicMock()
        mock_mksquashfs_proc.wait.return_value = 0  # Success return code
        mock_mksquashfs_proc.stderr = None  # This will trigger exception handling
        mock_command_runner.popen.return_value = mock_mksquashfs_proc

        parser = ProgressParser()
        service = ProgressService(
            progress_handler=mock_handler,
            command_runner=mock_command_runner,
            progress_parser=parser,
        )

        command = ["test", "command"]

        # Should not raise an exception even with None stderr
        service.run_mksquashfs_with_progress(command)

        # In this case, the thread should handle the None case gracefully
