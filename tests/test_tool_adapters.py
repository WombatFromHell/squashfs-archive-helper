"""
Comprehensive tests for tool_adapters.py module.

This test file covers all adapter classes and their methods to ensure proper
test coverage and functionality.
"""

import subprocess

import pytest

from squish.command_executor import ICommandExecutor
from squish.config import SquishFSConfig
from squish.errors import (
    ChecksumError,
    MksquashfsCommandExecutionError,
    UnsquashfsCommandExecutionError,
    UnsquashfsExtractCommandExecutionError,
)
from squish.progress import BuildProgressState, ExtractProgressState
from squish.tool_adapters import (
    MksquashfsAdapter,
    MockMksquashfsAdapter,
    MockSha256sumAdapter,
    MockUnsquashfsAdapter,
    MockZenityAdapter,
    Sha256sumAdapter,
    UnsquashfsAdapter,
    ZenityAdapter,
)


class TestMksquashfsAdapter:
    """Test MksquashfsAdapter class."""

    @pytest.fixture
    def mock_executor(self, mocker):
        """Create a mock command executor."""
        return mocker.MagicMock(spec=ICommandExecutor)

    @pytest.fixture
    def config(self):
        """Create a default config."""
        return SquishFSConfig()

    @pytest.fixture
    def adapter(self, mock_executor, config):
        """Create a MksquashfsAdapter instance."""
        return MksquashfsAdapter(mock_executor, config)

    def test_init(self, adapter, mock_executor, config):
        """Test adapter initialization."""
        assert adapter.executor == mock_executor
        assert adapter.config == config

    def test_build_success(self, adapter, mock_executor):
        """Test successful build operation."""
        sources = ["/path/to/source"]
        output = "/path/to/output.sqsh"
        excludes = ["-e", "*.tmp"]
        compression = "zstd"
        block_size = "1M"
        processors = 4

        adapter.build(sources, output, excludes, compression, block_size, processors)

        # Verify command construction
        expected_command = [
            "mksquashfs",
            "/path/to/source",
            "/path/to/output.sqsh",
            "-comp",
            "zstd",
            "-b",
            "1M",
            "-processors",
            "4",
            "-info",
            "-keep-as-directory",
            "-e",
            "*.tmp",
        ]
        mock_executor.execute.assert_called_once_with(expected_command, check=True)

    def test_build_error_handling(self, adapter, mock_executor):
        """Test error handling in build operation."""
        sources = ["/path/to/source"]
        output = "/path/to/output.sqsh"
        excludes = []
        compression = "zstd"
        block_size = "1M"
        processors = 4

        # Mock an exception
        mock_executor.execute.side_effect = Exception("Command failed")

        with pytest.raises(MksquashfsCommandExecutionError) as exc_info:
            adapter.build(
                sources, output, excludes, compression, block_size, processors
            )

        assert "mksquashfs" in str(exc_info.value)
        assert "Command failed" in str(exc_info.value)

    def test_build_with_progress(self, adapter, mock_executor):
        """Test build with progress tracking."""
        sources = ["/path/to/source"]
        output = "/path/to/output.sqsh"
        excludes = []
        compression = "zstd"
        block_size = "1M"
        processors = 4

        result = adapter.build_with_progress(
            sources, output, excludes, compression, block_size, processors
        )

        # Verify it calls the basic build method
        mock_executor.execute.assert_called_once()
        assert isinstance(result, BuildProgressState)


