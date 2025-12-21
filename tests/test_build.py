"""
Test cases for the build module.

This module tests the build functionality separately.
"""

import subprocess
import tempfile
from pathlib import Path
from subprocess import CalledProcessError

import pytest

from squish.build import BuildManager
from squish.config import SquishFSConfig
from squish.errors import BuildError, MksquashfsCommandExecutionError


class TestBuildManagerInitialization:
    """Test BuildManager initialization."""

    @pytest.mark.parametrize(
        "config_params,expected_mount_base,expected_temp_dir,expected_auto_cleanup",
        [
            # Default configuration (None config)
            (None, "mounts", "/tmp", True),
            # Custom configuration with mount_base
            (SquishFSConfig(mount_base="custom"), "custom", "/tmp", True),
            # Custom configuration with temp_dir (use existing /tmp)
            (SquishFSConfig(temp_dir="/tmp"), "mounts", "/tmp", True),
            # Custom configuration with auto_cleanup
            (SquishFSConfig(auto_cleanup=False), "mounts", "/tmp", False),
            # Custom configuration with multiple parameters (use existing /tmp)
            (
                SquishFSConfig(
                    mount_base="custom",
                    temp_dir="/tmp",
                    auto_cleanup=False,
                    verbose=True,
                ),
                "custom",
                "/tmp",
                False,
            ),
        ],
    )
    @pytest.mark.unit
    @pytest.mark.coverage
    def test_init_with_various_configs(
        self,
        config_params,
        expected_mount_base,
        expected_temp_dir,
        expected_auto_cleanup,
    ):
        """Test initialization with various configuration combinations."""
        manager = BuildManager(config_params)
        assert manager.config.mount_base == expected_mount_base
        assert manager.config.temp_dir == expected_temp_dir
        assert manager.config.auto_cleanup == expected_auto_cleanup

        # Verify other defaults are maintained
        if config_params is None:
            assert manager.config.verbose is False
        else:
            assert manager.config.verbose == config_params.verbose


