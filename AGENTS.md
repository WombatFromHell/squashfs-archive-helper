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
3. **Quality Checks**: Run `make quality` before commits to validate code with linting/formatting
4. **Complexity Analysis**: Use `make radon` for refactoring code complexity validation
5. Building and Deployment: Use `make all` to clean, build, and install locally to `~/.local/bin/mount-squashfs`
6. **Dependency Management**: Use `uv` for package operations
