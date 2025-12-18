"""
Test cases for the config module.

This module tests the configuration management functionality.
"""

import tempfile

import pytest

from squish.config import SquashFSConfig, get_default_config


class TestSquashFSConfig:
    """Test the SquashFSConfig dataclass."""

    def test_default_config(self):
        """Test that default configuration values are correct."""
        config = SquashFSConfig()
        assert config.mount_base == "mounts"
        assert config.temp_dir == "/tmp"
        assert config.auto_cleanup is True
        assert config.verbose is False

    def test_custom_config(self):
        """Test that custom configuration values are set correctly."""
        config = SquashFSConfig(
            mount_base="custom_mounts",
            temp_dir="/tmp",  # Use existing directory
            auto_cleanup=False,
            verbose=True,
        )
        assert config.mount_base == "custom_mounts"
        assert config.temp_dir == "/tmp"
        assert config.auto_cleanup is False
        assert config.verbose is True

    def test_invalid_mount_base(self):
        """Test that empty mount_base raises ValueError."""
        with pytest.raises(ValueError, match="mount_base cannot be empty"):
            SquashFSConfig(mount_base="")

    def test_invalid_temp_dir(self):
        """Test that empty temp_dir raises ValueError."""
        with pytest.raises(ValueError, match="temp_dir cannot be empty"):
            SquashFSConfig(temp_dir="")

    def test_nonexistent_temp_dir(self):
        """Test that nonexistent temp_dir raises ValueError."""
        with pytest.raises(ValueError, match="temp_dir does not exist"):
            SquashFSConfig(temp_dir="/nonexistent/path")

    def test_temp_dir_not_directory(self):
        """Test that temp_dir pointing to a file raises ValueError."""
        with tempfile.NamedTemporaryFile() as temp_file:
            with pytest.raises(ValueError, match="temp_dir is not a directory"):
                SquashFSConfig(temp_dir=temp_file.name)


def test_get_default_config():
    """Test the get_default_config function."""
    config = get_default_config()
    assert isinstance(config, SquashFSConfig)
    assert config.mount_base == "mounts"
    assert config.temp_dir == "/tmp"
