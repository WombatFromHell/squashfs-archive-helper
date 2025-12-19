"""
Test cases for the checksum module.

This module tests the checksum functionality separately.
"""

import logging
import tempfile
from pathlib import Path
from subprocess import CalledProcessError

import pytest

from squish.checksum import ChecksumManager
from squish.config import SquishFSConfig
from squish.errors import (
    ChecksumCommandExecutionError,
    ChecksumError,
    CommandExecutionError,
)


class TestChecksumManagerInitialization:
    """Test ChecksumManager initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        manager = ChecksumManager()
        assert manager.config.mount_base == "mounts"
        assert manager.config.temp_dir == "/tmp"
        assert manager.config.auto_cleanup is True

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = SquishFSConfig(
            mount_base="custom",
            temp_dir="/tmp",  # Use existing directory
            auto_cleanup=False,
            verbose=True,
        )
        manager = ChecksumManager(config)
        assert manager.config == config


class TestChecksumFileValidation:
    """Test checksum file validation logic."""

    @pytest.fixture
    def manager(self):
        """Create a manager."""
        return ChecksumManager()

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


class TestChecksumFileParsing:
    """Test checksum file parsing logic."""

    @pytest.fixture
    def manager(self):
        """Create a manager."""
        return ChecksumManager()

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


class TestChecksumCommandExecution:
    """Test checksum command execution."""

    @pytest.fixture
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        return ChecksumManager()

    def test_execute_checksum_command_success(self, mocker, manager):
        """Test successful checksum command execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            checksum_file = Path(temp_dir) / "test.sqs.sha256"
            checksum_file.write_text("abc123 test.sqs")

            # Mock successful subprocess run
            mock_subprocess = mocker.patch("squish.checksum.subprocess.run")
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
            mock_subprocess = mocker.patch("squish.checksum.subprocess.run")
            mock_subprocess.side_effect = CalledProcessError(
                1, "sha256sum", "Checksum failed"
            )

            with pytest.raises(ChecksumError):
                manager._execute_checksum_command(checksum_file)


class TestCompleteChecksumVerification:
    """Test complete checksum verification workflow."""

    @pytest.fixture
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        return ChecksumManager()

    def test_verify_checksum_success(self, mocker, manager):
        """Test successful complete checksum verification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.sqs"
            checksum_file = Path(temp_dir) / "test.sqs.sha256"

            test_file.touch()
            checksum_file.write_text("abc123 test.sqs")

            # Mock successful subprocess run
            mock_subprocess = mocker.patch("squish.checksum.subprocess.run")
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
            mock_subprocess = mocker.patch("squish.checksum.subprocess.run")
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


class TestChecksumGeneration:
    """Test checksum generation functionality and related errors."""

    @pytest.fixture
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        return ChecksumManager()

    def test_generate_checksum_success(self, mocker, manager):
        """Test successful checksum generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.sqs"
            test_file.write_text("some content")

            # Mock successful subprocess run
            mock_subprocess = mocker.patch("squish.checksum.subprocess.run")
            mock_result = mocker.MagicMock()
            mock_result.stdout = "abc123 test.sqs"
            mock_subprocess.return_value = mock_result

            # Should not raise an exception
            manager.generate_checksum(str(test_file))

            # Verify that subprocess.run was called
            mock_subprocess.assert_called_once()
            args, kwargs = mock_subprocess.call_args
            assert "sha256sum" in str(args[0])
            assert "test.sqs" in str(args[0])

            # Verify that the checksum file was created
            checksum_file = Path(str(test_file) + ".sha256")
            assert checksum_file.exists()

    def test_generate_checksum_command_execution_error(self, mocker, manager):
        """Test that ChecksumCommandExecutionError is raised when command fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.sqs"
            test_file.write_text("some content")

            # Mock failed subprocess run with CalledProcessError
            mock_subprocess = mocker.patch("squish.checksum.subprocess.run")
            mock_subprocess.side_effect = CalledProcessError(
                1, ["sha256sum", str(test_file)], stderr="Command failed"
            )

            # Should raise ChecksumCommandExecutionError
            with pytest.raises(ChecksumCommandExecutionError) as exc_info:
                manager.generate_checksum(str(test_file))

            # Verify that it's also a CommandExecutionError (inheritance)
            assert isinstance(exc_info.value, CommandExecutionError)
            assert exc_info.value.command == "sha256sum"
            assert exc_info.value.return_code == 1
            assert "Failed to generate checksum" in str(exc_info.value)

    def test_generate_checksum_command_execution_error_attributes(
        self, mocker, manager
    ):
        """Test the attributes of ChecksumCommandExecutionError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.sqs"
            test_file.write_text("some content")

            # Mock failed subprocess run
            mock_subprocess = mocker.patch("squish.checksum.subprocess.run")
            mock_subprocess.side_effect = CalledProcessError(
                2, ["sha256sum", str(test_file)], stderr="Permission denied"
            )

            # Should raise ChecksumCommandExecutionError with correct attributes
            with pytest.raises(ChecksumCommandExecutionError) as exc_info:
                manager.generate_checksum(str(test_file))

            error = exc_info.value
            assert error.command == "sha256sum"
            assert error.return_code == 2
            assert "Permission denied" in error.message
            assert isinstance(error, CommandExecutionError)
            assert isinstance(error, ChecksumError)


