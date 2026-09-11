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
bash "$SRC/squish.sh" --pipe --check "$WORK/space.sqsh" 2>&1 | grep -q "VERIFIED" || fail "checksum verify failed"
ok "checksum verify"

# 2b. unsquish --check: explicit arg and positional fallback.
bash "$SRC/unsquish.sh" --pipe --check "$WORK/space.sqsh" 2>&1 | grep -q "VERIFIED" || fail "unsquish --check failed"
bash "$SRC/unsquish.sh" --pipe "$WORK/space.sqsh" --check 2>&1 | grep -q "VERIFIED" || fail "unsquish --check positional fallback failed"
ok "unsquish --check"

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
if bash "$SRC/squish.sh" --pipe --check "$WORK/bad.sqsh" >/dev/null 2>&1; then
  fail "corrupted archive verified (should have failed)"
fi
ok "corrupted archive rejected"

#######################################
# OUTPUT FILENAME INFERENCE (no -o)
#######################################

TODAY="$(date +%Y%m%d)"

# 8. CLI single source, no -o -> <dirname>.sqsh in CWD.
mkdir -p "$WORK/infer_cli"
(cd "$WORK/infer_cli" && bash "$SRC/squish.sh" --pipe "$WORK/plain") || fail "cli inferred compress failed"
[[ -f "$WORK/infer_cli/plain.sqsh" && -f "$WORK/infer_cli/plain.sqsh.sha256" ]] || fail "cli inferred name wrong"
ok "cli single source inferred name"

# 9. CLI inferred name already taken -> archive-YYYYMMDD-N.sqsh.
mkdir -p "$WORK/infer_collide"
: > "$WORK/infer_collide/plain.sqsh"
(cd "$WORK/infer_collide" && bash "$SRC/squish.sh" --pipe "$WORK/plain") || fail "collision compress failed"
[[ -f "$WORK/infer_collide/archive-$TODAY-1.sqsh" ]] || fail "collision fallback name wrong"
ok "collision falls back to archive-YYYYMMDD-N"

# 10. CLI multi-source, no -o -> first source's name.
mkdir -p "$WORK/infer_multi"
(cd "$WORK/infer_multi" && bash "$SRC/squish.sh" --pipe "$WORK/plain" "$WORK/src with space") || fail "multi compress failed"
[[ -f "$WORK/infer_multi/plain.sqsh" ]] || fail "multi-source inferred name wrong"
ok "cli multi-source inferred name (first source)"

# 11. KIO single source, no -o -> <dirname>.sqsh (Dolphin single selection).
mkdir -p "$WORK/infer_kio"
(cd "$WORK/infer_kio" && bash "$SRC/squish.sh" --pipe -k "file://$WORK/src%20with%20space") || fail "kio inferred compress failed"
[[ -f "$WORK/infer_kio/src with space.sqsh" && -f "$WORK/infer_kio/src with space.sqsh.sha256" ]] || fail "kio single source inferred name wrong"
ok "kio single source inferred name"

# 12. KIO multi-source, no -o -> archive-YYYYMMDD-N.sqsh.
mkdir -p "$WORK/infer_kio_multi"
(cd "$WORK/infer_kio_multi" && bash "$SRC/squish.sh" --pipe -k "file://$WORK/plain" "file://$WORK/src%20with%20space") || fail "kio multi compress failed"
[[ -f "$WORK/infer_kio_multi/archive-$TODAY-1.sqsh" ]] || fail "kio multi fallback name wrong"
ok "kio multi-source archive-YYYYMMDD-N"

# 13. KIO %U single-argument list form (space-joined URIs as one arg).
mkdir -p "$WORK/infer_kio_arg"
(cd "$WORK/infer_kio_arg" && bash "$SRC/squish.sh" --pipe -k "file://$WORK/plain file://$WORK/src%20with%20space") || fail "kio single-arg compress failed"
[[ -f "$WORK/infer_kio_arg/archive-$TODAY-1.sqsh" ]] || fail "kio single-arg fallback name wrong"
ok "kio %U single-argument list"

# 14. KIO-inferred archive: checksum verifies and default-dir extract round-trips.
bash "$SRC/squish.sh" --pipe --check "$WORK/infer_kio/src with space.sqsh" 2>&1 | grep -q "VERIFIED" || fail "kio inferred checksum verify failed"
bash "$SRC/unsquish.sh" --pipe "$WORK/infer_kio/src with space.sqsh" || fail "default-dir extract failed"
diff -r "$WORK/src with space" "$WORK/infer_kio/src with space/src with space" >/dev/null 2>&1 || fail "default-dir extract mismatch"
ok "kio inferred round-trip (check + default-dir extract)"

# 15. unsquish -o to an existing non-empty directory must fail.
if bash "$SRC/unsquish.sh" --pipe "$WORK/infer_cli/plain.sqsh" -o "$WORK/plain" >/dev/null 2>&1; then
  fail "extract into non-empty dir should have failed"
fi
ok "non-empty output dir rejected"

echo "OK: $(basename "$0")"
