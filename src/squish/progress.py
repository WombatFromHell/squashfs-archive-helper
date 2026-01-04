"""
Progress parsing and Zenity integration for mksquashfs build operations.

This module provides functionality for parsing mksquashfs progress output
and integrating with Zenity progress dialogs.
"""

import logging
import re
import subprocess
from dataclasses import dataclass
from typing import Optional

# Import observer pattern components
from .observer import IProgressObserver, OperationType, ProgressInfo, ProgressState


class ProgressParseError(Exception):
    """Exception raised when progress parsing fails."""

    pass


class BuildCancelledError(Exception):
    """Exception raised when build is cancelled by user."""

    pass


class ExtractCancelledError(Exception):
    """Exception raised when extract is cancelled by user."""

    pass


@dataclass(frozen=True)
class MksquashfsProgress:
    """Immutable data class representing mksquashfs progress information."""

    current_files: int
    total_files: int
    percentage: int

    def __post_init__(self):
        """Validate the progress data."""
        if not (0 <= self.percentage <= 100):
            raise ValueError(f"Percentage must be between 0-100, got {self.percentage}")
        if self.current_files < 0:
            raise ValueError(f"Current files must be >= 0, got {self.current_files}")
        if self.total_files <= 0:
            raise ValueError(f"Total files must be > 0, got {self.total_files}")
        if self.current_files > self.total_files:
            raise ValueError(
                f"Current files ({self.current_files}) cannot exceed total files ({self.total_files})"
            )


@dataclass(frozen=True)
class UnsquashfsProgress:
    """Immutable data class representing unsquashfs progress information."""

    current_files: int
    total_files: int
    percentage: int

    def __post_init__(self):
        """Validate the progress data."""
        if not (0 <= self.percentage <= 100):
            raise ValueError(f"Percentage must be between 0-100, got {self.percentage}")
        if self.current_files < 0:
            raise ValueError(f"Current files must be >= 0, got {self.current_files}")
        if self.total_files <= 0:
            raise ValueError(f"Total files must be > 0, got {self.total_files}")
        if self.current_files > self.total_files:
            raise ValueError(
                f"Current files ({self.current_files}) cannot exceed total files ({self.total_files})"
            )


# Regex patterns for parsing mksquashfs progress output
PROGRESS_PATTERN = re.compile(r"^\s*\[[=\s|/]+\]\s+(\d+)/(\d+)\s+(\d+)%\s*$")

PERCENTAGE_PATTERN = re.compile(r"^\s*(\d+)/(\d+)\s+(\d+)%\s*$")

# Pattern for parsing file processing output (used for progress estimation)
FILE_PATTERN = re.compile(
    r"^\s*file\s+(.+?)\s*,\s*uncompressed\s+size\s+(\d+)\s+bytes\s*$"
)

# Regex patterns for parsing unsquashfs progress output
UNSQUASHFS_PERCENTAGE_PATTERN = re.compile(r"^\s*(\d+)%?\s*$")

UNSQUASHFS_FILE_PATTERN = re.compile(
    r"^\s*(\d+)\s+inodes\s+\((\d+)\s+blocks\)\s+to\s+write\s*$"
)

UNSQUASHFS_CREATED_PATTERN = re.compile(r"^\s*created\s+(\d+)\s+files\s*$")


