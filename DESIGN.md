# Squish Design Documentation

## Overview

**Squish** is a Python-based SquashFS management tool providing:

- Mounting/unmounting SquashFS archives
- Building SquashFS archives from source directories
- Listing archive contents
- Checksum verification
- Archive extraction

## Architecture

### Core Components

```mermaid
classDiagram
    direction TB

    class CLI {
        +parse_args()
        +resolve_command()
        +handle_*_operation()
    }

    class Core {
        +SquashFSManager()
        +mount()
        +unmount()
        +build()
        +list()
        +extract()
        +verify_checksum()
    }

    class Mounting {
        +MountManager()
        +mount()
        +unmount()
    }

    class Build {
        +BuildManager()
        +build_squashfs()
    }

    class Extract {
        +ExtractManager()
        +extract_squashfs()
    }

    class Checksum {
        +ChecksumManager()
        +verify_checksum()
    }

    class List {
        +ListManager()
        +list_squashfs()
    }

    class Progress {
        +ProgressTracker()
        +ExtractProgressTracker()
        +ZenityProgressService()
        +ProgressState
        +ExtractProgressState
    }

    class Config {
        +SquishFSConfig()
    }

    class Tracking {
        +MountTracker()
    }

    class Logging {
        +MountSquashFSLogger()
    }

    CLI --> Core : Uses
    Core --> Mounting : Uses
    Core --> Build : Uses
    Core --> Extract : Uses
    Core --> Checksum : Uses
    Core --> List : Uses
    Mounting --> Config : Uses
    Mounting --> Tracking : Uses
    Mounting --> Logging : Uses
    Build --> Progress : Uses
    Extract --> Progress : Uses
```

### Module Structure

```mermaid
graph TD
    A[entry.py] -->|Entry Point| B[squish/]
    B --> C[cli.py]
    B --> D[core.py]
    B --> E[mounting.py]
    B --> F[build.py]
    B --> G[extract.py]
    B --> H[checksum.py]
    B --> I[list.py]
    B --> J[config.py]
    B --> K[tracking.py]
    B --> L[logging.py]
    B --> M[progress.py]
    B --> N[dependencies.py]
    B --> O[errors.py]
```

## CLI Interface

### Commands

```bash
# Mount/Unmount
squish mount <file> [mount_point]        # or: squish m <file> [mount_point]
squish unmount <file> [mount_point]      # or: squish um <file> [mount_point]

# Checksum
squish check <file>                      # or: squish c <file>

# Build (Enhanced with Multiple Sources and Auto-Naming)
squish build [options] <sources>... [-o <output>]  # or: squish b [options] <sources>... [-o <output>]

# List
squish ls <archive>                     # or: squish l <archive>

# Extract
squish extract <archive> [-o <output>]   # or: squish ex <archive> [-o <output>]
```

### Key Options

| Command | Option              | Description                               |
| ------- | ------------------- | ----------------------------------------- |
| build   | `-P, --progress`    | Zenity progress dialog (console fallback) |
| build   | `-c, --compression` | Compression algorithm (default: zstd)     |
| build   | `-e, --exclude`     | Exclude patterns                          |
| build   | `-o, --output`      | Output archive file (auto-detected)       |
| extract | `-P, --progress`    | Zenity progress dialog (console fallback) |
| extract | `-o, --output`      | Output directory (default: current)       |

## Key Features

### Mount/Unmount

- Automatic mount point determination
- Robust mount tracking to prevent conflicts
- Configurable auto-cleanup
- Dependency validation (squashfuse, fusermount)

### Build (Enhanced)

- Multiple compression algorithms (zstd, gzip, xz)
- Exclusion patterns (patterns, wildcards, regex)
- Parallel processing with auto processor detection
- Automatic checksum generation (SHA256)
- Real-time progress tracking with Zenity/console
- Cancel button support
- **Source-based automatic filename generation**
- **Multiple sources support with automatic combination**
- **Smart output detection from command arguments**
- **Fallback to original archive naming pattern**

### Extract

- Archive extraction to specified directories
- Progress tracking with Zenity/console fallback
- Automatic output directory creation
- Default extraction to current directory
- Comprehensive error handling

### Progress Tracking

```mermaid
classDiagram
    direction TB

    class ProgressTracker {
        +process_output_line()
        +set_total_files()
        -_update_with_progress()
        -_process_file_line_functional()
    }

    class ExtractProgressTracker {
        +process_output_line()
        +set_total_files()
        -_update_with_progress()
        -_process_file_line_functional()
    }

    class ProgressState {
        +last_progress
        +file_count
        +total_files
        +total_size
        +processed_size
    }

    class ExtractProgressState {
        +last_progress
        +file_count
        +total_files
    }

    class ZenityProgressService {
        +start()
        +update()
        +check_cancelled()
        +close()
    }

    class ProgressParser {
        +parse_mksquashfs_progress()
        +parse_unsquashfs_progress()
    }

    class MksquashfsProgress {
        +current_files
        +total_files
        +percentage
    }

    class UnsquashfsProgress {
        +current_files
        +total_files
        +percentage
    }

    ProgressTracker --> ZenityProgressService : Uses
    ProgressTracker --> ProgressParser : Uses
    ProgressTracker --> ProgressState : Manages
    ExtractProgressTracker --> ZenityProgressService : Uses
    ExtractProgressTracker --> ProgressParser : Uses
    ExtractProgressTracker --> ExtractProgressState : Manages
    ProgressParser --> MksquashfsProgress : Creates
    ProgressParser --> UnsquashfsProgress : Creates
```

## Error Handling

### Error Hierarchy

