# Test Fixture Documentation

This document provides comprehensive documentation for the test fixtures and parametrization strategy used in the squish test suite.

## Overview

The test suite uses a centralized fixture approach with comprehensive parametrization to ensure thorough testing of all functionality while maintaining clean, maintainable test code.

## Fixture Organization

All fixtures are centralized in `tests/conftest.py` and are organized into several categories:

### 1. Basic Infrastructure Fixtures

These provide fundamental test infrastructure:

- **`test_config`**: Provides a test configuration with isolated temp directory using pytest's tmp_path
- **`clean_test_environment`** (autouse): Automatically cleans up test artifacts

### 2. Core Component Fixtures

These create core component instances with proper test configuration:

- **`tracker`**: Creates a MountTracker instance for testing with isolated temp directory (uses `test_config` fixture)
- **`logger`**: Creates a MountSquashFSLogger instance for testing
- **`mock_manager`**: Creates a mocked manager object for testing interactions with mocked dependencies
- **`build_manager`**: Creates a BuildManager instance for testing
- **`checksum_manager`**: Creates a ChecksumManager instance for testing
- **`mount_manager`**: Creates a MountManager instance for testing
- **`list_manager`**: Creates a ListManager instance for testing

### 3. Test Data Fixtures

These provide reusable test data for common scenarios:

- **`test_files`**: Creates common test files including squashfs file, checksum file, and source directory (backward compatible)
- **`build_test_files`**: Creates test files specifically for build tests with nested directories
- **`checksum_test_files`**: Creates test files specifically for checksum tests
- **`test_data_builder`**: Provides the test data builder for custom test data creation

### 4. Fixture Dependencies

Some fixtures depend on others:

- The `tracker` fixture depends on the `test_config` fixture to ensure isolated test environments
- The `mock_manager` fixture depends on pytest's built-in `mocker` fixture for creating mock objects
- The `test_config` fixture uses pytest's `tmp_path` fixture for better integration
- All manager fixtures depend on `test_config` for consistent configuration

### 5. Enhanced Built-in Fixtures

The test suite provides enhanced versions of built-in pytest fixtures with better documentation:

- **`capsys_fixture`**: Enhanced stdout/stderr capture with comprehensive documentation
- **`capfd_fixture`**: Enhanced file descriptor capture with comprehensive documentation
- **`monkeypatch_fixture`**: Enhanced monkeypatch functionality with comprehensive documentation
- **`tmp_path_factory_fixture`**: Enhanced session-scoped temporary directory with comprehensive documentation
- **`pytestconfig_fixture`**: Enhanced pytest configuration access with comprehensive documentation
- **`cache_fixture`**: Enhanced caching functionality with comprehensive documentation

These fixtures wrap the built-in pytest fixtures and provide better documentation and usage examples.

### 3. Fixture Dependencies

Some fixtures depend on others:

- The `tracker` fixture depends on the `test_config` fixture to ensure isolated test environments
- The `mock_manager` fixture depends on pytest's built-in `mocker` fixture for creating mock objects

## Parametrization Strategy

### Benefits of Parametrization

1. **Reduced Code Duplication**: Write tests once, run with multiple inputs
2. **Comprehensive Coverage**: Easily test edge cases and variations
3. **Maintainability**: Changes to test logic apply to all variations
4. **Readability**: Clear separation of test logic and test data

### Parametrization Patterns Used

The test suite extensively uses parametrization for comprehensive testing:

#### 1. Test Method Parametrization

```python
@pytest.mark.parametrize("invalid_path", [
    "/nonexistent/path/to/file.sqs",
    "/invalid/../path.sqs",
    "",
    "relative/path.sqs",
])
def test_invalid_path_handling(self, test_manager, invalid_path):
    # Tests the same logic with different invalid paths
```

#### 2. Combined Parametrization

```python
@pytest.mark.parametrize("mount_base,auto_cleanup", [
    ("mounts", True),
    ("test_mounts", False),
    ("custom", True),
])
def test_mount_scenarios(self, temp_dir, mount_base, auto_cleanup):
    # Tests combinations of parameters
```

#### 3. Complex Parametrization with Test Markers

