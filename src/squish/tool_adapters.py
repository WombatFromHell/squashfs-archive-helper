"""
Tool-specific adapters for the SquashFS Archive Helper.

This module provides adapter classes for external tools (mksquashfs, unsquashfs, etc.)
to abstract command execution and provide a consistent interface.
"""

from abc import ABC, abstractmethod
from typing import Optional

from .command_executor import ICommandExecutor
from .config import SquishFSConfig
from .errors import (
    ChecksumError,
    MksquashfsCommandExecutionError,
    UnsquashfsCommandExecutionError,
    UnsquashfsExtractCommandExecutionError,
)
from .progress import (
    BuildProgressState,
    ExtractProgressState,
    IProgressObserver,
)


class IToolAdapter(ABC):
    """Base interface for all tool adapters."""

    @abstractmethod
    def __init__(self, executor: ICommandExecutor, config: SquishFSConfig):
        """Initialize the tool adapter."""
        pass


class IMksquashfsAdapter(ABC):
    """Interface for mksquashfs tool adapter."""

    @abstractmethod
    def build(
        self,
        sources: list[str],
        output: str,
        excludes: list[str],
        compression: str,
        block_size: str,
        processors: int,
        progress_observer: Optional[IProgressObserver] = None,
    ) -> None:
        """Build a SquashFS archive using mksquashfs."""
        pass

    @abstractmethod
    def build_with_progress(
        self,
        sources: list[str],
        output: str,
        excludes: list[str],
        compression: str,
        block_size: str,
        processors: int,
        progress_observer: Optional[IProgressObserver] = None,
    ) -> BuildProgressState:
        """Build a SquashFS archive with progress tracking."""
        pass


class IUnsquashfsAdapter(ABC):
    """Interface for unsquashfs tool adapter."""

    @abstractmethod
    def extract(
        self,
        archive: str,
        output_dir: str,
        xattr_flags: list[str],
        progress_observer: Optional[IProgressObserver] = None,
    ) -> None:
        """Extract a SquashFS archive using unsquashfs."""
        pass

    @abstractmethod
    def extract_with_progress(
        self,
        archive: str,
        output_dir: str,
        xattr_flags: list[str],
        progress_observer: Optional[IProgressObserver] = None,
    ) -> ExtractProgressState:
        """Extract a SquashFS archive with progress tracking."""
        pass

    @abstractmethod
    def list_contents(self, archive: str) -> None:
        """List contents of a SquashFS archive using unsquashfs."""
        pass


class ISha256sumAdapter(ABC):
    """Interface for sha256sum tool adapter."""

    @abstractmethod
    def generate_checksum(self, file_path: str) -> str:
        """Generate SHA256 checksum for a file."""
        pass

    @abstractmethod
    def verify_checksum(self, file_path: str, checksum_file: str) -> bool:
        """Verify file checksum against a checksum file."""
        pass


class IZenityAdapter(ABC):
    """Interface for Zenity progress dialog adapter."""

    @abstractmethod
    def start_progress_dialog(self, title: str = "Processing") -> None:
        """Start a Zenity progress dialog."""
        pass

    @abstractmethod
    def update_progress(self, percentage: int, status: str = "") -> None:
        """Update the progress dialog."""
        pass

    @abstractmethod
    def check_cancelled(self) -> bool:
        """Check if the user cancelled the progress dialog."""
        pass

    @abstractmethod
    def close_progress_dialog(self) -> None:
        """Close the progress dialog."""
        pass


class MksquashfsAdapter(IMksquashfsAdapter):
    """Concrete implementation of mksquashfs tool adapter."""

    def __init__(self, executor: ICommandExecutor, config: SquishFSConfig):
        self.executor = executor
        self.config = config

    def build(
        self,
        sources: list[str],
        output: str,
        excludes: list[str],
        compression: str,
        block_size: str,
        processors: int,
        progress_observer: Optional[IProgressObserver] = None,
    ) -> None:
        """Build a SquashFS archive using mksquashfs."""
        command = (
            ["mksquashfs"]
            + sources
            + [
                output,
                "-comp",
                compression,
                "-b",
                block_size,
                "-processors",
                str(processors),
                "-info",  # Show file processing for progress estimation
                "-keep-as-directory",  # Keep source directory structure intact
            ]
            + excludes
        )

        try:
            self.executor.execute(command, check=True)
        except Exception as e:
            raise MksquashfsCommandExecutionError(
                "mksquashfs", getattr(e, "returncode", 1), str(e)
            )

    def build_with_progress(
        self,
        sources: list[str],
        output: str,
        excludes: list[str],
        compression: str,
        block_size: str,
        processors: int,
        progress_observer: Optional[IProgressObserver] = None,
    ) -> BuildProgressState:
        """Build a SquashFS archive with progress tracking."""
        # This would be implemented with progress parsing
        # For now, just call the basic build method
        self.build(sources, output, excludes, compression, block_size, processors)
        return BuildProgressState()


