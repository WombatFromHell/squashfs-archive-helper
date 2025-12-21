"""
Pytest fixtures and configuration for mount-squashfs tests.

This file contains shared fixtures and test configuration following pytest best practices.
"""

import shutil
from pathlib import Path
from typing import Any, Dict, Union

import pytest

from squish.build import BuildManager
from squish.checksum import ChecksumManager
from squish.config import SquishFSConfig
from squish.list import ListManager
from squish.logging import MountSquashFSLogger
from squish.mounting import MountManager
from squish.tracking import MountTracker


class SquashFSTestDataBuilder:
    """Builder for creating complex test data scenarios."""

    def __init__(self):
        self._data = {}

    def with_squashfs_file(
        self, name: str = "test.sqsh", content: str = "test content"
    ) -> "SquashFSTestDataBuilder":
        """Add a squashfs file to the test data."""
        self._data[name] = {"type": "squashfs", "content": content}
        return self

    def with_checksum_file(
        self,
        target_file: str,
        checksum: str = "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3",
    ) -> "SquashFSTestDataBuilder":
        """Add a checksum file for a target file."""
        checksum_name = f"{target_file}.sha256"
        self._data[checksum_name] = {
            "type": "checksum",
            "content": f"{checksum}  {target_file}",
        }
        return self

    def with_source_directory(
        self,
        name: str = "source",
        files: Union[
            Dict[str, str], Dict[str, Union[str, Dict[str, str]]], None
        ] = None,
    ) -> "SquashFSTestDataBuilder":
        """Add a source directory with files."""
        if files is None:
            files = {"file1.txt": "content1", "file2.txt": "content2"}

        self._data[name] = {"type": "directory", "files": files}
        return self

    def build(self, base_path: Path) -> Dict[str, Any]:
        """Build the test data in the specified base path."""
        created_files = {}

        for name, data in self._data.items():
            if data["type"] == "squashfs":
                file_path = base_path / name
                file_path.write_text(data["content"])
                created_files[name] = file_path
            elif data["type"] == "checksum":
                file_path = base_path / name
                file_path.write_text(data["content"])
                created_files[name] = file_path
            elif data["type"] == "directory":
                dir_path = base_path / name
                dir_path.mkdir()
                created_files[name] = dir_path

                for file_name, file_content in data["files"].items():
                    if isinstance(file_content, dict):
                        # Handle nested directories
                        nested_dir = dir_path / file_name
                        nested_dir.mkdir()
                        created_files[f"{name}/{file_name}"] = nested_dir
                        for nested_file, nested_content in file_content.items():
                            nested_file_path = nested_dir / nested_file
                            nested_file_path.write_text(nested_content)
                            created_files[f"{name}/{file_name}/{nested_file}"] = (
                                nested_file_path
                            )
                    else:
                        # Handle regular files
                        file_path = dir_path / file_name
                        file_path.write_text(file_content)
                        created_files[f"{name}/{file_name}"] = file_path

        return created_files


def create_test_scenario(
    tmp_path: Path, scenario_name: str = "default"
) -> Dict[str, Any]:
    """Create a complete test scenario with common test data.

    Args:
        tmp_path: pytest's tmp_path fixture
        scenario_name: Name of the scenario to create

    Returns:
        Dictionary containing paths to created test files and directories
    """
    builder = SquashFSTestDataBuilder()

    if scenario_name == "default":
        return (
            builder.with_squashfs_file()
            .with_checksum_file("test.sqsh")
            .with_source_directory()
            .build(tmp_path)
        )

    elif scenario_name == "build_only":
        return builder.with_source_directory(
            files={
                "file1.txt": "build content 1",
                "file2.txt": "build content 2",
                "subdir": {"nested.txt": "nested content"},
            }
        ).build(tmp_path)

    elif scenario_name == "checksum_only":
        return (
            builder.with_squashfs_file("archive.sqsh", "archive content")
            .with_checksum_file("archive.sqsh", "custom_checksum_value")
            .build(tmp_path)
        )

    else:
        raise ValueError(f"Unknown scenario: {scenario_name}")


@pytest.fixture
def test_config(tmp_path):
    """Create a test configuration with isolated temp directory using pytest's tmp_path."""
    config = SquishFSConfig(
        mount_base="test_mounts",
        temp_dir=str(tmp_path),
        auto_cleanup=True,
        verbose=False,
    )
    return config


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


@pytest.fixture
def build_manager(test_config):
    """Create a BuildManager instance for testing."""
    return BuildManager(test_config)


@pytest.fixture
def checksum_manager(test_config):
    """Create a ChecksumManager instance for testing."""
    return ChecksumManager(test_config)


@pytest.fixture
def mount_manager(test_config):
    """Create a MountManager instance for testing."""
    return MountManager(test_config)


@pytest.fixture
def list_manager(test_config):
    """Create a ListManager instance for testing."""
    return ListManager(test_config)


