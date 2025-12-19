"""
Progress handling functionality for SquashFS operations with kdialog.

This module contains interfaces and implementations for progress tracking
that can be easily mocked for testing.
"""

import os
import re
import subprocess
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from queue import Empty, Queue
from typing import Optional, Tuple


class ProgressHandler(ABC):
    """
    Abstract interface for progress handling during operations.
    """

    @abstractmethod
    def start_progress(
        self, title: str, max_val: int
    ) -> Tuple[subprocess.Popen, Queue]:
        """
        Start progress and return (process, command_queue).
        Send "SET <n>" or "CANCEL" to command_queue.
        """

    @abstractmethod
    def update_progress(self, command_queue, value: int) -> None:
        """Update progress value."""

    @abstractmethod
    def cancel_progress(self, command_queue) -> None:
        """Cancel progress."""

    @abstractmethod
    def complete_progress(self, command_queue) -> None:
        """Complete progress."""


class KdialogProgressHandler(ProgressHandler):
    """
    Progress handler that uses kdialog for GUI progress display.
    """

    def start_progress(
        self, title: str = "Progress", max_val: int = 100
    ) -> Tuple[subprocess.Popen, Queue]:
        """
        Launch `kdialog --progressbar` in background.
        Returns (process, command_queue) — send "SET <n>" or "CANCEL" to queue.
        """
        fifo = Path(tempfile.mktemp(suffix=".fifo"))
        try:
            os.mkfifo(fifo)
        except OSError as e:
            raise RuntimeError(f"Failed to create FIFO: {e}") from e

        # Start kdialog
        proc = subprocess.Popen(
            [
                "kdialog",
                "--progressbar",
                title,
                str(max_val),
                "--title",
                "SquashFS Progress",
            ],
            stdin=subprocess.PIPE,
            stdout=open(fifo, "w"),
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        # Command queue for thread-safe communication
        cmd_q = Queue()

        def writer():
            """Thread that reads from queue and writes to kdialog's stdin (via FIFO)."""
            try:
                with open(fifo, "r") as f:
                    while True:
                        try:
                            # Wait up to 0.5s for command — allows quick exit
                            cmd = cmd_q.get(timeout=0.5)
                            if cmd == "CANCEL":
                                break
                            f.write(cmd + "\n")
                            f.flush()
                        except Empty:
                            continue
            except (OSError, ValueError):
                pass  # FIFO closed or broken

        threading.Thread(target=writer, daemon=True, name="KDialogWriter").start()
        return proc, cmd_q

    def update_progress(self, command_queue, value: int) -> None:
        """Update progress value."""
        command_queue.put(f"SET {value}")

    def cancel_progress(self, command_queue) -> None:
        """Cancel progress."""
        command_queue.put("CANCEL")

    def complete_progress(self, command_queue) -> None:
        """Complete progress by setting to 100%."""
        command_queue.put("SET 100")


class NoopProgressHandler(ProgressHandler):
    """
    Progress handler that does nothing - useful for testing.
    """

    def __init__(self):
        self.completed_calls = []
        self.canceled_calls = []
        self.updated_calls = []

    def start_progress(
        self, title: str = "Progress", max_val: int = 100
    ) -> Tuple[subprocess.Popen, Queue]:
        """Start progress and return a mock process and queue."""
        # For testing, return a mock process and queue
        # Since we're not actually creating a subprocess, return a mocked Popen
        from unittest.mock import MagicMock

        mock_proc = MagicMock()
        mock_proc.terminate = lambda: None
        mock_proc.wait = lambda timeout=None: None
        mock_proc.kill = lambda: None
        mock_queue = Queue()
        return mock_proc, mock_queue

    def update_progress(self, command_queue, value: int) -> None:
        """Track progress updates."""
        self.updated_calls.append(value)

    def cancel_progress(self, command_queue) -> None:
        """Track progress cancellations."""
        self.canceled_calls.append(True)

    def complete_progress(self, command_queue) -> None:
        """Track progress completions."""
        self.completed_calls.append(True)


class CommandRunner(ABC):
    """
    Abstract interface for command execution that can be mocked for testing.
    """

    @abstractmethod
    def run(self, command: list, **kwargs) -> subprocess.CompletedProcess:
        """Execute a command and return result."""

    @abstractmethod
    def popen(self, command: list, **kwargs) -> subprocess.Popen:
        """Start a subprocess and return Popen object."""


class DefaultCommandRunner(CommandRunner):
    """
    Default command runner that executes commands using subprocess.
    """

    def run(self, command: list, **kwargs) -> subprocess.CompletedProcess:
        """Execute a command and return result."""
        return subprocess.run(command, **kwargs)

    def popen(self, command: list, **kwargs) -> subprocess.Popen:
        """Start a subprocess and return Popen object."""
        return subprocess.Popen(command, **kwargs)


class MockCommandRunner(CommandRunner):
    """
    Mock command runner for testing - tracks calls and can simulate results.
    """

    def __init__(self):
        self.run_calls = []
        self.popen_calls = []
        self.mock_results = {}

    def set_mock_result(
        self, command_pattern: str, result: subprocess.CompletedProcess
    ):
        """Set a mock result for commands matching a pattern."""
        self.mock_results[command_pattern] = result

    def run(self, command: list, **kwargs) -> subprocess.CompletedProcess:
        """Track the command and return either a mock result or a default."""
        self.run_calls.append((command, kwargs))

        # Look for matching mock result
        for pattern, result in self.mock_results.items():
            if pattern in " ".join(command):
                return result

        # Return a default success result
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    def popen(self, command: list, **kwargs) -> subprocess.Popen:
        """Track the command and return a mock process."""
        self.popen_calls.append((command, kwargs))

        # Create a mock Popen object using MagicMock to ensure proper type compatibility
        from unittest.mock import MagicMock

        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.wait = lambda timeout=None: 0
        mock_proc.terminate = lambda: None
        mock_proc.kill = lambda: None
        mock_proc.stdin = MagicMock()
        mock_proc.stdin.write = lambda x: None
        mock_proc.stdin.flush = lambda: None
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.read = lambda: ""
        mock_proc.stdout.readline = lambda: ""
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read = lambda: ""
        mock_proc.stderr.readline = lambda: ""
        return mock_proc


class ProgressParser:
    """
    Parse progress information from command output, specifically mksquashfs.
    """

    def parse_mksquashfs_progress(self, line: str) -> Optional[int]:
        """
        Parse mksquashfs -progress output.

        Examples:
          "[====================/                              ]  1234 inodes"
          "12.5% (456/3650 inodes)"
        Returns percent (0-100), or None if not progress line.
        """
        line = line.strip()

        # Define PROGRESS_BAR_WIDTH constant (standard width for mksquashfs progress bar)
        PROGRESS_BAR_WIDTH = 50  # Standard width based on typical mksquashfs output

        # Method 1: Parse bar (most reliable during scanning/compression)
        bar_match = re.search(r"\[([= ]*)/([= ]*)\]\s+\d+\s+inodes", line)
        if bar_match:
            done = len(bar_match.group(1).rstrip())
            return min(100, max(0, int((done / PROGRESS_BAR_WIDTH) * 100)))

        # Method 2: Parse percent (appears later in compression)
        pct_match = re.search(r"^(\d+(?:\.\d+)?)%\s*\(", line)
        if pct_match:
            return min(100, max(0, int(float(pct_match.group(1)))))

        return None


class ProgressService:
    """
    Service that coordinates progress handling, command execution, and progress parsing.
    """

    def __init__(
        self,
        progress_handler: ProgressHandler,
        command_runner: CommandRunner,
        progress_parser: ProgressParser,
    ):
        self.progress_handler = progress_handler
        self.command_runner = command_runner
        self.progress_parser = progress_parser

    def run_mksquashfs_with_progress(self, command: list) -> None:
        """Run mksquashfs command with kdialog progress bar."""
        # Start the kdialog progress bar
        proc, cmd_queue = self.progress_handler.start_progress(
            "Building SquashFS Archive", 100
        )

        try:
            # Start mksquashfs with stdout and stderr captured so we can parse progress
            mksquashfs_proc = self.command_runner.popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            def read_stderr():
                try:
                    if mksquashfs_proc.stderr is None:
                        return
                    for line in iter(mksquashfs_proc.stderr.readline, ""):
                        if line is None:
                            break
                        # Parse the progress from the line
                        progress = self.progress_parser.parse_mksquashfs_progress(line)
                        if progress is not None:
                            # Send progress update to kdialog
                            self.progress_handler.update_progress(cmd_queue, progress)
                except (AttributeError, TypeError):
                    # Handle errors that can occur when mocking
                    pass

            # Start thread to read stderr
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()

            # Wait for mksquashfs to complete
            return_code = mksquashfs_proc.wait()

            # Wait for stderr thread to finish
            stderr_thread.join(timeout=1)

            if return_code != 0:
                # Send cancel to kdialog if mksquashfs failed
                self.progress_handler.cancel_progress(cmd_queue)
                stderr_output = (
                    mksquashfs_proc.stderr.read()
                    if mksquashfs_proc.stderr
                    and hasattr(mksquashfs_proc.stderr, "read")
                    else ""
                )
                raise subprocess.CalledProcessError(
                    return_code, command, stderr=stderr_output
                )
            else:
                # Set progress to 100% to indicate completion
                self.progress_handler.complete_progress(cmd_queue)

        except subprocess.CalledProcessError:
            # Re-raise CalledProcessError as-is since it's a known error type
            raise
        except Exception as e:
            self.progress_handler.cancel_progress(cmd_queue)
            raise subprocess.SubprocessError(f"Error during archive creation: {str(e)}")
        finally:
            # Clean up kdialog process
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
