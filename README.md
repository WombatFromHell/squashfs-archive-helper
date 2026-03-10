# SquashFS Archive Helper

A set of bash wrappers with KDE service-menu integration for managing SquashFS archives with built-in integrity verification and GUI progress feedback.

## Features

- **High Compression**: Uses `zstd` (level 19) with 1MB blocks for optimal space savings.
- **Integrity First**: Automatically generates and verifies `.sha256` checksums during creation, extraction, and mounting.
- **FUSE Mounting**: Seamlessly mount/unmount SquashFS images using `squashfuse` without root privileges.
- **Adaptive UI**: Displays graphical progress bars via `yad` or `zenity` when available, falling back to a detailed CLI view.
- **Desktop Integration**: Includes a `.desktop` file for KDE (Dolphin/Konqueror) context menu actions: **Build**, **Extract**, **Mount**, and **Unmount**.

## Dependencies

- `squashfs-tools` (`mksquashfs`, `unsquashfs`)
- `squashfuse` (for mounting)
- `coreutils` (`sha256sum`)
- `yad` or `zenity` (optional, for GUI progress)

## Usage

### Creation (`squish`)

```bash
# Create an archive from one or more directories
squish /path/to/data -o backup.sqsh

# Mount an archive to a managed mountpoint (auto-verifies checksum)
squish -m backup.sqsh

# Unmount an archive and cleanup mountpoints
squish -u backup.sqsh
```

### Extraction (`unsquish`)

```bash
# Extract an archive (verifies checksum first)
unsquish backup.sqsh -o ./extracted_data

# List contents without extracting
unsquish --list backup.sqsh
```

## Installation

### Using Release Archive

1. Download and extract the latest release.
2. Run the included installation script:

   ```bash
   ./install.sh
   ```

   _This installs binaries to `~/.local/bin` and the KDE service menu to the appropriate local path._

### From Source

1. Clone the repository.
2. Build and install using the Makefile:

   ```bash
   make build
   make install
   ```

### Uninstallation

To remove all installed files, run:

```bash
./install.sh --uninstall
```

## Development

- `make package`: Creates a reproducible, versioned tarball in the `artifact/` directory.
- `make format`: Formats all shell scripts and markdown files.
