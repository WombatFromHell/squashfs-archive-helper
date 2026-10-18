#!/usr/bin/env bats
# One shared failure, one wording: the same broken archive has to be described
# the same way by every CLI that meets it. Pins the sentences the suites assert
# on so a reword cannot silently fork a failure path.

source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/helpers.bash"

make_unclean_archive() { # an archive whose checksum half is missing
  # Only failure wording is asserted, so the archive half never needs SquashFS bytes.
  printf 'payload\n' >"$WORK/data/nopair.sqsh"
}

make_unclean_archive

@test "squish and unsquish name a missing checksum pair the same way" {
  run_squish -m "$WORK/data/nopair.sqsh"
  [[ $RC -ne 0 ]]
  grep -q 'No paired checksum file found' <<<"$OUT"
  run_unsquish_in "$WORK/data" --check "$WORK/data/nopair.sqsh"
  [[ $RC -ne 0 ]]
  grep -q 'No paired checksum file found' <<<"$OUT"
}

@test "unsquish --list on a missing archive names the missing half" {
  run_unsquish_in "$WORK/data" --list "$WORK/data/ghost.sqsh"
  [[ $RC -ne 0 ]]
  grep -q 'Archive file not found' <<<"$OUT"
}

@test "squish reports an option used without a value" {
  run_squish --check "$WORK/data/nopair.sqsh" -o
  [[ $RC -ne 0 ]]
  grep -q 'Argument for -o is missing or invalid.' <<<"$OUT"
}

@test "unsquish reports an option used without a value the same way" {
  run_unsquish_in "$WORK/data" --check "$WORK/data/nopair.sqsh" -o
  [[ $RC -ne 0 ]]
  grep -q 'Argument for -o is missing or invalid.' <<<"$OUT"
}
