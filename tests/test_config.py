"""
Test cases for the config module.

This module tests the configuration management functionality.
"""

import tempfile

import pytest

from squish.config import SquishFSConfig, get_default_config


class TestSquishFSConfig:
    """Test the SquishFSConfig dataclass."""

    def test_default_config(self):
        """Test that default configuration values are correct."""
        config = SquishFSConfig()
        assert config.mount_base == "mounts"
        assert config.temp_dir == "/tmp"
        assert config.auto_cleanup is True
        assert config.verbose is False

    def test_custom_config(self):
        """Test that custom configuration values are set correctly."""
        config = SquishFSConfig(
            mount_base="custom_mounts",
            temp_dir="/tmp",  # Use existing directory
            auto_cleanup=False,
            verbose=True,
        )
        assert config.mount_base == "custom_mounts"
        assert config.temp_dir == "/tmp"
        assert config.auto_cleanup is False
        assert config.verbose is True

    @pytest.mark.parametrize(
        "param,value,expected_error_message",
        [
            ("mount_base", "", "mount_base cannot be empty"),
            ("temp_dir", "", "temp_dir cannot be empty"),
            ("temp_dir", "/nonexistent/path", "temp_dir does not exist"),
        ],
    )
    def test_invalid_config_parameters(self, param, value, expected_error_message):
        """Test that invalid configuration parameters raise ValueError."""
        kwargs = {param: value}
        with pytest.raises(ValueError, match=expected_error_message):
            SquishFSConfig(**kwargs)

    def test_temp_dir_not_directory(self):
        """Test that temp_dir pointing to a file raises ValueError."""
        with tempfile.NamedTemporaryFile() as temp_file:
            with pytest.raises(ValueError, match="temp_dir is not a directory"):
                SquishFSConfig(temp_dir=temp_file.name)


def test_get_default_config():
    """Test the get_default_config function."""
    config = get_default_config()
    assert isinstance(config, SquishFSConfig)
    assert config.mount_base == "mounts"
    assert config.temp_dir == "/tmp"
