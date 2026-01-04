"""
Cross-module test patterns for dependency checking and other shared behaviors.

This module contains consolidated tests for patterns that are repeated across
multiple modules (build, extract, checksum, etc.) to reduce redundancy.
"""

import subprocess

import pytest

from squish.build import BuildManager
from squish.checksum import ChecksumManager
from squish.config import SquishFSConfig
from squish.errors import DependencyError
from squish.extract import ExtractManager


class TestDependencyCheckingPatterns:
    """Consolidated tests for dependency checking patterns across modules."""

    @pytest.mark.parametrize(
        "manager_class,command,module_path,expected_error_message",
        [
            # Build module dependencies
            (
                BuildManager,
                "mksquashfs",
                "subprocess",
                "is not installed or not in PATH",
            ),
            (
                BuildManager,
                "unsquashfs",
                "subprocess",
                "is not installed or not in PATH",
            ),
            (BuildManager, "nproc", "subprocess", "is not installed or not in PATH"),
            # Extract module dependencies
            (ExtractManager, "unsquashfs", "subprocess", "unsquashfs is not installed"),
        ],
    )
    def test_dependency_checking_success_patterns(
        self,
        mocker,
        dependency_check_fixture,
        manager_class,
        command,
        module_path,
        expected_error_message,
    ):
        """Test successful dependency checking across all modules using parametrization."""
        # Create manager instance
        config = SquishFSConfig()
        manager = manager_class(config)

        # Setup successful dependency check
        dependency_check_fixture(
            manager, command, success=True, module_path=module_path
        )

        # Execute the appropriate dependency check method
        if isinstance(manager, BuildManager):
            manager._check_build_dependencies()
        elif isinstance(manager, ExtractManager):
            manager._check_extract_dependencies()

        # Should not raise any exceptions for successful checks
        # This is verified by the test not failing

    @pytest.mark.parametrize(
        "manager_class,command,module_path,expected_error_message",
        [
            # Build module dependencies
            (BuildManager, "mksquashfs", "subprocess", "mksquashfs is not installed"),
            (BuildManager, "unsquashfs", "subprocess", "unsquashfs is not installed"),
            (BuildManager, "nproc", "subprocess", "nproc is not installed"),
            # Extract module dependencies
            (ExtractManager, "unsquashfs", "subprocess", "unsquashfs is not installed"),
        ],
    )
    def test_dependency_checking_failure_patterns(
        self,
        mocker,
        dependency_check_fixture,
        manager_class,
        command,
        module_path,
        expected_error_message,
    ):
        """Test failed dependency checking across all modules using parametrization."""
        # Create manager instance
        config = SquishFSConfig()
        manager = manager_class(config)

        # For BuildManager, we need to mock all dependencies except the one we want to fail
        if isinstance(manager, BuildManager):
            mock_run = mocker.patch(f"{module_path}.run")

            def mock_run_side_effect(cmd, **kwargs):
                if cmd == ["which", command]:
                    from subprocess import CalledProcessError

                    raise CalledProcessError(1, f"which {command}")
                else:
                    # Other commands succeed
                    return mocker.MagicMock(returncode=0, check=lambda: True)

            mock_run.side_effect = mock_run_side_effect
        else:
            # For other managers, use the standard fixture
            dependency_check_fixture(
                manager, command, success=False, module_path=module_path
            )

        # Execute the appropriate dependency check method and verify exception
        if isinstance(manager, BuildManager):
            with pytest.raises(DependencyError, match=f"{command} is not installed"):
                manager._check_build_dependencies()
        elif isinstance(manager, ExtractManager):
            with pytest.raises(DependencyError, match=expected_error_message):
                manager._check_extract_dependencies()