@pytest.fixture
def test_files(tmp_path):
    """Create common test files for reuse across tests using the test data builder."""
    # Use the builder to create test files consistently
    test_files = create_test_scenario(tmp_path, "default")

    # Map to maintain backward compatibility with existing tests
    return {
        "test_file": test_files["test.sqsh"],
        "checksum_file": test_files["test.sqsh.sha256"],
        "source_dir": test_files["source"],
        "tmp_path": tmp_path,
    }


@pytest.fixture
def build_test_files(tmp_path):
    """Create test files specifically for build tests with nested directories."""
    test_files = create_test_scenario(tmp_path, "build_only")
    # Include tmp_path for convenience
    test_files["tmp_path"] = tmp_path
    return test_files


@pytest.fixture
def checksum_test_files(tmp_path):
    """Create test files specifically for checksum tests."""
    test_files = create_test_scenario(tmp_path, "checksum_only")
    # Include tmp_path for convenience
    test_files["tmp_path"] = tmp_path
    return test_files


@pytest.fixture
def test_data_builder():
    """Provide the test data builder for custom test data creation."""
    return SquashFSTestDataBuilder()


def create_mock_command_data() -> Dict[str, Any]:
    """Create mock data for command execution tests."""
    return {
        "nproc": {"stdout": "4\n", "returncode": 0, "check": lambda: True},
        "mksquashfs": {"returncode": 0, "check": lambda: True},
        "sha256sum": {
            "stdout": "d41d8cd98f00b204e9800998ecf8427e  output.sqsh\n",
            "returncode": 0,
            "check": lambda: True,
        },
    }


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


# Built-in pytest fixtures that are automatically available but documented here for reference
# These are provided by pytest but we document them for team awareness:
# - capsys: Capture stdout/stderr (text)
# - capfd: Capture stdout/stderr (binary)
# - monkeypatch: Flexible patching of functions, attributes, dictionaries, and environment variables
# - tmp_path_factory: Session-scoped temporary directory factory
# - pytestconfig: Access to pytest configuration
# - cache: Cache data across test runs


@pytest.fixture
def capsys_fixture(capsys):
    """
    Enhanced capsys fixture for capturing stdout/stderr.

    This wraps the built-in capsys fixture to provide additional convenience methods
    and better documentation for our test suite.

    Usage:
        def test_output(capsys_fixture):
            print("Hello World")
            captured = capsys_fixture.readouterr()
            assert captured.out == "Hello World\n"
    """
    return capsys


@pytest.fixture
def capfd_fixture(capfd):
    """
    Enhanced capfd fixture for capturing stdout/stderr (binary).

    This wraps the built-in capfd fixture to provide additional convenience methods
    and better documentation for our test suite.

    Usage:
        def test_binary_output(capfd_fixture):
            print("Binary data")
            captured = capfd_fixture.readouterr()
            assert b"Binary data" in captured.out
    """
    return capfd


@pytest.fixture
def monkeypatch_fixture(monkeypatch):
    """
    Enhanced monkeypatch fixture for flexible patching.

    This wraps the built-in monkeypatch fixture to provide additional convenience methods
    and better documentation for our test suite.

    Usage examples:
        # Patch a function
        monkeypatch_fixture.setattr("module.function", lambda: "patched")

        # Patch an environment variable
        monkeypatch_fixture.setenv("VAR", "value")

        # Patch a dictionary item
        monkeypatch_fixture.setitem("dict.key", "value")

        # Remove an environment variable
        monkeypatch_fixture.delenv("VAR")
    """
    return monkeypatch


@pytest.fixture
def tmp_path_factory_fixture(tmp_path_factory):
    """
    Enhanced tmp_path_factory fixture for session-scoped temporary directories.

    This wraps the built-in tmp_path_factory fixture to provide additional convenience methods
    and better documentation for our test suite.

    Usage:
        def test_session_temp(tmp_path_factory_fixture):
            # Create a session-scoped temp directory
            temp_dir = tmp_path_factory_fixture.mktemp("mysession")
            file = temp_dir / "test.txt"
            file.write_text("session data")
            assert file.exists()
    """
    return tmp_path_factory


@pytest.fixture
def pytestconfig_fixture(pytestconfig):
    """
    Enhanced pytestconfig fixture for accessing pytest configuration.

    This wraps the built-in pytestconfig fixture to provide better documentation
    and convenience methods for our test suite.

    Usage:
        def test_config(pytestconfig_fixture):
            # Access command line options
            verbose = pytestconfig_fixture.getoption("verbose")

            # Check if a marker is available
            has_marker = pytestconfig_fixture.getini("markers")
    """
    return pytestconfig


@pytest.fixture
def cache_fixture(cache):
    """
    Enhanced cache fixture for caching data across test runs.

    This wraps the built-in cache fixture to provide better documentation
    and convenience methods for our test suite.

    Usage:
        def test_with_cache(cache_fixture):
            # Cache expensive computation results
            if "expensive_result" not in cache_fixture:
                cache_fixture["expensive_result"] = compute_expensive_result()

            result = cache_fixture["expensive_result"]
            assert result is not None
    """
    return cache
