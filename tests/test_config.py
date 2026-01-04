"""Tests for configuration management functionality."""

import os
import tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from squish.config import (
    SquishFSConfig,
    get_default_config,
    get_env_config,
    get_merged_config,
    load_config_file,
)


class TestConfigFileLoading:
    """Test configuration file loading functionality."""

    def test_load_nonexistent_config_file(self, tmp_path):
        """Test loading config file when it doesn't exist."""
        # Ensure no config file exists
        config_home = tmp_path / ".config"
        config_home.mkdir()

        # Mock XDG_CONFIG_HOME
        old_xdg = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = str(config_home)

        try:
            result = load_config_file()
            assert result is None, "Should return None for non-existent file"
        finally:
            if old_xdg:
                os.environ["XDG_CONFIG_HOME"] = old_xdg
            elif "XDG_CONFIG_HOME" in os.environ:
                del os.environ["XDG_CONFIG_HOME"]

    def test_load_invalid_config_file(self, tmp_path):
        """Test loading config file with invalid TOML."""
        config_home = tmp_path / ".config"
        config_home.mkdir()
        config_file = config_home / "squish.toml"

        # Write invalid TOML
        config_file.write_text("invalid toml content [[[")

        # Mock XDG_CONFIG_HOME
        old_xdg = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = str(config_home)

        try:
            result = load_config_file()
            assert result is None, "Should return None for invalid TOML"
        finally:
            if old_xdg:
                os.environ["XDG_CONFIG_HOME"] = old_xdg
            elif "XDG_CONFIG_HOME" in os.environ:
                del os.environ["XDG_CONFIG_HOME"]

    def test_load_valid_config_file(self, tmp_path):
        """Test loading valid config file."""
        config_home = tmp_path / ".config"
        config_home.mkdir()
        config_file = config_home / "squish.toml"

        # Write valid TOML
        config_content = """
[default]
mount_base = "custom_mounts"
verbose = true
compression = "gzip"
"""
        config_file.write_text(config_content)

        # Mock XDG_CONFIG_HOME
        old_xdg = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = str(config_home)

        try:
            result = load_config_file()
            assert result is not None, "Should return config data"
            assert "default" in result, "Should contain 'default' section"
            assert result["default"]["mount_base"] == "custom_mounts"
            assert result["default"]["verbose"] is True
            assert result["default"]["compression"] == "gzip"
        finally:
            if old_xdg:
                os.environ["XDG_CONFIG_HOME"] = old_xdg
            elif "XDG_CONFIG_HOME" in os.environ:
                del os.environ["XDG_CONFIG_HOME"]

    def test_fallback_to_home_config(self, tmp_path):
        """Test fallback to ~/.config when XDG_CONFIG_HOME not set."""
        # Ensure XDG_CONFIG_HOME is not set
        old_xdg = os.environ.get("XDG_CONFIG_HOME")
        if "XDG_CONFIG_HOME" in os.environ:
            del os.environ["XDG_CONFIG_HOME"]

        # Create config in home directory
        home_config = tmp_path / ".config"
        home_config.mkdir()
        config_file = home_config / "squish.toml"

        config_content = """
[default]
temp_dir = "/custom/temp"
"""
        config_file.write_text(config_content)

        # Mock HOME
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(tmp_path)

        try:
            result = load_config_file()
            assert result is not None, "Should find config in home directory"
            assert result["default"]["temp_dir"] == "/custom/temp"
        finally:
            if old_xdg:
                os.environ["XDG_CONFIG_HOME"] = old_xdg
            if old_home:
                os.environ["HOME"] = old_home
            elif "HOME" in os.environ:
                del os.environ["HOME"]


class TestEnvironmentVariables:
    """Test environment variable configuration."""

    def test_get_env_config_empty(self):
        """Test environment config with no variables set."""
        # Clear any existing squish env vars
        env_vars = [
            "SQUISH_MOUNT_BASE",
            "SQUISH_TEMP_DIR",
            "SQUISH_AUTO_CLEANUP",
            "SQUISH_VERBOSE",
            "SQUISH_COMPRESSION",
            "SQUISH_BLOCK_SIZE",
            "SQUISH_PROCESSORS",
            "SQUISH_XATTR_MODE",
            "SQUISH_EXCLUDE",
        ]

        old_values = {}
        for var in env_vars:
            if var in os.environ:
                old_values[var] = os.environ[var]
                del os.environ[var]

        try:
            result = get_env_config()
            assert result == {}, "Should return empty dict when no env vars set"
        finally:
            # Restore old values
            for var, value in old_values.items():
                os.environ[var] = value

    def test_get_env_config_basic(self):
        """Test basic environment variable parsing."""
        os.environ["SQUISH_MOUNT_BASE"] = "env_mounts"
        os.environ["SQUISH_COMPRESSION"] = "xz"

        try:
            result = get_env_config()
            assert result["mount_base"] == "env_mounts"
            assert result["compression"] == "xz"
        finally:
            del os.environ["SQUISH_MOUNT_BASE"]
            del os.environ["SQUISH_COMPRESSION"]

    def test_get_env_config_boolean(self):
        """Test boolean environment variable parsing."""
        os.environ["SQUISH_VERBOSE"] = "true"
        os.environ["SQUISH_AUTO_CLEANUP"] = "1"

        try:
            result = get_env_config()
            assert result["verbose"] is True
            assert result["auto_cleanup"] is True
        finally:
            del os.environ["SQUISH_VERBOSE"]
            del os.environ["SQUISH_AUTO_CLEANUP"]

    def test_get_env_config_processors(self):
        """Test processors environment variable parsing."""
        os.environ["SQUISH_PROCESSORS"] = "8"

        try:
            result = get_env_config()
            assert result["processors"] == 8
        finally:
            del os.environ["SQUISH_PROCESSORS"]

    def test_get_env_config_exclude(self):
        """Test exclude patterns environment variable parsing."""
        os.environ["SQUISH_EXCLUDE"] = "*.tmp,*.log,*.backup"

        try:
            result = get_env_config()
            assert result["exclude"] == ["*.tmp", "*.log", "*.backup"]
        finally:
            del os.environ["SQUISH_EXCLUDE"]


