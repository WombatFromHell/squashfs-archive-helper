"""
Version management for the squish tool.

This module provides version information by:
1. Reading from package metadata when installed
2. Reading from pyproject.toml during development
"""

import tomllib
from functools import lru_cache
from pathlib import Path

# Build-time version placeholder (replaced during bundle build)
__version__ = "__BUILD_VERSION__"


@lru_cache(maxsize=None)
def _get_version_from_pyproject() -> str:
    """Read version from pyproject.toml (for development)."""
    # Find the project root (where pyproject.toml lives)
    current = Path(__file__).resolve()
    for parent in current.parents:
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
                return data["project"]["version"]
    return "0.0.0"  # Fallback


@lru_cache(maxsize=None)
def _get_version() -> str:
    """Get version from injected build-time version or runtime detection."""
    # If version was injected at build time, use it
    if __version__ != "__BUILD_VERSION__":
        return __version__

    # Runtime detection (development or installed package)
    try:
        from importlib.metadata import version as _metadata_version

        return _metadata_version("squish")
    except Exception:
        # Fallback to reading pyproject.toml directly (for development)
        return _get_version_from_pyproject()


def get_version() -> str:
    """
    Get the formatted version string with 'v' prefix.

    Returns:
        Version string formatted as 'v<version>' (e.g., 'v1.3.0').
    """
    return f"v{_get_version()}"


__version__ = _get_version()
