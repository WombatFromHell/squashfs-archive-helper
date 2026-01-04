"""
Test cases for the extract module.

This module tests the extract functionality separately.
"""

import os
import subprocess
from pathlib import Path
from subprocess import CalledProcessError

import pytest

from squish.config import SquishFSConfig
from squish.errors import (
    DependencyError,
    ExtractError,
    UnsquashfsExtractCommandExecutionError,
)
from squish.extract import ExtractManager
from squish.progress import ExtractCancelledError


class TestExtractManagerInitialization:
    """Test ExtractManager initialization."""


class TestExtractSquashFS:
    """Test extract squashfs functionality."""

    def test_extract_squashfs_success(
        self, mocker, extract_manager, extract_test_files
    ):
        """Test successful extract operation using centralized fixtures."""
        archive_file = extract_test_files["archive_file"]
        output_dir = extract_test_files["output_dir"]

        mock_run = mocker.patch("squish.extract.subprocess.run")

        # Mock successful unsquashfs output
        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] in ["which", "mksquashfs", "unsquashfs", "nproc"]:
                # Dependency checks - return successful mocks
                return mocker.MagicMock(returncode=0, check=lambda: True)
            elif cmd[0] == "unsquashfs" and "-d" in cmd:
                # Actual extract command
                mock_result = mocker.MagicMock()
                mock_result.returncode = 0
                mock_result.check = lambda: True
                return mock_result
            return mocker.MagicMock(returncode=0, check=lambda: True)

        mock_run.side_effect = mock_run_side_effect

        extract_manager.extract_squashfs(str(archive_file), str(output_dir))

        # Verify unsquashfs was called with correct arguments
        # Check that the last call was the actual extract command
        last_call = mock_run.call_args_list[-1]
        call_args = last_call[0][0]
        assert call_args[0] == "unsquashfs"
        assert "-d" in call_args
        assert str(output_dir) in call_args
        assert str(archive_file) in call_args

    def test_extract_squashfs_default_output_dir(
        self, mocker, extract_manager, extract_test_files
    ):
        """Test extract operation with default output directory (current dir) using centralized fixtures."""
        archive_file = extract_test_files["archive_file"]

        mock_run = mocker.patch("squish.extract.subprocess.run")

        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] in ["which", "mksquashfs", "unsquashfs", "nproc"]:
                return mocker.MagicMock(returncode=0, check=lambda: True)
            elif (
                cmd[0] == "unsquashfs"
            ):  # Check for unsquashfs command (with or without -d)
                mock_result = mocker.MagicMock()
                mock_result.returncode = 0
                mock_result.check = lambda: True
                return mock_result
            return mocker.MagicMock(returncode=0, check=lambda: True)

        mock_run.side_effect = mock_run_side_effect

        # Extract without specifying output directory (should default to ".")
        extract_manager.extract_squashfs(str(archive_file))

        # Verify unsquashfs was called with current directory as output
        # When extracting to ".", it should NOT include -d flag (uses default squashfs-root)
        last_call = mock_run.call_args_list[-1]
        call_args = last_call[0][0]
        assert call_args[0] == "unsquashfs"
        assert "-i" in call_args  # Should have -i flag for status
        assert (
            "-d" not in call_args
        )  # Should NOT have -d flag when using default location

    def test_extract_squashfs_archive_not_found(self, extract_manager):
        """Test extract operation with non-existent archive using centralized fixtures."""
        with pytest.raises(ExtractError, match="Archive not found"):
            extract_manager.extract_squashfs("/nonexistent/archive.sqsh")

    def test_extract_squashfs_archive_not_a_file(
        self, mocker, extract_manager, extract_test_files
    ):
        """Test extract operation with directory instead of file using centralized fixtures."""
        temp_dir = extract_test_files["tmp_path"] / "temp_dir"
        temp_dir.mkdir()

        with pytest.raises(ExtractError, match="Archive path is not a file"):
            extract_manager.extract_squashfs(str(temp_dir))

    def test_extract_squashfs_create_output_dir(
        self, mocker, extract_manager, extract_test_files
    ):
        """Test extract operation creates output directory if it doesn't exist using centralized fixtures."""
        archive_file = extract_test_files["archive_file"]
        output_dir = extract_test_files["tmp_path"] / "new_output_dir"

        mock_run = mocker.patch("squish.extract.subprocess.run")
        mock_access = mocker.patch("squish.extract.os.access")
        mock_access.return_value = True  # Mock as writable

        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] in ["which", "mksquashfs", "unsquashfs", "nproc"]:
                return mocker.MagicMock(returncode=0, check=lambda: True)
            elif cmd[0] == "unsquashfs" and "-d" in cmd:
                mock_result = mocker.MagicMock()
                mock_result.returncode = 0
                mock_result.check = lambda: True
                return mock_result
            return mocker.MagicMock(returncode=0, check=lambda: True)

        mock_run.side_effect = mock_run_side_effect

        # Extract to non-existent directory
        extract_manager.extract_squashfs(str(archive_file), str(output_dir))

        # Verify the extraction was attempted (directory creation happens internally)
        # The key is that no exception was raised and the command was called
        last_call = mock_run.call_args_list[-1]
        call_args = last_call[0][0]
        assert call_args[0] == "unsquashfs"
        assert "-d" in call_args
        assert str(output_dir) in call_args

    def test_extract_squashfs_output_dir_not_writable(
        self, mocker, extract_manager, extract_test_files
    ):
        """Test extract operation with non-writable output directory using centralized fixtures."""
        archive_file = extract_test_files["archive_file"]
        temp_dir = extract_test_files["tmp_path"] / "read_only_dir"
        temp_dir.mkdir()

        # Make directory read-only
        os.chmod(temp_dir, 0o444)

        try:
            with pytest.raises(ExtractError, match="Output directory is not writable"):
                extract_manager.extract_squashfs(str(archive_file), str(temp_dir))
        finally:
            # Restore permissions for cleanup
            os.chmod(temp_dir, 0o755)


class TestExtractCommandExecution:
    """Test extract command execution errors."""

    def test_unsquashfs_command_execution_error(
        self, mocker, extract_manager, extract_test_files
    ):
        """Test UnsquashfsExtractCommandExecutionError using centralized fixtures."""
        archive_file = extract_test_files["archive_file"]
        output_dir = extract_test_files["output_dir"]

        # Mock subprocess to fail
        mock_run = mocker.patch("squish.extract.subprocess.run")
        error = CalledProcessError(1, "unsquashfs")
        error.stderr = "Test error"
        mock_run.side_effect = error

        with pytest.raises(UnsquashfsExtractCommandExecutionError) as exc_info:
            extract_manager._execute_unsquashfs_extract(
                str(archive_file), str(output_dir), str(output_dir)
            )

        assert exc_info.value.command == "unsquashfs"
        assert exc_info.value.return_code == 1
        assert "Test error" in str(exc_info.value)