class TestUnsquashfsAdapter:
    """Test UnsquashfsAdapter class."""

    @pytest.fixture
    def mock_executor(self, mocker):
        """Create a mock command executor."""
        return mocker.MagicMock(spec=ICommandExecutor)

    @pytest.fixture
    def config(self):
        """Create a default config."""
        return SquishFSConfig()

    @pytest.fixture
    def adapter(self, mock_executor, config):
        """Create a UnsquashfsAdapter instance."""
        return UnsquashfsAdapter(mock_executor, config)

    def test_init(self, adapter, mock_executor, config):
        """Test adapter initialization."""
        assert adapter.executor == mock_executor
        assert adapter.config == config

    def test_extract_success(self, adapter, mock_executor):
        """Test successful extract operation."""
        archive = "/path/to/archive.sqsh"
        output_dir = "/path/to/output"
        xattr_flags = ["-x"]

        adapter.extract(archive, output_dir, xattr_flags)

        # Verify command construction
        expected_command = [
            "unsquashfs",
            "-i",
            "-d",
            "/path/to/output",
            "-x",
            "/path/to/archive.sqsh",
        ]
        mock_executor.execute.assert_called_once_with(
            expected_command, check=True, text=True
        )

    def test_extract_to_current_dir(self, adapter, mock_executor):
        """Test extract to current directory."""
        archive = "/path/to/archive.sqsh"
        output_dir = "."
        xattr_flags = ["-x"]

        adapter.extract(archive, output_dir, xattr_flags)

        # Verify command construction for current directory
        expected_command = ["unsquashfs", "-i", "-x", "/path/to/archive.sqsh"]
        mock_executor.execute.assert_called_once_with(
            expected_command, check=True, text=True
        )

    def test_extract_error_handling(self, adapter, mock_executor):
        """Test error handling in extract operation."""
        archive = "/path/to/archive.sqsh"
        output_dir = "/path/to/output"
        xattr_flags = []

        # Mock an exception
        mock_executor.execute.side_effect = Exception("Extract failed")

        with pytest.raises(UnsquashfsExtractCommandExecutionError) as exc_info:
            adapter.extract(archive, output_dir, xattr_flags)

        assert "unsquashfs" in str(exc_info.value)
        assert "Extract failed" in str(exc_info.value)

    def test_extract_with_progress(self, adapter, mock_executor):
        """Test extract with progress tracking."""
        archive = "/path/to/archive.sqsh"
        output_dir = "/path/to/output"
        xattr_flags = []

        result = adapter.extract_with_progress(archive, output_dir, xattr_flags)

        # Verify it calls the basic extract method
        mock_executor.execute.assert_called_once()
        assert isinstance(result, ExtractProgressState)

    def test_list_contents_success(self, adapter, mock_executor):
        """Test successful list contents operation."""
        archive = "/path/to/archive.sqsh"

        adapter.list_contents(archive)

        # Verify command construction
        expected_command = ["unsquashfs", "-llc", "/path/to/archive.sqsh"]
        mock_executor.execute.assert_called_once_with(
            expected_command, check=True, capture_output=True, text=True
        )

    def test_list_contents_error_handling(self, adapter, mock_executor):
        """Test error handling in list contents operation."""
        archive = "/path/to/archive.sqsh"

        # Mock an exception
        mock_executor.execute.side_effect = Exception("List failed")

        with pytest.raises(UnsquashfsCommandExecutionError) as exc_info:
            adapter.list_contents(archive)

        assert "unsquashfs" in str(exc_info.value)
        assert "List failed" in str(exc_info.value)


class TestSha256sumAdapter:
    """Test Sha256sumAdapter class."""

    @pytest.fixture
    def mock_executor(self, mocker):
        """Create a mock command executor."""
        return mocker.MagicMock(spec=ICommandExecutor)

    @pytest.fixture
    def config(self):
        """Create a default config."""
        return SquishFSConfig()

    @pytest.fixture
    def adapter(self, mock_executor, config):
        """Create a Sha256sumAdapter instance."""
        return Sha256sumAdapter(mock_executor, config)

    def test_init(self, adapter, mock_executor, config):
        """Test adapter initialization."""
        assert adapter.executor == mock_executor
        assert adapter.config == config

    def test_generate_checksum_success(self, adapter, mock_executor, mocker):
        """Test successful checksum generation."""
        file_path = "/path/to/file.sqsh"

        # Mock the result
        mock_result = mocker.MagicMock()
        mock_result.stdout = "d41d8cd98f00b204e9800998ecf8427e  /path/to/file.sqsh\n"
        mock_executor.execute.return_value = mock_result

        result = adapter.generate_checksum(file_path)

        # Verify command construction
        expected_command = ["sha256sum", "/path/to/file.sqsh"]
        mock_executor.execute.assert_called_once_with(
            expected_command, check=True, capture_output=True, text=True
        )
        assert result == "d41d8cd98f00b204e9800998ecf8427e"

    def test_generate_checksum_error_handling(self, adapter, mock_executor):
        """Test error handling in checksum generation."""
        file_path = "/path/to/file.sqsh"

        # Mock an exception
        mock_executor.execute.side_effect = Exception("Checksum failed")

        with pytest.raises(ChecksumError) as exc_info:
            adapter.generate_checksum(file_path)

        assert "Checksum failed" in str(exc_info.value)

    def test_verify_checksum_success(self, adapter, mock_executor, mocker):
        """Test successful checksum verification."""
        file_path = "/path/to/file.sqsh"
        checksum_file = "/path/to/checksum.sha256"

        # Mock the result
        mock_result = mocker.MagicMock()
        mock_result.stdout = "/path/to/file.sqsh: OK\n"
        mock_executor.execute.return_value = mock_result

        result = adapter.verify_checksum(file_path, checksum_file)

        # Verify command construction
        expected_command = ["sha256sum", "-c", "/path/to/checksum.sha256"]
        mock_executor.execute.assert_called_once_with(
            expected_command, check=True, capture_output=True, text=True
        )
        assert result is True

    def test_verify_checksum_failure(self, adapter, mock_executor, mocker):
        """Test failed checksum verification."""
        file_path = "/path/to/file.sqsh"
        checksum_file = "/path/to/checksum.sha256"

        # Mock the result
        mock_result = mocker.MagicMock()
        mock_result.stdout = "/path/to/file.sqsh: FAILED\n"
        mock_executor.execute.return_value = mock_result

        result = adapter.verify_checksum(file_path, checksum_file)

        assert result is False

    def test_verify_checksum_error_handling(self, adapter, mock_executor):
        """Test error handling in checksum verification."""
        file_path = "/path/to/file.sqsh"
        checksum_file = "/path/to/checksum.sha256"

        # Mock an exception
        mock_executor.execute.side_effect = Exception("Verification failed")

        with pytest.raises(ChecksumError) as exc_info:
            adapter.verify_checksum(file_path, checksum_file)

        assert "Verification failed" in str(exc_info.value)


