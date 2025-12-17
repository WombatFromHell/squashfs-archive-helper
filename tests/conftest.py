"""
Pytest fixtures and configuration for mount-squashfs tests.

This file contains shared fixtures and test configuration.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from mount_squashfs.config import SquashFSConfig
from mount_squashfs.core import SquashFSManager
from mount_squashfs.tracking import MountTracker


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def test_config():
    """Create a test configuration with isolated temp directory."""
    # Use a temporary directory instead of /tmp to avoid pollution
    with tempfile.TemporaryDirectory() as temp_dir:
        config = SquashFSConfig(
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
def test_tracker(test_config):
    """Create a MountTracker instance for testing."""
    return MountTracker(test_config)


@pytest.fixture
def test_manager(test_config):
    """Create a SquashFSManager instance for testing."""
    # Mock the dependency checking to avoid requiring actual squashfuse/fusermount
    manager = SquashFSManager(test_config)
    return manager


@pytest.fixture
def mock_squashfs_file(temp_dir):
    """Create a mock squashfs file for testing."""
    file_path = temp_dir / "test.sqs"
    file_path.touch()
    return str(file_path)


def parametrized_squashfs_file(temp_dir):
    """Create a mock squashfs file for testing."""
    file_path = temp_dir / "test_param.sqs"
    file_path.touch()
    return str(file_path)


@pytest.fixture
def mock_mount_point(temp_dir):
    """Create a mock mount point directory for testing."""
    mount_point = temp_dir / "mount_point"
    mount_point.mkdir()
    return str(mount_point)


@pytest.fixture
def parametrized_config(temp_dir):
    """Create a parametrized configuration for testing different scenarios."""
    config = SquashFSConfig(
        mount_base="mounts",
        temp_dir=str(temp_dir),
        auto_cleanup=True,
        verbose=False,
    )
    return config


@pytest.fixture
def mock_file_with_content(temp_dir):
    """Create a mock file with content for testing."""
    file_path = temp_dir / "test_content.sqs"
    file_path.write_bytes(b"test content")
    return str(file_path)


@pytest.fixture
def mock_error_scenarios(temp_dir):
    """Create various error scenarios for comprehensive error testing."""
    return "/path/to/nonexistent/file.sqs"


@pytest.fixture
def mock_invalid_paths():
    """Provide a set of invalid paths for testing error conditions."""
    return [
        "/nonexistent/path/to/file.sqs",
        "/invalid/../path.sqs",
        "",
        "relative/path.sqs",
        "invalid:path.sqs",
        "path/with//double/slashes.sqs",
    ]


@pytest.fixture
def mock_mount_error_scenarios(temp_dir):
    """Create scenarios that should trigger specific mount errors."""
    return {
        "file_path": str(temp_dir / "test.sqs"),
        "expected_error": "already mounted",
        "setup": lambda manager: None,
    }


@pytest.fixture
def mock_file_with_permissions(temp_dir):
    """Create a file with specific permissions for testing."""
    file_path = temp_dir / "test_permissions.sqs"
    file_path.touch()
    os.chmod(file_path, 0o644)
    return str(file_path)


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


@pytest.fixture
def isolated_test_environment(temp_dir):
    """Provide an isolated test environment with comprehensive cleanup."""
    # Save original working directory
    original_cwd = os.getcwd()

    # Create isolated environment
    isolated_dir = temp_dir / "isolated"
    isolated_dir.mkdir()

    # Change to isolated directory
    os.chdir(isolated_dir)

    yield isolated_dir

    # Restore original working directory
    os.chdir(original_cwd)

    # Clean up the isolated environment
    try:
        shutil.rmtree(isolated_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def parametrized_cleanup_strategy(temp_dir):
    """Test different cleanup strategies for mount management."""
    # Create some test artifacts
    test_file = temp_dir / "test.sqs"
    test_file.touch()

    mount_dir = temp_dir / "test_mount"
    mount_dir.mkdir()

    return {
        "test_file": str(test_file),
        "mount_dir": str(mount_dir),
        "cleanup_strategy": "conservative",
        "temp_dir": str(temp_dir),
    }


@pytest.fixture
def test_environment_isolation():
    """Ensure complete isolation between tests by using separate temp directories."""
    # Create a unique temp directory for this test
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create subdirectories for different purposes
        test_files_dir = temp_path / "files"
        test_files_dir.mkdir()

        test_mounts_dir = temp_path / "mounts"
        test_mounts_dir.mkdir()

        test_config_dir = temp_path / "config"
        test_config_dir.mkdir()

        yield {
            "base_dir": str(temp_path),
            "files_dir": str(test_files_dir),
            "mounts_dir": str(test_mounts_dir),
            "config_dir": str(test_config_dir),
        }

        # All cleanup is handled automatically by TemporaryDirectory


@pytest.fixture
def mock_system_environment(monkeypatch):
    """Mock system environment variables and settings for testing."""
    # Save original environment
    original_env = dict(os.environ)

    # Set up test environment variables
    test_env = {
        "MOUNT_SQUASHFS_TEST": "1",
        "MOUNT_SQUASHFS_TEMP": "/tmp/mount_squashfs_test",
        "MOUNT_SQUASHFS_VERBOSE": "0",
    }

    # Apply test environment
    for key, value in test_env.items():
        monkeypatch.setenv(key, value)

    yield test_env

    # Restore original environment
    for key in test_env.keys():
        if key in original_env:
            monkeypatch.setenv(key, original_env[key])
        else:
            monkeypatch.delenv(key, raising=False)
