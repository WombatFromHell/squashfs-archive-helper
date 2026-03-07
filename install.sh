#!/usr/bin/env bash
#
# install.sh - Install/Uninstall script for squish (SquashFS archive management tool)
#
# Usage:
#   ./install.sh              - Install squish
#   ./install.sh --uninstall  - Uninstall squish
#   ./install.sh --dry-run    - Show what would be done without making changes
#   ./install.sh --help       - Show this help message
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE="squish.pyz"
CHECKSUM="squish.pyz.sha256sum"
SERVICE_MENU="squashfs-actions.desktop"

INSTALL_DIR="$HOME/.local/bin"
SCRIPTS_DIR="$HOME/.local/bin/scripts"
SYMLINK="$HOME/.local/bin/squish"
SERVICE_DIR="$HOME/.local/share/kio/servicemenus"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[INFO]${NC} $*"; }
ok() { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*" >&2; }
err() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

show_help() {
    cat <<EOF
Install/Uninstall script for squish (SquashFS archive management tool)

Usage: $(basename "$0") [OPTIONS]

Options:
  -u, --uninstall   Uninstall squish (remove installed files)
  -n, --dry-run     Show what would be done without making changes
  -h, --help        Show this help message

Installation paths:
  Bundle:  \$HOME/.local/bin/scripts/squish.pyz
  Symlink: \$HOME/.local/bin/squish
  Service: \$HOME/.local/share/kio/servicemenus/squashfs-actions.desktop
EOF
}

check_dependencies() {
    local missing=0

    # Required: bundle file
    if [[ ! -f "$SCRIPT_DIR/$BUNDLE" ]]; then
        err "Missing required file: $SCRIPT_DIR/$BUNDLE"
        missing=1
    fi

    # Required: sha256sum for verification
    if ! command -v sha256sum &>/dev/null; then
        err "Missing required command: sha256sum"
        missing=1
    fi

    # Optional: kbuildsycoca5 for KDE menu refresh
    KDE_REFRESH=0
    if command -v kbuildsycoca5 &>/dev/null; then
        KDE_REFRESH=1
    fi

    return $missing
}

verify_checksum() {
    [[ ! -f "$SCRIPT_DIR/$CHECKSUM" ]] && return 0
    log "Verifying SHA256 checksum..."
    (cd "$SCRIPT_DIR" && sha256sum -c "$CHECKSUM" >/dev/null 2>&1) || {
        err "Checksum verification failed!"
        return 1
    }
    ok "Checksum verified"
}

check_path() {
    case ":$PATH:" in
        *:"$HOME/.local/bin":*) return 0 ;;
    esac
    warn "~/.local/bin is not in your PATH"
    warn "Add this to your shell config (e.g., ~/.bashrc or ~/.zshrc):"
    warn "  export PATH=\"\$HOME/.local/bin:\$PATH\""
}

do_install() {
    local dry_run="$1"

    # Determine target directory:
    # 1) Prefer ~/.local/bin/scripts/ if it exists
    # 2) Otherwise use ~/.local/bin/ (will be created if needed)
    local target_dir="$INSTALL_DIR"
    if [[ -d "$SCRIPTS_DIR" ]]; then
        target_dir="$SCRIPTS_DIR"
    fi

    # Check dependencies first (before any mutations)
    check_dependencies || return 1

    # Verify checksum
    verify_checksum || return 1

    if [[ "$dry_run" == "true" ]]; then
        [[ ! -d "$target_dir" ]] && log "[DRY-RUN] mkdir -p $target_dir"
        log "[DRY-RUN] cp $SCRIPT_DIR/$BUNDLE -> $target_dir/"
        [[ -f "$SCRIPT_DIR/$CHECKSUM" ]] && log "[DRY-RUN] cp $SCRIPT_DIR/$CHECKSUM -> $target_dir/"
        log "[DRY-RUN] ln -sf $target_dir/$BUNDLE -> $SYMLINK"
        log "[DRY-RUN] cp $SCRIPT_DIR/$SERVICE_MENU -> $SERVICE_DIR/"
        [[ "$KDE_REFRESH" -eq 1 ]] && log "[DRY-RUN] kbuildsycoca5 --noincremental"
        ok "Dry run complete"
        return 0
    fi

    # Install
    mkdir -p "$target_dir" "$SERVICE_DIR"
    cp -f "$SCRIPT_DIR/$BUNDLE" "$target_dir/"
    [[ -f "$SCRIPT_DIR/$CHECKSUM" ]] && cp -f "$SCRIPT_DIR/$CHECKSUM" "$target_dir/"
    chmod +x "$target_dir/$BUNDLE"
    ln -sf "$target_dir/$BUNDLE" "$SYMLINK"
    cp -f "$SCRIPT_DIR/$SERVICE_MENU" "$SERVICE_DIR/"
    [[ "$KDE_REFRESH" -eq 1 ]] && kbuildsycoca5 --noincremental

    echo
    ok "Installation complete!"
    echo
    log "Run squish with: squish  or  $target_dir/$BUNDLE"
    check_path
}

do_uninstall() {
    local dry_run="$1"

    # Check dependencies first (sha256sum not needed for uninstall, but kbuildsycoca5 is optional)
    KDE_REFRESH=0
    command -v kbuildsycoca5 &>/dev/null && KDE_REFRESH=1

    if [[ "$dry_run" == "true" ]]; then
        log "[DRY-RUN] rm -f $SYMLINK"
        log "[DRY-RUN] rm -f $SCRIPTS_DIR/$BUNDLE $SCRIPTS_DIR/$CHECKSUM"
        log "[DRY-RUN] rm -f $INSTALL_DIR/$BUNDLE $INSTALL_DIR/$CHECKSUM"
        log "[DRY-RUN] rm -f $SERVICE_DIR/$SERVICE_MENU"
        [[ "$KDE_REFRESH" -eq 1 ]] && log "[DRY-RUN] kbuildsycoca5 --noincremental"
        ok "Dry run complete"
        return 0
    fi

    # Remove files
    rm -f "$SYMLINK"
    rm -f "$SCRIPTS_DIR/$BUNDLE" "$SCRIPTS_DIR/$CHECKSUM"
    rm -f "$INSTALL_DIR/$BUNDLE" "$INSTALL_DIR/$CHECKSUM"
    rm -f "$SERVICE_DIR/$SERVICE_MENU"
    [[ "$KDE_REFRESH" -eq 1 ]] && kbuildsycoca5 --noincremental

    echo
    ok "Uninstallation complete!"
}

# Main
mode="install"
dry_run="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -u|--uninstall) mode="uninstall"; shift ;;
        -n|--dry-run) dry_run="true"; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) err "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ "$mode" == "install" ]]; then
    do_install "$dry_run"
else
    do_uninstall "$dry_run"
fi