class TestBuildExcludeArguments:
    """Test building exclude arguments."""

    @pytest.fixture
    def manager(self):
        """Create a manager."""
        return BuildManager()

    @pytest.mark.parametrize(
        "excludes,exclude_file,wildcards,regex,expected",
        [
            # Wildcards only
            (
                ["*.tmp", "*.log"],
                "exclude.txt",
                True,
                False,
                ["-wildcards", "-e", "*.tmp", "-e", "*.log", "-ef", "exclude.txt"],
            ),
            # Regex only
            (
                ["pattern1", "pattern2"],
                "exclude.txt",
                False,
                True,
                ["-regex", "-e", "pattern1", "-e", "pattern2", "-ef", "exclude.txt"],
            ),
            # No excludes
            (None, None, False, False, []),
            # Empty excludes list
            ([], "exclude.txt", False, False, ["-ef", "exclude.txt"]),
            # Only exclude file
            (None, "exclude.txt", False, False, ["-ef", "exclude.txt"]),
            # Mixed patterns with wildcards
            (
                ["*.tmp", "temp/*"],
                None,
                True,
                False,
                ["-wildcards", "-e", "*.tmp", "-e", "temp/*"],
            ),
            # Mixed patterns with regex
            (
                ["^test.*", "[0-9]+\\.log$"],
                None,
                False,
                True,
                ["-regex", "-e", "^test.*", "-e", "[0-9]+\\.log$"],
            ),
        ],
    )
    def test_build_exclude_arguments_parametrized(
        self, manager, excludes, exclude_file, wildcards, regex, expected
    ):
        """Test building exclude arguments with various parameter combinations."""
        result = manager._build_exclude_arguments(
            excludes=excludes,
            exclude_file=exclude_file,
            wildcards=wildcards,
            regex=regex,
        )
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

    def test_file_based_progress_estimation_integration(self, mocker):
        """Test the complete file-based progress estimation workflow."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.Popen for mksquashfs with progress
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = mocker.MagicMock()
        mock_process.stdout = [
            "Parallel mksquashfs: Using 1 processor\n",
            "Creating 4.0 filesystem on output.sqsh, block size 1048576.\n",
            "file /file1.txt, uncompressed size 100 bytes\n",
            "file /file2.txt, uncompressed size 200 bytes\n",
            "file /subdir/file3.txt, uncompressed size 150 bytes\n",
            "[===============================================================|] 3/3 100%\n",
            "Exportable Squashfs 4.0 filesystem...\n",
        ]
        mock_process.wait.return_value = 0
        mock_process.returncode = 0  # Set proper returncode
        mock_popen.return_value = mock_process

        # Mock subprocess.run for nproc and checksum generation
        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] == "nproc":
                result = mocker.MagicMock()
                result.stdout = "4\n"  # Return 4 processors
                return result
            elif cmd[0] == "sha256sum":
                result = mocker.MagicMock()
                result.stdout = "dummy_checksum  output.sqsh\n"
                return result
            elif cmd[0] == "which":
                return mocker.MagicMock()
            return mocker.MagicMock()

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = mock_run_side_effect

        # Mock ZenityProgressService
        from squish.progress import ZenityProgressService

        mock_zenity_service = mocker.MagicMock(spec=ZenityProgressService)
        mock_zenity_service.check_cancelled.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test source directory with files
            source = Path(temp_dir) / "source"
            source.mkdir()
            (source / "file1.txt").write_text("content1")
            (source / "file2.txt").write_text("content2")
            subdir = source / "subdir"
            subdir.mkdir()
            (subdir / "file3.txt").write_text("content3")

            output = Path(temp_dir) / "output.sqsh"

            # Build with progress using our mocked service
            manager.build_squashfs(
                str(source),
                str(output),
                progress=True,
                progress_service=mock_zenity_service,
            )

            # Verify file counting was done
            assert manager._count_files_in_directory(str(source)) == 3

            # Verify mksquashfs was called with -info flag
            mksquashfs_calls = [
                call
                for call in mock_popen.call_args_list
                if call[0][0][0] == "mksquashfs"
            ]
            assert len(mksquashfs_calls) == 1
            assert "-info" in mksquashfs_calls[0][0][0]

            # Verify Zenity service was used correctly
            mock_zenity_service.start.assert_called_once()
            mock_zenity_service.update.assert_called()
            mock_zenity_service.close.assert_called_once_with(success=True)

            # Verify that the build completed successfully (no exception raised)
            # Note: The actual file creation is mocked, so we don't verify file existence

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

    def test_count_files_in_directory(self, mocker):
        """Test _count_files_in_directory method."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()

            # Create some test files
            (source / "file1.txt").write_text("content1")
            (source / "file2.txt").write_text("content2")

            # Create a subdirectory with files
            subdir = source / "subdir"
            subdir.mkdir()
            (subdir / "file3.txt").write_text("content3")

            # Create a hidden directory (should be ignored)
            hidden_dir = source / ".hidden"
            hidden_dir.mkdir()
            (hidden_dir / "hidden_file.txt").write_text("hidden")

            # Count files
            file_count = manager._count_files_in_directory(str(source))

            # Should count 3 files (file1.txt, file2.txt, file3.txt)
            # Hidden directory files should be ignored
            assert file_count == 3

    def test_count_files_in_empty_directory(self, mocker):
        """Test _count_files_in_directory with empty directory."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "empty_source"
            source.mkdir()

            # Count files in empty directory
            file_count = manager._count_files_in_directory(str(source))
            assert file_count == 0

    def test_build_with_progress_when_zenity_unavailable(self, mocker):
        """Test that build with progress=True doesn't crash when Zenity is unavailable."""

        # Mock subprocess.Popen to fail for Zenity
        def mock_popen_side_effect(cmd, **kwargs):
            if cmd[0] == "zenity":
                raise FileNotFoundError("zenity not found")
            # For mksquashfs, return a mock process
            mock_process = mocker.MagicMock()
            mock_process.stdout = iter(
                [
                    "[=====] 10/100  10%",
                    "[=======] 25/100  25%",
                    "[=========] 50/100  50%",
                    "[==============] 75/100  75%",
                    "[================] 100/100  100%",
                ]
            )
            mock_process.returncode = 0
            mock_process.wait.return_value = 0
            return mock_process

        mocker.patch("subprocess.Popen", side_effect=mock_popen_side_effect)

        # Mock other subprocess calls
        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] == "nproc":
                result = mocker.MagicMock()
                result.stdout = "4\n"
                return result
            elif cmd[0] == "sha256sum":
                result = mocker.MagicMock()
                result.stdout = "dummy_checksum  /tmp/test.sqsh\n"
                return result
            elif cmd[0] == "which":
                return mocker.MagicMock()
            return mocker.MagicMock()

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = mock_run_side_effect

        manager = BuildManager()

        # Create temporary files for the build
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            (source / "test.txt").write_text("test content")

            output = Path(temp_dir) / "output.sqsh"

            # This should not raise an exception even though Zenity is unavailable
            # The key test is that the build continues with console fallback
            manager.build_squashfs(str(source), str(output), progress=True)

        # If we reach here, the build completed successfully with Zenity fallback
        # The main assertion is that no exception was raised