class TestExtractDependencyChecking:
    """Test extract dependency checking."""


class TestExtractIntegration:
    """Integration tests for extract functionality."""


class TestExtractEdgeCases:
    """Test edge cases for extract functionality."""

    def test_extract_with_special_characters_in_path(
        self, mocker, extract_manager, extract_test_files
    ):
        """Test extract operation with special characters in paths using centralized fixtures."""
        archive_file = extract_test_files["archive_file"]

        # Create output directory with special characters
        output_dir = extract_test_files["tmp_path"] / "test output dir"
        output_dir.mkdir()

        mock_run = mocker.patch("squish.extract.subprocess.run")

        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] in ["which", "mksquashfs", "unsquashfs", "nproc"]:
                return mocker.MagicMock(returncode=0, check=lambda: True)
            elif cmd[0] == "unsquashfs" and "-d" in cmd:
                mock_result = mocker.MagicMock()
                mock_result.returncode = 0
                mock_result.check = lambda: True
                return mock_result
            return mocker.MagicMock(returncode=0, check=lambda: True)

        mock_run.side_effect = mock_run_side_effect

        # Should handle special characters properly
        extract_manager.extract_squashfs(str(archive_file), str(output_dir))

        # Verify the command was called with the correct path
        last_call = mock_run.call_args_list[-1]
        call_args = last_call[0][0]
        assert str(output_dir) in call_args

    def test_extract_with_relative_paths(
        self, mocker, extract_manager, extract_test_files
    ):
        """Test extract operation with relative paths using centralized fixtures."""
        archive_file = extract_test_files["archive_file"]

        mock_run = mocker.patch("squish.extract.subprocess.run")
        mock_path = mocker.patch("squish.extract.Path")
        mock_os_access = mocker.patch("squish.extract.os.access")

        # Mock Path operations to avoid actual directory creation
        def mock_path_side_effect(path):
            mock_path_obj = mocker.MagicMock()
            mock_path_obj.exists.return_value = True
            mock_path_obj.is_file.return_value = True
            mock_path_obj.mkdir = mocker.MagicMock()
            return mock_path_obj

        mock_path.side_effect = mock_path_side_effect
        mock_os_access.return_value = True  # Mock as writable

        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] in ["which", "mksquashfs", "unsquashfs", "nproc"]:
                return mocker.MagicMock(returncode=0, check=lambda: True)
            elif cmd[0] == "unsquashfs" and "-d" in cmd:
                mock_result = mocker.MagicMock()
                mock_result.returncode = 0
                mock_result.check = lambda: True
                return mock_result
            return mocker.MagicMock(returncode=0, check=lambda: True)

        mock_run.side_effect = mock_run_side_effect

        # Use relative path for output directory - this should work without creating actual directories
        extract_manager.extract_squashfs(str(archive_file), "./relative_output")

        # Verify the command was called with the relative path
        last_call = mock_run.call_args_list[-1]
        call_args = last_call[0][0]
        assert call_args[0] == "unsquashfs"
        assert "./relative_output" in call_args


class TestExtractParametrized:
    """Parametrized tests for extract functionality demonstrating best practices."""

    @pytest.mark.parametrize(
        "output_dir,expected_path,should_have_d_flag",
        [
            (None, ".", False),  # Default output - no -d flag
            ("./custom", "./custom", True),  # Relative path - has -d flag
            ("/tmp/test", "/tmp/test", True),  # Absolute path - has -d flag
        ],
    )
    def test_extract_output_directory_variations(
        self,
        mocker,
        extract_manager,
        extract_test_files,
        output_dir,
        expected_path,
        should_have_d_flag,
    ):
        """Test extract operation with various output directory configurations."""
        archive_file = extract_test_files["archive_file"]

        mock_run = mocker.patch("squish.extract.subprocess.run")
        mock_path = mocker.patch("squish.extract.Path")
        mock_os_access = mocker.patch("squish.extract.os.access")

        # Mock Path operations to avoid actual directory creation
        def mock_path_side_effect(path):
            mock_path_obj = mocker.MagicMock()
            mock_path_obj.exists.return_value = True
            mock_path_obj.is_file.return_value = True
            mock_path_obj.mkdir = mocker.MagicMock()
            return mock_path_obj

        mock_path.side_effect = mock_path_side_effect
        mock_os_access.return_value = True  # Mock as writable

        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] in ["which", "mksquashfs", "unsquashfs", "nproc"]:
                return mocker.MagicMock(returncode=0, check=lambda: True)
            elif (
                cmd[0] == "unsquashfs"
            ):  # Check for unsquashfs command (with or without -d)
                mock_result = mocker.MagicMock()
                mock_result.returncode = 0
                mock_result.check = lambda: True
                return mock_result
            return mocker.MagicMock(returncode=0, check=lambda: True)

        mock_run.side_effect = mock_run_side_effect

        # Extract with the specified output directory
        extract_manager.extract_squashfs(str(archive_file), output_dir)

        # Verify the command was called with expected output directory
        last_call = mock_run.call_args_list[-1]
        call_args = last_call[0][0]
        assert call_args[0] == "unsquashfs"
        assert "-i" in call_args  # Should always have -i flag

        if should_have_d_flag:
            assert "-d" in call_args
            # Check that the expected path appears in the command
            if expected_path:
                assert expected_path in call_args
        else:
            assert "-d" not in call_args  # Should NOT have -d flag for default location

    @pytest.mark.parametrize(
        "scenario,archive_path,output_dir,expected_error,error_msg",
        [
            (
                "missing_archive",
                "/nonexistent/archive.sqsh",
                None,
                ExtractError,
                "Archive not found",
            ),
            (
                "invalid_output",
                None,  # Will use real file from fixture
                None,  # Will create invalid directory
                ExtractError,
                "Output directory is not writable",
            ),
            (
                "command_failure",
                None,  # Will use real file from fixture
                None,  # Will use real output from fixture
                UnsquashfsExtractCommandExecutionError,
                "Failed to extract archive contents",
            ),
        ],
    )
    def test_extract_error_scenarios_parametrized(
        self,
        mocker,
        extract_manager,
        extract_test_files,
        scenario,
        archive_path,
        output_dir,
        expected_error,
        error_msg,
    ):
        """Test various error scenarios using parametrization."""
        # Setup mocks and data based on scenario
        if scenario == "command_failure":
            archive_path = str(extract_test_files["archive_file"])
            output_dir = str(extract_test_files["output_dir"])

            # Mock dependency check to succeed
            mock_dependency_check = mocker.patch("squish.extract.subprocess.run")

            def dependency_check_side_effect(cmd, **kwargs):
                if cmd[0] == "which" and "unsquashfs" in cmd:
                    return mocker.MagicMock(returncode=0, check=lambda: True)
                elif cmd[0] == "unsquashfs" and "-d" in cmd:
                    # This is the actual extract command - make it fail
                    error = CalledProcessError(1, "unsquashfs")
                    error.stderr = "Test error"
                    raise error
                return mocker.MagicMock(returncode=0, check=lambda: True)

            mock_dependency_check.side_effect = dependency_check_side_effect
        elif scenario == "invalid_output":
            archive_path = str(extract_test_files["archive_file"])
            # Create a non-writable directory
            invalid_dir = extract_test_files["tmp_path"] / "invalid_dir"
            invalid_dir.mkdir()
            os.chmod(invalid_dir, 0o444)
            output_dir = str(invalid_dir)

            try:
                with pytest.raises(expected_error, match=error_msg):
                    extract_manager.extract_squashfs(archive_path, output_dir)
            finally:
                os.chmod(invalid_dir, 0o755)
            return
        elif scenario == "missing_archive":
            # Use the provided non-existent path
            pass

        # Execute and verify
        with pytest.raises(expected_error, match=error_msg):
            extract_manager.extract_squashfs(archive_path, output_dir)


