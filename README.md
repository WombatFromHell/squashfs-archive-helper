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
- `util-linux` (`mountpoint`, to drop mountpoints that are no longer mounted)
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

# Check a checksum without mounting or extracting (KDE: "Verify")
squish --check backup.sqsh

# List managed mountpoints, dropping the ones no longer mounted
squish --list-mounts

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
unsquish --pipe backup.sqsh   # 'phase hashfile-read', 'phase hash', hash %, 'phase extract'
squish --pipe src -o out.sqsh # 'phase hash', hash %, 'phase hashfile-write'
```

The hash-file phases carry no percentages — writing or reading the `.sha256` is instant —
so a renderer shows the label alone: the plugin reports `Reading hash file...` and
`Writing hash file...`.

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
unsquish --cancel               # stop whichever run you hold; refuses if several are running
```

A cancelled run exits `2`; a stale lock left by a killed process is reclaimed by the
next command. A build cancelled during its checksum keeps the archive it already
wrote — it simply has no `.sha256` pair.

With no archive named, `--cancel` asks the lock root who is running: exactly one live
squish run is stopped, and two or more are refused with every archive listed rather than
guessed.

In yazi, `n c` cancels as a **shell** action with `--orphan`, not a plugin action: yazi
queues plugin and shell jobs behind a running one, so a cancel without `--orphan` only
fires once the build ends. The binding ships in `squish.yazi/keymap.example.toml`; `n v`
verifies a checksum (`squish --pipe --check`) and reports the same progress the build and
extract actions show.

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

- `make test`: Runs the `bats` suite and the yazi plugin tests (`luajit`, skipped if absent).
- `make lint`: Runs shellcheck over `src/`, `assets/` and `tests/`.
- `make package`: Creates a reproducible, versioned tarball in the `artifact/` directory.
- `make format`: Formats all shell scripts and markdown files.