class UnifiedProgressParser:
    """
    Unified progress parser that implements squish.sh parsing logic.

    This class provides a unified interface for parsing both mksquashfs
    and unsquashfs progress output, matching the behavior of squish.sh.
    """

    def __init__(self):
        self.total_inodes = 0
        self.operation_type = None

    def parse_unsquashfs_progress(self, line: str) -> Optional[UnsquashfsProgress]:
        """
        Parse unsquashfs progress output matching squish.sh behavior.

        Args:
            line: A line of output from unsquashfs

        Returns:
            UnsquashfsProgress object if progress info found, None otherwise

        Raises:
            ProgressParseError: If the line contains progress info but parsing fails
        """
        # Regex 1: Parse Header for Total Inodes (Strict match)
        # Example: "5767 inodes (35882 blocks) to write"
        inodes_match = re.match(r"^\s*(\d+)\s+inodes\s+\(.*\)\s+to\s+write\s*$", line)
        if inodes_match:
            try:
                self.total_inodes = int(inodes_match.group(1))
                return None  # Header line, no progress to report
            except (ValueError, IndexError) as e:
                raise ProgressParseError(
                    f"Failed to parse total inodes from line '{line}': {e}"
                )

        # Regex 2: Parse Progress Lines (squish.sh format)
        # Example: "123/5767 2%"
        progress_match = re.match(r"^\s*(\d+)/(\d+)\s+(\d+)%\s*$", line)
        if progress_match:
            try:
                current_files = int(progress_match.group(1))
                total_files = int(progress_match.group(2))
                percentage = int(progress_match.group(3))

                # Use the header total if we found it, otherwise use the total from the line
                display_total = (
                    self.total_inodes if self.total_inodes > 0 else total_files
                )

                return UnsquashfsProgress(
                    current_files=current_files,
                    total_files=display_total,
                    percentage=percentage,
                )
            except (ValueError, IndexError) as e:
                raise ProgressParseError(
                    f"Failed to parse progress from line '{line}': {e}"
                )

        # Regex 3: Parse simple percentage format for backward compatibility
        # Example: "50%"
        percentage_match = UNSQUASHFS_PERCENTAGE_PATTERN.match(line)
        if percentage_match:
            try:
                percentage = int(percentage_match.group(1))
                # Estimate current files based on percentage and stored total_inodes
                if self.total_inodes > 0:
                    current_files = int((percentage / 100) * self.total_inodes)
                    return UnsquashfsProgress(
                        current_files=current_files,
                        total_files=self.total_inodes,
                        percentage=percentage,
                    )
                else:
                    # Can't determine current files without total_inodes
                    return None
            except (ValueError, IndexError) as e:
                raise ProgressParseError(
                    f"Failed to parse percentage progress from line '{line}': {e}"
                )

        # Regex 4: Parse created files format for backward compatibility
        # Example: "created 50 files"
        created_match = UNSQUASHFS_CREATED_PATTERN.match(line)
        if created_match:
            try:
                created_files = int(created_match.group(1))
                # Ignore zero files (initial state)
                if created_files == 0:
                    return None
                # Estimate progress based on created files
                if self.total_inodes > 0:
                    percentage = min(99, int((created_files / self.total_inodes) * 100))
                    return UnsquashfsProgress(
                        current_files=created_files,
                        total_files=self.total_inodes,
                        percentage=percentage,
                    )
                else:
                    # Can't determine percentage without total_inodes
                    return None
            except (ValueError, IndexError) as e:
                raise ProgressParseError(
                    f"Failed to parse created files progress from line '{line}': {e}"
                )

        return None

    def parse_mksquashfs_progress(
        self, line: str, total_files: int = 0
    ) -> Optional[MksquashfsProgress]:
        """
        Parse mksquashfs progress output matching squish.sh behavior.

        Args:
            line: A line of output from mksquashfs
            total_files: Total number of files (for progress calculation)

        Returns:
            MksquashfsProgress object if progress info found, None otherwise

        Raises:
            ProgressParseError: If the line contains progress info but parsing fails
        """
        # First try the squish.sh simple format: Integer or Integer%
        # Example: "50" or "50%"
        simple_match = re.match(r"^\s*(\d+)%?\s*$", line)
        if simple_match:
            try:
                percentage = int(simple_match.group(1))

                if total_files > 0:
                    current_files = int((total_files * percentage) / 100)
                    return MksquashfsProgress(
                        current_files=current_files,
                        total_files=total_files,
                        percentage=percentage,
                    )
                else:
                    # Can't determine current files without total
                    return MksquashfsProgress(
                        current_files=0,
                        total_files=1,  # Placeholder to avoid validation error
                        percentage=percentage,
                    )
            except (ValueError, IndexError) as e:
                raise ProgressParseError(
                    f"Failed to parse progress from line '{line}': {e}"
                )

        # Also try the original complex format for backward compatibility
        # Example: "[=====] 10/100  50%"
        complex_match = PROGRESS_PATTERN.match(line)
        if not complex_match:
            complex_match = PERCENTAGE_PATTERN.match(line)

        if complex_match:
            try:
                current_files = int(complex_match.group(1))
                total_files_from_line = int(complex_match.group(2))
                percentage = int(complex_match.group(3))

                # Use provided total_files if available and matches the line's total
                # Otherwise use the total from the line (more accurate for progress parsing)
                if total_files > 0 and total_files == total_files_from_line:
                    actual_total_files = total_files
                else:
                    actual_total_files = total_files_from_line

                return MksquashfsProgress(
                    current_files=current_files,
                    total_files=actual_total_files,
                    percentage=percentage,
                )
            except (ValueError, IndexError) as e:
                raise ProgressParseError(
                    f"Failed to parse progress from line '{line}': {e}"
                )

        return None


