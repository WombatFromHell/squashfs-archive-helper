#!/usr/bin/env bats
# The SHA-256 phase has to reach the --pipe consumer, not just the GUI: stdout
# carries progress lines (bare percentages plus a `phase <name>` marker) and the
# hash itself stays out of band, so stdout consumers that want one value
# (--print-mountpoint) keep getting exactly one value.

# shellcheck source=tests/helpers.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/helpers.bash"
# shellcheck source=tests/stubs.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/stubs.bash"

# run_script merges the streams; the pipe contract is stdout's alone, so this
# runner splits them: OUT is stdout, $WORK/err is stderr.
run_pipe() { # $1 = script under SRC, rest = arguments
  local script="$1"
  shift
  RC=0
  OUT="$(cd "$WORK/data" && bash "$SRC/$script" "$@" 2>"$WORK/err")" || RC=$?
}

pct_after_marker() { # count percentage lines following the given phase marker
  awk -v m="$1" '$0 == m { f = 1; next } f && /^[0-9]+$/ { n++ } END { print n + 0 }' <<<"$OUT"
}

stub_progress_emitters
stub_pv
use_stub_dir

make_tree() {
  mkdir -p "$WORK/tree"
  printf 'hello\n' >"$WORK/tree/a.txt"
}

make_pair() { # an archive plus its checksum, as the mount suite models it
  printf 'payload\n' >"$WORK/data/one.sqsh"
  (cd "$WORK/data" && sha256sum one.sqsh) >"$WORK/data/one.sqsh.sha256"
}

@test "squish --pipe streams the hash phase after compression" {
  make_tree
  run_pipe squish.sh --pipe "$WORK/tree" -o "$WORK/a.sqsh"
  [[ $RC -eq 0 ]]
  [[ $(grep -c '^phase hash$' <<<"$OUT") -eq 1 ]]
  [[ $(pct_after_marker "phase hash") -gt 0 ]]
  run ! grep -qE '^[0-9]+$|^phase ' "$WORK/err"
  grep -qE '^[0-9a-f]{64}  a\.sqsh$' "$WORK/a.sqsh.sha256"
}

@test "unsquish --pipe streams the hash phase before the extract phase" {
  make_tree
  run_pipe squish.sh --pipe "$WORK/tree" -o "$WORK/b.sqsh"
  [[ $RC -eq 0 ]]
  run_pipe unsquish.sh --pipe "$WORK/b.sqsh" -o "$WORK/out"
  [[ $RC -eq 0 ]]
  [[ $(grep -c '^phase hash$' <<<"$OUT") -eq 1 ]]
  [[ $(grep -c '^phase extract$' <<<"$OUT") -eq 1 ]]
  [[ $(pct_after_marker "phase hash") -gt 0 ]]
  [[ $(pct_after_marker "phase extract") -gt 0 ]]
  [[ $(grep -n '^phase hash$' <<<"$OUT" | cut -d: -f1) -lt $(grep -n '^phase extract$' <<<"$OUT" | cut -d: -f1) ]]
}

@test "--print-mountpoint keeps stdout to one path while pv is available" {
  make_pair
  mount_model_fuse "$WORK/marks"
  run_pipe squish.sh -m one.sqsh --print-mountpoint
  [[ $RC -eq 0 ]]
  [[ "$(wc -l <<<"$OUT")" -eq 1 ]]
  [[ "$OUT" == "$XDG_RUNTIME_DIR/squish-mounts/one.01.mounted" ]]
  run ! grep -qE '^[0-9]+$|^phase ' <<<"$OUT"
}

@test "squish --pipe -m streams the hash phase too" {
  make_pair
  mount_model_fuse "$WORK/marks"
  run_pipe squish.sh --pipe -m one.sqsh
  [[ $RC -eq 0 ]]
  [[ $(grep -c '^phase hash$' <<<"$OUT") -eq 1 ]]
  [[ $(pct_after_marker "phase hash") -gt 0 ]]
}

# The hash file is the other half of the pair, and it is the step a user watches
# for: a build writing it and a verify reading it must say so on the pipe stream,
# not stay silent while the archive's own hash streams percentages.
@test "squish --pipe reports the hash file being written" {
  make_tree
  run_pipe squish.sh --pipe "$WORK/tree" -o "$WORK/d.sqsh"
  [[ $RC -eq 0 ]]
  [[ $(grep -c '^phase hashfile-write$' <<<"$OUT") -eq 1 ]]
  [[ $(grep -n '^phase hash$' <<<"$OUT" | cut -d: -f1) -lt $(grep -n '^phase hashfile-write$' <<<"$OUT" | cut -d: -f1) ]]
  grep -qE '^[0-9a-f]{64}  d\.sqsh$' "$WORK/d.sqsh.sha256"
  run ! grep -q '^phase ' "$WORK/err"
}

@test "unsquish --pipe --check reports the hash file being read" {
  make_tree
  run_pipe squish.sh --pipe "$WORK/tree" -o "$WORK/e.sqsh"
  run_pipe unsquish.sh --pipe --check "$WORK/e.sqsh"
  [[ $RC -eq 0 ]]
  [[ $(grep -c '^phase hashfile-read$' <<<"$OUT") -eq 1 ]]
  [[ $(grep -n '^phase hashfile-read$' <<<"$OUT" | cut -d: -f1) -lt $(grep -n '^phase hash$' <<<"$OUT" | cut -d: -f1) ]]
  grep -q 'VERIFIED' "$WORK/err"
  run ! grep -q '^phase ' "$WORK/err"
}

@test "hash file phases appear when pv is missing" {
  make_tree
  rm "$WORK/stub/pv"
  PATH="$WORK/stub:/usr/bin:/bin" run_pipe squish.sh --pipe "$WORK/tree" -o "$WORK/f.sqsh"
  [[ $RC -eq 0 ]]
  [[ $(grep -c '^phase hashfile-write$' <<<"$OUT") -eq 1 ]]
  PATH="$WORK/stub:/usr/bin:/bin" run_pipe unsquish.sh --pipe --check "$WORK/f.sqsh"
  [[ $RC -eq 0 ]]
  [[ $(grep -c '^phase hashfile-read$' <<<"$OUT") -eq 1 ]]
}

@test "hashing stays silent and correct when pv is missing" {
  make_tree
  # No pv anywhere on PATH: the stub model is removed and the PATH is narrowed
  # to /usr/bin, so the fallback plain sha256sum path runs.
  rm "$WORK/stub/pv"
  PATH="$WORK/stub:/usr/bin:/bin" run_pipe squish.sh --pipe "$WORK/tree" -o "$WORK/c.sqsh"
  [[ $RC -eq 0 ]]
  run ! grep -q '^phase hash$' <<<"$OUT"
  grep -qE '^[0-9a-f]{64}  c\.sqsh$' "$WORK/c.sqsh.sha256"
  PATH="$WORK/stub:/usr/bin:/bin" run_pipe unsquish.sh --pipe --check "$WORK/c.sqsh"
  [[ $RC -eq 0 ]]
  run ! grep -q '^phase hash$' <<<"$OUT"
  grep -q 'VERIFIED' "$WORK/err"
}