class TestExtractErrorMatrix:
    """Comprehensive error test matrix for extract functionality."""

    # Define error scenarios as a list of tuples for better organization
    ERROR_SCENARIOS = [
        # (scenario_name, archive_path, output_dir, expected_error, error_pattern, setup_function)
        (
            "missing_archive",
            "/nonexistent/archive.sqsh",
            None,
            ExtractError,
            "Archive not found",
            None,
        ),
        (
            "directory_as_archive",
            None,  # Will be set up in fixture
            None,
            ExtractError,
            "Archive path is not a file",
            "setup_directory_as_archive",
        ),
        (
            "non_writable_output",
            None,  # Will be set up in fixture
            None,  # Will be set up in fixture
            ExtractError,
            "Output directory is not writable",
            "setup_non_writable_output",
        ),
        (
            "dependency_missing",
            None,  # Will be set up in fixture
            None,
            DependencyError,
            "unsquashfs is not installed",
            "setup_missing_dependency",
        ),
        (
            "command_execution_failure",
            None,  # Will be set up in fixture
            None,  # Will be set up in fixture
            UnsquashfsExtractCommandExecutionError,
            "Failed to extract archive contents",
            "setup_command_failure",
        ),
    ]

    def setup_directory_as_archive(self, extract_test_files):
        """Setup scenario where a directory is used as archive path."""
        temp_dir = extract_test_files["tmp_path"] / "temp_dir"
        temp_dir.mkdir()
        return str(temp_dir), None

    def setup_non_writable_output(self, extract_test_files):
        """Setup scenario with non-writable output directory."""
        archive_file = extract_test_files["archive_file"]
        invalid_dir = extract_test_files["tmp_path"] / "invalid_dir"
        invalid_dir.mkdir()
        os.chmod(invalid_dir, 0o444)
        return str(archive_file), str(invalid_dir)

    def setup_missing_dependency(self, extract_test_files):
        """Setup scenario with missing dependency."""
        archive_file = extract_test_files["archive_file"]
        return str(archive_file), None

    def setup_command_failure(self, extract_test_files):
        """Setup scenario with command execution failure."""
        archive_file = extract_test_files["archive_file"]
        output_dir = extract_test_files["output_dir"]
        return str(archive_file), str(output_dir)

    @pytest.mark.parametrize(
        "scenario_name,archive_path,output_dir,expected_error,error_pattern,setup_function",
        ERROR_SCENARIOS,
    )
    def test_extract_error_matrix(
        self,
        mocker,
        extract_manager,
        extract_test_files,
        scenario_name,
        archive_path,
        output_dir,
        expected_error,
        error_pattern,
        setup_function,
    ):
        """Comprehensive error test matrix using parametrization."""
        # Setup scenario-specific mocks and data
        if setup_function:
            setup_method = getattr(self, setup_function)
            archive_path, output_dir = setup_method(extract_test_files)

        # Setup mocks based on scenario
        if scenario_name == "command_execution_failure":
            # Mock dependency check to succeed, but command execution to fail
            mock_run = mocker.patch("squish.extract.subprocess.run")

            def command_failure_side_effect(cmd, **kwargs):
                if cmd[0] == "which" and "unsquashfs" in cmd:
                    return mocker.MagicMock(returncode=0, check=lambda: True)
                elif cmd[0] == "unsquashfs" and "-d" in cmd:
                    error = CalledProcessError(1, "unsquashfs")
                    error.stderr = "Test error"
                    raise error
                return mocker.MagicMock(returncode=0, check=lambda: True)

            mock_run.side_effect = command_failure_side_effect
        elif scenario_name == "dependency_missing":
            mock_run = mocker.patch("squish.extract.subprocess.run")
            mock_run.side_effect = CalledProcessError(1, "which unsquashfs")

        # Execute and verify
        with pytest.raises(expected_error, match=error_pattern):
            extract_manager.extract_squashfs(archive_path, output_dir)


