#!/usr/bin/env bash
set -euo pipefail

# Configuration
PRIO_BIN_DIR="$HOME/.local/bin/scripts"
BIN_DIR="$HOME/.local/bin"
KDE_DIR="$HOME/.local/share/kio/servicemenus"
BINS=("squish.sh" "unsquish.sh")
DESKTOP="squashfs-actions.desktop"

do_install() {
  echo "Installing SquashFS Archive Helper..."
  mkdir -p "$BIN_DIR" "$KDE_DIR"

  # Determine target directory for binaries (.sh files)
  # Use PRIO_BIN_DIR if it exists, otherwise fall back to BIN_DIR
  local target_dir="$BIN_DIR"
  if [[ -d $PRIO_BIN_DIR ]]; then
    target_dir="$PRIO_BIN_DIR"
  fi

  # Install binaries and create shortened links in BIN_DIR
  for bin in "${BINS[@]}"; do
    if [[ -f $bin ]]; then
      local bin_dest="$target_dir/$bin"
      local link_dest="$BIN_DIR/${bin%.sh}"

      echo "  -> $bin_dest"
      install -m 755 "$bin" "$bin_dest"

      echo "  -> $link_dest (link)"
      ln -sf "$bin_dest" "$link_dest"
    fi
  done

  # Install KDE service menu
  if [[ -f $DESKTOP ]]; then
    echo "  -> $KDE_DIR/$DESKTOP"
    install -m 755 "$DESKTOP" "$KDE_DIR/"
  fi

  # Refresh KDE cache if tools exist
  found_kde_tool=false
  for cmd in kbuildsycoca6 kbuildsycoca5; do
    if command -v "$cmd" &>/dev/null; then
      echo "Refreshing KDE cache with $cmd..."
      "$cmd" --noincremental >/dev/null 2>&1 || true
      found_kde_tool=true
      break
    fi
  done

  if [[ $found_kde_tool == "false" ]]; then
    echo "Warning: No KDE cache refresh tool found (kbuildsycoca6/5). You may need to restart your session to see the new context menu actions."
  fi

  echo "Installation complete. Ensure $BIN_DIR is in your PATH."
}

do_uninstall() {
  echo "Uninstalling..."
  for bin in "${BINS[@]}"; do
    # Remove shortened links
    rm -f "$BIN_DIR/${bin%.sh}"
    # Remove binaries from both possible locations
    rm -f "$BIN_DIR/$bin"
    rm -f "$PRIO_BIN_DIR/$bin"
  done
  rm -f "$KDE_DIR/$DESKTOP"
  echo "Uninstalled successfully."
}

case "${1:-}" in
  -u | --uninstall) do_uninstall ;;
  -h | --help)
    echo "Usage: $0 [-u|--uninstall]"
    exit 0
    ;;
  *) do_install ;;
esac
