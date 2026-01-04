"""
Pytest fixtures and configuration for mount-squashfs tests.

This file contains shared fixtures and test configuration following pytest best practices.
"""

import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Union

import pytest

from squish.build import BuildManager
from squish.checksum import ChecksumManager
from squish.config import SquishFSConfig
from squish.extract import ExtractManager
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

    def with_extract_scenario(
        self,
        archive_name: str = "extract_archive.sqsh",
        archive_content: str = "extract archive content",
        output_dir: str = "extract_output",
    ) -> "SquashFSTestDataBuilder":
        """Add a complete extract test scenario with archive and output directory."""
        self._data[archive_name] = {
            "type": "squashfs",
            "content": archive_content,
            "role": "extract_archive",
        }
        self._data[output_dir] = {
            "type": "directory",
            "role": "extract_output",
        }
        return self

    def with_mount_scenario(
        self,
        archive_name: str = "mount_archive.sqsh",
        archive_content: str = "mount archive content",
        mount_point: str = "mount_point",
    ) -> "SquashFSTestDataBuilder":
        """Add a complete mount test scenario with archive and mount point."""
        self._data[archive_name] = {
            "type": "squashfs",
            "content": archive_content,
            "role": "mount_archive",
        }
        self._data[mount_point] = {
            "type": "directory",
            "role": "mount_point",
        }
        return self

    def with_list_scenario(
        self,
        archive_name: str = "list_archive.sqsh",
        archive_content: str = "list archive content",
    ) -> "SquashFSTestDataBuilder":
        """Add a complete list test scenario with archive."""
        self._data[archive_name] = {
            "type": "squashfs",
            "content": archive_content,
            "role": "list_archive",
        }
        return self

    def with_build_scenario(
        self,
        source_name: str = "build_source",
        output_name: str = "build_output.sqsh",
        source_files: Union[
            Dict[str, str], Dict[str, Union[str, Dict[str, str]]], None
        ] = None,
    ) -> "SquashFSTestDataBuilder":
        """Add a complete build test scenario with source directory and expected output."""
        if source_files is None:
            source_files = {
                "file1.txt": "build content 1",
                "file2.txt": "build content 2",
                "subdir": {"nested.txt": "nested content"},
            }

        self._data[source_name] = {
            "type": "directory",
            "files": source_files,
            "role": "build_source",
        }
        self._data[output_name] = {
            "type": "expected_output",
            "role": "build_output",
        }
        return self

    def with_checksum_scenario(
        self,
        archive_name: str = "checksum_archive.sqsh",
        archive_content: str = "checksum archive content",
        checksum_value: str = "custom_checksum_value",
    ) -> "SquashFSTestDataBuilder":
        """Add a complete checksum test scenario with archive and checksum file."""
        self._data[archive_name] = {
            "type": "squashfs",
            "content": archive_content,
            "role": "checksum_archive",
        }
        checksum_name = f"{archive_name}.sha256"
        self._data[checksum_name] = {
            "type": "checksum",
            "content": f"{checksum_value}  {archive_name}",
            "role": "checksum_file",
        }
        return self

    def with_error_scenario(
        self,
        error_type: str = "dependency",
        error_files: Optional[Dict[str, str]] = None,
    ) -> "SquashFSTestDataBuilder":
        """Add an error test scenario with specific error conditions."""
        if error_files is None:
            error_files = {
                "missing_tool.txt": "This file represents a missing tool scenario",
                "invalid_permissions.txt": "This file represents invalid permissions",
            }

        for name, content in error_files.items():
            self._data[name] = {
                "type": "error_file",
                "content": content,
                "error_type": error_type,
            }
        return self

    def with_progress_scenario(
        self,
        archive_name: str = "progress_archive.sqsh",
        archive_content: str = "progress archive content",
        progress_files: Optional[Dict[str, str]] = None,
    ) -> "SquashFSTestDataBuilder":
        """Add a progress tracking test scenario with archive and progress files."""
        if progress_files is None:
            progress_files = {
                "progress_log.txt": "Progress log content",
                "zenity_output.txt": "Zenity progress output",
            }

        self._data[archive_name] = {
            "type": "squashfs",
            "content": archive_content,
            "role": "progress_archive",
        }

        for name, content in progress_files.items():
            self._data[name] = {
                "type": "progress_file",
                "content": content,
            }
        return self

    def with_complex_nested_directory(
        self,
        name: str = "complex_source",
        structure: Optional[Dict[str, Union[str, Dict]]] = None,
    ) -> "SquashFSTestDataBuilder":
        """Add a complex nested directory structure for comprehensive testing."""
        if structure is None:
            structure = {
                "level1": {
                    "file1.txt": "level1 file1",
                    "file2.txt": "level1 file2",
                    "level2": {
                        "file3.txt": "level2 file3",
                        "level3": {
                            "file4.txt": "level3 file4",
                            "file5.txt": "level3 file5",
                        },
                    },
                },
                "sibling_dir": {
                    "sibling_file.txt": "sibling content",
                },
                "root_file.txt": "root level file",
            }

        self._data[name] = {"type": "directory", "files": structure}
        return self

    def build(self, base_path: Path) -> Dict[str, Any]:
        """Build the test data in the specified base path."""
        created_files = {}

        for name, data in self._data.items():
            if data["type"] == "squashfs":
                file_path = base_path / name
                file_path.write_text(data["content"])
                created_files[name] = file_path

                # Handle different roles
                if data.get("role") == "extract_archive":
                    created_files["extract_archive"] = file_path
                elif data.get("role") == "mount_archive":
                    created_files["mount_archive"] = file_path
                elif data.get("role") == "list_archive":
                    created_files["list_archive"] = file_path
                elif data.get("role") == "checksum_archive":
                    created_files["checksum_archive"] = file_path
                elif data.get("role") == "progress_archive":
                    created_files["progress_archive"] = file_path

            elif data["type"] == "checksum":
                file_path = base_path / name
                file_path.write_text(data["content"])
                created_files[name] = file_path

                # Handle checksum roles
                if data.get("role") == "checksum_file":
                    created_files["checksum_file"] = file_path

            elif data["type"] == "directory":
                dir_path = base_path / name
                dir_path.mkdir()
                created_files[name] = dir_path

                # Handle different roles
                if data.get("role") == "extract_output":
                    created_files["extract_output"] = dir_path
                elif data.get("role") == "mount_point":
                    created_files["mount_point"] = dir_path
                elif data.get("role") == "build_source":
                    created_files["build_source"] = dir_path

                # Process files if they exist in the data
                if "files" in data:
                    self._create_directory_structure(
                        dir_path, data["files"], created_files, name
                    )

            elif data["type"] == "expected_output":
                # This is a placeholder for expected output files
                created_files[name] = base_path / name

            elif data["type"] == "error_file":
                file_path = base_path / name
                file_path.write_text(data["content"])
                created_files[name] = file_path

            elif data["type"] == "progress_file":
                file_path = base_path / name
                file_path.write_text(data["content"])
                created_files[name] = file_path

        return created_files

    def _create_directory_structure(
        self,
        base_dir: Path,
        structure: Dict[str, Union[str, Dict]],
        created_files: Dict[str, Any],
        parent_name: str = "",
    ) -> None:
        """Recursively create directory structure from nested dictionary."""
        for item_name, item_content in structure.items():
            item_path = base_dir / item_name

            if isinstance(item_content, dict):
                # This is a directory
                item_path.mkdir()
                created_files[f"{parent_name}/{item_name}"] = item_path
                # Recursively create nested structure
                self._create_directory_structure(
                    item_path, item_content, created_files, f"{parent_name}/{item_name}"
                )
            else:
                # This is a file
                item_path.write_text(item_content)
                created_files[f"{parent_name}/{item_name}"] = item_path


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
        test_files = builder.with_build_scenario().build(tmp_path)
        # Maintain backward compatibility by adding "source" key
        if "build_source" in test_files:
            test_files["source"] = test_files["build_source"]
        return test_files

    elif scenario_name == "checksum_only":
        test_files = builder.with_checksum_scenario().build(tmp_path)
        # Maintain backward compatibility by adding expected keys
        if "checksum_archive.sqsh" in test_files:
            test_files["archive.sqsh"] = test_files["checksum_archive.sqsh"]
            test_files["archive.sqsh.sha256"] = test_files[
                "checksum_archive.sqsh.sha256"
            ]
        return test_files

    elif scenario_name == "extract_only":
        return builder.with_extract_scenario().build(tmp_path)

    elif scenario_name == "mount_only":
        return builder.with_mount_scenario().build(tmp_path)

    elif scenario_name == "list_only":
        return builder.with_list_scenario().build(tmp_path)

    elif scenario_name == "complex_nested":
        return builder.with_complex_nested_directory().build(tmp_path)

    elif scenario_name == "progress_scenario":
        return builder.with_progress_scenario().build(tmp_path)

    elif scenario_name == "error_scenario":
        return builder.with_error_scenario().build(tmp_path)

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
def extract_manager(test_config):
    """Create an ExtractManager instance for testing."""
    return ExtractManager(test_config)


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
def extract_test_files(tmp_path):
    """Create test files specifically for extract tests."""
    # Create a squashfs archive file for extraction
    archive_file = tmp_path / "test_archive.sqsh"
    archive_file.write_text("mock squashfs content")

    # Create an existing output directory
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    return {
        "archive_file": archive_file,
        "output_dir": output_dir,
        "tmp_path": tmp_path,
    }