class TestExtractIntegrationPatterns:
    """Integration test patterns demonstrating best practices for extract functionality."""

    def test_extract_integration_with_test_data_builder(
        self, mocker, test_data_builder, tmp_path
    ):
        """Test extract integration using the test data builder pattern."""
        # Create test scenario using the builder
        test_files = test_data_builder.with_extract_scenario(
            "integration_archive.sqsh", "integration content"
        ).build(tmp_path)

        archive_file = test_files["integration_archive.sqsh"]
        output_dir = test_files[
            "extract_output"
        ]  # Use the standard key from the builder

        # Create manager with verbose logging for integration testing
        config = SquishFSConfig(verbose=True)
        manager = ExtractManager(config)

        # Mock successful extraction
        mock_run = mocker.patch("squish.extract.subprocess.run")

        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] in ["which", "mksquashfs", "unsquashfs", "nproc"]:
                return mocker.MagicMock(returncode=0, check=lambda: True)
            elif cmd[0] == "unsquashfs" and "-d" in cmd:
                mock_result = mocker.MagicMock()
                mock_result.returncode = 0
                mock_result.check = lambda: True
                return mock_result
            return mocker.MagicMock(returncode=0, check=lambda: True)

        mock_run.side_effect = mock_run_side_effect

        # Test the full integration workflow
        mock_print = mocker.patch("builtins.print")
        manager.extract_squashfs(str(archive_file), str(output_dir))

        # Verify integration behavior
        mock_print.assert_called_with(
            f"Successfully extracted {archive_file} to {output_dir}"
        )

    def test_extract_integration_with_scenario_fixture(
        self, mocker, extract_scenario_files
    ):
        """Test extract integration using the scenario fixture pattern."""
        archive_file = extract_scenario_files["extract_archive.sqsh"]
        output_dir = extract_scenario_files["extract_output"]

        # Create manager with custom configuration
        config = SquishFSConfig(
            mount_base="integration_mounts", auto_cleanup=True, verbose=True
        )
        manager = ExtractManager(config)

        # Mock successful extraction
        mock_run = mocker.patch("squish.extract.subprocess.run")

        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] in ["which", "mksquashfs", "unsquashfs", "nproc"]:
                return mocker.MagicMock(returncode=0, check=lambda: True)
            elif cmd[0] == "unsquashfs" and "-d" in cmd:
                mock_result = mocker.MagicMock()
                mock_result.returncode = 0
                mock_result.check = lambda: True
                return mock_result
            return mocker.MagicMock(returncode=0, check=lambda: True)

        mock_run.side_effect = mock_run_side_effect

        # Test configuration integration
        assert manager.config.mount_base == "integration_mounts"
        assert manager.config.auto_cleanup is True

        # Test extraction workflow
        mock_print = mocker.patch("builtins.print")
        manager.extract_squashfs(str(archive_file), str(output_dir))

        # Verify success message
        mock_print.assert_called_with(
            f"Successfully extracted {archive_file} to {output_dir}"
        )

    @pytest.mark.parametrize(
        "config_params,expected_verbose",
        [
            ({"verbose": True}, True),
            ({"verbose": False}, False),
            ({}, False),  # Default
        ],
    )
    def test_extract_configuration_integration(
        self, mocker, extract_test_files, config_params, expected_verbose
    ):
        """Test extract configuration integration with parametrization."""
        archive_file = extract_test_files["archive_file"]
        output_dir = extract_test_files["output_dir"]

        # Create manager with parametrized configuration
        config = SquishFSConfig(**config_params)
        manager = ExtractManager(config)

        # Verify configuration
        assert manager.config.verbose == expected_verbose

        # Mock successful extraction
        mock_run = mocker.patch("squish.extract.subprocess.run")

        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] in ["which", "mksquashfs", "unsquashfs", "nproc"]:
                return mocker.MagicMock(returncode=0, check=lambda: True)
            elif cmd[0] == "unsquashfs" and "-d" in cmd:
                mock_result = mocker.MagicMock()
                mock_result.returncode = 0
                mock_result.check = lambda: True
                return mock_result
            return mocker.MagicMock(returncode=0, check=lambda: True)

        mock_run.side_effect = mock_run_side_effect

        # Test extraction with different configurations
        manager.extract_squashfs(str(archive_file), str(output_dir))

        # Verify the command was executed
        assert len(mock_run.call_args_list) > 0
        last_call = mock_run.call_args_list[-1]
        call_args = last_call[0][0]
        assert call_args[0] == "unsquashfs"