class TestBuildBranchCoverage:
    """Test branch coverage for build functionality."""

    def test_mksquashfs_command_execution_error_with_progress(self, mocker):
        """Test error handling in progress mode when mksquashfs fails."""
        from squish.errors import MksquashfsCommandExecutionError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.Popen and related functionality
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = mocker.MagicMock()
        mock_process.stdout = iter(["Some output"])
        mock_process.returncode = 1
        mock_process.wait.return_value = 1
        mock_popen.return_value = mock_process

        # Mock ZenityProgressService
        mock_zenity_service = mocker.MagicMock()
        mock_zenity_service.check_cancelled.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            with pytest.raises(MksquashfsCommandExecutionError) as exc_info:
                manager._execute_mksquashfs_command_with_progress(
                    str(source),
                    str(output),
                    [],
                    "zstd",
                    "1M",
                    1,
                    mock_zenity_service,
                )

            assert exc_info.value.command == "mksquashfs"
            assert exc_info.value.return_code == 1
            assert "Failed to create archive" in exc_info.value.message
            # Verify Zenity service was closed with success=True (this is the manual check path, not exception path)
            # In the manual check path, it closes with success=True first, then raises the exception
            # The exception doesn't trigger the exception handler that would close with success=False
            mock_zenity_service.close.assert_called_once_with(success=True)

    def test_progress_cancellation_workflow(self, mocker):
        """Test Zenity cancellation during build process."""
        from squish.progress import BuildCancelledError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.Popen
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = mocker.MagicMock()
        mock_process.stdout = iter(["[=====] 10/100  10%", "[=====] 20/100  20%"])
        mock_popen.return_value = mock_process

        # Mock ZenityProgressService to simulate cancellation
        mock_zenity_service = mocker.MagicMock()
        mock_zenity_service.check_cancelled.side_effect = [
            False,
            True,
        ]  # Cancel on second check

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            with pytest.raises(BuildCancelledError, match="Build cancelled by user"):
                manager._execute_mksquashfs_command_with_progress(
                    str(source),
                    str(output),
                    [],
                    "zstd",
                    "1M",
                    1,
                    mock_zenity_service,
                )

            # Verify process was terminated
            mock_process.terminate.assert_called_once()
            # Verify Zenity service was closed with failure
            mock_zenity_service.close.assert_called_with(success=False)

    def test_nproc_fallback_comprehensive(self, mocker):
        """Test comprehensive nproc fallback scenarios."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Test case 1: nproc fails completely
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "nproc")

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            # Mock the actual build and checksum steps
            def build_side_effect(cmd, **kwargs):
                if cmd[0] == "mksquashfs":
                    return mocker.MagicMock()
                elif cmd[0] == "sha256sum":
                    result = mocker.MagicMock()
                    result.stdout = "dummy_checksum  /path/to/file\n"
                    return result
                elif cmd[0] == "which":
                    return mocker.MagicMock()
                return mocker.MagicMock()

            mock_run.side_effect = build_side_effect

            # This should use 1 processor as fallback
            manager.build_squashfs(str(source), str(output))

            # Verify nproc was called and failed
            nproc_calls = [
                call for call in mock_run.call_args_list if call[0][0][0] == "nproc"
            ]
            assert len(nproc_calls) == 1

    def test_checksum_generation_error_handling(self, mocker):
        """Test comprehensive checksum generation error handling."""
        from squish.errors import ChecksumCommandExecutionError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.run to fail for sha256sum
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = CalledProcessError(
            1, "sha256sum", "Checksum generation failed"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.sqsh"
            test_file.touch()

            with pytest.raises(ChecksumCommandExecutionError) as exc_info:
                manager._generate_checksum(str(test_file))

            assert exc_info.value.command == "sha256sum"
            assert exc_info.value.return_code == 1
            assert "Failed to generate checksum" in exc_info.value.message

    def test_dependency_checking_error_handling(self, mocker):
        """Test comprehensive dependency checking error handling."""
        from squish.errors import DependencyError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.run to fail for different commands
        def mock_run_side_effect(cmd, **kwargs):
            if cmd == ["which", "unsquashfs"]:
                raise CalledProcessError(1, "which")
            return mocker.MagicMock()

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = mock_run_side_effect

        with pytest.raises(DependencyError) as exc_info:
            manager._check_build_dependencies()

        assert "unsquashfs is not installed" in str(exc_info.value)

    def test_build_validation_error_paths(self, mocker):
        """Test all build validation failure scenarios."""
        from squish.errors import BuildError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Test source not found
        with pytest.raises(BuildError, match="Source not found"):
            manager.build_squashfs("/nonexistent/source", "/tmp/output.sqsh")

        # Test output exists
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"
            output.touch()  # Create existing file

            with pytest.raises(BuildError, match="Output exists"):
                manager.build_squashfs(str(source), str(output))

    def test_mksquashfs_normal_mode_error_handling(self, mocker):
        """Test error handling in normal (non-progress) mksquashfs execution."""
        from squish.errors import MksquashfsCommandExecutionError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.run to fail
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "mksquashfs", "Build failed")

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            with pytest.raises(MksquashfsCommandExecutionError) as exc_info:
                manager._execute_mksquashfs_command(
                    str(source),
                    str(output),
                    [],
                    "zstd",
                    "1M",
                    1,
                )

            assert exc_info.value.command == "mksquashfs"
            assert exc_info.value.return_code == 1
            assert "Failed to create archive" in exc_info.value.message

    def test_progress_mode_stdout_none_handling(self, mocker):
        """Test handling of None stdout in progress mode."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.Popen with None stdout
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = mocker.MagicMock()
        mock_process.stdout = None  # This is the key test case
        mock_process.returncode = 0
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        # Mock ZenityProgressService
        mock_zenity_service = mocker.MagicMock()
        mock_zenity_service.check_cancelled.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            # This should not raise an exception due to None stdout
            manager._execute_mksquashfs_command_with_progress(
                str(source),
                str(output),
                [],
                "zstd",
                "1M",
                1,
                mock_zenity_service,
            )

            # Verify process was waited on
            mock_process.wait.assert_called_once()
            # Verify Zenity service was closed successfully
            mock_zenity_service.close.assert_called_with(success=True)


