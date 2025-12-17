# Test Fixture Documentation

This document provides comprehensive documentation for the test fixtures and parametrization strategy used in the mount-squashfs-helper test suite.

## Overview

The test suite uses a centralized fixture approach with comprehensive parametrization to ensure thorough testing of all functionality while maintaining clean, maintainable test code.

## Fixture Organization

All fixtures are centralized in `tests/conftest.py` and are organized into several categories:

### 1. Basic Fixtures

These provide fundamental test infrastructure:

- **`temp_dir`**: Creates a temporary directory for tests
- **`test_config`**: Provides a test configuration with isolated temp directory
- **`test_tracker`**: Creates a MountTracker instance for testing
- **`test_manager`**: Creates a SquashFSManager instance for testing

### 2. Parametrized File Fixtures

These fixtures create test files with different characteristics:

- **`mock_squashfs_file(file_extension)`**: Creates files with different extensions (.sqs, .squashfs)
- **`mock_file_with_content(file_type, content)`**: Creates files with different content types (empty, small, binary)
- **`mock_file_with_permissions(permission)`**: Creates files with specific permissions (0o000, 0o400, 0o600, 0o777)

### 3. Parametrized Configuration Fixtures

These provide different configuration scenarios:

- **`parametrized_config(config_params)`**: Tests different configuration combinations
- **`mock_invalid_paths()`**: Provides invalid paths for error testing

### 4. Error Scenario Fixtures

These create specific error conditions:

- **`mock_error_scenarios(error_scenario)`**: Creates various error scenarios (nonexistent files, invalid permissions, etc.)
- **`mock_mount_error_scenarios(mount_error_type)`**: Creates mount-specific error scenarios

### 5. Isolation and Cleanup Fixtures

These ensure test isolation and proper cleanup:

- **`clean_test_environment`** (autouse): Automatically cleans up test artifacts
- **`isolated_test_environment`**: Provides complete environment isolation
- **`parametrized_cleanup_strategy(cleanup_strategy)`**: Tests different cleanup approaches
- **`test_environment_isolation`**: Ensures complete isolation between tests
- **`mock_system_environment`**: Mocks system environment variables

## Parametrization Strategy

### Benefits of Parametrization

1. **Reduced Code Duplication**: Write tests once, run with multiple inputs
2. **Comprehensive Coverage**: Easily test edge cases and variations
3. **Maintainability**: Changes to test logic apply to all variations
4. **Readability**: Clear separation of test logic and test data

### Parametrization Patterns Used

#### 1. Fixture Parametrization

```python
@pytest.fixture
@pytest.mark.parametrize("file_extension", [".sqs", ".squashfs"])
def mock_squashfs_file(temp_dir, file_extension):
    # Creates files with different extensions
```

#### 2. Test Method Parametrization

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

#### 3. Combined Parametrization

```python
@pytest.mark.parametrize("mount_base,auto_cleanup", [
    ("mounts", True),
    ("test_mounts", False),
    ("custom", True),
])
def test_mount_scenarios(self, temp_dir, mount_base, auto_cleanup):
    # Tests combinations of parameters
```

## Fixture Usage Examples

### Basic Usage

```python
def test_basic_mount(test_manager, mock_squashfs_file):
    """Test basic mount functionality."""
    manager = test_manager
    file_path = mock_squashfs_file
    
    # Test logic here
    assert Path(file_path).exists()
```

### Parametrized Usage

```python
def test_file_extensions(mock_squashfs_file):
    """Test that will run for each file extension."""
    file_path = mock_squashfs_file
    
    # This test runs twice - once for .sqs, once for .squashfs
    assert file_path.endswith((".sqs", ".squashfs"))
```

### Error Scenario Testing

```python
def test_error_handling(test_manager, mock_error_scenarios):
    """Test error handling for various scenarios."""
    manager = test_manager
    error_path = mock_error_scenarios
    
    # Test that errors are handled appropriately
    with pytest.raises((MountError, MountPointError)):
        manager.mount(error_path)
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

### 3. Parametrization Guidelines

- **Test meaningful variations**: Only parametrize when there are meaningful differences
- **Keep parameter sets manageable**: Avoid combinatorial explosions
- **Document parameter meanings**: Use clear parameter names and docstrings
- **Consider test performance**: Too much parametrization can slow down test runs

## Test Coverage Strategy

The parametrized approach ensures comprehensive coverage of:

### File Types and Formats
- Different file extensions (.sqs, .squashfs)
- Various file content types
- Different file permissions

### Configuration Scenarios
- Different mount base directories
- Auto-cleanup enabled/disabled
- Verbose mode on/off

### Error Conditions
- Nonexistent files
- Invalid permissions
- Invalid paths
- Filesystem errors
- Mount point issues

### Edge Cases
- Special characters in filenames
- Deep directory structures
- Empty files
- Binary content
- Various permission settings

## Running Parametrized Tests

When running tests, you'll see output like:

```
tests/test_parametrized_examples.py::TestParametrizedFileExtensions::test_mount_different_extensions[.sqs] PASSED
tests/test_parametrized_examples.py::TestParametrizedFileExtensions::test_mount_different_extensions[.squashfs] PASSED
```

This shows that the same test ran multiple times with different parameters.

## Maintenance and Evolution

### Adding New Fixtures

1. **Identify the need**: Determine what test scenario isn't covered
2. **Design the fixture**: Keep it focused and composable
3. **Add parametrization**: If applicable, add meaningful parameter variations
4. **Document**: Add clear docstrings and examples
5. **Integrate**: Use the fixture in existing tests where appropriate

### Updating Existing Fixtures

1. **Assess impact**: Understand which tests use the fixture
2. **Make changes**: Update the fixture implementation
3. **Update tests**: Adjust any tests that need modification
4. **Verify**: Run the full test suite to ensure nothing broke

## Conclusion

The centralized fixture approach with comprehensive parametrization provides:

- **Thorough testing**: Covers a wide range of scenarios and edge cases
- **Maintainable code**: Reduces duplication and makes tests easier to understand
- **Flexibility**: Easy to add new test cases and scenarios
- **Reliability**: Proper isolation and cleanup between tests

This strategy ensures that the mount-squashfs-helper is robustly tested while keeping the test code clean and maintainable.