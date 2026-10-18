# shellcheck shell=bash
# Tool models for the suites that drive squish through PATH stubs.
# Source after tests/helpers.bash, then call the models a test observes through.
# Models write scripts into "$WORK/stub"; putting that directory first on PATH
# is the suite's own choice (use_stub_dir), because some suites need the real
# squashfs-tools next to the models.
#
# "Mounted" is modelled by a file inside $MARK_DIR whose name is the mountpoint
# with every slash turned into an underscore. mount_model_fuse and is_mount_marked
# are the only two places that spelling is written, and they must stay in step.

use_stub_dir() { export PATH="$WORK/stub:$PATH"; }

stub_dialog_ready() { # $@ = GUI program names to make "available" (silent, success)
  local name
  for name in "$@"; do
    cat >"$WORK/stub/$name" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
    chmod +x "$WORK/stub/$name"
  done
}

mount_model_fuse() { # squashfuse/umount/fusermount/mountpoint, state in $MARK_DIR
  export MARK_DIR="$1"
  mkdir -p "$MARK_DIR"

  cat >"$WORK/stub/squashfuse" <<'EOF'
#!/usr/bin/env bash
mp="${*: -1}"
: >"$MARK_DIR/${mp//\//_}"
exit 0
EOF

  cat >"$WORK/stub/umount" <<'EOF'
#!/usr/bin/env bash
mp="${*: -1}"
rm -f "$MARK_DIR/${mp//\//_}" 2>/dev/null
exit 0
EOF

  cat >"$WORK/stub/fusermount" <<'EOF'
#!/usr/bin/env bash
mp="${*: -1}"
rm -f "$MARK_DIR/${mp//\//_}" 2>/dev/null
exit 0
EOF

  cat >"$WORK/stub/mountpoint" <<'EOF'
#!/usr/bin/env bash
mp="${*: -1}"
[[ -e "$MARK_DIR/${mp//\//_}" ]]
EOF

  local tool
  for tool in squashfuse umount fusermount mountpoint; do
    chmod +x "$WORK/stub/$tool"
  done
}

# A mounted path is a file in $MARK_DIR named after that path with slashes
# turned into underscores. These three spellings are that one convention.
mark_mount() { : >"$MARK_DIR/${1//\//_}"; }
unmark_mount() { rm -f "$MARK_DIR/${1//\//_}" 2>/dev/null; }
is_mount_marked() { [[ -e "$MARK_DIR/${1//\//_}" ]]; }

# The desktop's folder handler is modelled here, not stubbed silently: a suite
# that asks for --open needs to see which folder it was handed. $OPENLOG is
# exported so the model resolves it when it runs.
stub_opener_record() { # xdg-open that records each call's argv in $OPENLOG
  export OPENLOG
  cat >"$WORK/stub/xdg-open" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$OPENLOG"
exit 0
EOF
  chmod +x "$WORK/stub/xdg-open"
}

stub_opener_refuse() { # xdg-open that cannot open anything
  cat >"$WORK/stub/xdg-open" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
  chmod +x "$WORK/stub/xdg-open"
}

stub_yad_quiet() { # a YAD window that drains its stdin and succeeds
  cat >"$WORK/stub/yad" <<'EOF'
#!/usr/bin/env bash
[[ "$*" == *--progress* ]] && cat >/dev/null
exit 0
EOF
  chmod +x "$WORK/stub/yad"
}

stub_yad_argv() { # a YAD window whose argv is inspectable; exits $YAD_EXIT
  export DIALOGLOG
  cat >"$WORK/stub/yad" <<'EOF'
#!/usr/bin/env bash
printf '@@dialog@@\n' >>"$DIALOGLOG"
for a in "$@"; do printf '%s\n' "$a" >>"$DIALOGLOG"; done
# Only a progress gauge gets a stdin feed; a popup gets none, and bats hands the
# runner an open stdin, so an unconditional read would block the whole suite.
[[ "$*" == *--progress* ]] && cat >/dev/null
exit "${YAD_EXIT:-0}"
EOF
  chmod +x "$WORK/stub/yad"
}

stub_yad_receipt() { # a YAD gauge that records the lines it is handed
  export RECEIPT
  cat >"$WORK/stub/yad" <<'EOF'
#!/usr/bin/env bash
printf '@@dialog@@\n' >>"$RECEIPT"
if [[ "$*" == *--progress* ]]; then
  while IFS= read -r line; do printf '%s\n' "$line" >>"$RECEIPT"; done
fi
exit 0
EOF
  chmod +x "$WORK/stub/yad"
}

stub_progress_emitters() { # mksquashfs/unsquashfs stand-ins that print bare percentages
  cat >"$WORK/stub/mksquashfs" <<'EOF'
#!/usr/bin/env bash
have_pct=0 have_info=0
for a in "$@"; do
  case "$a" in
    -percentage) have_pct=1 ;;
    -info) have_info=1 ;;
  esac
done
printf 'Parallel model emitter\nCreating filesystem.\n'
if [[ $have_pct -eq 1 && $have_info -eq 0 ]]; then printf '10\n50\n100\n'; fi
# An emitter that produced no archive would be a real error; model must write one.
[[ -e "$2" ]] || : >"$2"
exit 0
EOF

  cat >"$WORK/stub/unsquashfs" <<'EOF'
#!/usr/bin/env bash
have_pct=0 have_info=0
for a in "$@"; do
  case "$a" in
    -percentage) have_pct=1 ;;
    -info) have_info=1 ;;
  esac
done
printf 'Parallel model extractor\n2 inodes to write\n'
if [[ $have_pct -eq 1 && $have_info -eq 0 ]]; then printf '100\n'; fi
exit 0
EOF

  chmod +x "$WORK/stub/mksquashfs" "$WORK/stub/unsquashfs"
}
