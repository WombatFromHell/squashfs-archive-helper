"""
Pytest fixtures and configuration for mount-squashfs tests.

This file contains shared fixtures and test configuration following pytest best practices.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from squish.config import SquishFSConfig
from squish.logging import MountSquashFSLogger
from squish.tracking import MountTracker


@pytest.fixture
def test_config():
    """Create a test configuration with isolated temp directory."""
    # Use a temporary directory instead of /tmp to avoid pollution
    with tempfile.TemporaryDirectory() as temp_dir:
        config = SquishFSConfig(
            mount_base="test_mounts",
            temp_dir=temp_dir,
            auto_cleanup=True,
            verbose=False,
        )
        yield config
        # Clean up any remaining files in the temp directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


@pytest.fixture
def tracker(test_config):
    """Create a MountTracker instance for testing with isolated temp dir."""
    return MountTracker(test_config)


@pytest.fixture
def logger():
    """Create a logger instance for testing."""
    return MountSquashFSLogger("test_logger", verbose=False)


@pytest.fixture
def mock_manager(mocker):
    """Create a mock manager."""
    manager = mocker.MagicMock()
    return manager


@pytest.fixture(autouse=True)
def clean_test_environment():
    """Automatically clean up test artifacts using pytest patterns."""
    # This fixture runs automatically for all tests
    yield
    # Clean up any test mounts directories that might have been created
    # This includes common mount base names used in tests
    mount_base_names = ["mounts", "test_mounts", "custom", "test"]
    for mount_base in mount_base_names:
        mount_dir = Path(f"./{mount_base}")
        if mount_dir.exists():
            try:
                shutil.rmtree(mount_dir, ignore_errors=True)
            except Exception:
                pass

    # Clean up any .mounted files in current directory
    for mounted_file in Path(".").glob("*.mounted"):
        try:
            mounted_file.unlink()
        except Exception:
            pass