class TestExtractCoverageGaps:
    """Test coverage gaps in extract module."""

    def test_count_files_in_archive_empty(self, mocker):
        """Test counting files in empty archive."""
        mock_result = mocker.MagicMock()
        mock_result.stdout = ""  # Empty archive
        mocker.patch("subprocess.run", return_value=mock_result)

        manager = ExtractManager()
        count = manager._count_files_in_archive("empty.sqsh")

        assert count == 0

    def test_count_files_in_archive_only_directories(self, mocker):
        """Test counting files in archive with only directories."""
        mock_result = mocker.MagicMock()
        mock_result.stdout = "dir1/\ndir2/\ndir3/\n"  # Only directories
        mocker.patch("subprocess.run", return_value=mock_result)

        manager = ExtractManager()
        count = manager._count_files_in_archive("dirs_only.sqsh")

        assert count == 0

    def test_count_files_in_archive_mixed_content(self, mocker):
        """Test counting files in archive with mixed files and directories."""
        mock_result = mocker.MagicMock()
        mock_result.stdout = (
            "file1.txt\ndir1/\ndir1/file2.txt\ndir1/file3.txt\nfile4.txt\n"
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        manager = ExtractManager()
        count = manager._count_files_in_archive("test.sqsh")

        assert count == 4  # Should count only files, not directories

    def test_count_files_in_archive_command_failure(self, mocker, capsys):
        """Test counting files when unsquashfs command fails."""
        mock_error = mocker.MagicMock()
        mock_error.stderr = "Command failed: archive not found"
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1, "unsquashfs", stderr=mock_error
            ),
        )

        manager = ExtractManager()
        count = manager._count_files_in_archive("corrupt.sqsh")

        assert count == 0  # Should fallback to 0 on failure
        # Verify warning was logged
        captured = capsys.readouterr()
        assert "Failed to count files in archive corrupt.sqsh" in captured.out

    def test_execute_unsquashfs_extract_success(self, mocker, capsys):
        """Test successful unsquashfs extraction."""
        mock_run = mocker.patch("subprocess.run", return_value=mocker.MagicMock())

        manager = ExtractManager()
        manager._execute_unsquashfs_extract("test.sqsh", "/output", "/output")

        # Verify command was called correctly with -i flag for status info and xattr flags
        # When output_dir is not ".", it should include -d flag and xattr flags
        mock_run.assert_called_once_with(
            [
                "unsquashfs",
                "-i",
                "-d",
                "/output",
                "-xattrs-include",
                "^user.",
                "test.sqsh",
            ],
            check=True,
            text=True,
        )
        # Verify success message
        captured = capsys.readouterr()
        assert "Successfully extracted test.sqsh to /output" in captured.out

    def test_execute_unsquashfs_extract_default_location(self, mocker, capsys):
        """Test unsquashfs extraction to default location (squashfs-root)."""
        mock_run = mocker.patch("subprocess.run", return_value=mocker.MagicMock())

        manager = ExtractManager()
        manager._execute_unsquashfs_extract("test.sqsh", ".", str(Path.cwd()))

        # Verify command was called without -d flag but with xattr flags for default location
        mock_run.assert_called_once_with(
            ["unsquashfs", "-i", "-xattrs-include", "^user.", "test.sqsh"],
            check=True,
            text=True,
        )
        # Verify success message - should show resolved path
        captured = capsys.readouterr()
        assert "Successfully extracted test.sqsh to " in captured.out
        assert str(Path.cwd()) in captured.out

    def test_execute_unsquashfs_extract_failure(self, mocker, capsys):
        """Test unsquashfs extraction failure."""
        mock_error = mocker.MagicMock()
        mock_error.stderr = "Extraction failed: corrupt archive"
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1, "unsquashfs", stderr="Extraction failed: corrupt archive"
            ),
        )

        manager = ExtractManager()

        with pytest.raises(UnsquashfsExtractCommandExecutionError) as exc_info:
            manager._execute_unsquashfs_extract("corrupt.sqsh", "/output", "/output")

        assert "Failed to extract archive contents" in str(exc_info.value)
        assert "corrupt archive" in str(exc_info.value)

    def test_execute_unsquashfs_extract_with_progress_success(self, mocker, capsys):
        """Test successful extraction with progress tracking."""
        # Mock subprocess.run for file counting
        mock_count_result = mocker.MagicMock()
        mock_count_result.stdout = "file1.txt\nfile2.txt\n"
        mocker.patch("subprocess.run", return_value=mock_count_result)

        # Mock process and progress service
        mock_process = mocker.MagicMock()
        mock_process.stdout = ["25%", "50%", "75%", "100%"]
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_popen = mocker.patch("subprocess.Popen", return_value=mock_process)

        mock_progress_service = mocker.MagicMock()
        mock_progress_service.check_cancelled.return_value = False

        # Mock the ExtractProgressTracker to avoid progress parsing issues
        mock_tracker_class = mocker.patch("squish.extract.ExtractProgressTracker")
        mock_tracker_instance = mock_tracker_class.return_value
        mock_tracker_instance.zenity_service = mock_progress_service

        manager = ExtractManager()
        manager._execute_unsquashfs_extract_with_progress(
            "test.sqsh", "/output", "/output", mock_progress_service
        )

        # Verify process was started and closed successfully
        mock_popen.assert_called_once()
        mock_progress_service.start.assert_called_once()
        mock_progress_service.close.assert_called_once_with(success=True)
        # Verify success message
        captured = capsys.readouterr()
        assert "Successfully extracted test.sqsh to /output" in captured.out

    def test_execute_unsquashfs_extract_with_progress_cancellation(self, mocker):
        """Test extraction cancellation during progress."""
        # Mock subprocess.run for file counting
        mock_count_result = mocker.MagicMock()
        mock_count_result.stdout = "file1.txt\nfile2.txt\nfile3.txt\n"
        mocker.patch("subprocess.run", return_value=mock_count_result)

        # Mock process and progress service
        mock_process = mocker.MagicMock()
        mock_process.stdout = ["50%", "75%", "Cancelled"]
        mock_process.wait.return_value = None
        mocker.patch("subprocess.Popen", return_value=mock_process)

        mock_progress_service = mocker.MagicMock()
        mock_progress_service.check_cancelled.side_effect = [False, False, True]

        manager = ExtractManager()

        # Mock the ExtractProgressTracker to avoid the early exception from progress parsing
        mock_tracker_class = mocker.patch("squish.extract.ExtractProgressTracker")
        mock_tracker_instance = mock_tracker_class.return_value
        # Mock the zenity_service attribute to return our mock progress service
        mock_tracker_instance.zenity_service = mock_progress_service

        with pytest.raises(ExtractCancelledError) as exc_info:
            manager._execute_unsquashfs_extract_with_progress(
                "test.sqsh", "/output", "/output", mock_progress_service
            )

        assert "Extract cancelled by user" in str(exc_info.value)
        mock_process.terminate.assert_called_once()
        mock_progress_service.close.assert_called_once_with(success=False)

    def test_execute_unsquashfs_extract_with_progress_command_failure(self, mocker):
        """Test extraction with progress when command fails."""
        # Mock subprocess.run for file counting
        mock_count_result = mocker.MagicMock()
        mock_count_result.stdout = "file1.txt\nfile2.txt\n"
        mocker.patch("subprocess.run", return_value=mock_count_result)

        # Mock process to fail
        mock_process = mocker.MagicMock()
        mock_process.stdout = ["25%", "50%"]
        mock_process.wait.return_value = 1  # Non-zero return code
        mocker.patch("subprocess.Popen", return_value=mock_process)

        mock_progress_service = mocker.MagicMock()
        mock_progress_service.check_cancelled.return_value = False

        # Mock the ExtractProgressTracker
        mock_tracker_class = mocker.patch("squish.extract.ExtractProgressTracker")
        mock_tracker_instance = mock_tracker_class.return_value
        mock_tracker_instance.zenity_service = mock_progress_service

        manager = ExtractManager()

        with pytest.raises(UnsquashfsExtractCommandExecutionError) as exc_info:
            manager._execute_unsquashfs_extract_with_progress(
                "test.sqsh", "/output", "/output", mock_progress_service
            )

        assert "Failed to extract archive" in str(exc_info.value)
        # The progress service is closed with success=False when the command fails
        # So we should expect only one call with success=False
        mock_progress_service.close.assert_called_once_with(success=False)

    def test_extract_squashfs_validation_errors(self, mocker):
        """Test extract_squashfs validation error paths."""
        manager = ExtractManager()

        # Test non-existent archive
        with pytest.raises(ExtractError) as exc_info:
            manager.extract_squashfs("/nonexistent/archive.sqsh", "/output")
        assert "Archive not found" in str(exc_info.value)

        # Test archive that's not a file (create directory)
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_archive = Path(temp_dir) / "fake.sqsh"
            fake_archive.mkdir()
            with pytest.raises(ExtractError) as exc_info:
                manager.extract_squashfs(str(fake_archive), "/output")
            assert "Archive path is not a file" in str(exc_info.value)

    def test_extract_squashfs_output_directory_creation(self, mocker, tmp_path):
        """Test output directory creation during extraction."""
        # Create a fake archive file
        archive_file = tmp_path / "test.sqsh"
        archive_file.touch()

        mocker.patch("subprocess.run", return_value=mocker.MagicMock())
        mocker.patch("squish.extract.ExtractManager._check_extract_dependencies")

        manager = ExtractManager()
        output_dir = tmp_path / "new_output"

        # Mock file counting and extraction
        mock_count_result = mocker.MagicMock()
        mock_count_result.stdout = "file1.txt\n"
        mocker.patch("subprocess.run", return_value=mock_count_result)

        # Test that output directory is created
        assert not output_dir.exists()
        manager.extract_squashfs(str(archive_file), str(output_dir))
        assert output_dir.exists()

    def test_extract_squashfs_output_directory_permission_error(self, mocker, tmp_path):
        """Test output directory creation with permission error."""
        import os

        # Create a fake archive file
        archive_file = tmp_path / "test.sqsh"
        archive_file.touch()

        # Create a directory that we can't write to
        output_dir = tmp_path / "read_only_dir"
        output_dir.mkdir()
        os.chmod(output_dir, 0o444)  # Read-only

        # Mock dependency check
        mocker.patch("squish.extract.ExtractManager._check_extract_dependencies")

        manager = ExtractManager()

        with pytest.raises(ExtractError) as exc_info:
            manager.extract_squashfs(str(archive_file), str(output_dir))

        assert "Output directory is not writable" in str(exc_info.value)
        # Clean up
        os.chmod(output_dir, 0o755)


