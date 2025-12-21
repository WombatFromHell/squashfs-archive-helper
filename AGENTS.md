# AGENTS.md - Tool Usage Guide for Agentic Tools

## Development Environment Tools

### Testing Tools

- `make test` - Full test suite with coverage reporting

### Code Quality Tools

- `make quality` - Code linting/formatting checks
- `make radon` - Code complexity analysis

## Agent Workflow

1. **Testing**: Use `uv run pytest -xvs` for test execution
2. **Coverage Analysis**: Use `uv run pytest --cov=src/squish --cov-report=term-missing --cov-branch` to check code coverage (as configured in pyproject.toml)
3. **Quality Checks**: Run `make quality` before commits to validate linting/formatting
4. **Complexity Analysis**: Use `make radon` for refactoring code complexity validation
5. Building and Deployment: Use `make all` to clean, build, and install locally to `~/.local/bin/mount-squashfs`
6. **Dependency Management**: Use `uv` for package operations
7. **Test Expansion**: When adding new features or fixing bugs, ensure comprehensive test coverage for:
   - Success paths
   - Error handling paths
   - Edge cases
   - Exception scenarios
   - Integration between components

## Test Coverage Strategy

The project maintains a high test coverage standard (90%+). When expanding coverage:

1. **Identify Missing Coverage**: Run coverage reports to find untested lines
2. **Prioritize Critical Paths**: Focus on error handling, validation, and core logic
3. **Add Targeted Tests**: Create specific tests for missing scenarios
4. **Verify Coverage**: Run coverage analysis after adding tests
5. **Maintain Quality**: Ensure new tests follow existing patterns and conventions

**Note**: `entry.py` is intentionally not covered by tests as it only serves as an entrypoint for zipapp bundling.

## Test Markers

The project uses pytest markers for test categorization as defined in pyproject.toml:

- **`@pytest.mark.slow`**: Marks tests as slow (deselect with '-m not slow')
- **`@pytest.mark.integration`**: Marks integration tests (deselect with '-m not integration')
- **`@pytest.mark.unit`**: Marks unit tests (deselect with '-m not unit')
- **`@pytest.mark.regression`**: Marks regression tests for known issues
- **`@pytest.mark.coverage`**: Marks tests specifically targeting coverage gaps
- **`@pytest.mark.edge_case`**: Marks tests for edge cases and boundary conditions
- **`@pytest.mark.performance`**: Marks performance-sensitive tests
- **`@pytest.mark.requires_zenity`**: Marks tests that require Zenity for GUI features
- **`@pytest.mark.requires_sudo`**: Marks tests that require sudo privileges
- **`@pytest.mark.network`**: Marks tests that require network access

## Modern Fixture-Based Testing Approach

The test suite uses a comprehensive fixture-based approach with test data builders to improve maintainability and reduce duplication, as implemented in `tests/conftest.py`.

### Recommended Testing Patterns

#### 1. Using Predefined Fixtures

For common test scenarios, use the predefined fixtures:

```python
# For build tests
def test_build_operation(build_test_files, mocker):
    source = build_test_files["source"]
    output = build_test_files["tmp_path"] / "output.sqsh"

    # Mock dependencies and test logic
    mock_run = mocker.patch("squish.build.subprocess.run")
    # ... test implementation

# For checksum tests
def test_checksum_verification(checksum_test_files, mocker):
    test_file = checksum_test_files["archive.sqsh"]
    checksum_file = checksum_test_files["archive.sqsh.sha256"]

    # Test checksum verification logic
    # ... test implementation
```

#### 2. Using Custom Test Data Builder

For complex or specialized test scenarios, use the test data builder:

```python
def test_custom_scenario(test_data_builder, tmp_path, mocker):
    test_files = test_data_builder \
        .with_squashfs_file("custom.sqsh", "custom content") \
        .with_checksum_file("custom.sqsh", "custom_checksum_value") \
        .with_source_directory("custom_source", {
            "file1.txt": "content1",
            "subdir": {"nested.txt": "nested content"}
        }) \
        .build(tmp_path)

    # Use custom test files in your test
    squashfs_file = test_files["custom.sqsh"]
    source_dir = test_files["custom_source"]
    # ... test implementation
```

#### 3. Migration Guide for Existing Tests

When updating existing tests to use the new fixture approach:

**Before (Manual Setup):**

```python
def test_example_old(mocker, tmp_path):
    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "source"
        source.mkdir()
        (source / "file1.txt").write_text("content1")
        # ... more manual setup
        # ... test logic
```

**After (Fixture-Based):**

```python
def test_example_new(mocker, build_test_files):
    source = build_test_files["source"]
    # ... same test logic, cleaner setup
```

### Fixture Reference

#### Available Fixtures

- **`test_files`**: Basic test files (squashfs, checksum, source directory) - backward compatible
- **`build_test_files`**: Build-focused test files with nested directories
- **`checksum_test_files`**: Checksum verification test files
- **`test_data_builder`**: Custom test data creation using `SquashFSTestDataBuilder`
- **`test_config`**: Test configuration with isolated temp directory using pytest's `tmp_path`
- **`build_manager`**, `checksum_manager`, `mount_manager`, `list_manager`: Module-specific managers
- **`tracker`**: MountTracker instance for testing
- **`logger`**: MountSquashFSLogger instance for testing
- **`mock_manager`**: Mock manager for testing interactions

#### Enhanced Built-in Fixtures

The test suite provides enhanced versions of built-in pytest fixtures:

- **`capsys_fixture`**: Enhanced stdout/stderr capture
- **`capfd_fixture`**: Enhanced binary stdout/stderr capture
- **`monkeypatch_fixture`**: Enhanced flexible patching
- **`tmp_path_factory_fixture`**: Enhanced session-scoped temp directory
- **`pytestconfig_fixture`**: Enhanced pytest configuration access
- **`cache_fixture`**: Enhanced caching functionality

#### Best Practices

1. **Use Predefined Scenarios First**: Check if existing fixtures meet your needs
2. **Custom Builders for Complex Cases**: Use `test_data_builder` for specialized setups
3. **Keep Test Data Simple**: Only create what's needed for the specific test
4. **Document Complex Setups**: Add comments explaining non-standard test data
5. **Maintain Consistency**: Follow existing patterns and naming conventions
6. **Use Enhanced Fixtures**: Prefer the enhanced fixture versions for better documentation

## Common Coverage Gaps

Typical areas that often need additional coverage:

- Exception handling paths
- Error conditions and edge cases
- System exit scenarios
- File permission and access errors
- Command execution failures
- Validation failures
- Progress tracking and cancellation scenarios
- Zenity integration and fallback behavior
