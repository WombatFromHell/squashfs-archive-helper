#!/usr/bin/env bats
# --hash <file.sqsh> re-runs the hash flow for an existing archive: the
# .sha256 pair is recomputed from the archive, never from the old hash file.
# Exit codes match the rest of the tool: 0 written, 1 missing, 2 cancelled,
# 3 busy (one operation per archive).

# shellcheck source=tests/helpers.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/helpers.bash"
# shellcheck source=tests/stubs.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/stubs.bash"

stub_progress_emitters
stub_pv
use_stub_dir

make_archive() { printf 'payload\n' >"$WORK/data/one.sqsh"; }

@test "--hash rewrites the pair from the archive" {
  make_archive
  printf 'stale\n' >"$WORK/data/one.sqsh.sha256"
  run_squish --hash one.sqsh
  [[ $RC -eq 0 ]]
  grep -qE '^[0-9a-f]{64}  one\.sqsh$' "$WORK/data/one.sqsh.sha256"
  [[ "$OUT" == *"Checksum written"* ]]
}

@test "--hash works with the positional before the flag" {
  make_archive
  run_squish one.sqsh --hash
  [[ $RC -eq 0 ]]
  grep -qE '^[0-9a-f]{64}  one\.sqsh$' "$WORK/data/one.sqsh.sha256"
}

@test "--hash streams the hash phases in pipe mode" {
  make_archive
  run_squish --pipe --hash one.sqsh
  [[ $RC -eq 0 ]]
  [[ "$OUT" == *"phase hash"* && "$OUT" == *"phase hashfile-write"* ]]
}

@test "--hash refuses a missing archive" {
  run_squish --hash no.sqsh
  [[ $RC -eq 1 ]]
  [[ "$OUT" == *"not found"* ]]
}

@test "--hash without a file is a usage error" {
  run_squish --hash
  [[ $RC -eq 1 ]]
  [[ "$OUT" == *"Argument for hash is missing or invalid"* ]]
}

@test "--hash refuses while another operation holds the archive" {
  make_archive
  plant_lock "$WORK/data/one.sqsh" $$
  run_squish --hash one.sqsh
  [[ $RC -eq 3 ]]
  [[ "$OUT" == *"Another squish operation"* ]]
}

@test "--hash on a busy archive does not touch the pair" {
  make_archive
  printf 'stale\n' >"$WORK/data/one.sqsh.sha256"
  plant_lock "$WORK/data/one.sqsh" $$
  run_squish --hash one.sqsh
  [[ $RC -eq 3 ]]
  [[ "$(cat "$WORK/data/one.sqsh.sha256")" == "stale" ]]
}