class UnsquashfsAdapter(IUnsquashfsAdapter):
    """Concrete implementation of unsquashfs tool adapter."""

    def __init__(self, executor: ICommandExecutor, config: SquishFSConfig):
        self.executor = executor
        self.config = config

    def extract(
        self,
        archive: str,
        output_dir: str,
        xattr_flags: list[str],
        progress_observer: Optional[IProgressObserver] = None,
    ) -> None:
        """Extract a SquashFS archive using unsquashfs."""
        if output_dir == ".":
            command = ["unsquashfs", "-i"] + xattr_flags + [archive]
        else:
            command = ["unsquashfs", "-i", "-d", output_dir] + xattr_flags + [archive]

        try:
            self.executor.execute(command, check=True, text=True)
        except Exception as e:
            raise UnsquashfsExtractCommandExecutionError(
                "unsquashfs", getattr(e, "returncode", 1), str(e)
            )

    def extract_with_progress(
        self,
        archive: str,
        output_dir: str,
        xattr_flags: list[str],
        progress_observer: Optional[IProgressObserver] = None,
    ) -> ExtractProgressState:
        """Extract a SquashFS archive with progress tracking."""
        # This would be implemented with progress parsing
        # For now, just call the basic extract method
        self.extract(archive, output_dir, xattr_flags)
        return ExtractProgressState()

    def list_contents(self, archive: str) -> None:
        """List contents of a SquashFS archive using unsquashfs."""
        command = ["unsquashfs", "-llc", archive]

        try:
            self.executor.execute(command, check=True, capture_output=True, text=True)
        except Exception as e:
            raise UnsquashfsCommandExecutionError(
                "unsquashfs", getattr(e, "returncode", 1), str(e)
            )


class Sha256sumAdapter(ISha256sumAdapter):
    """Concrete implementation of sha256sum tool adapter."""

    def __init__(self, executor: ICommandExecutor, config: SquishFSConfig):
        self.executor = executor
        self.config = config

    def generate_checksum(self, file_path: str) -> str:
        """Generate SHA256 checksum for a file."""
        command = ["sha256sum", file_path]

        try:
            result = self.executor.execute(
                command, check=True, capture_output=True, text=True
            )
            # Extract checksum from output (format: "checksum  filename")
            return result.stdout.strip().split()[0]
        except Exception as e:
            raise ChecksumError(f"Failed to generate checksum: {e}")

    def verify_checksum(self, file_path: str, checksum_file: str) -> bool:
        """Verify file checksum against a checksum file."""
        command = ["sha256sum", "-c", str(checksum_file)]

        try:
            result = self.executor.execute(
                command, check=True, capture_output=True, text=True
            )
            # Check if verification was successful
            return "OK" in result.stdout
        except Exception as e:
            raise ChecksumError(f"Checksum verification failed: {e}")


class ZenityAdapter(IZenityAdapter):
    """Concrete implementation of Zenity progress dialog adapter."""

    def __init__(self, executor: ICommandExecutor, config: SquishFSConfig):
        self.executor = executor
        self.config = config
        self.process = None

    def start_progress_dialog(self, title: str = "Processing") -> None:
        """Start a Zenity progress dialog."""
        # Launch zenity with auto-kill and auto-close
        command = [
            "zenity",
            "--progress",
            "--title",
            title,
            "--text",
            "Starting...",
            "--percentage",
            "0",
            "--auto-kill",
            "--auto-close",
        ]

        try:
            # Start zenity as a subprocess with stdin pipe for progress updates
            import subprocess

            self.process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception:
            # Zenity not available - this is not an error, just fall back to console
            self.process = None

    def update_progress(self, percentage: int, status: str = "") -> None:
        """Update the progress dialog."""
        if self.process and self.process.stdin:
            # Zenity expects percentage followed by optional status text
            if status:
                self.process.stdin.write(f"{percentage}\n#{status}\n")
            else:
                self.process.stdin.write(f"{percentage}\n")
            self.process.stdin.flush()

    def check_cancelled(self) -> bool:
        """Check if the user cancelled the progress dialog."""
        if self.process:
            # Check if process has terminated
            return self.process.poll() is not None
        return False

    def close_progress_dialog(self) -> None:
        """Close the progress dialog."""
        if self.process:
            if self.process.stdin:
                # Send 100% to close the dialog
                self.process.stdin.write("100\n")
                self.process.stdin.flush()
                self.process.stdin.close()
            # Wait for process to terminate
            self.process.wait()
            self.process = None


