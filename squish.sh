#!/usr/bin/env bash

# squish.sh - Create squashfs archives with excludes support
# Simplified to core functionality with proper exclude handling

set -euo pipefail

# Defaults - using optimal settings
COMPRESSION="zstd"
BLOCK_SIZE="1M"
EXCLUDES=()
LIST_MODE=false

usage() {
  local name="squish.sh"
  echo "Usage: $name [OPTIONS] <source> <output>"
  echo "       $name --ls <archive>"
  echo ""
  echo "Create a squashfs archive with checksum or list archive contents"
  echo ""
  echo "Options:"
  echo "  -e PATTERN  Exclude files/dirs (can be used multiple times)"
  echo "  -f FILE     Exclude patterns from file (one per line)"
  echo "  -w          Enable wildcard matching for excludes"
  echo "  -r          Enable regex matching for excludes"
  echo "  --ls        List contents of squashfs archive"
  echo "  -h          Show this help"
  echo ""
  echo "Examples:"
  echo "  $name /source archive.sqsh"
  echo "  $name -e '*.tmp' -e '*.log' /source archive.sqsh"
  echo "  $name -f exclude.txt /source archive.sqsh"
  echo "  $name --ls archive.sqsh"
}

# Parse arguments - handle long options manually
while [[ $# -gt 0 ]]; do
  case "$1" in
  -e)
    EXCLUDES+=("-e" "$2")
    shift 2
    ;;
  -f)
    EXCLUDES+=("-ef" "$2")
    shift 2
    ;;
  -w)
    EXCLUDES+=("-wildcards")
    shift
    ;;
  -r)
    EXCLUDES+=("-regex")
    shift
    ;;
  --ls)
    LIST_MODE=true
    shift
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  --)
    shift
    break
    ;;
  -*)
    echo "Error: Unknown option: $1" >&2
    usage
    exit 1
    ;;
  *)
    break
    ;;
  esac
done

if [ "$LIST_MODE" = true ]; then
  # List mode - expect single archive argument
  [ $# -ne 1 ] && {
    echo "Error: Expected <archive> for --ls mode" >&2
    usage
    exit 1
  }
  ARCHIVE="$1"

  # Check archive exists
  [ ! -e "$ARCHIVE" ] && {
    echo "Error: Archive not found: $ARCHIVE" >&2
    exit 1
  }

  # Verify unsquashfs command
  command -v unsquashfs >/dev/null || {
    echo "Error: unsquashfs not found" >&2
    exit 1
  }

  # List archive contents
  unsquashfs -llc "$ARCHIVE"
  exit 0
fi

# Create mode - expect source and output
[ $# -ne 2 ] && {
  echo "Error: Expected <source> <output>" >&2
  usage
  exit 1
}
SOURCE="$1"
OUTPUT="$2"

# Check source exists
[ ! -e "$SOURCE" ] && {
  echo "Error: Source not found: $SOURCE" >&2
  exit 1
}

# Check if output exists
[ -e "$OUTPUT" ] && {
  echo "Error: Output exists: $OUTPUT" >&2
  exit 1
}

# Verify required commands
command -v mksquashfs >/dev/null || {
  echo "Error: mksquashfs not found" >&2
  exit 1
}
command -v nproc >/dev/null || {
  echo "Error: nproc not found" >&2
  exit 1
}
command -v sha256sum >/dev/null || {
  echo "Error: sha256sum not found" >&2
  exit 1
}

# Build and execute mksquashfs command with excludes
mksquashfs_cmd=(
  "mksquashfs"
  "$SOURCE"
  "$OUTPUT"
  "-comp" "$COMPRESSION"
  "-b" "$BLOCK_SIZE"
  "-processors" "$(nproc)"
  "${EXCLUDES[@]}"
)

"${mksquashfs_cmd[@]}" &&
  echo "Created: $OUTPUT" &&
  sha256sum "$OUTPUT" >"$OUTPUT.sha256" &&
  echo "Wrote checksum: $OUTPUT.sha256"