class TestZenityAdapter:
    """Test ZenityAdapter class."""

    @pytest.fixture
    def mock_executor(self, mocker):
        """Create a mock command executor."""
        return mocker.MagicMock(spec=ICommandExecutor)

    @pytest.fixture
    def config(self):
        """Create a default config."""
        return SquishFSConfig()

    @pytest.fixture
    def adapter(self, mock_executor, config):
        """Create a ZenityAdapter instance."""
        return ZenityAdapter(mock_executor, config)

    def test_init(self, adapter, mock_executor, config):
        """Test adapter initialization."""
        assert adapter.executor == mock_executor
        assert adapter.config == config
        assert adapter.process is None

    def test_start_progress_dialog_success(self, adapter, mock_executor, mocker):
        """Test successful start of progress dialog."""
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = mocker.MagicMock()
        mock_process.stdin = mocker.MagicMock()
        mock_process.stdout = mocker.MagicMock()
        mock_process.stderr = mocker.MagicMock()
        mock_popen.return_value = mock_process

        adapter.start_progress_dialog("Test Title")

        # Verify subprocess call
        expected_command = [
            "zenity",
            "--progress",
            "--title",
            "Test Title",
            "--text",
            "Starting...",
            "--percentage",
            "0",
            "--auto-kill",
            "--auto-close",
        ]
        mock_popen.assert_called_once_with(
            expected_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert adapter.process == mock_process

    def test_start_progress_dialog_failure(self, adapter, mock_executor, mocker):
        """Test failure to start progress dialog (Zenity not available)."""
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.side_effect = Exception("Zenity not found")

        adapter.start_progress_dialog("Test Title")

        # Should not raise an exception, just set process to None
        assert adapter.process is None

    def test_update_progress(self, adapter, mocker):
        """Test progress update."""
        # Create a mock process
        mock_process = mocker.MagicMock()
        mock_process.stdin = mocker.MagicMock()
        mock_process.poll.return_value = None  # Not cancelled
        adapter.process = mock_process

        adapter.update_progress(50, "Processing files...")

        # Verify stdin write
        mock_process.stdin.write.assert_called_once_with("50\n#Processing files...\n")
        mock_process.stdin.flush.assert_called_once()

    def test_update_progress_without_status(self, adapter, mocker):
        """Test progress update without status text."""
        # Create a mock process
        mock_process = mocker.MagicMock()
        mock_process.stdin = mocker.MagicMock()
        adapter.process = mock_process

        adapter.update_progress(75)

        # Verify stdin write without status
        mock_process.stdin.write.assert_called_once_with("75\n")
        mock_process.stdin.flush.assert_called_once()

    def test_check_cancelled(self, adapter, mocker):
        """Test cancellation check."""
        # Test not cancelled
        mock_process = mocker.MagicMock()
        mock_process.poll.return_value = None
        adapter.process = mock_process

        assert adapter.check_cancelled() is False

        # Test cancelled
        mock_process.poll.return_value = 0
        assert adapter.check_cancelled() is True

        # Test no process
        adapter.process = None
        assert adapter.check_cancelled() is False

    def test_close_progress_dialog(self, adapter, mocker):
        """Test closing progress dialog."""
        # Create a mock process
        mock_process = mocker.MagicMock()
        mock_process.stdin = mocker.MagicMock()
        mock_process.wait = mocker.MagicMock()
        adapter.process = mock_process

        adapter.close_progress_dialog()

        # Verify close sequence
        mock_process.stdin.write.assert_called_once_with("100\n")
        mock_process.stdin.flush.assert_called_once()
        mock_process.stdin.close.assert_called_once()
        mock_process.wait.assert_called_once()
        assert adapter.process is None

    def test_close_progress_dialog_no_process(self, adapter):
        """Test closing progress dialog when no process exists."""
        adapter.process = None

        # Should not raise an exception
        adapter.close_progress_dialog()
        assert adapter.process is None


class TestMockAdapters:
    """Test mock adapter implementations."""

    def test_mock_mksquashfs_adapter(self):
        """Test MockMksquashfsAdapter."""
        adapter = MockMksquashfsAdapter()

        # Test build method
        adapter.build(["source"], "output.sqsh", ["-e", "*.tmp"], "zstd", "1M", 4)
        assert len(adapter.build_calls) == 1
        assert adapter.build_calls[0]["sources"] == ["source"]
        assert adapter.build_calls[0]["output"] == "output.sqsh"

        # Test build_with_progress method
        result = adapter.build_with_progress(
            ["source"], "output.sqsh", [], "zstd", "1M", 4
        )
        assert len(adapter.build_with_progress_calls) == 1
        assert isinstance(result, BuildProgressState)

    def test_mock_unsquashfs_adapter(self):
        """Test MockUnsquashfsAdapter."""
        adapter = MockUnsquashfsAdapter()

        # Test extract method
        adapter.extract("archive.sqsh", "/output", ["-x"])
        assert len(adapter.extract_calls) == 1
        assert adapter.extract_calls[0]["archive"] == "archive.sqsh"

        # Test extract_with_progress method
        result = adapter.extract_with_progress("archive.sqsh", "/output", [])
        assert len(adapter.extract_with_progress_calls) == 1
        assert isinstance(result, ExtractProgressState)

        # Test list_contents method
        adapter.list_contents("archive.sqsh")
        assert len(adapter.list_calls) == 1
        assert adapter.list_calls[0]["archive"] == "archive.sqsh"

    def test_mock_sha256sum_adapter(self):
        """Test MockSha256sumAdapter."""
        adapter = MockSha256sumAdapter()

        # Test generate_checksum method
        result = adapter.generate_checksum("file.sqsh")
        assert len(adapter.generate_calls) == 1
        assert adapter.generate_calls[0]["file_path"] == "file.sqsh"
        assert result == "mock_checksum_file.sqsh"

        # Test verify_checksum method
        result = adapter.verify_checksum("file.sqsh", "checksum.sha256")
        assert len(adapter.verify_calls) == 1
        assert adapter.verify_calls[0]["file_path"] == "file.sqsh"
        assert result is False

    def test_mock_zenity_adapter(self):
        """Test MockZenityAdapter."""
        adapter = MockZenityAdapter()

        # Test start_progress_dialog method
        adapter.start_progress_dialog("Test Title")
        assert len(adapter.start_calls) == 1
        assert adapter.start_calls[0]["title"] == "Test Title"

        # Test update_progress method
        adapter.update_progress(50, "Processing...")
        assert len(adapter.update_calls) == 1
        assert adapter.update_calls[0]["percentage"] == 50

        # Test check_cancelled method
        adapter.check_cancelled()
        assert len(adapter.check_calls) == 1

        # Test close_progress_dialog method
        adapter.close_progress_dialog()
        assert len(adapter.close_calls) == 1

        # Test set_cancelled method
        adapter.set_cancelled(True)
        assert adapter.cancelled is True
        assert adapter.check_cancelled() is True