class TestExtractXattrErrorHandling:
    """Test xattr error handling in extract operations."""

    def test_execute_unsquashfs_extract_xattr_error_all_mode(self, mocker):
        """Test xattr error handling when xattr_mode is 'all'."""
        from squish.config import SquishFSConfig

        # Create config with xattr_mode="all"
        config = SquishFSConfig(xattr_mode="all")
        manager = ExtractManager(config)

        # Mock subprocess to fail with xattr error
        mock_error = mocker.MagicMock()
        mock_error.stderr = "write_xattr: could not write xattr security.selinux"
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1,
                "unsquashfs",
                stderr="write_xattr: could not write xattr security.selinux",
            ),
        )

        with pytest.raises(Exception) as exc_info:
            manager._execute_unsquashfs_extract("test.sqsh", "/output", "/output")

        # Should raise XattrError with appropriate suggestion
        assert "Xattr Error" in str(exc_info.value)
        assert "Try using --xattr-mode user-only" in str(exc_info.value)
        assert "run as superuser" in str(exc_info.value)

    def test_execute_unsquashfs_extract_xattr_error_user_only_mode(self, mocker):
        """Test xattr error handling when xattr_mode is 'user-only'."""
        from squish.config import SquishFSConfig

        # Create config with xattr_mode="user-only"
        config = SquishFSConfig(xattr_mode="user-only")
        manager = ExtractManager(config)

        # Mock subprocess to fail with xattr error
        mock_error = mocker.MagicMock()
        mock_error.stderr = "xattr extraction failed"
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1, "unsquashfs", stderr="xattr extraction failed"
            ),
        )

        with pytest.raises(Exception) as exc_info:
            manager._execute_unsquashfs_extract("test.sqsh", "/output", "/output")

        # Should raise XattrError with appropriate suggestion
        assert "Xattr Error" in str(exc_info.value)
        assert "Xattr extraction failed" in str(exc_info.value)
        assert "--xattr-mode none" in str(exc_info.value)

    def test_execute_unsquashfs_extract_with_progress_xattr_error(self, mocker):
        """Test xattr error handling in progress mode."""
        # Mock subprocess.run for file counting
        mock_count_result = mocker.MagicMock()
        mock_count_result.stdout = "file1.txt\nfile2.txt\n"
        mocker.patch("subprocess.run", return_value=mock_count_result)

        # Mock process to fail with xattr error
        mock_process = mocker.MagicMock()
        mock_process.stdout = [
            "25%",
            "50%",
            "write_xattr: could not write xattr security.selinux",
        ]
        mock_process.wait.return_value = 1  # Non-zero return code
        mocker.patch("subprocess.Popen", return_value=mock_process)

        mock_progress_service = mocker.MagicMock()
        mock_progress_service.check_cancelled.return_value = False

        # Mock the ExtractProgressTracker
        mock_tracker_class = mocker.patch("squish.extract.ExtractProgressTracker")
        mock_tracker_instance = mock_tracker_class.return_value
        mock_tracker_instance.zenity_service = mock_progress_service

        manager = ExtractManager()

        with pytest.raises(Exception) as exc_info:
            manager._execute_unsquashfs_extract_with_progress(
                "test.sqsh", "/output", "/output", mock_progress_service
            )

        # Should raise XattrError
        assert "Xattr Error" in str(exc_info.value)
        # Default config uses user-only mode, so it should suggest --xattr-mode none
        assert "--xattr-mode none" in str(exc_info.value)

    def test_execute_unsquashfs_extract_with_progress_xattr_error_exception_handling(
        self, mocker
    ):
        """Test xattr error handling in exception handler of progress mode."""
        # Mock subprocess.run for file counting
        mock_count_result = mocker.MagicMock()
        mock_count_result.stdout = "file1.txt\nfile2.txt\n"
        mocker.patch("subprocess.run", return_value=mock_count_result)

        # Mock process to fail with xattr error
        mock_process = mocker.MagicMock()
        mock_process.stdout = [
            "25%",
            "50%",
            "write_xattr: could not write xattr security.selinux",
        ]
        mock_process.wait.return_value = 1  # Non-zero return code
        mocker.patch("subprocess.Popen", return_value=mock_process)

        mock_progress_service = mocker.MagicMock()
        mock_progress_service.check_cancelled.return_value = False

        # Mock the ExtractProgressTracker
        mock_tracker_class = mocker.patch("squish.extract.ExtractProgressTracker")
        mock_tracker_instance = mock_tracker_class.return_value
        mock_tracker_instance.zenity_service = mock_progress_service

        manager = ExtractManager()

        # Mock the UnsquashfsExtractCommandExecutionError to be raised
        # and then caught and re-raised as XattrError
        with pytest.raises(Exception) as exc_info:
            manager._execute_unsquashfs_extract_with_progress(
                "test.sqsh", "/output", "/output", mock_progress_service
            )

        # Should raise XattrError (re-raised from UnsquashfsExtractCommandExecutionError)
        assert "Xattr Error" in str(exc_info.value)
        # Default config uses user-only mode, so it should suggest --xattr-mode none
        assert "--xattr-mode none" in str(exc_info.value)


