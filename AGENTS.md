# AGENTS.md - Tool Usage Guide for Agentic Tools

## Development Environment Tools

### Testing Tools

- `make test` - Full test suite with coverage reporting

### Code Quality Tools

- `make quality` - Code linting/formatting checks
- `make radon` - Code complexity analysis

## Agent Workflow

1. **Testing**: Use `uv run pytest -xvs` for test execution
2. **Coverage Analysis**: Use `uv run pytest --cov=src --cov-report=term-missing` to check code coverage
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

## Common Coverage Gaps

Typical areas that often need additional coverage:

- Exception handling paths
- Error conditions and edge cases
- System exit scenarios
- File permission and access errors
- Command execution failures
- Validation failures