@pytest.fixture
def dependency_check_fixture(mocker):
    """Shared fixture for dependency checking tests across modules.

    This fixture provides a standardized way to test dependency checking
    patterns across build, extract, and other modules.
    """

    def setup_dependency_check(
        manager, command, success=True, module_path="subprocess"
    ):
        """Setup dependency check with configurable success/failure.

        Args:
            manager: The manager instance to test
            command: The command name to mock (e.g., 'mksquashfs', 'unsquashfs')
            success: Whether the dependency check should succeed
            module_path: The module path for subprocess.run mocking

        Returns:
            The mock_run object for additional assertions if needed
        """
        mock_run = mocker.patch(f"{module_path}.run")

        if success:
            # Mock successful command execution
            mock_run.return_value = mocker.MagicMock(returncode=0, check=lambda: True)
        else:
            # Mock failed command execution
            from subprocess import CalledProcessError

            mock_run.side_effect = CalledProcessError(1, f"which {command}")

        return mock_run

    return setup_dependency_check


@pytest.fixture
def extract_scenario_files(tmp_path):
    """Create test files for extract scenarios using the test data builder."""
    test_files = create_test_scenario(tmp_path, "extract_only")
    # Include tmp_path for convenience
    test_files["tmp_path"] = tmp_path
    return test_files