```python
@pytest.mark.parametrize(
    "config_params,expected_mount_base,expected_temp_dir,expected_auto_cleanup",
    [
        # Default configuration (None config)
        (None, "mounts", "/tmp", True),
        # Custom configuration with mount_base
        (SquishFSConfig(mount_base="custom"), "custom", "/tmp", True),
        # Custom configuration with temp_dir (use existing /tmp)
        (SquishFSConfig(temp_dir="/tmp"), "mounts", "/tmp", True),
        # Custom configuration with auto_cleanup
        (SquishFSConfig(auto_cleanup=False), "mounts", "/tmp", False),
    ]
)
@pytest.mark.unit
@pytest.mark.coverage
def test_init_with_various_configs(
    self, config_params, expected_mount_base, expected_temp_dir, expected_auto_cleanup
):
    # Tests initialization with various configuration combinations
```

## New Test Data Builder Approach

The test suite now uses a comprehensive test data builder approach to reduce duplication and improve maintainability.

### Test Data Builder Fixtures

#### 1. `build_test_files` Fixture

For build tests with nested directories:

```python
def test_build_with_fixture(build_test_files, mocker):
    """Test build functionality using the build test files fixture."""
    source = build_test_files["source"]
    output = build_test_files["tmp_path"] / "output.sqsh"
    
    # Mock dependencies and test build logic
    mock_run = mocker.patch("squish.build.subprocess.run")
    # ... test logic
```

#### 2. `checksum_test_files` Fixture

For checksum verification tests:

```python
def test_checksum_with_fixture(checksum_test_files, mocker):
    """Test checksum functionality using the checksum test files fixture."""
    test_file = checksum_test_files["archive.sqsh"]
    checksum_file = checksum_test_files["archive.sqsh.sha256"]
    
    # Test checksum verification logic
    # ... test logic
```

#### 3. `test_data_builder` Fixture

For custom test data creation:

```python
def test_custom_scenario(test_data_builder, tmp_path):
    """Test with custom test data using the builder."""
    test_files = test_data_builder \
        .with_squashfs_file("custom.sqsh", "custom content") \
        .with_checksum_file("custom.sqsh", "custom_checksum_value") \
        .with_source_directory("custom_source", {"custom.txt": "custom"}) \
        .build(tmp_path)
    
    # Use custom test files in your test
    # ... test logic
```

### Migration from Old to New Approach

#### Before (Manual Setup)

```python
def test_build_squashfs_success_old(mocker, manager):
    """Old approach with manual setup."""
    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "source"
        source.mkdir()
        output = Path(temp_dir) / "output.sqsh"
        # ... rest of test
```

#### After (Fixture-Based)

```python
def test_build_squashfs_success_new(mocker, manager, build_test_files):
    """New approach with fixture-based setup."""
    source = build_test_files["source"]
    output = build_test_files["tmp_path"] / "output.sqsh"
    # ... rest of test (same logic, cleaner setup)
```

## Fixture Usage Examples

### Basic Usage

```python
def test_basic_mount(test_config):
    """Test basic mount functionality."""
    config = test_config

    # Test logic here
    assert config.mount_base == "test_mounts"
```

## Best Practices

### 1. Fixture Design

- **Keep fixtures focused**: Each fixture should have a single responsibility
- **Make fixtures composable**: Design fixtures to work well together
- **Use parametrization wisely**: Don't over-parametrize - keep test cases meaningful
- **Document fixture purposes**: Clear docstrings explaining what each fixture provides

### 2. Test Organization

- **Group related tests**: Use test classes to group related functionality
- **Use descriptive names**: Test method names should clearly describe what's being tested
- **Keep tests independent**: Each test should be able to run in isolation
- **Use appropriate assertions**: Be specific about what you're testing

### 3. Mocking Guidelines

- **Mock system dependencies**: Use mocking to avoid external dependencies in unit tests
- **Clear mock behavior**: Make it obvious what the mock is doing in each test
- **Verify mock calls**: When appropriate, verify that expected system calls are made
- **Isolate functionality**: Use mocks to test specific functionality without side effects

### 4. Parametrization Guidelines

