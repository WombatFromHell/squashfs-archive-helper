# Squish - SquashFS Archive Management Tool

**Squish** is a powerful Python-based SquashFS archive management tool that provides a wrapper around archive-related operations with a user-friendly CLI interface.

## 🚀 Quick Start

```bash
# Initialize and build the project
uv venv --clear; uv sync
make all
```

## 📦 Features

- **Mount/Unmount**: Automatic mount point determination with robust tracking
- **Build**: Enhanced archive creation with source-based naming and multiple sources
- **Extract**: Comprehensive archive extraction with progress tracking
- **Checksum**: Reliable verification and generation
- **List**: Efficient archive content listing
- **Progress Tracking**: Real-time feedback with Zenity/console support
- **Error Handling**: Comprehensive classification and recovery

## 📖 Installation & Setup

### Prerequisites

**Required Tools:**

- `squashfuse` - Mounting operations
- `fusermount` - Unmounting operations
- `mksquashfs` - Building archives
- `unsquashfs` - Listing/extracting contents
- `sha256sum` - Checksum operations
- `zenity` - Progress dialog (optional, with console fallback)

**Platform Support:**

- ✅ **Linux**: Full functionality
- ⚠️ **Other platforms**: Limited (dependency-based)

### Setup with UV

```bash
# Clear any existing virtual environment and sync dependencies
uv venv --clear; uv sync
```

### Build and Install

```bash
# Clean, build, and install locally
make all
```

This will:

1. Clean previous builds
2. Create a Python bundle in `dist/squish.pyz`
3. Install to `~/.local/bin/squish`
4. Set up KIO servicemenu integration (Linux)

## 🎯 CLI Commands

### Command Structure

```bash
squish <command> [options] [arguments]
```

**Unique prefix matching** is supported for all commands:

- `m` → `mount`
- `um` → `unmount`
- `c` → `check`
- `b` → `build`
- `ext` → `extract`
- `l` → `ls`

### Mount/Unmount

```bash
# Mount a SquashFS archive
squish mount <file> [mount_point]
squish m <file> [mount_point]

# Unmount a SquashFS archive
squish unmount <file> [mount_point]
squish um <file> [mount_point]
```

**Features:**

- **Automatic Mount Point Determination**: Uses `mount_base` configuration for intelligent mount point creation
- Robust mount tracking to prevent conflicts
- Configurable auto-cleanup
- Dependency validation

**Mount Base Functionality:**

The `mount_base` configuration controls how automatic mount points are created:

**1. Automatic Mount Point Generation:**

- When no explicit mount point is provided, Squish creates one automatically
- Format: `<current_directory>/<mount_base>/<archive_filename>`
- Default `mount_base`: `"mounts"`
- Example: `squish mount archive.sqsh` creates `./mounts/archive/`

**2. Configuration Options:**

- **Config File**: Set in `squish.toml` under `[default]` section
- **Environment Variable**: `SQUISH_MOUNT_BASE`
- **Default Value**: `"mounts"`

**3. Mount Point Resolution Algorithm:**

```
1. If explicit mount_point provided → use it directly
2. If no mount_point provided → create: current_dir/mount_base/archive_stem/
3. Create directory if it doesn't exist
4. Validate mount point is available
```

**4. Auto-Cleanup Behavior:**

- When `auto_cleanup=True` (default), empty mount base directories are removed
- Only cleans up directories named after `mount_base` configuration
- Prevents accidental cleanup of user-created directories

**Examples:**

```bash
# Using default mount_base ("mounts")
squish mount archive.sqsh
# Creates: ./mounts/archive/

# Using custom mount_base via config
# squish.toml: mount_base = "squashfs_mounts"
squish mount archive.sqsh
# Creates: ./squashfs_mounts/archive/

# Explicit mount point (ignores mount_base)
squish mount archive.sqsh /custom/mount/point
# Uses: /custom/mount/point

# Environment variable override
export SQUISH_MOUNT_BASE="my_mounts"
squish mount archive.sqsh
# Creates: ./my_mounts/archive/
```

**Configuration Example:**

```toml
[default]
mount_base = "squashfs_mounts"  # Custom mount base directory
auto_cleanup = true              # Enable automatic cleanup
```

### Checksum Verification

```bash
# Verify checksum of a SquashFS archive
squish check <file>
squish c <file>
```

### Build Archives

```bash
# Basic build with auto-naming (no explicit -o flag needed)
squish build <sources>...
squish b <sources>...

# Build with explicit output using -o flag
squish build <sources>... -o <output>

# Build with GUI progress dialog using -P flag
squish build <sources>... -c zstd -b 1M -P --exclude "*.tmp"
```

**Implicit Output Filename Functionality:**

The `build` command features intelligent automatic output filename detection and generation:

**1. Automatic Output Detection Algorithm:**

- If the last argument ends with `.sqsh`, `.sqs`, or `.squashfs`, it's treated as the output filename
- If no explicit output is specified, the tool generates a filename based on the sources
- The `-o` flag always takes precedence over automatic detection

**2. Source-Based Filename Generation:**

- **Single Directory**: Uses directory name + `.sqsh` extension
  - `MyProject/` → `MyProject.sqsh`
  - `project-files/` → `project-files.sqsh`
- **Single File**: Removes all extensions and adds `.sqsh` extension
  - `archive.tar.gz` → `archive.sqsh`
  - `data.backup.2023.tar.xz` → `data.backup.sqsh`
  - `backup.iso` → `backup.sqsh`

**3. Multiple Sources Without Output:**

- Generates `archive-YYYYMMDD-nn.sqsh` pattern
- `YYYYMMDD` = current date (e.g., `20251222`)
- `nn` = sequential number to prevent conflicts
- Example: `archive-20251222-01.sqsh`

**4. Conflict Resolution:**

- If the generated filename already exists, appends sequential number
- Example: `MyProject.sqsh` → `MyProject-01.sqsh` → `MyProject-02.sqsh`

**Examples:**

```bash
# Implicit output detection (last arg is .sqsh file)
squish build ./source1 ./source2 ./output.sqsh

# Explicit output using -o flag (overrides detection)
squish build ./source1 ./source2 -o ./custom-output.sqsh

# Single directory with auto-naming
squish build ./MyProject
# Creates: ./MyProject.sqsh

# Single file with auto-naming
squish build ./archive.tar.gz
# Creates: ./archive.sqsh

# Multiple sources without output (generic naming)
squish build ./source1 ./source2
# Creates: ./archive-20251222-01.sqsh

# Conflict resolution example
squish build ./MyProject  # Creates MyProject.sqsh
squish build ./MyProject  # Creates MyProject-01.sqsh
squish build ./MyProject  # Creates MyProject-02.sqsh
```

**Multiple Sources Support:**

```bash
# Auto-detected output (last arg ends with .sqsh)
squish build ./source1 ./source2 ./output.sqsh

# Explicit output using -o flag
squish build ./source1 ./source2 -o ./output.sqsh

# Generic naming for multiple sources (no output specified)
squish build ./source1 ./source2
# Creates: ./archive-YYYYMMDD-nn.sqsh (e.g., archive-20251222-01.sqsh)
```

**Build Options:**

| Option                            | Description                                                 | Default |
| --------------------------------- | ----------------------------------------------------------- | ------- |
| `-o, --output OUTPUT`             | Output archive file (optional, auto-detected from last arg) | `None`  |
| `-e, --exclude EXCLUDE`           | Exclude pattern                                             | `None`  |
| `-f, --exclude-file EXCLUDE_FILE` | File with exclude patterns                                  | `None`  |
| `-w, --wildcards`                 | Enable wildcard matching                                    | `False` |
| `-r, --regex`                     | Enable regex matching                                       | `False` |
| `-c, --compression COMPRESSION`   | Compression algorithm (default: zstd)                       | `zstd`  |
| `-b, --block-size BLOCK_SIZE`     | Block size (default: 1M)                                    | `1M`    |
| `-p, --processors PROCESSORS`     | Number of processors (default: auto)                        | `auto`  |
| `-P, --progress`                  | Show progress dialog with Zenity                            | `False` |

**Positional Arguments:**

- `sources`: Source directories/files to archive (required, one or more)

**Progress Flag Details:**

- `-P, --progress`: Shows a **GUI Zenity progress dialog** with real-time build progress
- Automatically falls back to console progress if Zenity is unavailable
- Includes cancel button support for interrupting long-running build operations

### List Archive Contents

```bash
# List contents of a SquashFS archive
squish ls <archive>
squish l <archive>
```

### Extract Archives

```bash
# Extract to current directory (no explicit -o flag needed)
squish extract <archive>
squish ex <archive>

# Extract to specific directory using -o flag
squish extract <archive> -o <output_directory>

# Extract with GUI progress dialog using -P flag
squish extract <archive> -P
```

**Extract Options:**

| Option           | Description                                       | Default           |
| ---------------- | ------------------------------------------------- | ----------------- |
| `-o, --output`   | **Optional** output directory                     | Current directory |
| `-P, --progress` | **GUI Zenity progress dialog** (console fallback) | `False`           |

## 🔧 Configuration

### Configuration File

Create a `squish.toml` file in your `$HOME/.config/` or the `$XDG_CONFIG_HOME/` directory:

```toml
[default]
mount_base = "/path/to/mounts"
auto_cleanup = true
verbose = false
compression = "zstd"
block_size = "1M"
processors = "auto"
xattr_mode = "user-only"
```