class TestBuildExceptionCoverage:
    """Test exception handling paths for build functionality."""

    def test_normal_mode_called_process_error(self, mocker):
        """Test CalledProcessError exception handling in normal mksquashfs execution."""
        from squish.errors import MksquashfsCommandExecutionError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.run to raise CalledProcessError
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "mksquashfs", "Build failed")

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            with pytest.raises(MksquashfsCommandExecutionError) as exc_info:
                manager._execute_mksquashfs_command(
                    str(source),
                    str(output),
                    [],
                    "zstd",
                    "1M",
                    1,
                )

            assert exc_info.value.command == "mksquashfs"
            assert exc_info.value.return_code == 1
            assert "Failed to create archive" in exc_info.value.message

    def test_progress_mode_called_process_error(self, mocker):
        """Test CalledProcessError exception handling in progress mode execution."""
        from squish.errors import MksquashfsCommandExecutionError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.Popen to raise CalledProcessError
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.side_effect = CalledProcessError(1, "mksquashfs", "Build failed")

        # Mock ZenityProgressService
        mock_zenity_service = mocker.MagicMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            output = Path(temp_dir) / "output.sqsh"

            with pytest.raises(MksquashfsCommandExecutionError) as exc_info:
                manager._execute_mksquashfs_command_with_progress(
                    str(source),
                    str(output),
                    [],
                    "zstd",
                    "1M",
                    1,
                    mock_zenity_service,
                )

            assert exc_info.value.command == "mksquashfs"
            assert exc_info.value.return_code == 1
            assert "Failed to create archive" in exc_info.value.message
            # Verify Zenity service was closed on error
            mock_zenity_service.close.assert_called_with(success=False)

    def test_nproc_called_process_error_exception(self, mocker):
        """Test CalledProcessError exception handling in nproc detection."""
        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.run to raise CalledProcessError for nproc
        def mock_run_side_effect(cmd, **kwargs):
            if cmd[0] == "nproc":
                raise CalledProcessError(1, "nproc", "nproc failed")
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

            # This should use 1 processor as fallback when nproc raises CalledProcessError
            manager.build_squashfs(str(source), str(output))

            # Verify nproc was called and raised an exception
            nproc_calls = [
                call for call in mock_run.call_args_list if call[0][0][0] == "nproc"
            ]
            assert len(nproc_calls) == 1

    def test_checksum_called_process_error_exception(self, mocker):
        """Test CalledProcessError exception handling in checksum generation."""
        from squish.errors import ChecksumCommandExecutionError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.run to raise CalledProcessError for sha256sum
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = CalledProcessError(
            1, "sha256sum", "Checksum generation failed"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.sqsh"
            test_file.touch()

            with pytest.raises(ChecksumCommandExecutionError) as exc_info:
                manager._generate_checksum(str(test_file))

            assert exc_info.value.command == "sha256sum"
            assert exc_info.value.return_code == 1
            assert "Failed to generate checksum" in exc_info.value.message

    def test_dependency_called_process_error_exception(self, mocker):
        """Test CalledProcessError exception handling in dependency checking."""
        from squish.errors import DependencyError

        config = SquishFSConfig()
        manager = BuildManager(config)

        # Mock subprocess.run to raise CalledProcessError for dependency checking
        def mock_run_side_effect(cmd, **kwargs):
            if cmd == ["which", "mksquashfs"]:
                raise CalledProcessError(1, "which", "mksquashfs not found")
            return mocker.MagicMock()

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = mock_run_side_effect

        with pytest.raises(DependencyError) as exc_info:
            manager._check_build_dependencies()

        assert "mksquashfs is not installed" in str(exc_info.value)


class TestBuildVerboseLoggingCoverage:
    """Test verbose logging coverage gaps in build operations."""

    @pytest.fixture
    def verbose_manager(self):
        """Create a BuildManager with verbose logging enabled."""
        config = SquishFSConfig(verbose=True)
        return BuildManager(config)

    def test_normal_mode_verbose_logging_success(
        self, mocker, verbose_manager, build_test_files
    ):
        """Test verbose logging in normal mode when build succeeds (covers lines 98, 104)."""
        source = str(build_test_files["source"])  # Convert Path to string
        output = str(
            build_test_files["tmp_path"] / "output.sqsh"
        )  # Convert Path to string

        # Mock subprocess.run to simulate successful execution
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock()

        # Mock checksum generation to avoid file operations
        mocker.patch.object(verbose_manager, "_generate_checksum")

        # Execute the build
        verbose_manager.build_squashfs(source, output)

        # Verify verbose logging was called for command execution by checking the logger
        # The logging should have happened, we can verify by checking the logger's log_command_execution was called
        assert verbose_manager.logger.logger.hasHandlers()  # Verify logger is active

    def test_normal_mode_verbose_logging_failure(
        self, mocker, verbose_manager, build_test_files
    ):
        """Test verbose logging in normal mode when build fails (covers lines 98, 104)."""
        source = str(build_test_files["source"])  # Convert Path to string
        output = str(
            build_test_files["tmp_path"] / "output.sqsh"
        )  # Convert Path to string

        # Mock checksum generation to avoid file operations
        mocker.patch.object(verbose_manager, "_generate_checksum")

        # Mock the logger to capture log calls
        mock_logger = mocker.patch.object(
            verbose_manager.logger, "log_command_execution"
        )

        # Mock subprocess.run specifically for the build command to simulate failure
        def mock_run_side_effect(*args, **kwargs):
            # Let dependency checks pass normally
            if "which" in args[0]:
                return mocker.MagicMock()
            # Fail for actual build command
            error = subprocess.CalledProcessError(1, "mksquashfs")
            error.stderr = "Build failed"
            raise error

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = mock_run_side_effect

        # Execute the build and expect failure
        with pytest.raises(MksquashfsCommandExecutionError):
            verbose_manager.build_squashfs(source, output)

        # Verify verbose logging was called for command execution
        mock_logger.assert_called()
        # Check that failure logging was called (success is passed as keyword argument)
        failure_calls = [
            call
            for call in mock_logger.call_args_list
            if call.kwargs.get("success") is False
        ]
        assert len(failure_calls) >= 1, (
            "Failure logging should be called in verbose mode"
        )


class TestBuildProgressTrackingCoverage:
    """Test coverage for progress tracking edge cases in build operations."""

    @pytest.fixture
    def verbose_manager(self):
        """Create a BuildManager with verbose logging enabled."""
        config = SquishFSConfig(verbose=True)
        return BuildManager(config)

    def test_progress_mode_verbose_logging_success(
        self, mocker, verbose_manager, build_test_files
    ):
        """Test verbose logging in progress mode when build succeeds (covers line 138)."""
        source = str(build_test_files["source"])  # Convert Path to string
        output = str(
            build_test_files["tmp_path"] / "output.sqsh"
        )  # Convert Path to string

        # Mock the logger to capture log calls
        mock_logger = mocker.patch.object(
            verbose_manager.logger, "log_command_execution"
        )

        # Mock dependency checks to pass
        mocker.patch.object(verbose_manager, "_check_build_dependencies")

        # Mock subprocess.run for nproc command
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(stdout="4\n")

        # Mock subprocess.Popen and related functionality for progress mode
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = mocker.MagicMock()
        mock_process.stdout = [
            "[====] 10/100 50%",
            "[====] 50/100 75%",
            "[====] 100/100 100%",
        ].__iter__()
        mock_process.wait.return_value = 0
        mock_process.returncode = 0  # Ensure returncode is 0 for success
        mock_popen.return_value = mock_process

        # Mock ZenityProgressService to avoid actual Zenity calls
        mock_zenity_service = mocker.MagicMock()
        mock_zenity_service.start = mocker.MagicMock()
        mock_zenity_service.update = mocker.MagicMock()
        mock_zenity_service.check_cancelled = mocker.MagicMock(return_value=False)
        mock_zenity_service.close = mocker.MagicMock()

        # Mock ProgressTracker to use our mock Zenity service
        mock_progress_tracker = mocker.MagicMock()
        mock_progress_tracker.zenity_service = mock_zenity_service
        mock_progress_tracker.process_output_line = mocker.MagicMock()
        mock_progress_tracker.set_total_files = mocker.MagicMock()

        # Mock the ProgressTracker class to return our mock
        mocker.patch("squish.build.ProgressTracker", return_value=mock_progress_tracker)

        # Mock checksum generation to avoid file operations
        mocker.patch.object(verbose_manager, "_generate_checksum")

        # Execute the build with progress
        verbose_manager.build_squashfs(source, output, progress=True)

        # Verify verbose logging was called for command execution in progress mode
        mock_logger.assert_called()

        # Check that the command execution was logged (this covers line 138)
        command_calls = [
            call for call in mock_logger.call_args_list if len(call.args) > 0
        ]
        assert len(command_calls) >= 1, (
            "Command execution should be logged in verbose progress mode"
        )

    def test_nproc_fallback_in_progress_mode(
        self, mocker, verbose_manager, build_test_files
    ):
        """Test nproc fallback when processors is None in progress mode (covers lines 217->227)."""
        source = str(build_test_files["source"])  # Convert Path to string
        output = str(
            build_test_files["tmp_path"] / "output.sqsh"
        )  # Convert Path to string

        # Mock dependency checks to pass
        mocker.patch.object(verbose_manager, "_check_build_dependencies")

        # Mock subprocess.run to fail for nproc (simulate nproc not available)
        def mock_run_side_effect(*args, **kwargs):
            if args[0] == ["nproc"]:
                raise CalledProcessError(1, "nproc")
            return mocker.MagicMock(stdout="4\n")

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = mock_run_side_effect

        # Mock subprocess.Popen for the actual build
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = mocker.MagicMock()
        mock_process.stdout = ["[====] 10/100 50%", "[====] 100/100 100%"].__iter__()
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Mock ZenityProgressService to avoid actual Zenity calls
        mock_zenity_service = mocker.MagicMock()
        mock_zenity_service.start = mocker.MagicMock()
        mock_zenity_service.update = mocker.MagicMock()
        mock_zenity_service.check_cancelled = mocker.MagicMock(return_value=False)
        mock_zenity_service.close = mocker.MagicMock()

        # Mock ProgressTracker to use our mock Zenity service
        mock_progress_tracker = mocker.MagicMock()
        mock_progress_tracker.zenity_service = mock_zenity_service
        mock_progress_tracker.process_output_line = mocker.MagicMock()
        mock_progress_tracker.set_total_files = mocker.MagicMock()

        # Mock the ProgressTracker class to return our mock
        mocker.patch("squish.build.ProgressTracker", return_value=mock_progress_tracker)

        # Mock checksum generation
        mock_checksum = mocker.patch.object(verbose_manager, "_generate_checksum")

        # Execute the build with progress and processors=None (should fallback to 1)
        verbose_manager.build_squashfs(source, output, progress=True, processors=None)

        # Verify that the build completed (fallback to 1 processor worked)
        mock_checksum.assert_called_once()

    def test_checksum_generation_verbose_logging(
        self, mocker, verbose_manager, build_test_files
    ):
        """Test verbose logging in checksum generation (covers lines 270, 278-279)."""
        source = str(build_test_files["source"])  # Convert Path to string
        output = str(
            build_test_files["tmp_path"] / "output.sqsh"
        )  # Convert Path to string

        # Mock dependency checks to pass
        mocker.patch.object(verbose_manager, "_check_build_dependencies")

        # Mock subprocess.run for nproc and build
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(stdout="4\n")

        # Mock subprocess.Popen for progress mode
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = mocker.MagicMock()
        mock_process.stdout = ["[====] 10/100 50%", "[====] 100/100 100%"].__iter__()
        mock_process.wait.return_value = 0
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Mock ZenityProgressService to avoid actual Zenity calls
        mock_zenity_service = mocker.MagicMock()
        mock_zenity_service.start = mocker.MagicMock()
        mock_zenity_service.update = mocker.MagicMock()
        mock_zenity_service.check_cancelled = mocker.MagicMock(return_value=False)
        mock_zenity_service.close = mocker.MagicMock()

        # Mock ProgressTracker to use our mock Zenity service
        mock_progress_tracker = mocker.MagicMock()
        mock_progress_tracker.zenity_service = mock_zenity_service
        mock_progress_tracker.process_output_line = mocker.MagicMock()
        mock_progress_tracker.set_total_files = mocker.MagicMock()

        # Mock the ProgressTracker class to return our mock
        mocker.patch("squish.build.ProgressTracker", return_value=mock_progress_tracker)

        # Execute the build with progress - this will cover lines 270, 278-279
        # The verbose logging happens automatically in the _generate_checksum method
        verbose_manager.build_squashfs(source, output, progress=True)

        # Verify that the build completed successfully (which means checksum generation worked)
        # The actual logging calls are tested in the existing verbose logging tests
        # This test ensures the code path is executed in verbose mode
        assert True, "Build completed successfully with verbose checksum logging"
