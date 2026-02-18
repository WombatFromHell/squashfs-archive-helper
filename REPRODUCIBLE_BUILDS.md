# Reproducible Builds

This project implements a deterministic build system to ensure that building the same source code always produces bit-for-bit identical artifacts, regardless of when or where the build is performed.

## Why Reproducible Builds?

Reproducible builds provide:

- **Verifiability**: Anyone can verify that the distributed binary matches the source code
- **Security**: Protection against supply chain attacks and tampering
- **Trust**: Independent parties can reproduce builds to confirm integrity
- **Debugging**: Easier to track down issues when builds are consistent

## Build Artifacts

The build process produces:

- `squish.pyz` - Self-executing Python bundle (zipapp format)
- `squish.pyz.sha256sum` - SHA256 checksum for verification

## Determinism Mechanisms

### 1. Fixed Timestamp (SOURCE_DATE_EPOCH)

All file timestamps are normalized to a fixed epoch to eliminate build-time variability:

```makefile
SOURCE_DATE_EPOCH ?= 315532800  # Jan 1, 1980 00:00:00 UTC
export SOURCE_DATE_EPOCH
```

This follows the [reproducible-builds.org SOURCE_DATE_EPOCH specification](https://reproducible-builds.org/specs/source-date-epoch/).

### 2. Deterministic File Ordering

Files are added to the bundle in a consistent, locale-independent order:

```bash
find . -type f | LC_ALL=C sort | zip -X -q -@ ../archive.zip
```

### 3. Stripped Metadata

The `-X` flag strips extra file attributes from the zip archive to prevent system-specific metadata from affecting the build.

### 4. Clean Staging

Each build starts with a fresh staging directory to prevent leftover files from affecting the output:

```bash
rm -rf $(BUILD_DIR)/staging
mkdir -p $(BUILD_DIR)/staging
cp -r $(SRC_DIR)/* $(BUILD_DIR)/staging/
```

### 5. Timestamp Normalization

All files in the staging directory have their timestamps set to SOURCE_DATE_EPOCH:

```bash
find $(BUILD_DIR)/staging -exec touch -d "@$(SOURCE_DATE_EPOCH)" {} \;
```

## Building

### Standard Build

```bash
make build
```

### Custom Timestamp

To use a different SOURCE_DATE_EPOCH:

```bash
SOURCE_DATE_EPOCH=1609459200 make build  # Jan 1, 2021 00:00:00 UTC
```

### Full Clean Build

```bash
make all  # clean + build + install
```

## Verification

### Checksum Verification

After building, verify the artifact:

```bash
cd dist && sha256sum -c squish.pyz.sha256sum
```

### Reproducing a Build

To verify that builds are reproducible:

1. Build the artifact:

   ```bash
   make build
   ```

2. Record the checksum:

   ```bash
   cat dist/squish.pyz.sha256sum
   ```

3. Clean and rebuild:

   ```bash
   make clean && make build
   ```

4. Compare checksums - they should be identical.

### Cross-System Verification

To verify reproducibility across different systems:

1. Both parties build from the same source commit
2. Use the same SOURCE_DATE_EPOCH value
3. Compare SHA256 checksums - they should match exactly

## Nix Environment

For maximum reproducibility, use the provided Nix shell:

```bash
nix develop
make build
```

This ensures consistent toolchain versions and build dependencies.

## Technical Details

### Build Process Flow

```
src/ → staging/ → archive.zip → squish.pyz
  ↓      ↓           ↓            ↓
copy  normalize   zip with    prepend
      timestamps  -X flag     shebang
```

### Entry Point

The `__main__.py` is created during build to enable bundle execution:

```python
from entry import main; main()
```

The entry point imports and runs the CLI from the `squish` package.

### Version Extraction

The build extracts the version from `pyproject.toml` for logging:

```makefile
VERSION := $(shell grep '^version = ' pyproject.toml | cut -d'"' -f2)
```

## Limitations

- The shebang line (`#!/usr/bin/env python3`) may vary between systems
- Installation paths are user-specific
- KDE service menu integration requires KDE Plasma

## References

- [Reproducible Builds Project](https://reproducible-builds.org/)
- [SOURCE_DATE_EPOCH Specification](https://reproducible-builds.org/specs/source-date-epoch/)
- [Python Zipapp Documentation](https://docs.python.org/3/library/zipapp.html)