class TestExtractRemainingCoverageGaps:
    """Test remaining coverage gaps in extract module."""

    def test_extract_squashfs_output_directory_creation_error_handling(
        self, mocker, tmp_path
    ):
        """Test output directory creation error handling.

        This test focuses on the specific error path where directory creation fails
        due to permission issues. It creates a real scenario where a parent directory
        is not writable, causing the mkdir operation to fail.
        """
        import os

        # Create a fake archive file
        archive_file = tmp_path / "test.sqsh"
        archive_file.touch()

        # Mock dependency check to avoid actual dependency validation
        mocker.patch("squish.extract.ExtractManager._check_extract_dependencies")

        # Create a parent directory that we'll make read-only
        parent_dir = tmp_path / "parent_dir"
        parent_dir.mkdir()

        # Make the parent directory read-only to simulate permission issues
        os.chmod(parent_dir, 0o444)  # Read-only

        try:
            manager = ExtractManager()
            output_dir = parent_dir / "new_output"

            # Mock the exists check to return False so we attempt directory creation
            def mock_exists(self):
                if "new_output" in str(self):
                    return False  # Directory doesn't exist
                return True  # Other paths exist

            mocker.patch("squish.extract.Path.exists", new_callable=lambda: mock_exists)

            with pytest.raises(ExtractError) as exc_info:
                manager.extract_squashfs(str(archive_file), str(output_dir))

            assert "Failed to create output directory" in str(exc_info.value)
            assert "Permission denied" in str(exc_info.value)
        finally:
            # Restore permissions for cleanup
            os.chmod(parent_dir, 0o755)

    def test_extract_squashfs_default_output_dir_with_progress(self, mocker, tmp_path):
        """Test extract with default output directory and progress."""
        # Create a fake archive file
        archive_file = tmp_path / "test.sqsh"
        archive_file.touch()

        # Create mock progress service
        mock_progress_service = mocker.MagicMock()
        mock_progress_service.check_cancelled.return_value = False

        manager = ExtractManager()

        # Mock dependency check to avoid actual subprocess calls
        mocker.patch("squish.extract.ExtractManager._check_extract_dependencies")

        # Mock the file counting method to return a specific count
        mocker.patch(
            "squish.extract.ExtractManager._count_files_in_archive", return_value=2
        )

        # Mock process and progress service for the first extraction
        mock_process = mocker.MagicMock()
        mock_process.stdout = ["25%", "50%", "75%", "100%"]
        mock_process.wait.return_value = None
        mock_process.returncode = 0
        mock_popen = mocker.patch("subprocess.Popen", return_value=mock_process)

        mock_progress_service.check_cancelled.return_value = False

        # Test extraction with progress to default location (.)
        manager.extract_squashfs(
            str(archive_file), progress=True, progress_service=mock_progress_service
        )

        # Create output directory
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Mock the ExtractProgressTracker
        mock_tracker_class = mocker.patch("squish.extract.ExtractProgressTracker")
        mock_tracker_instance = mock_tracker_class.return_value
        mock_tracker_instance.zenity_service = mock_progress_service

        manager = ExtractManager()

        # Test extraction with progress to custom location
        manager.extract_squashfs(
            str(archive_file),
            str(output_dir),
            progress=True,
            progress_service=mock_progress_service,
        )

        # Verify process was started and closed successfully for both extractions
        assert mock_popen.call_count == 2
        mock_progress_service.start.assert_called()
        mock_progress_service.close.assert_called_with(success=True)


class TestExtractAutomaticXattrHandling:
    """Test automatic xattr handling based on user privileges."""

    def test_automatic_xattr_mode_detection_non_root(self, mocker):
        """Test that non-root users get user-only xattr mode."""
        # Mock is_root_user to return False (non-root)
        mocker.patch("squish.config.is_root_user", return_value=False)

        from squish.config import SquishFSConfig

        config = SquishFSConfig()

        assert config.xattr_mode == "user-only"

    def test_automatic_xattr_mode_detection_root(self, mocker):
        """Test that root users get all xattr mode."""
        # Mock is_root_user to return True (root)
        mocker.patch("squish.config.is_root_user", return_value=True)

        from squish.config import SquishFSConfig

        config = SquishFSConfig()

        assert config.xattr_mode == "all"

    def test_xattr_flags_for_non_root_user(self, mocker):
        """Test that non-root users get appropriate xattr flags."""
        # Create config with user-only xattr mode (as would be set for non-root users)
        config = SquishFSConfig(xattr_mode="user-only")
        manager = ExtractManager(config)
        flags = manager._get_xattr_flags()

        # Non-root users should get user-only xattr flags
        assert flags == ["-xattrs-include", "^user."]

    def test_xattr_flags_for_root_user(self, mocker):
        """Test that root users get appropriate xattr flags."""
        # Create config with all xattr mode (as would be set for root users)
        config = SquishFSConfig(xattr_mode="all")
        manager = ExtractManager(config)
        flags = manager._get_xattr_flags()

        # Root users should get all xattr flags
        assert flags == ["-xattrs"]

    def test_xattr_error_detection_still_works(self):
        """Test that xattr error detection still works correctly."""
        manager = ExtractManager()

        # Test various xattr error patterns
        xattr_errors = [
            "write_xattr: could not write xattr security.selinux",
            "xattr extraction failed",
            "security.selinux permission denied",
        ]

        for error in xattr_errors:
            assert manager._is_xattr_error(error), f"Should detect xattr error: {error}"

    def test_non_xattr_errors_not_detected(self):
        """Test that non-xattr errors are not detected as xattr errors."""
        manager = ExtractManager()

        # Test non-xattr errors
        non_xattr_errors = [
            "file not found",
            "permission denied",
            "corrupt archive",
        ]

        for error in non_xattr_errors:
            assert not manager._is_xattr_error(error), (
                f"Should not detect as xattr error: {error}"
            )

    def test_manual_override_still_possible(self):
        """Test that manual override of xattr mode is still possible."""
        from squish.config import SquishFSConfig

        # Test that we can still manually override the xattr mode
        config = SquishFSConfig(xattr_mode="none")
        assert config.xattr_mode == "none"

        manager = ExtractManager(config)
        flags = manager._get_xattr_flags()
        assert flags == ["-no-xattrs"]

    def test_invalid_xattr_mode_rejected(self):
        """Test that invalid xattr modes are still rejected."""
        from squish.config import SquishFSConfig

        with pytest.raises(ValueError) as exc_info:
            SquishFSConfig(xattr_mode="invalid")

        assert "xattr_mode must be one of" in str(exc_info.value)

    def test_xattr_flags_in_commands_non_root(self, mocker):
        """Test that xattr flags are correctly added to commands for non-root users."""
        # Create config with user-only xattr mode (as would be set for non-root users)
        config = SquishFSConfig(xattr_mode="user-only")

        mock_run = mocker.patch("subprocess.run", return_value=mocker.MagicMock())

        manager = ExtractManager(config)
        manager._execute_unsquashfs_extract("test.sqsh", "/output", "/output")

        # Verify command includes user-only xattr flags
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "-xattrs-include" in call_args
        assert "^user." in call_args

    def test_xattr_flags_in_commands_root(self, mocker):
        """Test that xattr flags are correctly added to commands for root users."""
        # Create config with all xattr mode (as would be set for root users)
        config = SquishFSConfig(xattr_mode="all")

        mock_run = mocker.patch("subprocess.run", return_value=mocker.MagicMock())

        manager = ExtractManager(config)
        manager._execute_unsquashfs_extract("test.sqsh", "/output", "/output")

        # Verify command includes all xattr flags
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "-xattrs" in call_args
        assert "-xattrs-include" not in call_args  # Should not have user-only flags