class TestConfigurationMerging:
    """Test configuration merging functionality."""

    def test_get_merged_config_defaults_only(self):
        """Test merging with only default values."""
        config = get_merged_config()

        assert config.mount_base == "mounts"
        assert config.temp_dir == "/tmp"
        assert config.auto_cleanup is True
        assert config.verbose is False
        assert config.compression == "zstd"
        assert config.block_size == "1M"
        assert config.processors is None
        # xattr_mode is auto-detected, so it will be either "all" or "user-only"
        assert config.xattr_mode in ["all", "user-only"]
        assert config.exclude is None

    def test_get_merged_config_cli_override(self):
        """Test CLI arguments override other sources."""
        cli_args = {"verbose": True, "compression": "gzip", "processors": 4}

        config = get_merged_config(cli_args)

        assert config.verbose is True
        assert config.compression == "gzip"
        assert config.processors == 4

    def test_get_merged_config_env_override(self):
        """Test environment variables override config file."""
        # Create a temporary config file
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_home = Path(tmp_dir) / ".config"
            config_home.mkdir()
            config_file = config_home / "squish.toml"

            config_content = """
[default]
compression = "xz"
block_size = "256K"
"""
            config_file.write_text(config_content)

            # Set environment variable
            os.environ["SQUISH_COMPRESSION"] = "lzma"

            # Mock config home
            old_xdg = os.environ.get("XDG_CONFIG_HOME")
            os.environ["XDG_CONFIG_HOME"] = str(config_home)

            try:
                config = get_merged_config()
                assert config.compression == "lzma"  # From env var
                assert config.block_size == "256K"  # From config file
            finally:
                del os.environ["SQUISH_COMPRESSION"]
                if old_xdg:
                    os.environ["XDG_CONFIG_HOME"] = old_xdg
                elif "XDG_CONFIG_HOME" in os.environ:
                    del os.environ["XDG_CONFIG_HOME"]

    def test_get_merged_config_precedence_order(self):
        """Test full precedence order: CLI > Env > File > Defaults."""
        # Create config file
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_home = Path(tmp_dir) / ".config"
            config_home.mkdir()
            config_file = config_home / "squish.toml"

            config_content = """
[default]
compression = "file_compression"
verbose = false
"""
            config_file.write_text(config_content)

            # Set environment variable
            os.environ["SQUISH_COMPRESSION"] = "env_compression"

            # Mock config home
            old_xdg = os.environ.get("XDG_CONFIG_HOME")
            os.environ["XDG_CONFIG_HOME"] = str(config_home)

            try:
                # CLI should override everything
                cli_args = {"compression": "cli_compression", "verbose": True}
                config = get_merged_config(cli_args)

                assert config.compression == "cli_compression"  # CLI wins
                assert config.verbose is True  # CLI wins
            finally:
                del os.environ["SQUISH_COMPRESSION"]
                if old_xdg:
                    os.environ["XDG_CONFIG_HOME"] = old_xdg
                elif "XDG_CONFIG_HOME" in os.environ:
                    del os.environ["XDG_CONFIG_HOME"]


class TestDefaultConfig:
    """Test default configuration functionality."""

    def test_get_default_config(self):
        """Test getting default configuration."""
        config = get_default_config()

        assert isinstance(config, SquishFSConfig)
        assert config.mount_base == "mounts"
        assert config.temp_dir == "/tmp"
        assert config.auto_cleanup is True
        assert config.verbose is False
        assert config.compression == "zstd"
        assert config.block_size == "1M"
        assert config.processors is None
        # xattr_mode is auto-detected, so it will be either "all" or "user-only"
        assert config.xattr_mode in ["all", "user-only"]
        assert config.exclude is None

    def test_default_config_immutability(self):
        """Test that default config is immutable."""
        config = get_default_config()

        # Test immutability by trying to modify the config
        # Since it's a frozen dataclass, normal attribute assignment should fail
        with pytest.raises(FrozenInstanceError):  # Should raise FrozenInstanceError
            config.mount_base = "new_value"  # type: ignore[attr-defined]


