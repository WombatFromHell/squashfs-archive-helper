# SquashFS Archive Helper

A set of bash wrappers with KDE service-menu integration for managing SquashFS archives with built-in integrity verification and GUI progress feedback.

## Features

- **High Compression**: Uses `zstd` (level 19 by default, `squish -c <n>`) with 1MB blocks for optimal space savings.
- **Integrity First**: Automatically generates and verifies `.sha256` checksums during creation, extraction, and mounting.
- **FUSE Mounting**: Seamlessly mount/unmount SquashFS images using `squashfuse` without root privileges.
- **Adaptive UI**: Displays graphical progress bars via `yad` or `zenity` when available, falling back to a detailed CLI view.
- **Desktop Integration**: Includes a `.desktop` file for KDE (Dolphin/Konqueror) context menu actions: **Verify**, **Extract**, **Mount**, **Unmount**, **Build**, and **Build with options**. Each file's actions are grouped into one **Squish** submenu (`X-KDE-Submenu`) placed at the top level of the menu (`X-KDE-Priority=TopLevel`) rather than inside KDE's **Actions** submenu.

## Dependencies

- `squashfs-tools` (`mksquashfs`, `unsquashfs`)
- `squashfuse` (for mounting)
- `coreutils` (`sha256sum`)
- `yad` or `zenity` (optional, for GUI progress)
- `pv` (optional, for byte-by-byte hash progress in `--pipe` mode)

## Usage

### Creation (`squish`)

```bash
# Create an archive from one or more directories
squish /path/to/data -o backup.sqsh

# Create an archive with a faster compression level
squish /path/to/data -o backup.sqsh -c 3

# Ask for the archive name and level in a dialog first (KDE: "Build with options")
squish --prompt /path/to/data

# Mount an archive to a managed mountpoint (auto-verifies checksum)
squish -m backup.sqsh

# Unmount an archive and cleanup mountpoints
squish -u backup.sqsh

# Mount and open the mounts folder in the desktop's own file manager
squish -m --open backup.sqsh

# Move into the mountpoint the command just created
cd "$(squish -m --print-mountpoint backup.sqsh)"
```

### Extraction (`unsquish`)

```bash
# Extract an archive (verifies checksum first)
unsquish backup.sqsh -o ./extracted_data

# List contents without extracting
unsquish --list backup.sqsh
```

### Machine-readable mode (`--pipe`)

Both commands can put progress on stdout for another program to render (the yazi plugin does
this). A `phase <name>` line marks each phase, bare integers are percentages, and every log
line goes to stderr:

```bash
unsquish --pipe backup.sqsh   # 'phase hash', hash percentages, then 'phase extract'
```

### One archive at a time

A build, an extraction or a mount of the same archive runs one at a time — the lock
is shared between `squish` and `unsquish`, keyed on the archive path. A second
command on a busy archive exits `3` and names the process holding it; nothing is
queued:

```bash
unsquish backup.sqsh           # holds backup.sqsh until it finishes
unsquish backup.sqsh -o other  # [ERROR] ... is running (pid ...); exit 3
```

A rebuild of an archive that is currently mounted is refused the same way (exit 1):
the mount outlives the mount command, so unmount it first.

To stop the run that holds it — the backend is stopped with it, and the partial
output is cleaned up:

```bash
unsquish --cancel backup.sqsh   # or: squish --cancel backup.sqsh
```

A cancelled run exits `2`; a stale lock left by a killed process is reclaimed by the
next command. A build cancelled during its checksum keeps the archive it already
wrote — it simply has no `.sha256` pair.

The yazi plugin refuses the same way, shows which process is busy, and offers `n c` to
stop an extract or mount of the archive under the cursor. A build is locked by its
output archive, which does not exist yet, so stop a build from a terminal:
`squish --cancel /path/to/output.sqsh`.

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