```mermaid
classDiagram
    direction TB

    class SquashFSError {
        <<Base Exception>>
    }

    class CommandExecutionError {
        <<Base>>
        +command
        +return_code
        +message
    }

    SquashFSError <|-- DependencyError
    SquashFSError <|-- MountError
    SquashFSError <|-- UnmountError
    SquashFSError <|-- BuildError
    SquashFSError <|-- ExtractError
    SquashFSError <|-- ChecksumError
    SquashFSError <|-- ListError
    SquashFSError <|-- ConfigError
    SquashFSError <|-- MountPointError
    SquashFSError <|-- XattrError

    CommandExecutionError <|-- MountCommandExecutionError
    CommandExecutionError <|-- UnmountCommandExecutionError
    CommandExecutionError <|-- MksquashfsCommandExecutionError
    CommandExecutionError <|-- UnsquashfsCommandExecutionError
    CommandExecutionError <|-- UnsquashfsExtractCommandExecutionError

    class BuildCancelledError {
        <<Exception>>
    }

    class ExtractCancelledError {
        <<Exception>>
    }
```

## Testing

### Test Coverage (Current)

```
TOTAL: 94% coverage (1204 statements, 59 missing)

Module Coverage:
- 100%: __init__.py, checksum.py, config.py, errors.py, logging.py, tracking.py
- 97-99%: build.py, core.py, progress.py
- 88-94%: cli.py, dependencies.py, extract.py, list.py, mounting.py
```

### Test Architecture

```mermaid
classDiagram
    direction TB

    class TestFixtures {
        +test_files
        +build_test_files
        +checksum_test_files
        +test_data_builder
        +test_config
    }

    class TestDataBuilder {
        +with_squashfs_file()
        +with_checksum_file()
        +with_source_directory()
        +build()
    }

    class TestMarkers {
        +@pytest.mark.slow
        +@pytest.mark.integration
        +@pytest.mark.unit
        +@pytest.mark.regression
        +@pytest.mark.edge_case
    }

    TestFixtures --> TestDataBuilder : Uses
```

## System Requirements

### Required Tools

- **squashfuse**: Mounting operations
- **fusermount**: Unmounting operations
- **mksquashfs**: Building archives
- **unsquashfs**: Listing/extracting contents
- **sha256sum**: Checksum operations
- **zenity**: Progress dialog (optional, with console fallback)

### Platform Support

- **Linux**: Full functionality
- **Other platforms**: Limited (dependency-based)

## Configuration

### Main Options

```yaml
mount_base: "/path/to/mounts" # Base directory for automatic mount points
auto_cleanup: true # Enable automatic mount directory cleanup
verbose: false # Enable detailed logging
compression: "zstd" # Default compression algorithm
block_size: "1M" # Default block size
processors: "auto" # Default processor count
xattr_mode: "user-only" # Xattr extraction mode (all/user-only/none)
```

## Enhanced Build Functionality

### Source-Based Filename Generation

The build system now automatically generates output filenames based on the source name:

**Algorithm:**

1. For directories: Use directory name + `.sqsh` extension
2. For files: Remove all extensions and add `.sqsh` extension
3. If output file already exists, fall back to `archive-YYYYMMDD-nn.sqsh` pattern

**Examples:**

- Directory `MyProject` → `MyProject.sqsh`
- File `MyArchive.tar.gz` → `MyArchive.sqsh`
- File `data.backup.2023.tar.xz` → `data.backup.sqsh`

### Multiple Sources Support

The build command now accepts multiple source arguments:

**Command Structure:**

```bash
squish build [options] <source1> <source2>... <output.sqsh>
squish build [options] <source1> <source2>... -o <output.sqsh>
```

**Automatic Output Detection:**

- If last argument ends with `.sqsh`, `.sqs`, or `.squashfs`, it's treated as output
- For single sources: Use source-based naming (e.g., `MyProject.sqsh`)
- For multiple sources with no output: Use generic naming pattern `archive-YYYYMMDD-nn.sqsh`
- Explicit `-o` flag always takes precedence

**Multiple Sources Processing:**

1. **Direct mksquashfs Integration**: Pass multiple source arguments directly to `mksquashfs`
2. **No Temporary Copying**: Eliminates disk quota issues by avoiding intermediate file copying
3. **Efficient Resource Usage**: Uses native `mksquashfs` multiple source support
4. **Automatic Output Naming**: Generates `archive-YYYYMMDD-nn.sqsh` pattern for multiple sources without specified output

### Usage Examples

**Single Source with Auto-Naming:**

```bash
# Directory source
squish build ./MyProject
# Creates: ./MyProject.sqsh

# File source
squish build ./archive.tar.gz
# Creates: ./archive.sqsh
```

**Multiple Sources:**

```bash
# Auto-detected output
squish build ./source1 ./source2 ./output.sqsh

# Explicit output
squish build ./source1 ./source2 -o ./output.sqsh

# Generic naming for multiple sources (no output specified)
squish build ./Altheia ./Neyyah
# Creates: ./archive-YYYYMMDD-nn.sqsh (e.g., archive-20251222-01.sqsh)
```

## Conclusion

Squish provides a comprehensive, modular SquashFS management solution with:

- ✅ Clean architecture with separation of concerns
- ✅ Robust error handling with detailed error types
- ✅ Comprehensive testing (94% coverage)
- ✅ User-friendly interface with clear logging
- ✅ Real-time progress tracking with cancel support
- ✅ Archive extraction with automatic directory creation
- ✅ Zenity integration with graceful console fallback
- ✅ **Enhanced build with source-based naming and multiple sources**
- ✅ **Efficient multiple source handling without disk quota issues**
- ✅ **Direct mksquashfs integration for optimal performance**

The system is designed for maintainability, extensibility, and reliability.
