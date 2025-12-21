"""
Test cases for the extract module.

This module tests the extract functionality separately.
"""

import os
from subprocess import CalledProcessError

import pytest

from squish.config import SquishFSConfig
from squish.errors import (
    DependencyError,
    ExtractError,
    UnsquashfsExtractCommandExecutionError,
)
from squish.extract import ExtractManager


class TestExtractManagerInitialization:
    """Test ExtractManager initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        manager = ExtractManager()
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
        manager = ExtractManager(config)
        assert manager.config == config


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
            elif cmd[0] == "unsquashfs" and "-d" in cmd:
                mock_result = mocker.MagicMock()
                mock_result.returncode = 0
                mock_result.check = lambda: True
                return mock_result
            return mocker.MagicMock(returncode=0, check=lambda: True)

        mock_run.side_effect = mock_run_side_effect

        # Extract without specifying output directory (should default to ".")
        extract_manager.extract_squashfs(str(archive_file))

        # Verify unsquashfs was called with current directory as output
        last_call = mock_run.call_args_list[-1]
        call_args = last_call[0][0]
        assert call_args[0] == "unsquashfs"
        assert "-d" in call_args
        assert "." in call_args

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
                str(archive_file), str(output_dir)
            )

        assert exc_info.value.command == "unsquashfs"
        assert exc_info.value.return_code == 1
        assert "Test error" in str(exc_info.value)


class TestExtractDependencyChecking:
    """Test extract dependency checking."""

    def test_check_extract_dependencies_success(self, mocker, extract_manager):
        """Test successful dependency checking using centralized fixtures."""
        # Mock successful dependency check
        mock_run = mocker.patch("squish.extract.subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=0, check=lambda: True)

        # Should not raise an exception
        extract_manager._check_extract_dependencies()

    def test_check_extract_dependencies_failure(self, mocker, extract_manager):
        """Test failed dependency checking using centralized fixtures."""
        # Mock failed dependency check
        mock_run = mocker.patch("squish.extract.subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "which unsquashfs")

        with pytest.raises(DependencyError, match="unsquashfs is not installed"):
            extract_manager._check_extract_dependencies()


class TestExtractIntegration:
    """Integration tests for extract functionality."""

    def test_extract_integration_with_verbose_logging(
        self, mocker, capsys, extract_test_files
    ):
        """Test extract operation with verbose logging enabled using centralized fixtures."""
        config = SquishFSConfig(verbose=True)
        manager = ExtractManager(config)

        archive_file = extract_test_files["archive_file"]
        output_dir = extract_test_files["output_dir"]

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

        # Capture output using pytest-mock
        mock_print = mocker.patch("builtins.print")
        manager.extract_squashfs(str(archive_file), str(output_dir))

        # Verify success message was printed
        mock_print.assert_called_with(
            f"Successfully extracted {archive_file} to {output_dir}"
        )

    def test_extract_integration_error_handling(
        self, mocker, extract_manager, extract_test_files
    ):
        """Test extract operation error handling in integration using centralized fixtures."""
        archive_file = extract_test_files["archive_file"]

        # Mock dependency check to fail
        mock_run = mocker.patch("squish.extract.subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "which unsquashfs")

        with pytest.raises(DependencyError):
            extract_manager.extract_squashfs(str(archive_file))


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
        "output_dir,expected_path",
        [
            (None, "."),  # Default output
            ("./custom", "./custom"),  # Relative path
            ("/tmp/test", "/tmp/test"),  # Absolute path
        ],
    )
    def test_extract_output_directory_variations(
        self, mocker, extract_manager, extract_test_files, output_dir, expected_path
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
            elif cmd[0] == "unsquashfs" and "-d" in cmd:
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
        assert "-d" in call_args

        # Check that the expected path appears in the command
        if expected_path:
            assert expected_path in call_args

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