class MockMksquashfsAdapter(IMksquashfsAdapter):
    """Mock implementation of mksquashfs adapter for testing."""

    def __init__(self, *args, **kwargs):
        self.build_calls = []
        self.build_with_progress_calls = []

    def build(
        self,
        sources: list[str],
        output: str,
        excludes: list[str],
        compression: str,
        block_size: str,
        processors: int,
        progress_observer: Optional[IProgressObserver] = None,
    ) -> None:
        """Mock build method."""
        self.build_calls.append(
            {
                "sources": sources,
                "output": output,
                "excludes": excludes,
                "compression": compression,
                "block_size": block_size,
                "processors": processors,
            }
        )

    def build_with_progress(
        self,
        sources: list[str],
        output: str,
        excludes: list[str],
        compression: str,
        block_size: str,
        processors: int,
        progress_observer: Optional[IProgressObserver] = None,
    ) -> BuildProgressState:
        """Mock build with progress method."""
        self.build_with_progress_calls.append(
            {
                "sources": sources,
                "output": output,
                "excludes": excludes,
                "compression": compression,
                "block_size": block_size,
                "processors": processors,
            }
        )
        return BuildProgressState()


class MockUnsquashfsAdapter(IUnsquashfsAdapter):
    """Mock implementation of unsquashfs adapter for testing."""

    def __init__(self, *args, **kwargs):
        self.extract_calls = []
        self.extract_with_progress_calls = []
        self.list_calls = []

    def extract(
        self,
        archive: str,
        output_dir: str,
        xattr_flags: list[str],
        progress_observer: Optional[IProgressObserver] = None,
    ) -> None:
        """Mock extract method."""
        self.extract_calls.append(
            {
                "archive": archive,
                "output_dir": output_dir,
                "xattr_flags": xattr_flags,
            }
        )

    def extract_with_progress(
        self,
        archive: str,
        output_dir: str,
        xattr_flags: list[str],
        progress_observer: Optional[IProgressObserver] = None,
    ) -> ExtractProgressState:
        """Mock extract with progress method."""
        self.extract_with_progress_calls.append(
            {
                "archive": archive,
                "output_dir": output_dir,
                "xattr_flags": xattr_flags,
            }
        )
        return ExtractProgressState()

    def list_contents(self, archive: str) -> None:
        """Mock list contents method."""
        self.list_calls.append({"archive": archive})


class MockSha256sumAdapter(ISha256sumAdapter):
    """Mock implementation of sha256sum adapter for testing."""

    def __init__(self, *args, **kwargs):
        self.generate_calls = []
        self.verify_calls = []
        self.mock_checksums = {}

    def generate_checksum(self, file_path: str) -> str:
        """Mock checksum generation."""
        self.generate_calls.append({"file_path": file_path})
        # Return a mock checksum based on file path
        return f"mock_checksum_{file_path}"

    def verify_checksum(self, file_path: str, checksum_file: str) -> bool:
        """Mock checksum verification."""
        self.verify_calls.append(
            {"file_path": file_path, "checksum_file": checksum_file}
        )
        # Return True if we have a matching mock checksum
        return file_path in self.mock_checksums


class MockZenityAdapter(IZenityAdapter):
    """Mock implementation of Zenity adapter for testing."""

    def __init__(self, *args, **kwargs):
        self.start_calls = []
        self.update_calls = []
        self.check_calls = []
        self.close_calls = []
        self.cancelled = False

    def start_progress_dialog(self, title: str = "Processing") -> None:
        """Mock start progress dialog."""
        self.start_calls.append({"title": title})

    def update_progress(self, percentage: int, status: str = "") -> None:
        """Mock update progress."""
        self.update_calls.append({"percentage": percentage, "status": status})

    def check_cancelled(self) -> bool:
        """Mock check cancelled."""
        self.check_calls.append({})
        return self.cancelled

    def close_progress_dialog(self) -> None:
        """Mock close progress dialog."""
        self.close_calls.append({})

    def set_cancelled(self, cancelled: bool = True) -> None:
        """Set cancelled state for testing."""
        self.cancelled = cancelled
