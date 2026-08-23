#!/usr/bin/env bash
# Integration self-check for squish.sh / unsquish.sh against real tools.
set -uo pipefail

SRC="$(cd "$(dirname "$0")/../src" && pwd)"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok()   { echo "ok: $1"; }

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

# Source tree with a space in the directory name and nested content.
mkdir -p "$WORK/src with space/sub" "$WORK/plain"
printf 'hello\n' > "$WORK/plain/a.txt"
printf 'w o r l d\n' > "$WORK/src with space/b.txt"
printf 'deep\n' > "$WORK/src with space/sub/c.txt"

# 1. Compress a directory whose path contains a space (exercises quoting).
# --pipe forces the machine-readable path so the YAD/Zenity GUI is never used.
bash "$SRC/squish.sh" --pipe "$WORK/src with space" -o "$WORK/space.sqsh" || fail "squish compress failed"
[[ -f "$WORK/space.sqsh" ]] || fail "archive not created"
[[ -f "$WORK/space.sqsh.sha256" ]] || fail "checksum not created"
ok "compress (path with space)"

# 2. Checksum verification of a good archive.
bash "$SRC/squish.sh" --check "$WORK/space.sqsh" 2>&1 | grep -q "VERIFIED" || fail "checksum verify failed"
ok "checksum verify"

# 3. Extract and compare contents recursively.
bash "$SRC/unsquish.sh" --pipe "$WORK/space.sqsh" -o "$WORK/out_space" || fail "unsquish extract failed"
diff -r "$WORK/src with space" "$WORK/out_space/src with space" >/dev/null 2>&1 || fail "extracted contents differ"
ok "extract + content match"

# 4. List archive members.
bash "$SRC/unsquish.sh" --list "$WORK/space.sqsh" 2>&1 | grep -q "b.txt" || fail "list did not show member"
ok "list archive"

# 5. KIO URI mode (file:// decoding end-to-end).
bash "$SRC/squish.sh" --pipe -k "file://$WORK/plain" -o "$WORK/kio.sqsh" || fail "kio compress failed"
[[ -f "$WORK/kio.sqsh" ]] || fail "kio archive not created"
ok "kio uri mode"

# 6. Extract to an explicit directory.
bash "$SRC/unsquish.sh" --pipe "$WORK/kio.sqsh" -o "$WORK/kio_out" || fail "kio extract failed"
diff -r "$WORK/plain" "$WORK/kio_out/plain" >/dev/null 2>&1 || fail "kio extracted contents differ"
ok "extract explicit dir"

# 7. Corrupted archive (with a matching-but-stale checksum) must be rejected.
cp "$WORK/space.sqsh" "$WORK/bad.sqsh"
cp "$WORK/space.sqsh.sha256" "$WORK/bad.sqsh.sha256"
printf 'x' >> "$WORK/bad.sqsh"
if bash "$SRC/squish.sh" --check "$WORK/bad.sqsh" >/dev/null 2>&1; then
  fail "corrupted archive verified (should have failed)"
fi
ok "corrupted archive rejected"

echo "OK: $(basename "$0")"
