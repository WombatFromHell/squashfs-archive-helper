"""
Test cases for the core module.

This module tests the core functionality of the SquashFSManager class.
"""

import pytest

from squish.config import SquishFSConfig
from squish.core import SquashFSManager
from squish.errors import DependencyError


class TestSquashFSManagerInitialization:
    """Test SquashFSManager initialization functionality."""

    def test_init_with_default_config(self, mocker):
        """Test initialization with default configuration."""
        # Mock dependencies to avoid actual system calls
        mocker.patch("squish.dependencies.check_all_dependencies")

        manager = SquashFSManager()
        assert isinstance(manager.config, SquishFSConfig)
        assert manager.config.mount_base == "mounts"  # Default value

    def test_init_with_custom_config(self, mocker):
        """Test initialization with custom configuration."""
        # Mock dependencies to avoid actual system calls
        mocker.patch("squish.dependencies.check_all_dependencies")

        custom_config = SquishFSConfig(mount_base="custom_mounts")
        manager = SquashFSManager(custom_config)
        assert manager.config == custom_config
        assert manager.config.mount_base == "custom_mounts"


class TestSquashFSManagerCoverageGaps:
    """Test coverage gap scenarios for SquashFSManager."""

    def test_init_non_linux_os(self, mocker):
        """Test initialization fails on non-Linux OS."""
        # Mock platform.system to return a non-Linux OS in the dependencies module
        # since that's where the call to platform.system() happens
        mocker.patch("squish.dependencies.platform.system", return_value="Windows")

        with pytest.raises(
            DependencyError, match="This script is currently only supported on Linux"
        ):
            SquashFSManager()

    def test_init_with_dependency_error(self, mocker):
        """Test initialization when dependency check fails."""
        # Mock the check_all_dependencies to raise an exception
        mocker.patch(
            "squish.core.check_all_dependencies",
            side_effect=DependencyError("Dependency missing"),
        )

        with pytest.raises(DependencyError, match="Dependency missing"):
            SquashFSManager(config=SquishFSConfig())


class TestSquashFSManagerFunctionality:
    """Test SquashFSManager functionality methods."""

    def test_mount_method(self, mocker):
        """Test the mount method delegates to mount_manager."""
        # Mock dependencies
        mocker.patch("squish.dependencies.check_all_dependencies")
        mock_mount_manager = mocker.patch("squish.core.MountManager")
        mock_instance = mocker.MagicMock()
        mock_mount_manager.return_value = mock_instance

        manager = SquashFSManager()
        manager.mount_manager = mock_instance

        # Call the method
        manager.mount("test.squashfs", "/mnt/test")

        # Verify delegation
        mock_instance.mount.assert_called_once_with("test.squashfs", "/mnt/test")

    def test_unmount_method(self, mocker):
        """Test the unmount method delegates to mount_manager."""
        # Mock dependencies
        mocker.patch("squish.dependencies.check_all_dependencies")
        mock_mount_manager = mocker.patch("squish.core.MountManager")
        mock_instance = mocker.MagicMock()
        mock_mount_manager.return_value = mock_instance

        manager = SquashFSManager()
        manager.mount_manager = mock_instance

        # Call the method
        manager.unmount("test.squashfs", "/mnt/test")

        # Verify delegation
        mock_instance.unmount.assert_called_once_with("test.squashfs", "/mnt/test")

    def test_verify_checksum_method(self, mocker):
        """Test the verify_checksum method delegates to checksum_manager."""
        # Mock dependencies
        mocker.patch("squish.dependencies.check_all_dependencies")
        mock_checksum_manager = mocker.patch("squish.core.ChecksumManager")
        mock_instance = mocker.MagicMock()
        mock_checksum_manager.return_value = mock_instance

        manager = SquashFSManager()
        manager.checksum_manager = mock_instance

        # Call the method
        manager.verify_checksum("test.squashfs")

        # Verify delegation
        mock_instance.verify_checksum.assert_called_once_with("test.squashfs")

    def test_build_squashfs_method(self, mocker):
        """Test the build_squashfs method delegates to build_manager."""
        # Mock dependencies
        mocker.patch("squish.dependencies.check_all_dependencies")
        mock_build_manager = mocker.patch("squish.core.BuildManager")
        mock_instance = mocker.MagicMock()
        mock_build_manager.return_value = mock_instance

        manager = SquashFSManager()
        manager.build_manager = mock_instance

        # Call the method with various parameters
        manager.build_squashfs(
            "source_dir",
            "output.squashfs",
            excludes=["*.tmp", "*.log"],
            compression="xz",
            block_size="4M",
            processors=4,
        )

        # Verify delegation
        mock_instance.build_squashfs.assert_called_once_with(
            "source_dir",
            "output.squashfs",
            ["*.tmp", "*.log"],
            None,
            False,
            False,
            "xz",
            "4M",
            4,
            False,  # progress parameter (default value)
            None,
        )

    def test_list_squashfs_method(self, mocker):
        """Test the list_squashfs method delegates to list_manager."""
        # Mock dependencies
        mocker.patch("squish.dependencies.check_all_dependencies")
        mock_list_manager = mocker.patch("squish.core.ListManager")
        mock_instance = mocker.MagicMock()
        mock_list_manager.return_value = mock_instance

        manager = SquashFSManager()
        manager.list_manager = mock_instance

        # Call the method
        manager.list_squashfs("test.squashfs")

        # Verify delegation
        mock_instance.list_squashfs.assert_called_once_with("test.squashfs")
