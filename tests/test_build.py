"""
Test cases for the build module.

This module tests the build functionality separately.
"""

import tempfile
from pathlib import Path
from subprocess import CalledProcessError

import pytest

from squish.build import BuildManager
from squish.config import SquishFSConfig
from squish.errors import BuildError, MksquashfsCommandExecutionError


class TestBuildManagerInitialization:
    """Test BuildManager initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        manager = BuildManager()
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
        manager = BuildManager(config)
        assert manager.config == config


class TestBuildExcludeArguments:
    """Test building exclude arguments."""

    @pytest.fixture
    def manager(self):
        """Create a manager."""
        return BuildManager()

    def test_build_exclude_arguments(self, manager):
        """Test building exclude arguments."""
        excludes = ["*.tmp", "*.log"]
        exclude_file = "exclude.txt"

        result = manager._build_exclude_arguments(
            excludes=excludes, exclude_file=exclude_file, wildcards=True, regex=False
        )

        expected = ["-wildcards", "-e", "*.tmp", "-e", "*.log", "-ef", "exclude.txt"]
        assert result == expected

    def test_build_exclude_arguments_regex_only(self, manager):
        """Test building exclude arguments with regex=True only."""
        excludes = ["pattern1", "pattern2"]
        exclude_file = "exclude.txt"

        result = manager._build_exclude_arguments(
            excludes=excludes, exclude_file=exclude_file, wildcards=False, regex=True
        )

        expected = ["-regex", "-e", "pattern1", "-e", "pattern2", "-ef", "exclude.txt"]
        assert result == expected

    def test_build_exclude_arguments_no_excludes(self, manager):
        """Test building exclude arguments with no excludes."""
        result = manager._build_exclude_arguments()

        expected = []
        assert result == expected


class TestBuildSquashFS:
    """Test build squashfs functionality."""

    @pytest.fixture
    def manager(self, mocker):
        """Create a manager with mocked dependencies."""
        return BuildManager()

    def test_build_squashfs_success(self, mocker, manager):
        """Test successful build operation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            # Mock subprocess.run
            mock_run = mocker.patch("squish.build.subprocess.run")

            # Mock subprocess.run to return appropriate values
            def mock_run_side_effect(cmd, **kwargs):
                if cmd[0] == "nproc":
                    return mocker.MagicMock(
                        stdout="4\n", returncode=0, check=lambda: True
                    )
                elif cmd[0] == "mksquashfs":
                    return mocker.MagicMock(returncode=0, check=lambda: True)
                elif cmd[0] == "sha256sum":
                    # Return a mock with proper stdout for checksum
                    mock_result = mocker.MagicMock()
                    mock_result.stdout = f"d41d8cd98f00b204e9800998ecf8427e  {output}\n"
                    mock_result.returncode = 0
                    mock_result.check = lambda: True
                    return mock_result
                return mocker.MagicMock(returncode=0, check=lambda: True)

            mock_run.side_effect = mock_run_side_effect

            manager.build_squashfs(str(source), str(output))

            # Verify mksquashfs was called
            assert mock_run.call_count >= 3  # nproc + mksquashfs + sha256sum

            # Verify checksum was generated
            checksum_file = str(output) + ".sha256"
            assert Path(checksum_file).exists()

            # Verify checksum content
            with open(checksum_file, "r") as f:
                content = f.read()
            assert f"d41d8cd98f00b204e9800998ecf8427e  {output}" in content

    def test_build_squashfs_source_not_found(self, manager):
        """Test build operation with non-existent source."""
        with pytest.raises(BuildError, match="Source not found"):
            manager.build_squashfs("/nonexistent/source", "/output.sqsh")

    def test_build_squashfs_output_exists(self, manager):
        """Test build operation with existing output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"
            output.touch()  # Create existing file

            with pytest.raises(BuildError, match="Output exists"):
                manager.build_squashfs(str(source), str(output))


class TestBuildCommandExecution:
    """Test build command execution errors."""

    def test_mksquashfs_command_execution_error(self, mocker):
        """Test MksquashfsCommandExecutionError."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess to fail
        mock_run = mocker.patch("squish.build.subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "mksquashfs", "Test error")

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            with pytest.raises(MksquashfsCommandExecutionError) as exc_info:
                manager._execute_mksquashfs_command(
                    str(source), str(output), [], "zstd", "1M", 1
                )

            assert exc_info.value.command == "mksquashfs"
            assert exc_info.value.return_code == 1
            assert "Failed to create archive" in exc_info.value.message
            assert isinstance(exc_info.value, BuildError)

    def test_execute_mksquashfs_command_with_kdialog_success(self, mocker):
        """Test executing mksquashfs command with kdialog enabled and success."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock the subprocess run inside _run_mksquashfs_with_progress_service
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=0)

        # Mock the progress service to avoid actual kdialog execution
        mock_progress_service = mocker.MagicMock()
        mock_progress_service.run_mksquashfs_with_progress = mocker.MagicMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            # This should not raise an exception
            manager._execute_mksquashfs_command(
                str(source),
                str(output),
                [],
                "zstd",
                "1M",
                1,
                kdialog=True,
                progress_service=mock_progress_service,
            )

            # Since kdialog is True, it should call _run_mksquashfs_with_progress_service instead of subprocess.run
            # Verify that the command was called with progress flag by checking internal command construction
            # In the method, when kdialog=True, the -progress flag should be added
            # So we need to check that the internal method was called with the right parameters
            # Check that run_mksquashfs_with_progress was called with command including -progress
            assert mock_progress_service.run_mksquashfs_with_progress.called


class TestBuildDependencyChecking:
    """Test build dependency checking functionality."""

    def test_check_build_dependencies_success(self, mocker):
        """Test successful build dependency checking."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock successful subprocess.run for all commands
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock()

        # This should not raise an exception
        manager._check_build_dependencies()

    def test_check_build_dependencies_failure(self, mocker):
        """Test failed build dependency checking."""
        from squish.errors import DependencyError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock failed subprocess.run
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "which")

        with pytest.raises(DependencyError, match="is not installed or not in PATH"):
            manager._check_build_dependencies()

    def test_build_squashfs_kdialog_dependency_check_failure(self, mocker):
        """Test kdialog dependency check failure during build."""
        from squish.errors import DependencyError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock successful build deps check but failed kdialog check
        def mock_run_side_effect(cmd, **kwargs):
            if cmd == ["which", "kdialog"]:
                raise CalledProcessError(1, "which")
            else:
                return mocker.MagicMock()

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = mock_run_side_effect

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            with pytest.raises(DependencyError, match="kdialog is not installed"):
                manager.build_squashfs(str(source), str(output), kdialog=True)

    def test_build_squashfs_nproc_fallback(self, mocker):
        """Test nproc command failure with fallback to 1 processor."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock successful dependencies and source validation
        mock_run = mocker.patch("subprocess.run")

        def run_side_effect(cmd, **kwargs):
            if cmd[0] == "nproc":
                raise CalledProcessError(1, "nproc")  # Fail nproc to trigger fallback
            elif "mksquashfs" in cmd[0]:
                return mocker.MagicMock()
            elif "sha256sum" in cmd[0]:
                result = mocker.MagicMock()
                result.stdout = "dummy_checksum  /path/to/file\n"
                return result
            else:
                return mocker.MagicMock()

        mock_run.side_effect = run_side_effect

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            # This should not raise an exception and should use 1 processor as fallback
            manager.build_squashfs(str(source), str(output))

    def test_build_squashfs_with_progress_service_subprocess_error(self, mocker):
        """Test progress service with SubprocessError during archive creation."""
        import subprocess

        from squish.errors import MksquashfsCommandExecutionError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock successful dependencies and source validation
        mock_run = mocker.patch("subprocess.run")

        def run_side_effect(cmd, **kwargs):
            if cmd[0] in ["mksquashfs", "nproc"]:
                return mocker.MagicMock()
            elif "sha256sum" in cmd[0]:
                result = mocker.MagicMock()
                result.stdout = "dummy_checksum  /path/to/file\n"
                return result
            else:
                return mocker.MagicMock()

        mock_run.side_effect = run_side_effect

        # Mock progress service to raise SubprocessError to trigger the exception handling
        mock_progress_service = mocker.MagicMock()
        mock_progress_service.run_mksquashfs_with_progress.side_effect = (
            subprocess.SubprocessError("Test subprocess error")
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            with pytest.raises(MksquashfsCommandExecutionError) as exc_info:
                manager._run_mksquashfs_with_progress_service(
                    ["mksquashfs", str(source), str(output)], mock_progress_service
                )

            assert "Error during archive creation" in exc_info.value.message

    def test_build_squashfs_with_progress_service_called_process_error(self, mocker):
        """Test progress service with CalledProcessError during archive creation."""
        from squish.errors import MksquashfsCommandExecutionError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock successful dependencies and source validation
        mock_run = mocker.patch("subprocess.run")

        def run_side_effect(cmd, **kwargs):
            if cmd[0] in ["mksquashfs", "nproc"]:
                return mocker.MagicMock()
            elif "sha256sum" in cmd[0]:
                result = mocker.MagicMock()
                result.stdout = "dummy_checksum  /path/to/file\n"
                return result
            else:
                return mocker.MagicMock()

        mock_run.side_effect = run_side_effect

        # Mock progress service to raise CalledProcessError
        from subprocess import CalledProcessError

        mock_progress_service = mocker.MagicMock()
        mock_progress_service.run_mksquashfs_with_progress.side_effect = (
            CalledProcessError(1, "mksquashfs", "Test error")
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            with pytest.raises(MksquashfsCommandExecutionError) as exc_info:
                manager._run_mksquashfs_with_progress_service(
                    ["mksquashfs", str(source), str(output)], mock_progress_service
                )

            assert "Failed to create archive" in exc_info.value.message

    def test_generate_checksum_command_execution_error(self, mocker):
        """Test checksum generation command execution failure."""
        from squish.errors import ChecksumCommandExecutionError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.run to fail for sha256sum
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "sha256sum", "Test error")

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.sqsh"
            test_file.touch()

            with pytest.raises(ChecksumCommandExecutionError) as exc_info:
                manager._generate_checksum(str(test_file))

            assert exc_info.value.command == "sha256sum"
            assert exc_info.value.return_code == 1
            assert "Failed to generate checksum" in exc_info.value.message


class TestBuildCoverageGaps:
    """Test coverage gap scenarios for build functionality."""

    def test_run_mksquashfs_with_progress_service_defaults(self, mocker):
        """Test _run_mksquashfs_with_progress_service with default progress service."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock the progress service components to avoid actual kdialog execution
        mock_progress_handler = mocker.MagicMock()
        mock_command_runner = mocker.MagicMock()
        mock_progress_parser = mocker.MagicMock()

        mock_progress_service_cls = mocker.patch("squish.build.ProgressService")
        mock_progress_service_instance = mocker.MagicMock()
        mock_progress_service_cls.return_value = mock_progress_service_instance

        # Mock the subprocess operations
        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] == "mksquashfs":
                result = mocker.MagicMock()
                result.returncode = 0
                return result
            else:
                return mocker.MagicMock()

        mock_popen = mocker.patch("subprocess.Popen")
        mock_proc = mocker.MagicMock()
        mock_proc.stderr = mocker.MagicMock()
        mock_proc.stderr.readline.return_value = ""
        mock_proc.stderr.__iter__.return_value = iter([""])
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        # Mock imports for the progress service
        mocker.patch(
            "squish.build.KdialogProgressHandler", return_value=mock_progress_handler
        )
        mocker.patch(
            "squish.build.DefaultCommandRunner", return_value=mock_command_runner
        )
        mocker.patch("squish.build.ProgressParser", return_value=mock_progress_parser)

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            # This should not raise an exception when called with default progress service
            command = ["mksquashfs", str(source), str(output)]
            manager._run_mksquashfs_with_progress_service(command)

    def test_generate_checksum_success(self, mocker):
        """Test successful checksum generation."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.run to succeed
        mock_run = mocker.patch("subprocess.run")
        mock_result = mocker.MagicMock()
        mock_result.stdout = "d41d8cd98f00b204e9800998ecf8427e  test_file.squashfs\n"
        mock_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test_file.squashfs"
            test_file.touch()

            # This should not raise an exception
            manager._generate_checksum(str(test_file))

            # Verify checksum file was created
            checksum_file = Path(str(test_file) + ".sha256")
            assert checksum_file.exists()

            # Verify checksum content
            with open(checksum_file, "r") as f:
                content = f.read().strip()
            assert "d41d8cd98f00b204e9800998ecf8427e" in content

    def test_check_build_dependencies_implementation(self, mocker):
        """Test _check_build_dependencies actual implementation path."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock successful subprocess.run for all commands
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock()

        # This should not raise an exception
        manager._check_build_dependencies()

        # Verify that 'which' commands were called for the expected dependencies
        calls = mock_run.call_args_list
        commands_checked = [call[0][0][1] for call in calls if call[0][0][0] == "which"]
        assert "mksquashfs" in commands_checked
        assert "unsquashfs" in commands_checked
        assert "nproc" in commands_checked

    def test_build_squashfs_with_kdialog_dependency_missing(self, mocker):
        """Test kdialog dependency check failure during build with kdialog=True."""
        from squish.errors import DependencyError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess runs
        def mock_run_side_effect(cmd, **kwargs):
            if cmd == ["which", "kdialog"]:
                # Simulate kdialog not being found
                raise CalledProcessError(1, "which")
            elif cmd[0] in ["nproc", "mksquashfs", "sha256sum"]:
                result = mocker.MagicMock()
                if cmd[0] == "nproc":
                    result.stdout = "4\n"
                return result
            return mocker.MagicMock()

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = mock_run_side_effect

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            with pytest.raises(DependencyError, match="kdialog is not installed"):
                manager.build_squashfs(str(source), str(output), kdialog=True)

    def test_build_squashfs_processors_fallback(self, mocker):
        """Test processors fallback to 1 when nproc command fails."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.run to simulate nproc failure
        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] == "nproc":
                # Raise CalledProcessError to trigger fallback
                raise CalledProcessError(1, "nproc")
            elif cmd[0] in ["mksquashfs", "sha256sum"]:
                result = mocker.MagicMock()
                result.stdout = "dummy_checksum  /path/to/file\n"
                return result
            elif cmd[0] == "which":
                return mocker.MagicMock()
            return mocker.MagicMock()

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = mock_run_side_effect

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            # This should not raise an exception and should use 1 processor as fallback
            manager.build_squashfs(str(source), str(output))

            # Verify that nproc was called and failed, triggering the fallback
            nproc_calls = [
                call for call in mock_run.call_args_list if call[0][0][0] == "nproc"
            ]
            assert len(nproc_calls) == 1

    def test_check_build_dependencies_missing_command(self, mocker):
        """Test _check_build_dependencies with a missing command."""
        from squish.errors import DependencyError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.run to fail for one of the commands
        def mock_run_side_effect(cmd, **kwargs):
            if cmd == ["which", "mksquashfs"]:
                raise CalledProcessError(1, "which")
            return mocker.MagicMock()

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = mock_run_side_effect

        with pytest.raises(DependencyError, match="mksquashfs is not installed"):
            manager._check_build_dependencies()

    def test_execute_mksquashfs_with_kdialog_progress(self, mocker):
        """Test _execute_mksquashfs_command with kdialog enabled."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock successful dependencies and source validation
        mock_run = mocker.patch("subprocess.run")

        def run_side_effect(cmd, **kwargs):
            if cmd[0] in ["mksquashfs", "nproc"]:
                return mocker.MagicMock()
            elif "sha256sum" in cmd[0]:
                result = mocker.MagicMock()
                result.stdout = "dummy_checksum  /path/to/file\n"
                return result
            else:
                return mocker.MagicMock()

        mock_run.side_effect = run_side_effect

        # Mock the progress service to avoid actual kdialog execution
        mock_progress_service = mocker.MagicMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            # This should call _run_mksquashfs_with_progress_service due to kdialog=True
            manager._execute_mksquashfs_command(
                str(source),
                str(output),
                [],
                "zstd",
                "1M",
                1,
                kdialog=True,
                progress_service=mock_progress_service,
            )

            # Verify that _run_mksquashfs_with_progress_service was called
            mock_progress_service.run_mksquashfs_with_progress.assert_called_once()

    def test_execute_mksquashfs_without_kdialog_success(self, mocker):
        """Test _execute_mksquashfs_command without kdialog (normal execution path)."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock successful subprocess.run
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            # This should execute the normal path without kdialog
            manager._execute_mksquashfs_command(
                str(source), str(output), [], "zstd", "1M", 1, kdialog=False
            )

            # Verify subprocess.run was called
            mock_run.assert_called_once()

    def test_execute_mksquashfs_without_kdialog_failure(self, mocker):
        """Test _execute_mksquashfs_command without kdialog when subprocess fails."""
        from squish.errors import MksquashfsCommandExecutionError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.run to fail
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "mksquashfs", "Test error")

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            with pytest.raises(MksquashfsCommandExecutionError):
                manager._execute_mksquashfs_command(
                    str(source), str(output), [], "zstd", "1M", 1, kdialog=False
                )

    def test_run_mksquashfs_with_progress_service_with_provided_service(self, mocker):
        """Test _run_mksquashfs_with_progress_service when progress_service is provided."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock successful dependencies
        mocker.patch("subprocess.run", return_value=mocker.MagicMock())

        # Mock progress service
        provided_progress_service = mocker.MagicMock()

        command = ["mksquashfs", "/source", "/output"]

        # This should use the provided progress service instead of creating a new one
        manager._run_mksquashfs_with_progress_service(
            command, provided_progress_service
        )

        # Verify that the provided service was used
        provided_progress_service.run_mksquashfs_with_progress.assert_called_once_with(
            command
        )
