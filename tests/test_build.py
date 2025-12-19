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

    def test_build_squashfs_success(self, mocker, manager, build_test_files):
        """Test successful build operation."""
        source = build_test_files["source"]
        output = build_test_files["tmp_path"] / "output.sqsh"

        # Mock subprocess.run
        mock_run = mocker.patch("squish.build.subprocess.run")

        # Mock subprocess.run to return appropriate values
        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] == "nproc":
                return mocker.MagicMock(stdout="4\n", returncode=0, check=lambda: True)
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

    def test_build_squashfs_output_exists(self, manager, build_test_files):
        """Test build operation with existing output."""
        source = build_test_files["source"]
        output = build_test_files["tmp_path"] / "output.sqsh"
        output.touch()  # Create existing file

        with pytest.raises(BuildError, match="Output exists"):
            manager.build_squashfs(str(source), str(output))


class TestBuildCommandExecution:
    """Test build command execution errors."""

    def test_mksquashfs_command_execution_error(self, mocker, build_test_files):
        """Test MksquashfsCommandExecutionError."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess to fail
        mock_run = mocker.patch("squish.build.subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "mksquashfs", "Test error")

        source = build_test_files["source"]
        output = build_test_files["tmp_path"] / "output.sqsh"

        with pytest.raises(MksquashfsCommandExecutionError) as exc_info:
            manager._execute_mksquashfs_command(
                str(source), str(output), [], "zstd", "1M", 1
            )

        assert exc_info.value.command == "mksquashfs"
        assert exc_info.value.return_code == 1
        assert "Failed to create archive" in exc_info.value.message
        assert isinstance(exc_info.value, BuildError)




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



    def test_build_squashfs_nproc_fallback(self, mocker, build_test_files):
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

        source = build_test_files["source"]
        output = build_test_files["tmp_path"] / "output.sqsh"

        # This should not raise an exception and should use 1 processor as fallback
        manager.build_squashfs(str(source), str(output))



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