class TestConfigValidation:
    """Test configuration validation."""

    def test_valid_config_creation(self, tmp_path):
        """Test creating config with valid values."""
        # Create a temporary directory for temp_dir
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        config = SquishFSConfig(
            mount_base="test_mounts",
            temp_dir=str(temp_dir),
            auto_cleanup=False,
            verbose=True,
            compression="gzip",
            block_size="256K",
            processors=2,
            xattr_mode="user-only",
            exclude=["*.tmp"],
        )

        assert config.mount_base == "test_mounts"
        assert config.xattr_mode == "user-only"

    def test_invalid_mount_base(self):
        """Test validation of mount_base."""
        with pytest.raises(ValueError, match="mount_base cannot be empty"):
            SquishFSConfig(mount_base="")

    def test_invalid_temp_dir(self):
        """Test validation of temp_dir."""
        with pytest.raises(ValueError, match="temp_dir cannot be empty"):
            SquishFSConfig(temp_dir="")

    def test_invalid_xattr_mode(self):
        """Test validation of xattr_mode."""
        with pytest.raises(ValueError, match="xattr_mode must be one of"):
            SquishFSConfig(xattr_mode="invalid_mode")

    def test_nonexistent_temp_dir(self):
        """Test validation of non-existent temp_dir."""
        with pytest.raises(ValueError, match="temp_dir does not exist"):
            SquishFSConfig(temp_dir="/nonexistent/path")

    def test_temp_dir_not_directory(self, tmp_path):
        """Test validation when temp_dir is not a directory."""
        # Create a file instead of directory
        temp_file = tmp_path / "temp.txt"
        temp_file.write_text("not a directory")

        with pytest.raises(ValueError, match="temp_dir is not a directory"):
            SquishFSConfig(temp_dir=str(temp_file))


class TestConfigIntegration:
    """Integration tests for configuration system."""

    def test_full_config_workflow(self, tmp_path):
        """Test complete configuration workflow."""
        # Setup config file
        config_home = tmp_path / ".config"
        config_home.mkdir()
        config_file = config_home / "squish.toml"

        config_content = """
[default]
mount_base = "file_mounts"
compression = "file_gzip"
auto_cleanup = false
"""
        config_file.write_text(config_content)

        # Setup environment
        os.environ["SQUISH_COMPRESSION"] = "env_xz"
        os.environ["SQUISH_BLOCK_SIZE"] = "env_512K"

        # Mock config home
        old_xdg = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = str(config_home)

        try:
            # Test with CLI override
            cli_args = {"compression": "cli_lzma", "verbose": True, "processors": 8}

            config = get_merged_config(cli_args)

            # Verify precedence
            assert config.mount_base == "file_mounts"  # From file
            assert config.compression == "cli_lzma"  # From CLI (overrides env and file)
            assert config.block_size == "env_512K"  # From env (overrides file)
            assert config.auto_cleanup is False  # From file
            assert config.verbose is True  # From CLI
            assert config.processors == 8  # From CLI

        finally:
            del os.environ["SQUISH_COMPRESSION"]
            del os.environ["SQUISH_BLOCK_SIZE"]
            if old_xdg:
                os.environ["XDG_CONFIG_HOME"] = old_xdg
            elif "XDG_CONFIG_HOME" in os.environ:
                del os.environ["XDG_CONFIG_HOME"]

    def test_config_file_optional_behavior(self):
        """Test that missing config file doesn't break functionality."""
        # Ensure no config file exists
        old_xdg = os.environ.get("XDG_CONFIG_HOME")
        if "XDG_CONFIG_HOME" in os.environ:
            del os.environ["XDG_CONFIG_HOME"]

        try:
            # Should work fine without config file
            config = get_merged_config({"verbose": True})
            assert config.verbose is True
            assert config.mount_base == "mounts"  # Default value
        finally:
            if old_xdg:
                os.environ["XDG_CONFIG_HOME"] = old_xdg


class TestTOMLOptionalSupport:
    """Test that the application works without TOML support."""

    def test_config_without_toml_module(self, monkeypatch):
        """Test that configuration works when toml module is not available."""
        # Mock the toml import to simulate it not being available
        import builtins
        import sys

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "toml":
                raise ImportError("No module named toml")
            return original_import(name, *args, **kwargs)

        # Temporarily replace the import function
        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Force reimport of config module to trigger our mock
        if "squish.config" in sys.modules:
            del sys.modules["squish.config"]

        try:
            # Import the config module - this should work even without toml
            from squish.config import get_merged_config, load_config_file

            # Test that we can get a config without toml
            config = get_merged_config({"verbose": True})
            assert config.verbose is True
            assert config.mount_base == "mounts"  # Default value

            # Test that load_config_file returns None when toml is not available
            result = load_config_file()
            assert result is None  # Should return None when toml is not available

        finally:
            # Restore the original import function
            monkeypatch.setattr(builtins, "__import__", original_import)

            # Clean up the mocked module
            if "squish.config" in sys.modules:
                del sys.modules["squish.config"]
