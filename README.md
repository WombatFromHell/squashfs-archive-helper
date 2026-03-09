# SquashFS Archive Helper

A bash wrapper with KDE service-menu integration for managing SquashFS archives with built-in integrity verification and GUI progress feedback.

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

# Mount an archive to a managed mountpoint
squish -m backup.sqsh

# Unmount an archive
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

1. Install `src/squish.sh` and `src/unsquish.sh` to your `PATH` (e.g., `~/.local/bin/`) and link them as `squish` and `unsquish`.
2. (KDE Users) Copy `assets/squashfs-actions.desktop` to `~/.local/share/kio/servicemenus/`.
