#!/usr/bin/env bash
# Targeted slice: closing/cancelling the YAD hash dialog must not be reported as
# corruption. Asserts on the text handed to the dialog (what the user sees) and
# on what squish says on stderr.
set -uo pipefail

SRC="$(cd "$(dirname "$0")/../src" && pwd)"
fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "ok: $1"; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/stub" "$WORK/data/src" "$WORK/run"
printf 'hello\n' >"$WORK/data/src/a.txt"
mksquashfs "$WORK/data/src" "$WORK/data/good.sqsh" -no-xattrs >/dev/null 2>&1
( cd "$WORK/data" && sha256sum good.sqsh ) >"$WORK/data/good.sqsh.sha256"
cp "$WORK/data/good.sqsh" "$WORK/data/bad.sqsh"
cp "$WORK/data/good.sqsh.sha256" "$WORK/data/bad.sqsh.sha256"
printf 'tampered\n' >>"$WORK/data/bad.sqsh"

export XDG_RUNTIME_DIR="$WORK/run"
mounts_dir="$WORK/data/squish-mounts"
export DIALOGLOG="$WORK/dialog-args.log"
: >"$DIALOGLOG"

# Stub yad records the argv it is given: that is the text the user would see.
cat >"$WORK/stub/yad" <<'EOF'
#!/usr/bin/env bash
printf '@@dialog@@\n' >>"$DIALOGLOG"
for a in "$@"; do printf '%s\n' "$a" >>"$DIALOGLOG"; done
cat >/dev/null
exit "${YAD_EXIT:-0}"
EOF
chmod +x "$WORK/stub/yad"
export PATH="$WORK/stub:$PATH"

run_squish() { # $@ = squish arguments; sets OUT (stderr+stdout) and RC
  OUT="$(cd "$WORK/data" && bash "$SRC/squish.sh" "$@" 2>&1)"
  RC=$?
}

dialog_says_failed() { grep -qi 'FAILED' "$DIALOGLOG"; }
count_trackers() { find "$XDG_RUNTIME_DIR" -maxdepth 1 -name '*.[0-9][0-9].mounted' | wc -l; }

#######################################
# 1. Honest dialog: good pair verifies, corrupted pair reports FAILED.
#######################################
export YAD_EXIT=0
run_squish --check good.sqsh
grep -q 'VERIFIED' <<<"$OUT" || fail "clean archive did not verify (exit $RC): $OUT"
ok "clean archive verifies with an honest dialog"

run_squish --check bad.sqsh
dialog_says_failed || fail "corrupted archive showed no FAILED dialog: $(tail -6 "$DIALOGLOG")"
[[ $RC -ne 0 ]] || fail "corrupted --check exited 0"
ok "corrupted archive reports FAILED"

#######################################
# 2. Cancelled dialog: user closed the window mid-hash.
#######################################
export YAD_EXIT=3
: >"$DIALOGLOG"

run_squish -m good.sqsh
[[ $RC -ne 0 ]] || fail "mount proceeded despite a cancelled hash dialog (exit $RC)"
dialog_says_failed &&
  fail "cancelled hash dialog showed a FAILED dialog to the user (exit $RC): $(tail -6 "$DIALOGLOG")"
grep -qi 'cancel' <<<"$OUT" ||
  fail "cancelled verification not reported as a cancellation (exit $RC): $OUT"
[[ $(count_trackers) -eq 0 ]] || fail "cancelled verification leaked $(count_trackers) tracker files"
[[ ! -e "$mounts_dir/good.01.mounted" ]] || fail "cancelled verification created a mountpoint"
ok "cancelled hash dialog: reported as cancelled, nothing mounted, no leak"

run_squish --check good.sqsh
dialog_says_failed && fail "--check showed a FAILED dialog after a cancelled hash (exit $RC)"
[[ $RC -ne 0 ]] || fail "--check exited 0 after a cancelled dialog (exit $RC)"
ok "--check with a cancelled dialog is not reported as corruption"

echo "OK: $(basename "$0")"