class TestDependencyCheckingImplementation:
    """Consolidated tests for dependency checking implementation details."""

    @pytest.mark.parametrize(
        "manager_class,expected_commands,expected_error_commands",
        [
            # BuildManager checks multiple commands
            (
                BuildManager,
                ["mksquashfs", "unsquashfs", "nproc"],
                ["mksquashfs", "unsquashfs", "nproc"],
            ),
            # ExtractManager checks only unsquashfs
            (ExtractManager, ["unsquashfs"], ["unsquashfs"]),
        ],
    )
    def test_dependency_checking_implementation_details(
        self, mocker, manager_class, expected_commands, expected_error_commands
    ):
        """Test that dependency checking calls the expected commands with correct parameters."""
        # Create manager instance
        config = SquishFSConfig()
        manager = manager_class(config)

        # Mock successful subprocess.run
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock()

        # Execute the appropriate dependency check method
        if isinstance(manager, BuildManager):
            manager._check_build_dependencies()
        elif isinstance(manager, ExtractManager):
            manager._check_extract_dependencies()

        # Verify that 'which' commands were called for the expected dependencies
        calls = mock_run.call_args_list
        commands_checked = [call[0][0][1] for call in calls if call[0][0][0] == "which"]

        # Verify all expected commands were checked
        for cmd in expected_commands:
            assert cmd in commands_checked, f"Expected command {cmd} was not checked"

        # Verify each command was called with correct parameters
        for call in calls:
            if call[0][0][0] == "which":
                assert call[1] == {
                    "check": True,
                    "stdout": subprocess.PIPE,
                    "stderr": subprocess.PIPE,
                }

    @pytest.mark.parametrize(
        "manager_class,failing_command,expected_error_message",
        [
            # Test each BuildManager command failure
            (BuildManager, "mksquashfs", "mksquashfs is not installed"),
            (BuildManager, "unsquashfs", "unsquashfs is not installed"),
            (BuildManager, "nproc", "nproc is not installed"),
            # Test ExtractManager command failure
            (ExtractManager, "unsquashfs", "unsquashfs is not installed"),
        ],
    )
    def test_dependency_checking_specific_command_failures(
        self, mocker, manager_class, failing_command, expected_error_message
    ):
        """Test that specific command failures are handled correctly."""
        # Create manager instance
        config = SquishFSConfig()
        manager = manager_class(config)

        # Mock subprocess.run to fail only for the specific command
        def mock_run_side_effect(cmd, **kwargs):
            if cmd == ["which", failing_command]:
                from subprocess import CalledProcessError

                raise CalledProcessError(1, f"which {failing_command}")
            else:
                # Other commands succeed
                return mocker.MagicMock(returncode=0, check=lambda: True)

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = mock_run_side_effect

        # Execute the appropriate dependency check method and verify exception
        if isinstance(manager, BuildManager):
            with pytest.raises(DependencyError, match=expected_error_message):
                manager._check_build_dependencies()
        elif isinstance(manager, ExtractManager):
            with pytest.raises(DependencyError, match=expected_error_message):
                manager._check_extract_dependencies()


class TestManagerInitializationPatterns:
    """Consolidated tests for manager initialization patterns across modules."""

    @pytest.mark.parametrize(
        "manager_class,expected_defaults",
        [
            # BuildManager default configuration
            (
                BuildManager,
                {
                    "mount_base": "mounts",
                    "temp_dir": "/tmp",
                    "auto_cleanup": True,
                    "verbose": False,
                },
            ),
            # ExtractManager default configuration
            (
                ExtractManager,
                {
                    "mount_base": "mounts",
                    "temp_dir": "/tmp",
                    "auto_cleanup": True,
                    "verbose": False,
                },
            ),
            # ChecksumManager default configuration
            (
                ChecksumManager,
                {
                    "mount_base": "mounts",
                    "temp_dir": "/tmp",
                    "auto_cleanup": True,
                    "verbose": False,
                },
            ),
        ],
    )
    def test_manager_initialization_with_defaults(
        self, manager_class, expected_defaults
    ):
        """Test manager initialization with default configuration across all modules."""
        manager = manager_class()

        # Verify all expected default values
        for key, expected_value in expected_defaults.items():
            actual_value = getattr(manager.config, key)
            assert actual_value == expected_value, (
                f"Expected {key}={expected_value}, got {actual_value}"
            )

    @pytest.mark.parametrize(
        "manager_class,custom_config,expected_overrides",
        [
            # BuildManager with custom mount_base
            (
                BuildManager,
                SquishFSConfig(mount_base="custom"),
                {"mount_base": "custom"},
            ),
            # ExtractManager with custom auto_cleanup
            (
                ExtractManager,
                SquishFSConfig(auto_cleanup=False),
                {"auto_cleanup": False},
            ),
            # ChecksumManager with custom verbose
            (ChecksumManager, SquishFSConfig(verbose=True), {"verbose": True}),
            # BuildManager with multiple custom parameters
            (
                BuildManager,
                SquishFSConfig(mount_base="custom", auto_cleanup=False, verbose=True),
                {"mount_base": "custom", "auto_cleanup": False, "verbose": True},
            ),
        ],
    )
    def test_manager_initialization_with_custom_config(
        self, manager_class, custom_config, expected_overrides
    ):
        """Test manager initialization with custom configuration across all modules."""
        manager = manager_class(custom_config)

        # Verify custom values override defaults
        for key, expected_value in expected_overrides.items():
            actual_value = getattr(manager.config, key)
            assert actual_value == expected_value, (
                f"Expected {key}={expected_value}, got {actual_value}"
            )

        # Verify defaults are maintained for non-overridden values
        # (mount_base default is "mounts", temp_dir default is "/tmp")
        if "mount_base" not in expected_overrides:
            assert manager.config.mount_base == "mounts"
        if "temp_dir" not in expected_overrides:
            assert manager.config.temp_dir == "/tmp"


class TestOperationSuccessFailurePatterns:
    """Consolidated tests for operation success/failure patterns across modules."""

    # This class can be expanded with more parametrized tests for
    # build success/failure, extract success/failure, etc.
    pass