@pytest.fixture
def mount_test_files(tmp_path):
    """Create test files specifically for mount tests."""
    test_files = create_test_scenario(tmp_path, "mount_only")
    # Include tmp_path for convenience
    test_files["tmp_path"] = tmp_path
    return test_files


@pytest.fixture
def list_test_files(tmp_path):
    """Create test files specifically for list tests."""
    test_files = create_test_scenario(tmp_path, "list_only")
    # Include tmp_path for convenience
    test_files["tmp_path"] = tmp_path
    return test_files


@pytest.fixture
def complex_nested_test_files(tmp_path):
    """Create test files with complex nested directory structure."""
    test_files = create_test_scenario(tmp_path, "complex_nested")
    # Include tmp_path for convenience
    test_files["tmp_path"] = tmp_path
    return test_files


@pytest.fixture
def progress_test_files(tmp_path):
    """Create test files specifically for progress tracking tests."""
    test_files = create_test_scenario(tmp_path, "progress_scenario")
    # Include tmp_path for convenience
    test_files["tmp_path"] = tmp_path
    return test_files


@pytest.fixture
def error_test_files(tmp_path):
    """Create test files specifically for error handling tests."""
    test_files = create_test_scenario(tmp_path, "error_scenario")
    # Include tmp_path for convenience
    test_files["tmp_path"] = tmp_path
    return test_files


@pytest.fixture
def mock_dependencies(mocker):
    """Mock common dependencies for testing."""
    # Mock subprocess.run
    mock_run = mocker.patch("subprocess.run")

    # Mock common commands
    def mock_run_side_effect(cmd, **kwargs):
        if isinstance(cmd, list) and cmd[0] == "nproc":
            return mocker.MagicMock(stdout="4\n", returncode=0, check=lambda: True)
        elif isinstance(cmd, list) and cmd[0] == "mksquashfs":
            return mocker.MagicMock(returncode=0, check=lambda: True)
        elif isinstance(cmd, list) and cmd[0] == "unsquashfs":
            return mocker.MagicMock(returncode=0, check=lambda: True)
        elif isinstance(cmd, list) and cmd[0] == "sha256sum":
            return mocker.MagicMock(
                stdout="d41d8cd98f00b204e9800998ecf8427e  output.sqsh\n",
                returncode=0,
                check=lambda: True,
            )
        else:
            return mocker.MagicMock(returncode=0, check=lambda: True)

    mock_run.side_effect = mock_run_side_effect

    return {
        "mock_run": mock_run,
        "mock_check": mocker.patch("subprocess.run").return_value.check,
    }


@pytest.fixture
def test_scenario_templates():
    """Provide common test scenario templates."""
    return {
        "build_success": {
            "description": "Successful build operation",
            "expected_result": "Build completes successfully",
            "test_data": {
                "source": "build_source",
                "output": "output.sqsh",
                "compression": "zstd",
            },
        },
        "extract_success": {
            "description": "Successful extract operation",
            "expected_result": "Extract completes successfully",
            "test_data": {
                "archive": "extract_archive.sqsh",
                "output": "extract_output",
            },
        },
        "mount_success": {
            "description": "Successful mount operation",
            "expected_result": "Mount completes successfully",
            "test_data": {
                "archive": "mount_archive.sqsh",
                "mount_point": "mount_point",
            },
        },
        "checksum_validation": {
            "description": "Checksum validation scenarios",
            "expected_result": "Checksum validation works correctly",
            "test_data": {
                "archive": "checksum_archive.sqsh",
                "checksum_file": "checksum_archive.sqsh.sha256",
            },
        },
    }


@pytest.fixture
def integration_test_setup(tmp_path):
    """Setup for integration tests with all components."""
    from squish.core import SquashFSManager

    # Create test configuration
    config = SquishFSConfig(
        mount_base="integration_test_mounts",
        temp_dir=str(tmp_path),
        auto_cleanup=True,
        verbose=False,
    )

    # Create manager with all components
    manager = SquashFSManager(config)

    # Create test data
    test_files = create_test_scenario(tmp_path, "complex_nested")

    return {
        "config": config,
        "manager": manager,
        "test_files": test_files,
        "tmp_path": tmp_path,
    }


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