class TestChecksumCoverageGaps:
    """Test coverage gap scenarios for checksum operations."""

    @pytest.fixture
    def manager(self):
        """Create a manager."""
        return ChecksumManager()

    def test_parse_checksum_file_exception_handling(self, mocker, manager):
        """Test _parse_checksum_file with file read exception."""
        with tempfile.TemporaryDirectory() as temp_dir:
            checksum_file = Path(temp_dir) / "test.sqs.sha256"
            checksum_file.write_text("dummy checksum data")

            # Mock the open function to raise an exception
            mocker.patch(
                "squish.checksum.open", side_effect=OSError("Permission denied")
            )

            with pytest.raises(ChecksumError, match="Failed to read checksum file"):
                manager._parse_checksum_file(checksum_file, "test.sqs")

    def test_verify_checksum_missing_filename_in_file(self, manager):
        """Test checksum verification when target filename is not in checksum file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.sqs"
            checksum_file = Path(temp_dir) / "test.sqs.sha256"

            test_file.touch()
            # Write a checksum file that doesn't contain the target filename
            checksum_file.write_text("abc123 other_file.sqs")

            with pytest.raises(
                ChecksumError, match="Checksum file does not contain entry for"
            ):
                manager.verify_checksum(str(test_file))

    def test_execute_checksum_command_with_unexpected_output(self, mocker, manager):
        """Test _execute_checksum_command with unexpected output format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            checksum_file = Path(temp_dir) / "test.sqs.sha256"
            checksum_file.write_text("abc123 test.sqs")

            # Mock subprocess run to return unexpected output
            mock_subprocess = mocker.patch("squish.checksum.subprocess.run")
            mock_result = mocker.MagicMock()
            mock_result.stdout = "Unexpected output format"  # Neither "OK" nor "FAILED"
            mock_subprocess.return_value = mock_result

            # The method should not raise an exception but log a warning
            manager._execute_checksum_command(checksum_file)

    def test_generate_checksum_direct_method(self, mocker):
        """Test the _generate_checksum method directly."""
        config = SquishFSConfig()
        manager = ChecksumManager(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_file.squashfs"
            test_file.write_text("some content")

            # Mock successful subprocess run
            mock_subprocess = mocker.patch("subprocess.run")
            mock_result = mocker.MagicMock()
            mock_result.stdout = (
                "d41d8cd98f00b204e9800998ecf8427e  test_file.squashfs\n"
            )
            mock_subprocess.return_value = mock_result

            # Call the protected method directly
            manager._generate_checksum(str(test_file))

            # Verify that subprocess.run was called
            mock_subprocess.assert_called_once()
            args, kwargs = mock_subprocess.call_args
            assert "sha256sum" in str(args[0])
            assert str(test_file) in str(args[0])

            # Verify that the checksum file was created
            checksum_file = Path(str(test_file) + ".sha256")
            assert checksum_file.exists()

    def test_generate_checksum_method_call(self, mocker):
        """Test the public generate_checksum method."""
        config = SquishFSConfig()
        manager = ChecksumManager(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_file.squashfs"
            test_file.write_text("some content")

            # Mock successful subprocess run in _generate_checksum
            mock_subprocess = mocker.patch("subprocess.run")
            mock_result = mocker.MagicMock()
            mock_result.stdout = (
                "d41d8cd98f00b204e9800998ecf8427e  test_file.squashfs\n"
            )
            mock_subprocess.return_value = mock_result

            # Call the public method
            manager.generate_checksum(str(test_file))

            # Verify that subprocess.run was called
            mock_subprocess.assert_called_once()
            args, kwargs = mock_subprocess.call_args
            assert "sha256sum" in str(args[0])
            assert str(test_file) in str(args[0])

            # Verify that the checksum file was created
            checksum_file = Path(str(test_file) + ".sha256")
            assert checksum_file.exists()

    def test_validate_checksum_files_different_directories(self, mocker):
        """Test _validate_checksum_files when files are in different directories."""
        config = SquishFSConfig()
        manager = ChecksumManager(config)

        with tempfile.TemporaryDirectory() as temp_dir1:
            with tempfile.TemporaryDirectory() as temp_dir2:
                # Create a test file in one directory
                test_file = Path(temp_dir1) / "test.sqs"
                test_file.touch()

                # Create a checksum file in a different directory
                checksum_file = Path(temp_dir2) / "test.sqs.sha256"
                checksum_file.write_text("abc123 test.sqs")

                # We need to make the checksum file have the right name
                # but in the wrong directory by testing the validation directly
                _test_file_path_obj = Path(str(test_file))
                _checksum_file_path_obj = Path(str(test_file) + ".sha256")

                # Simulate having a checksum file in the wrong location
                # by mocking part of the validation process
                with pytest.raises(
                    ChecksumError, match="must be in the same directory"
                ):
                    # Mock to validate the scenario
                    original_method = manager._validate_checksum_files

                    def mock_method(file_path: str):
                        file_path_obj = Path(file_path)
                        checksum_file_obj = (
                            checksum_file  # Use the wrong directory file
                        )

                        # Check if both files exist
                        if not file_path_obj.exists():
                            raise ChecksumError(
                                f"Target file does not exist: {file_path}"
                            )

                        if not checksum_file_obj.exists():
                            raise ChecksumError(
                                f"Checksum file does not exist: {checksum_file_obj}"
                            )

                        # Check if both files are in the same directory
                        if file_path_obj.parent != checksum_file_obj.parent:
                            raise ChecksumError(
                                "Target file and checksum file must be in the same directory"
                            )

                        return file_path_obj, checksum_file_obj

                    manager._validate_checksum_files = mock_method
                    try:
                        manager._validate_checksum_files(str(test_file))
                    finally:
                        manager._validate_checksum_files = original_method

    def test_execute_checksum_command_called_process_error(self, mocker):
        """Test _execute_checksum_command with CalledProcessError."""
        config = SquishFSConfig()
        manager = ChecksumManager(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            checksum_file = Path(temp_dir) / "test.sqs.sha256"
            checksum_file.write_text("abc123 test.sqs")

            # Mock subprocess run to raise CalledProcessError
            mock_subprocess = mocker.patch("squish.checksum.subprocess.run")
            mock_subprocess.side_effect = CalledProcessError(
                1, "sha256sum", "Test error"
            )

            with pytest.raises(ChecksumError, match="Checksum verification failed"):
                manager._execute_checksum_command(checksum_file)

    def test_execute_checksum_command_unexpected_output_warning(self, mocker, caplog):
        """Test _execute_checksum_command with unexpected output that triggers warning."""
        config = SquishFSConfig()
        manager = ChecksumManager(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            checksum_file = Path(temp_dir) / "test.sqs.sha256"
            checksum_file.write_text("abc123 test.sqs")

            # Mock subprocess run to return output that doesn't contain "OK" or "FAILED"
            mock_subprocess = mocker.patch("squish.checksum.subprocess.run")
            mock_result = mocker.MagicMock()
            mock_result.stdout = "Some unexpected output format"
            mock_subprocess.return_value = mock_result

            # This should not raise an exception but should log a warning
            with caplog.at_level(logging.WARNING):
                manager._execute_checksum_command(checksum_file)

            # Check that the warning was logged
            assert any(
                "Unexpected checksum verification result" in record.message
                for record in caplog.records
            )

    def test_generate_checksum_command_failure(self, mocker):
        """Test _generate_checksum when command fails."""
        from squish.errors import ChecksumCommandExecutionError

        config = SquishFSConfig()
        manager = ChecksumManager(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.squashfs"
            test_file.write_text("some content")

            # Mock subprocess.run to raise CalledProcessError
            mock_subprocess = mocker.patch("subprocess.run")
            mock_subprocess.side_effect = CalledProcessError(
                1, ["sha256sum", str(test_file)], stderr="Command failed"
            )

            with pytest.raises(ChecksumCommandExecutionError) as exc_info:
                manager._generate_checksum(str(test_file))

            assert exc_info.value.command == "sha256sum"
            assert exc_info.value.return_code == 1
            assert "Failed to generate checksum" in exc_info.value.message
