#!/usr/bin/env bats
# Integration self-check for squish.sh / unsquish.sh against the real tools.
# --pipe keeps every case on the machine-readable path, so the YAD/Zenity GUI
# is never opened.

source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/helpers.bash"

TODAY="$(date +%Y%m%d)"

make_trees() { # source trees with a space in the directory name and nesting
  mkdir -p "$WORK/plain" "$WORK/src with space/sub"
  printf 'hello\n' >"$WORK/plain/a.txt"
  printf 'w o r l d\n' >"$WORK/src with space/b.txt"
  printf 'deep\n' >"$WORK/src with space/sub/c.txt"
}

# bats runs the file top level once per test, so the fixture is declared here
# and every test gets its own fresh copy in its own WORK.
make_trees

@test "compresses a directory whose path contains a space" {
  run_squish_in "$WORK/data" --pipe "$WORK/src with space" -o "$WORK/space.sqsh"
  [[ -f "$WORK/space.sqsh" && -f "$WORK/space.sqsh.sha256" ]]
}

@test "squish verifies the checksum of an archive it created" {
  run_squish_in "$WORK/data" --pipe "$WORK/plain" -o "$WORK/check.sqsh"
  run_squish_in "$WORK/data" --pipe --check "$WORK/check.sqsh"
  [[ $OUT == *VERIFIED* ]]
}

@test "unsquish --check accepts the flag before and after the archive" {
  run_squish_in "$WORK/data" --pipe "$WORK/plain" -o "$WORK/check.sqsh"
  run_unsquish_in "$WORK/data" --pipe --check "$WORK/check.sqsh"
  [[ $OUT == *VERIFIED* ]]
  run_unsquish_in "$WORK/data" --pipe "$WORK/check.sqsh" --check
  [[ $OUT == *VERIFIED* ]]
}

@test "extracts and keeps the contents identical" {
  run_squish_in "$WORK/data" --pipe "$WORK/src with space" -o "$WORK/extract.sqsh"
  run_unsquish_in "$WORK/data" --pipe "$WORK/extract.sqsh" -o "$WORK/out_space"
  diff -r "$WORK/src with space" "$WORK/out_space/src with space" >/dev/null 2>&1
}

@test "lists archive members" {
  run_squish_in "$WORK/data" --pipe "$WORK/src with space" -o "$WORK/list.sqsh"
  run_unsquish_in "$WORK/data" --list "$WORK/list.sqsh"
  grep -q b.txt <<<"$OUT"
}

@test "compresses a file:// URI" {
  run_squish_in "$WORK/data" --pipe -k "file://$WORK/plain" -o "$WORK/kio.sqsh"
  [[ -f "$WORK/kio.sqsh" ]]
}

@test "extracts to an explicit directory" {
  run_squish_in "$WORK/data" --pipe -k "file://$WORK/plain" -o "$WORK/kio_x.sqsh"
  run_unsquish_in "$WORK/data" --pipe "$WORK/kio_x.sqsh" -o "$WORK/kio_out"
  diff -r "$WORK/plain" "$WORK/kio_out/plain" >/dev/null 2>&1
}

@test "rejects a corrupted archive even when its stale checksum matches" {
  run_squish_in "$WORK/data" --pipe "$WORK/plain" -o "$WORK/good.sqsh"
  cp "$WORK/good.sqsh" "$WORK/bad.sqsh"
  cp "$WORK/good.sqsh.sha256" "$WORK/bad.sqsh.sha256"
  printf 'x' >>"$WORK/bad.sqsh"
  run_squish_in "$WORK/data" --pipe --check "$WORK/bad.sqsh"
  [[ $RC -ne 0 ]]
}

@test "names a single CLI source after its directory" {
  mkdir -p "$WORK/infer_cli"
  run_squish_in "$WORK/infer_cli" --pipe "$WORK/plain"
  [[ -f "$WORK/infer_cli/plain.sqsh" && -f "$WORK/infer_cli/plain.sqsh.sha256" ]]
}

@test "falls back to archive-YYYYMMDD-N when the inferred name is taken" {
  mkdir -p "$WORK/infer_collide"
  : >"$WORK/infer_collide/plain.sqsh"
  run_squish_in "$WORK/infer_collide" --pipe "$WORK/plain"
  [[ -f "$WORK/infer_collide/archive-$TODAY-1.sqsh" ]]
}

@test "names a multi-source CLI action after its first source" {
  mkdir -p "$WORK/infer_multi"
  run_squish_in "$WORK/infer_multi" --pipe "$WORK/plain" "$WORK/src with space"
  [[ -f "$WORK/infer_multi/plain.sqsh" ]]
}

@test "names a single KIO source after its directory" {
  mkdir -p "$WORK/infer_kio"
  run_squish_in "$WORK/infer_kio" --pipe -k "file://$WORK/src%20with%20space"
  [[ -f "$WORK/infer_kio/src with space.sqsh" &&
    -f "$WORK/infer_kio/src with space.sqsh.sha256" ]]
}

@test "names a multi-source KIO action archive archive-YYYYMMDD-N" {
  mkdir -p "$WORK/infer_kio_multi"
  run_squish_in "$WORK/infer_kio_multi" --pipe -k \
    "file://$WORK/plain" "file://$WORK/src%20with%20space"
  [[ -f "$WORK/infer_kio_multi/archive-$TODAY-1.sqsh" ]]
}

@test "accepts the KDE %U single-argument URI list" {
  mkdir -p "$WORK/infer_kio_arg"
  run_squish_in "$WORK/infer_kio_arg" --pipe -k \
    "file://$WORK/plain file://$WORK/src%20with%20space"
  [[ -f "$WORK/infer_kio_arg/archive-$TODAY-1.sqsh" ]]
}

@test "round-trips a KIO-inferred archive through check and default extract" {
  mkdir -p "$WORK/infer_kio_rt"
  run_squish_in "$WORK/infer_kio_rt" --pipe -k "file://$WORK/src%20with%20space"
  run_squish_in "$WORK/data" --pipe --check "$WORK/infer_kio_rt/src with space.sqsh"
  [[ $OUT == *VERIFIED* ]]
  run_unsquish_in "$WORK/data" --pipe "$WORK/infer_kio_rt/src with space.sqsh"
  diff -r "$WORK/src with space" \
    "$WORK/infer_kio_rt/src with space/src with space" >/dev/null 2>&1
}

@test "refuses to extract over a non-empty directory" {
  run_squish_in "$WORK/data" --pipe "$WORK/plain" -o "$WORK/reject.sqsh"
  run_unsquish_in "$WORK/data" --pipe "$WORK/reject.sqsh" -o "$WORK/plain"
  [[ $RC -ne 0 ]]
}
