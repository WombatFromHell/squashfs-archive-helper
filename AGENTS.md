# AGENTS.md - Agentic Coding Environment

## Project Overview

**squish** - SquashFS archive management tool with CLI for mount, build, extract, and checksum operations.

## Quick Reference

| Task         | Command                              |
| ------------ | ------------------------------------ |
| Build bundle | `make build`                         |
| Test         | `make test`                          |
| Quality      | `make quality`                       |
| All          | `make all` (clean + build + install) |
| Dependencies | `uv add <pkg>` / `uv remove <pkg>`   |

## Environment

- **Python**: 3.13+ (see `.python-version`)
- **Package Manager**: `uv`
- **Virtual Env**: Auto-created via `uv sync`
- **Build Output**: `dist/squish.pyz` (Python bundle)
- **Install Target**: `~/.local/bin/squish`

## Code Quality

```bash
make quality  # lint + format
make radon    # complexity analysis
```

## Testing

```bash
# Full suite with coverage
make test

# Direct pytest with verbose output
uv run pytest -xvs

# Coverage report
uv run pytest --cov=src/squish --cov-report=term-missing --cov-branch
```

## Test Markers

- `@pytest.mark.slow` - Slow tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.requires_sudo` - Needs sudo
- `@pytest.mark.requires_zenity` - Needs Zenity GUI

## Project Structure

```
src/
  ├── entry.py          # Bundle entry point
  └── squish/           # Main package
      ├── cli.py        # CLI interface
      ├── build.py      # SquashFS build logic
      ├── mounting.py   # Mount/unmount operations
      ├── extract.py    # Extract operations
      ├── checksum.py   # Checksum generation/verification
      └── ...
tests/                  # Test suite
dist/                   # Build artifacts (.pyz, .sha256sum)
```

## External Dependencies

Required system tools (checked at runtime):

- `mksquashfs` / `unsquashfs` - Archive creation/extraction
- `squashfuse` / `fusermount` - Mount operations
- `sha256sum` - Checksum operations
- `zenity` - GUI progress (optional, falls back to console)

## Reproducible Builds

Bundles are deterministic via `SOURCE_DATE_EPOCH` (default: 315532800).
See [REPRODUCIBLE_BUILDS.md](REPRODUCIBLE_BUILDS.md) for details.

## Installation

`make install` installs to:

- `~/.local/bin/squish` (symlink to bundle)
- `~/.local/bin/scripts/squish.pyz` (bundle)
- `~/.local/share/kio/servicemenus/squashfs-actions.desktop` (KDE menu)
