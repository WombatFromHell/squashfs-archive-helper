#!/usr/bin/env bats
# The two configurable build knobs: -c <num> must reach mksquashfs as
# -Xcompression-level <num> (default 19), and --prompt must ask for the archive
# name and level through the dialog before the same argv is built.

# bats runs every test in its own subshell, so exporting a fixture variable is
# local to that test on purpose — the stub tools read it from the environment.
# shellcheck disable=SC2030,SC2031
# shellcheck source=tests/helpers.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/helpers.bash"
# shellcheck source=tests/stubs.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/stubs.bash"

mkdir -p "$WORK/plain"
printf 'hello\n' >"$WORK/plain/a.txt"

@test "keeps compression level 19 when -c is absent" {
  export MKLOG="$WORK/mk.log"
  stub_mksquashfs_argv
  use_stub_dir
  run_squish_in "$WORK/data" --pipe "$WORK/plain" -o "$WORK/default.sqsh"
  [[ $RC -eq 0 ]]
  grep -q -- '-Xcompression-level 19' "$MKLOG"
}

@test "-c <num> sets the compression level mksquashfs is given" {
  export MKLOG="$WORK/mk.log"
  stub_mksquashfs_argv
  use_stub_dir
  run_squish_in "$WORK/data" --pipe "$WORK/plain" "$WORK/plain/a.txt" \
    -o "$WORK/level.sqsh" -c 9
  [[ $RC -eq 0 ]]
  grep -q -- '-Xcompression-level 9' "$MKLOG"
  grep -q -- '-comp zstd' "$MKLOG"
}

@test "-c rejects a missing or non-numeric level" {
  run_squish_in "$WORK/data" --pipe "$WORK/plain" -c
  [[ $RC -ne 0 ]]
  grep -q -- 'Argument for -c is missing or invalid.' <<<"$OUT"
  run_squish_in "$WORK/data" --pipe "$WORK/plain" -c nope
  [[ $RC -ne 0 ]]
  grep -q -- 'Argument for -c is missing or invalid.' <<<"$OUT"
}

@test "--prompt takes the name and level from the dialog" {
  export MKLOG="$WORK/mk.log" PROMPT_REPLY=$'picked.sqsh\n5' YAD_EXIT=0
  stub_mksquashfs_argv
  stub_yad_prompt
  use_stub_dir
  run_squish_in "$WORK/data" --prompt "$WORK/plain"
  [[ $RC -eq 0 ]]
  [[ -f "$WORK/data/picked.sqsh" ]]
  grep -q -- '-Xcompression-level 5' "$MKLOG"
}

@test "--prompt appends .sqsh to a name without an extension" {
  export MKLOG="$WORK/mk.log" PROMPT_REPLY=$'mypack\n9' YAD_EXIT=0
  stub_mksquashfs_argv
  stub_yad_prompt
  use_stub_dir
  run_squish_in "$WORK/data" --prompt "$WORK/plain"
  [[ $RC -eq 0 ]]
  [[ -f "$WORK/data/mypack.sqsh" ]]
  grep -q -- '/mypack.sqsh ' "$MKLOG"
}

@test "--prompt cancels before anything is built" {
  export MKLOG="$WORK/mk.log" PROMPT_REPLY='' YAD_EXIT=1
  stub_mksquashfs_argv
  stub_yad_prompt
  use_stub_dir
  run_squish_in "$WORK/data" --prompt "$WORK/plain"
  [[ $RC -ne 0 ]]
  [[ ! -e "$WORK/data/plain.sqsh" ]]
}

@test "--prompt refuses to ask in pipe mode" {
  stub_yad_prompt
  use_stub_dir
  run_squish_in "$WORK/data" --pipe --prompt "$WORK/plain"
  [[ $RC -ne 0 ]]
  grep -q -- 'cannot prompt' <<<"$OUT"
}
