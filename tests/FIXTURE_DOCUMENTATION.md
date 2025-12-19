# Test Fixture Documentation

This document provides comprehensive documentation for the test fixtures and parametrization strategy used in the squish test suite.

## Overview

The test suite uses a centralized fixture approach with comprehensive parametrization to ensure thorough testing of all functionality while maintaining clean, maintainable test code.

## Fixture Organization

All fixtures are centralized in `tests/conftest.py` and are organized into several categories:

### 1. Basic Infrastructure Fixtures

These provide fundamental test infrastructure:

- **`test_config`**: Provides a test configuration with isolated temp directory
- **`clean_test_environment`** (autouse): Automatically cleans up test artifacts

### 2. Core Component Fixtures

These create core component instances with proper test configuration:

- **`tracker`**: Creates a MountTracker instance for testing with isolated temp directory (uses `test_config` fixture)
- **`logger`**: Creates a MountSquashFSLogger instance for testing
- **`mock_manager`**: Creates a mocked manager object for testing interactions with mocked dependencies

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

## Test Coverage Strategy

The fixture-based approach ensures comprehensive coverage of:

### Configuration Scenarios
- Different mount base directories
- Auto-cleanup enabled/disabled
- Different temp directories

### System Operations
- Mount operations
- Unmount operations
- Checksum verification
- Build operations
- List operations
- Dependency checking

### Error Conditions
- Dependency check failures
- Mount failures
- Unmount failures
- Build failures
- List failures
- Checksum verification failures
- Invalid file paths
- Invalid mount points

### File Types and Formats
- Different file extensions (.sqs, .squashfs)
- Various file content types
- Different file permissions
- Files with and without checksums

### Edge Cases
- Nonexistent files
- Empty files
- Files with content
- Special characters in filenames
- Deep directory structures
- Various permission settings

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

### Updating Existing Fixtures

1. **Assess impact**: Understand which tests use the fixture
2. **Make changes**: Update the fixture implementation
3. **Update tests**: Adjust any tests that need modification
4. **Verify**: Run the full test suite to ensure nothing broke

## Conclusion

The centralized fixture approach with comprehensive parametrization and mocking provides:

- **Thorough testing**: Covers a wide range of scenarios and edge cases
- **Maintainable code**: Reduces duplication and makes tests easier to understand
- **Flexibility**: Easy to add new test cases and scenarios
- **Reliability**: Proper isolation and cleanup between tests
- **Fast execution**: Mocked system calls avoid dependencies on external tools

This strategy ensures that the squish utility is robustly tested while keeping the test code clean and maintainable.