def parse_mksquashfs_progress(line: str) -> Optional[MksquashfsProgress]:
    """
    Parse mksquashfs progress output and extract progress information.

    Args:
        line: A line of output from mksquashfs

    Returns:
        MksquashfsProgress object if progress info found, None otherwise

    Raises:
        ProgressParseError: If the line contains progress info but parsing fails
    """
    # Try standard progress bar format first
    match = PROGRESS_PATTERN.match(line)
    if not match:
        # Try percentage-only format
        match = PERCENTAGE_PATTERN.match(line)

    if match:
        try:
            current_files = int(match.group(1))
            total_files = int(match.group(2))
            percentage = int(match.group(3))

            return MksquashfsProgress(
                current_files=current_files,
                total_files=total_files,
                percentage=percentage,
            )
        except (ValueError, IndexError) as e:
            raise ProgressParseError(
                f"Failed to parse progress from line '{line}': {e}"
            )

    return None


def parse_unsquashfs_progress(
    line: str, total_files: int
) -> Optional[UnsquashfsProgress]:
    """
    Parse unsquashfs progress output and extract progress information.

    Args:
        line: A line of output from unsquashfs
        total_files: Total number of files in the archive (for progress calculation)

    Returns:
        UnsquashfsProgress object if progress info found, None otherwise

    Raises:
        ProgressParseError: If the line contains progress info but parsing fails
    """
    # Try percentage format first
    percentage_match = UNSQUASHFS_PERCENTAGE_PATTERN.match(line)
    if percentage_match:
        try:
            percentage = int(percentage_match.group(1))
            # Estimate current files based on percentage
            current_files = int((percentage / 100) * total_files)
            return UnsquashfsProgress(
                current_files=current_files,
                total_files=total_files,
                percentage=percentage,
            )
        except (ValueError, IndexError) as e:
            raise ProgressParseError(
                f"Failed to parse percentage progress from line '{line}': {e}"
            )

    # Try file count pattern - but only if it's a progress update, not the initial summary
    # The initial "X inodes (Y blocks) to write" line should be ignored for progress tracking
    file_match = UNSQUASHFS_FILE_PATTERN.match(line)
    if file_match:
        try:
            inodes = int(file_match.group(1))
            # Ignore zero inodes (initial state)
            if inodes == 0:
                return None
            # Also ignore if inodes exceed total files (this is the initial summary line)
            if inodes > total_files:
                return None
            # For unsquashfs, inodes roughly correspond to files
            current_files = inodes
            percentage = min(99, int((current_files / total_files) * 100))
            return UnsquashfsProgress(
                current_files=current_files,
                total_files=total_files,
                percentage=percentage,
            )
        except (ValueError, IndexError) as e:
            raise ProgressParseError(
                f"Failed to parse file progress from line '{line}': {e}"
            )

    # Try created files pattern
    created_match = UNSQUASHFS_CREATED_PATTERN.match(line)
    if created_match:
        try:
            created_files = int(created_match.group(1))
            # Ignore zero files (initial state)
            if created_files == 0:
                return None
            percentage = min(99, int((created_files / total_files) * 100))
            return UnsquashfsProgress(
                current_files=created_files,
                total_files=total_files,
                percentage=percentage,
            )
        except (ValueError, IndexError) as e:
            raise ProgressParseError(
                f"Failed to parse created files progress from line '{line}': {e}"
            )

    return None