class TestExtractXattrFlagsMethod:
    """Test the _get_xattr_flags() method specifically for coverage."""

    def test_get_xattr_flags_all_mode(self):
        """Test _get_xattr_flags() with 'all' mode."""
        from squish.config import SquishFSConfig

        config = SquishFSConfig(xattr_mode="all")
        manager = ExtractManager(config)
        flags = manager._get_xattr_flags()
        assert flags == ["-xattrs"]

    def test_get_xattr_flags_user_only_mode(self):
        """Test _get_xattr_flags() with 'user-only' mode."""
        from squish.config import SquishFSConfig

        config = SquishFSConfig(xattr_mode="user-only")
        manager = ExtractManager(config)
        flags = manager._get_xattr_flags()
        assert flags == ["-xattrs-include", "^user."]

    def test_get_xattr_flags_none_mode(self):
        """Test _get_xattr_flags() with 'none' mode."""
        from squish.config import SquishFSConfig

        config = SquishFSConfig(xattr_mode="none")
        manager = ExtractManager(config)
        flags = manager._get_xattr_flags()
        assert flags == ["-no-xattrs"]

    def test_get_xattr_flags_unknown_mode_fallback(self, mocker):
        """Test _get_xattr_flags() with unknown mode (should fallback to user-only)."""
        from squish.config import SquishFSConfig

        # Create config with valid mode first
        config = SquishFSConfig(xattr_mode="all")
        manager = ExtractManager(config)

        # Test the fallback behavior by directly calling with an invalid mode
        # We'll monkey patch the config.xattr_mode property
        original_config = manager.config
        try:
            # Use a different approach - test the method logic directly
            # Since we can't modify the frozen dataclass, we'll test the fallback
            # by checking the method handles unknown modes correctly

            # Create a mock config object that returns invalid mode
            mock_config = mocker.MagicMock()
            mock_config.xattr_mode = "invalid_mode"

            # Temporarily replace the config
            manager.config = mock_config

            flags = manager._get_xattr_flags()
            # Should fallback to user-only
            assert flags == ["-xattrs-include", "^user."]

        finally:
            # Restore original config
            manager.config = original_config


class TestExtractProgressParsingFix:
    """Test the fix for progress parsing with unsquashfs -percentage output."""

    def test_progress_parsing_ignores_initial_inode_summary(self):
        """Test that initial 'X inodes (Y blocks) to write' line is ignored for progress."""
        from squish.progress import parse_unsquashfs_progress

        # Test that the initial summary line is ignored when it exceeds total files
        initial_summary_line = "1574 inodes (9606 blocks) to write"
        result = parse_unsquashfs_progress(initial_summary_line, 100)
        assert result is None, (
            "Initial summary line should be ignored when inodes > total_files"
        )

        # Test that the same line works when total_files is sufficient
        result = parse_unsquashfs_progress(initial_summary_line, 2000)
        assert result is not None, "Should parse when inodes <= total_files"
        assert result.current_files == 1574
        assert result.total_files == 2000
        assert result.percentage == 78  # 1574/2000 * 100 = 78.7 -> min(99, 78) = 78

    def test_progress_parsing_percentage_lines(self):
        """Test that percentage lines are correctly parsed."""
        from squish.progress import parse_unsquashfs_progress

        percentage_lines = ["10%", "20%", "50%", "100%", " 25% ", "75%"]
        expected_results = [
            (10, 100, 10),
            (20, 100, 20),
            (50, 100, 50),
            (100, 100, 100),
            (25, 100, 25),
            (75, 100, 75),
        ]

        for line, expected in zip(percentage_lines, expected_results):
            result = parse_unsquashfs_progress(line, 100)
            assert result is not None, f"Should parse percentage line: {line}"
            assert result.current_files == expected[0]
            assert result.total_files == expected[1]
            assert result.percentage == expected[2]

    def test_progress_parsing_created_files_lines(self):
        """Test that 'created X files' lines are correctly parsed."""
        from squish.progress import parse_unsquashfs_progress

        created_lines = ["created 10 files", "created 50 files", "created 100 files"]
        expected_results = [
            (10, 100, 10),
            (50, 100, 50),
            (100, 100, 99),  # min(99, 100) = 99
        ]

        for line, expected in zip(created_lines, expected_results):
            result = parse_unsquashfs_progress(line, 100)
            assert result is not None, f"Should parse created files line: {line}"
            assert result.current_files == expected[0]
            assert result.total_files == expected[1]
            assert result.percentage == expected[2]

    def test_progress_parsing_ignores_zero_values(self):
        """Test that lines with zero values are ignored."""
        from squish.progress import parse_unsquashfs_progress

        zero_lines = [
            "0 inodes (0 blocks) to write",
            "created 0 files",
        ]

        for line in zero_lines:
            result = parse_unsquashfs_progress(line, 100)
            assert result is None, f"Zero value lines should be ignored: {line}"

    def test_progress_parsing_percentage_without_sign(self):
        """Test that percentage lines without % sign are correctly parsed (unsquashfs -percentage format)."""
        from squish.progress import parse_unsquashfs_progress

        # Test the format that unsquashfs -percentage actually outputs
        percentage_lines_without_sign = ["10", "20", "50", "100", " 25 ", "75"]
        expected_results = [
            (10, 100, 10),
            (20, 100, 20),
            (50, 100, 50),
            (100, 100, 100),
            (25, 100, 25),
            (75, 100, 75),
        ]

        for line, expected in zip(percentage_lines_without_sign, expected_results):
            result = parse_unsquashfs_progress(line, 100)
            assert result is not None, (
                f"Should parse percentage line without sign: {line}"
            )
            assert result.current_files == expected[0]
            assert result.total_files == expected[1]
            assert result.percentage == expected[2]

    def test_progress_parsing_backward_compatibility_with_percentage_sign(self):
        """Test that percentage lines with % sign still work (backward compatibility)."""
        from squish.progress import parse_unsquashfs_progress

        # Test that the old format with % sign still works
        percentage_lines_with_sign = ["10%", "20%", "50%", "100%", " 25% ", "75%"]
        expected_results = [
            (10, 100, 10),
            (20, 100, 20),
            (50, 100, 50),
            (100, 100, 100),
            (25, 100, 25),
            (75, 100, 75),
        ]

        for line, expected in zip(percentage_lines_with_sign, expected_results):
            result = parse_unsquashfs_progress(line, 100)
            assert result is not None, f"Should parse percentage line with sign: {line}"
            assert result.current_files == expected[0]
            assert result.total_files == expected[1]
            assert result.percentage == expected[2]
