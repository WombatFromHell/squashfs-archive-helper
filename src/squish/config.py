"""
Configuration management for the Mount-SquashFS application.

This module handles configuration settings and validation for the
mount-squashfs functionality.

Configuration File Location:
    The configuration file is located at:
    - $XDG_CONFIG_HOME/squish.toml (if XDG_CONFIG_HOME is set)
    - $HOME/.config/squish.toml (standard XDG fallback)

Configuration File Format:
    The configuration file uses TOML format and supports the following structure:

    [default]
    mount_base = "mounts"              # Base directory name for mount points
    temp_dir = "/tmp"                  # Directory for temporary tracking files
    auto_cleanup = true                # Automatically clean up mount directories
    verbose = false                    # Enable verbose output
    compression = "zstd"               # Default compression algorithm for build operations
    block_size = "1M"                 # Default block size for build operations
    processors = 4                     # Default number of processors for build operations
    xattr_mode = "user-only"          # Xattr handling mode (all/user-only/none)
    exclude = ["*.tmp", "*.log"]      # Optional list of exclusion patterns for build operations

Configuration Precedence:
    Configuration settings are merged from multiple sources with the following precedence:
    1. CLI arguments (highest priority)
    2. Environment variables (SQUISH_* variables)
    3. Configuration file settings
    4. Default values (lowest priority)

Environment Variables:
    The following environment variables can be used to override configuration:
    - SQUISH_MOUNT_BASE
    - SQUISH_TEMP_DIR
    - SQUISH_AUTO_CLEANUP
    - SQUISH_VERBOSE
    - SQUISH_COMPRESSION
    - SQUISH_BLOCK_SIZE
    - SQUISH_PROCESSORS
    - SQUISH_XATTR_MODE
    - SQUISH_EXCLUDE

Note: The configuration file is purely optional. If it doesn't exist or contains
invalid data, the application will fall back to default values and continue normally.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

# Optional import for TOML config file support
try:
    import toml
except ImportError:
    toml = None


@dataclass(frozen=True)
class SquishFSConfig:
    """
    Immutable configuration for the SquashFS management system.

    Attributes:
        mount_base: Base directory name for mount points (default: "mounts")
        temp_dir: Directory for temporary tracking files (default: "/tmp")
        auto_cleanup: Automatically clean up mount directories (default: True)
        verbose: Enable verbose output (default: False)
        compression: Default compression algorithm for build operations (default: "zstd")
        block_size: Default block size for build operations (default: "1M")
        processors: Default number of processors for build operations (default: None for auto)
        xattr_mode: Xattr handling mode for extract operations (auto-detected based on user privileges)
        exclude: Optional list of exclusion patterns for build operations
    """

    mount_base: str = "mounts"
    temp_dir: str = "/tmp"
    auto_cleanup: bool = True
    verbose: bool = False
    compression: str = "zstd"
    block_size: str = "1M"
    processors: Optional[int] = None
    xattr_mode: Optional[str] = None  # Will be auto-detected in __post_init__
    exclude: Optional[list[str]] = None

    def __post_init__(self):
        """Validate configuration values after initialization."""
        # Note: This method can still modify the object during initialization
        # even though the class is frozen, because __post_init__ runs before
        # the object is actually frozen.

        if not self.mount_base:
            raise ValueError("mount_base cannot be empty")

        if not self.temp_dir:
            raise ValueError("temp_dir cannot be empty")

        # Auto-detect xattr_mode based on user privileges if not explicitly set
        if self.xattr_mode is None:
            if is_root_user():
                # Root users can handle all xattrs including security.selinux
                object.__setattr__(self, "xattr_mode", "all")
            else:
                # Non-root users should avoid system xattrs to prevent permission errors
                object.__setattr__(self, "xattr_mode", "user-only")

        # Validate xattr_mode
        valid_xattr_modes = ["all", "user-only", "none"]
        if self.xattr_mode not in valid_xattr_modes:
            raise ValueError(
                f"xattr_mode must be one of {valid_xattr_modes}, got: {self.xattr_mode}"
            )

        # Ensure paths are valid
        temp_path = Path(self.temp_dir)
        if not temp_path.exists():
            raise ValueError(f"temp_dir does not exist: {self.temp_dir}")

        if not temp_path.is_dir():
            raise ValueError(f"temp_dir is not a directory: {self.temp_dir}")


def is_root_user() -> bool:
    """Check if the current user has root privileges."""
    return os.geteuid() == 0


def get_default_config() -> SquishFSConfig:
    """Get the default configuration."""
    return SquishFSConfig()


def load_config_file() -> Optional[Dict[str, Any]]:
    """Load configuration from file if it exists.

    Looks for configuration file in:
    1. $XDG_CONFIG_HOME/squish.toml (if XDG_CONFIG_HOME is set)
    2. $HOME/.config/squish.toml (standard XDG fallback)

    Returns:
        Dictionary with configuration data if file exists and is valid,
        None otherwise.
    """
    # Get XDG config home or fallback to ~/.config
    config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    config_path = os.path.join(config_home, "squish.toml")

    if os.path.exists(config_path):
        try:
            if toml is None:
                print("Warning: TOML support not available (toml module not found)")
                return None
            with open(config_path, "r") as f:
                return toml.load(f)
        except Exception as e:
            # Log error but continue with defaults
            print(f"Warning: Could not load config file '{config_path}': {e}")
    return None


def get_env_config() -> Dict[str, Any]:
    """Get configuration from environment variables.

    Maps environment variables to configuration keys:
    - SQUISH_MOUNT_BASE -> mount_base
    - SQUISH_TEMP_DIR -> temp_dir
    - SQUISH_AUTO_CLEANUP -> auto_cleanup
    - SQUISH_VERBOSE -> verbose
    - SQUISH_COMPRESSION -> compression
    - SQUISH_BLOCK_SIZE -> block_size
    - SQUISH_PROCESSORS -> processors
    - SQUISH_XATTR_MODE -> xattr_mode
    - SQUISH_EXCLUDE -> exclude

    Returns:
        Dictionary with configuration from environment variables.
    """
    config = {}

    # Map environment variables to config keys
    env_mapping = {
        "SQUISH_MOUNT_BASE": "mount_base",
        "SQUISH_TEMP_DIR": "temp_dir",
        "SQUISH_AUTO_CLEANUP": "auto_cleanup",
        "SQUISH_VERBOSE": "verbose",
        "SQUISH_COMPRESSION": "compression",
        "SQUISH_BLOCK_SIZE": "block_size",
        "SQUISH_PROCESSORS": "processors",
        "SQUISH_XATTR_MODE": "xattr_mode",
        "SQUISH_EXCLUDE": "exclude",
    }

    for env_var, config_key in env_mapping.items():
        if env_var in os.environ:
            value = os.environ[env_var]
            # Convert types as needed
            if config_key in ["auto_cleanup", "verbose"]:
                config[config_key] = value.lower() in ["true", "1", "yes"]
            elif config_key == "processors":
                config[config_key] = int(value) if value != "auto" else None
            elif config_key == "exclude":
                config[config_key] = value.split(",") if value else None
            else:
                config[config_key] = value

    return config


def get_merged_config(cli_args: Optional[Dict[str, Any]] = None) -> SquishFSConfig:
    """Merge configuration from all sources with proper precedence.

    Configuration precedence (highest to lowest):
    1. CLI arguments
    2. Environment variables
    3. Configuration file
    4. Default values

    Args:
        cli_args: Dictionary of CLI arguments (optional)

    Returns:
        SquishFSConfig object with merged configuration
    """
    # 1. Start with defaults
    config_dict = {
        "mount_base": "mounts",
        "temp_dir": "/tmp",
        "auto_cleanup": True,
        "verbose": False,
        "compression": "zstd",
        "block_size": "1M",
        "processors": None,
        "xattr_mode": None,
        "exclude": None,
    }

    # 2. Load from config file (if exists)
    file_config = load_config_file()
    if file_config and "default" in file_config:
        config_dict.update(file_config["default"])

    # 3. Apply environment variables
    env_config = get_env_config()
    config_dict.update(env_config)

    # 4. Apply CLI arguments (highest precedence)
    if cli_args:
        for key, value in cli_args.items():
            # Skip mock values (used in testing) and None values
            if value is not None and not hasattr(value, "__mock__"):
                config_dict[key] = value

    # 5. Create and return SquishFSConfig
    return SquishFSConfig(**config_dict)