class ZenityProgressService(IProgressObserver):
    """
    Service for managing Zenity progress dialog.

    This class handles the Zenity progress dialog lifecycle and
    provides methods for updating progress and handling cancel events.
    Implements IProgressObserver interface for integration with observer pattern.
    """

    def __init__(self, title: str = "Building SquashFS"):
        self.title = title
        self.process: Optional[subprocess.Popen] = None
        self.cancelled = False
        self.logger = logging.getLogger(__name__)
        self._operation_type = None

    def start(self, initial_text: str = "Starting build..."):
        """Start the Zenity progress dialog."""
        if self.process is not None:
            raise RuntimeError("Zenity progress dialog already started")

        try:
            # Launch zenity with auto-kill and auto-close
            self.process = subprocess.Popen(
                [
                    "zenity",
                    "--progress",
                    "--title",
                    self.title,
                    "--text",
                    initial_text,
                    "--percentage",
                    "0",
                    "--auto-close",
                    "--auto-kill",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Send initial status text to ensure it's displayed properly
            # Zenity needs both percentage and status text to initialize correctly
            if self.process.stdin:
                self.process.stdin.write("0\n")  # Initial percentage
                self.process.stdin.write(f"# {initial_text}\n")  # Initial status text
                self.process.stdin.flush()

        except FileNotFoundError:
            # Zenity not available - fall back to console-only mode
            self.process = None
            self._fallback_mode = True
            self.logger.warning("Zenity not found, falling back to console progress")

    def update(self, progress):
        """Update the progress dialog with new progress information."""
        if self.process is None and not hasattr(self, "_fallback_mode"):
            raise RuntimeError("Zenity progress dialog not started")

        if self.process is None:
            # Console fallback mode - just log the progress
            self.logger.info(
                f"Progress: {progress.percentage}% ({progress.current_files}/{progress.total_files} files)"
            )
            return

        if self.process.stdin is None:
            raise RuntimeError("Zenity progress dialog not started")

        if self.cancelled:
            return

        # Send percentage to zenity
        self.process.stdin.write(f"{progress.percentage}\n")
        self.process.stdin.flush()

        # Send status text with more detailed information
        if progress.total_files > 0:
            status_text = (
                f"Processing files: {progress.current_files}/{progress.total_files} "
                f"({progress.percentage}%)"
            )
        else:
            status_text = f"Processing: {progress.percentage}% complete"

        self.process.stdin.write(f"# {status_text}\n")
        self.process.stdin.flush()

    def check_cancelled(self) -> bool:
        """Check if the user has cancelled the operation."""
        if self.process is None:
            # Console fallback mode - no cancellation possible
            return False

        # Check if zenity process has terminated (user clicked cancel)
        if self.process.poll() is not None:
            self.cancelled = True
            return True

        return False

    def close(self, success: bool = True):
        """Close the progress dialog."""
        if self.process is None:
            # Console fallback mode - nothing to close
            if success:
                self.logger.info("Build completed successfully")
            else:
                self.logger.warning("Build completed with issues")
            return

        try:
            if self.process.stdin:
                # Send 100% if successful
                if success:
                    try:
                        self.process.stdin.write("100\n")
                        self.process.stdin.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        # Zenity may have already closed the pipe - this is normal
                        pass
                try:
                    self.process.stdin.close()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    # Pipe may already be closed - this is normal during cleanup
                    pass
        except Exception:
            # Catch any other unexpected exceptions during cleanup
            pass

        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.process.kill()
        finally:
            self.process = None

    def on_progress_update(self, progress: ProgressInfo) -> None:
        """
        Handle progress updates from the observer pattern.

        Args:
            progress: ProgressInfo object containing progress information
        """
        if self.process is None and not hasattr(self, "_fallback_mode"):
            raise RuntimeError("Zenity progress dialog not started")

        if self.process is None:
            # Console fallback mode - just log the progress
            self.logger.info(
                f"Progress: {progress.percentage}% ({progress.current}/{progress.total})"
            )
            return

        if self.process.stdin is None:
            raise RuntimeError("Zenity progress dialog not started")

        if self.cancelled:
            return

        # Send percentage to zenity
        self.process.stdin.write(f"{progress.percentage}\n")
        self.process.stdin.flush()

        # Send status text with more detailed information
        if progress.total > 0:
            status_text = (
                f"{progress.operation_type.name}: {progress.current}/{progress.total} "
                f"({progress.percentage}%)"
            )
        else:
            status_text = (
                f"{progress.operation_type.name}: {progress.percentage}% complete"
            )

        self.process.stdin.write(f"# {status_text}\n")
        self.process.stdin.flush()

    def on_completion(self, progress: ProgressInfo, success: bool) -> None:
        """
        Handle operation completion from the observer pattern.

        Args:
            progress: ProgressInfo object containing final progress information
            success: Boolean indicating if operation completed successfully
        """
        self.close(success)
        if success:
            self.logger.info(f"{progress.operation_type.name} completed successfully")
        else:
            self.logger.warning(f"{progress.operation_type.name} completed with issues")

    def on_cancellation(self, progress: ProgressInfo) -> None:
        """
        Handle operation cancellation from the observer pattern.

        Args:
            progress: ProgressInfo object containing progress at cancellation time
        """
        self.close(success=False)
        self.logger.warning(f"{progress.operation_type.name} was cancelled")

    def on_error(self, progress: ProgressInfo, error: Exception) -> None:
        """
        Handle errors during operation from the observer pattern.

        Args:
            progress: ProgressInfo object containing progress at error time
            error: The exception that occurred
        """
        self.close(success=False)
        self.logger.error(f"{progress.operation_type.name} failed with error: {error}")

    def start_operation(
        self, operation_type: OperationType, initial_text: str = "Starting operation..."
    ):
        """
        Start a new operation and initialize the progress dialog.

        Args:
            operation_type: Type of operation being performed
            initial_text: Initial text to display in the progress dialog
        """
        self._operation_type = operation_type
        self.start(initial_text)


@dataclass(frozen=True)
class BuildProgressState:
    """Immutable build progress state."""

    last_progress: Optional[MksquashfsProgress] = None
    file_count: int = 0
    total_files: Optional[int] = None
    total_size: int = 0
    processed_size: int = 0


class ProgressTracker:
    """
    Progress tracker that uses the observer pattern and unified progress parser.

    This class manages the state of the build progress and
    coordinates between the parser and Zenity service using
    the observer pattern and unified progress parsing.
    """

    def __init__(self, zenity_service: ZenityProgressService):
        self.zenity_service = zenity_service
        self._state = BuildProgressState()
        self._parser = UnifiedProgressParser()

    def process_output_line(self, line: str):
        """Process a line of mksquashfs output with functional state updates."""
        # Use the unified parser to parse standard progress output
        progress = self._parser.parse_mksquashfs_progress(
            line, self._state.total_files or 0
        )
        if progress:
            new_state = self._update_with_progress(progress)
            self._state = new_state

            # Convert to ProgressInfo for observer pattern
            progress_info = ProgressInfo(
                operation_type=OperationType.BUILD,
                state=ProgressState.IN_PROGRESS,
                current=progress.current_files,
                total=progress.total_files,
                percentage=progress.percentage,
                message=f"Building: {progress.current_files}/{progress.total_files} files",
            )
            self.zenity_service.on_progress_update(progress_info)
            return

        # If no standard progress, try file-based progress estimation
        new_state = self._process_file_line_functional(line)
        if new_state != self._state:
            self._state = new_state

        if self.zenity_service.check_cancelled():
            raise BuildCancelledError("Build cancelled by user")

    def _update_with_progress(self, progress: MksquashfsProgress) -> BuildProgressState:
        """Pure function to update state with progress."""
        return BuildProgressState(
            last_progress=progress,
            file_count=self._state.file_count,
            total_files=self._state.total_files,
            total_size=self._state.total_size,
            processed_size=self._state.processed_size,
        )

    def _process_file_line_functional(self, line: str) -> BuildProgressState:
        """Pure function to process file lines and return new state."""
        # Check if this is a file processing line
        file_match = FILE_PATTERN.match(line)
        if not file_match:
            return self._state

        file_count = self._state.file_count + 1
        file_size = int(file_match.group(2))
        processed_size = self._state.processed_size + file_size

        # Estimate progress based on file count if we have total files
        if self._state.total_files is not None and self._state.total_files > 0:
            percentage = min(99, int((file_count / self._state.total_files) * 100))
            mock_progress = MksquashfsProgress(
                current_files=file_count,
                total_files=self._state.total_files,
                percentage=percentage,
            )

            # Update Zenity service with new progress
            self.zenity_service.update(mock_progress)

            return BuildProgressState(
                last_progress=mock_progress,
                file_count=file_count,
                total_files=self._state.total_files,
                total_size=self._state.total_size,
                processed_size=processed_size,
            )
        else:
            # We can't estimate progress yet, but we can update status
            status_text = f"Processing files: {file_count} files processed"
            if self.zenity_service.process and self.zenity_service.process.stdin:
                # Send a status update without changing percentage
                self.zenity_service.process.stdin.write(f"# {status_text}\n")
                self.zenity_service.process.stdin.flush()

            return BuildProgressState(
                last_progress=self._state.last_progress,
                file_count=file_count,
                total_files=self._state.total_files,
                total_size=self._state.total_size,
                processed_size=processed_size,
            )

    def set_total_files(self, total_files: int):
        """Functional update of total files."""
        self._state = BuildProgressState(
            last_progress=self._state.last_progress,
            file_count=self._state.file_count,
            total_files=total_files,
            total_size=self._state.total_size,
            processed_size=self._state.processed_size,
        )


@dataclass(frozen=True)
class ExtractProgressState:
    """Immutable extract progress state."""

    last_progress: Optional[UnsquashfsProgress] = None
    file_count: int = 0
    total_files: Optional[int] = None


class ExtractProgressTracker:
    """
    Extract progress tracker that uses the observer pattern and unified progress parser.

    This class manages the state of the extract progress and
    coordinates between the parser and Zenity service using
    the observer pattern and unified progress parsing.
    """

    def __init__(self, zenity_service: ZenityProgressService):
        self.zenity_service = zenity_service
        self._state = ExtractProgressState()
        self._parser = UnifiedProgressParser()

    def process_output_line(self, line: str):
        """Process a line of unsquashfs output with functional state updates."""
        progress_found = False

        # First try to parse standard progress output using unified parser
        progress = self._parser.parse_unsquashfs_progress(line)
        if progress:
            new_state = self._update_with_progress(progress)
            self._state = new_state

            # Convert to ProgressInfo for observer pattern
            progress_info = ProgressInfo(
                operation_type=OperationType.EXTRACT,
                state=ProgressState.IN_PROGRESS,
                current=progress.current_files,
                total=progress.total_files,
                percentage=progress.percentage,
                message=f"Extracting: {progress.current_files}/{progress.total_files} files",
            )
            self.zenity_service.on_progress_update(progress_info)
            progress_found = True

        # If no standard progress, try file-based progress estimation
        if not progress_found:
            new_state = self._process_file_line_functional(line)
            if new_state != self._state:
                self._state = new_state

        if self.zenity_service.check_cancelled():
            raise ExtractCancelledError("Extract cancelled by user")

    def _update_with_progress(
        self, progress: UnsquashfsProgress
    ) -> ExtractProgressState:
        """Pure function to update state with progress."""
        return ExtractProgressState(
            last_progress=progress,
            file_count=self._state.file_count,
            total_files=self._state.total_files,
        )

    def _process_file_line_functional(self, line: str) -> ExtractProgressState:
        """Pure function to process file lines and return new state."""
        # Check if this is a file creation line
        created_match = UNSQUASHFS_CREATED_PATTERN.match(line)
        if not created_match:
            return self._state

        try:
            created_files = int(created_match.group(1))
            # Ignore zero files (initial state)
            if created_files == 0:
                return self._state

            # Estimate progress based on file count if we have total files
            if self._state.total_files is not None and self._state.total_files > 0:
                percentage = min(
                    99, int((created_files / self._state.total_files) * 100)
                )

                # Create a mock progress object
                mock_progress = UnsquashfsProgress(
                    current_files=created_files,
                    total_files=self._state.total_files,
                    percentage=percentage,
                )

                # Update Zenity service with new progress
                self.zenity_service.update(mock_progress)

                return ExtractProgressState(
                    last_progress=mock_progress,
                    file_count=created_files,
                    total_files=self._state.total_files,
                )
            else:
                # Update file count but don't change progress
                return ExtractProgressState(
                    last_progress=self._state.last_progress,
                    file_count=created_files,
                    total_files=self._state.total_files,
                )
        except (ValueError, IndexError):
            # If we can't parse, just return current state
            return self._state

    def set_total_files(self, total_files: int):
        """Functional update of total files."""
        self._state = ExtractProgressState(
            last_progress=self._state.last_progress,
            file_count=self._state.file_count,
            total_files=total_files,
        )