- **Test meaningful variations**: Only parametrize when there are meaningful differences
- **Keep parameter sets manageable**: Avoid combinatorial explosions
- **Document parameter meanings**: Use clear parameter names and docstrings
- **Consider test performance**: Too much parametrization can slow down test runs

## Test Data Management

The test suite includes a comprehensive test data builder approach implemented directly in `tests/conftest.py` for improved test data organization and reusability.

### Test Data Builder

The `SquashFSTestDataBuilder` class provides a fluent interface for creating complex test data scenarios:

```python
builder = SquashFSTestDataBuilder()
builder.with_squashfs_file("test.sqsh", "content")
       .with_checksum_file("test.sqsh", "checksum_value")
       .with_source_directory("source", {
           "file1.txt": "content1",
           "subdir": {"nested.txt": "nested content"}
       })
       .build(tmp_path)
```

### Predefined Scenarios

The `create_test_scenario` function provides common test scenarios for quick setup:

- **`default`**: Includes squashfs file, checksum file, and source directory
- **`build_only`**: Focused on build test requirements with nested directories
- **`checksum_only`**: Focused on checksum verification tests

### Mock Command Data

The `create_mock_command_data` function provides standardized mock data for command execution tests, ensuring consistency across tests.

## New Testing Patterns and Best Practices

### Parametrization Enhancements

The test suite makes extensive use of parametrization to reduce duplication and ensure comprehensive coverage:

```python
@pytest.mark.parametrize(
    "config_kwargs,expected_mount_base,expected_temp_dir",
    [
        ({}, "mounts", "/tmp"),
        ({"mount_base": "custom"}, "custom", "/tmp"),
        ({"temp_dir": "/custom/tmp"}, "mounts", "/custom/tmp"),
    ]
)
def test_build_manager_initialization(config_kwargs, expected_mount_base, expected_temp_dir):
    manager = BuildManager(**config_kwargs)
    assert manager.config.mount_base == expected_mount_base
    assert manager.config.temp_dir == expected_temp_dir
```

### Advanced Mocking Patterns

The test suite uses advanced pytest-mock features for comprehensive testing:

```python
# Use mocker.spy for partial mocking
mock_spy = mocker.spy(logger, 'info')

# Use mocker.patch.object for method patching
mock_method = mocker.patch.object(manager, '_validate_source')

# Use mocker.patch.dict for dictionary patching
mock_env = mocker.patch.dict('os.environ', {'DEBUG': '1'})

# Use mocker.stub for creating stubs
stub = mocker.stub(name='test_stub')
```

### Test Execution

The test suite is configured in `pyproject.toml` with default options for comprehensive coverage:

```bash
# Run tests with default configuration (coverage + verbose)
uv run pytest

# Run specific test markers
uv run pytest -m unit
uv run pytest -m coverage

# Run tests with additional verbosity
uv run pytest -xvs
```

## Test Coverage Strategy

The fixture-based approach ensures comprehensive coverage of:

### Configuration Scenarios
- Different mount base directories
- Auto-cleanup enabled/disabled
- Different temp directories
- Various configuration combinations

### System Operations
- Mount operations with automatic mount point determination
- Unmount operations with robust mount tracking
- Checksum verification with SHA256 integrity checking
- Build operations with multiple compression algorithms
- List operations for archive content listing
- Dependency checking for system tools
- Progress tracking with Zenity integration and console fallback

### Error Conditions
- Dependency check failures for missing system tools
- Mount failures due to permission issues or conflicts
- Unmount failures and cleanup scenarios
- Build failures with various error conditions
- List failures for invalid archives
- Checksum verification failures
- Invalid file paths and mount points
- Progress parsing errors and cancellation scenarios

### File Types and Formats
- Different file extensions (.sqs, .squashfs)
- Various file content types and sizes
- Different file permissions and ownership
- Files with and without checksums
- Nested directory structures

### Edge Cases
- Nonexistent files and directories
- Empty files and directories
- Files with special characters in filenames
- Deep directory structures with nested content
- Various permission settings and access control
- Progress tracking edge cases and cancellation scenarios

## Running Parametrized Tests

When running tests, you'll see output like:

```
tests/test_config.py::TestConfigScenario::test_mount_base[True] PASSED
tests/test_config.py::TestConfigScenario::test_mount_base[False] PASSED
```

This shows that the same test ran multiple times with different parameters.

## Maintenance and Evolution

### Adding New Fixtures

1. **Identify the need**: Determine what test scenario isn't covered
2. **Design the fixture**: Keep it focused and composable
3. **Add parametrization**: If applicable, add meaningful parameter variations
4. **Document**: Add clear docstrings and examples
5. **Integrate**: Use the fixture in existing tests where appropriate
6. **Update documentation**: Keep FIXTURE_DOCUMENTATION.md current

### Updating Existing Fixtures

1. **Assess impact**: Understand which tests use the fixture
2. **Make changes**: Update the fixture implementation
3. **Update tests**: Adjust any tests that need modification
4. **Verify**: Run the full test suite to ensure nothing broke
5. **Update documentation**: Reflect changes in FIXTURE_DOCUMENTATION.md

### Test Data Builder Usage

When creating complex test scenarios, use the `SquashFSTestDataBuilder`:

```python
def test_complex_scenario(test_data_builder, tmp_path):
    """Test with complex test data using the builder."""
    test_files = test_data_builder \
        .with_squashfs_file("complex.sqsh", "complex content") \
        .with_checksum_file("complex.sqsh", "complex_checksum_value") \
        .with_source_directory("complex_source", {
            "file1.txt": "content1",
            "file2.txt": "content2",
            "subdir": {
                "nested1.txt": "nested content 1",
                "nested2.txt": "nested content 2"
            }
        }) \
        .build(tmp_path)
    
    # Use the created test files in your test
    squashfs_file = test_files["complex.sqsh"]
    source_dir = test_files["complex_source"]
    # ... test logic
```

## Test Contribution Guide

### Adding New Tests

1. **Identify the need**: Determine what functionality isn't covered
2. **Choose the right location**: Place tests in the appropriate test file
3. **Use existing fixtures**: Leverage existing fixtures for consistency
4. **Follow naming conventions**: Use clear, descriptive test names
5. **Add documentation**: Include comprehensive docstrings
6. **Consider parametrization**: Use parametrization for similar test cases

### Using Test Data Module

The test data module provides reusable components for test data creation:

```python
# Import the test data builder
from tests.test_data import TestDataBuilder

# Create complex test scenarios
test_files = TestDataBuilder() \
    .with_squashfs_file("test.sqsh") \
    .with_checksum_file("test.sqsh") \
    .with_source_directory("source", {"file1.txt": "content"}) \
    .build(tmp_path)
```

### Test Maintenance

1. **Regular review**: Periodically review tests for relevance
2. **Update documentation**: Keep fixture documentation current
3. **Monitor coverage**: Ensure new code is properly tested
4. **Optimize performance**: Identify and address slow tests
5. **Remove redundancy**: Consolidate similar tests using parametrization

### Test Documentation Standards

All test methods should include:

1. **Clear purpose**: What behavior is being tested
2. **Test scenario**: The specific scenario being tested
3. **Expected outcome**: What should happen when the test runs
4. **Edge cases**: Any special conditions or edge cases covered

Example:

```python
def test_build_squashfs_source_not_found(self, manager):
    """Test that build operation fails gracefully when source directory doesn't exist.
    
    This test verifies that the build_squashfs method properly validates
    the source directory existence and raises a BuildError with a clear
    message when the source is not found.
    """
    with pytest.raises(BuildError, match="Source not found"):
        manager.build_squashfs("/nonexistent/source", "/output.sqsh")
```

## Conclusion

The centralized fixture approach with comprehensive parametrization and mocking provides:

- **Thorough testing**: Covers a wide range of scenarios and edge cases
- **Maintainable code**: Reduces duplication and makes tests easier to understand
- **Flexibility**: Easy to add new test cases and scenarios
- **Reliability**: Proper isolation and cleanup between tests
- **Fast execution**: Mocked system calls avoid dependencies on external tools

This strategy ensures that the squish utility is robustly tested while keeping the test code clean and maintainable.