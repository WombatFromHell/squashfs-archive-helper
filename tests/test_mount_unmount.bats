#!/usr/bin/env bats
# Integration self-check for the mount/unmount/tracker subsystem.
# The FUSE tools are stubbed on PATH: no real filesystem is mounted, so a
# marker file models "is this path mounted" and the tracker bookkeeping is what
# gets asserted.

source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/helpers.bash"
# shellcheck source=./stubs.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/stubs.bash"

mounts_dir="$XDG_RUNTIME_DIR/squish-mounts"
mount_model_fuse "$WORK/marks"
stub_yad_quiet
use_stub_dir

make_archive() { # an archive plus its checksum.
  # squashfuse is modelled on PATH, so nothing here reads the bytes as SquashFS:
  # the archive half is a plain file and the suite pays no archival cost.
  printf 'payload\n' >"$WORK/data/one.sqsh"
  ( cd "$WORK/data" && sha256sum one.sqsh ) >"$WORK/data/one.sqsh.sha256"
}

# bats runs the file top level once per test, so the fixture is declared here
# and every test gets its own fresh copy in its own WORK.
make_archive

@test "mount writes a tracker, creates the mountpoint, and marks it mounted" {
  run_squish -m one.sqsh
  [[ $RC -eq 0 ]]
  grep -q 'Mounted successfully' <<<"$OUT"
  [[ $(count_trackers) -eq 1 ]]
  local tracker
  tracker="$(find "$XDG_RUNTIME_DIR" -maxdepth 1 -name '*.[0-9][0-9].mounted')"
  [[ $(head -n1 "$tracker") == "$mounts_dir/one.01.mounted" ]]
  [[ $(tail -n1 "$tracker") == "$WORK/data/one.sqsh" ]]
  [[ -d "$mounts_dir/one.01.mounted" ]]
  is_mount_marked "$mounts_dir/one.01.mounted"
}

@test "refuses to mount a second time while the mount is live" {
  run_squish -m one.sqsh
  [[ $RC -eq 0 ]]
  run_squish -m one.sqsh
  [[ $RC -ne 0 ]]
  grep -qi 'already mounted' <<<"$OUT"
  [[ $(count_trackers) -eq 1 ]]
}

@test "unmount clears the tracker, the mountpoint, and the mount state" {
  run_squish -m one.sqsh
  [[ $RC -eq 0 ]]
  run_squish -u one.sqsh
  [[ $RC -eq 0 ]]
  grep -q 'Unmounted successfully' <<<"$OUT"
  [[ $(count_trackers) -eq 0 ]]
  [[ ! -d "$mounts_dir" ]]
  ! is_mount_marked "$mounts_dir/one.01.mounted"
}

@test "--list-mounts prints the archive to mountpoint pair" {
  run_squish -m one.sqsh
  [[ $RC -eq 0 ]]
  run_squish --list-mounts
  [[ $RC -eq 0 ]]
  grep -qF "$WORK/data/one.sqsh -> $mounts_dir/one.01.mounted" <<<"$OUT"
}

@test "the mountpoint is the same whatever folder the command runs in" {
  run_squish_in "$WORK" -m "$WORK/data/one.sqsh"
  [[ $RC -eq 0 ]]
  [[ -d "$mounts_dir/one.01.mounted" ]]
  [[ ! -d "$WORK/squish-mounts" ]]
}

@test "unmount cleans the mount, not a folder named after the run location" {
  run_squish -m one.sqsh
  [[ $RC -eq 0 ]]
  run_squish_in "$WORK" -u "$WORK/data/one.sqsh"
  [[ $RC -eq 0 ]]
  [[ ! -d "$mounts_dir" ]]
  [[ ! -d "$WORK/squish-mounts" ]]
}

@test "--open hands the shared mounts folder to the desktop handler" {
  export OPENLOG="$WORK/stub/openlog"
  stub_opener_record
  run_squish -m one.sqsh --open
  [[ $RC -eq 0 ]]
  grep -q 'Mounted successfully' <<<"$OUT"
  [[ "$(tail -n1 "$OPENLOG")" == "$mounts_dir" ]]
}

@test "an opener that cannot open still leaves a working mount" {
  stub_opener_refuse
  run_squish -m one.sqsh --open
  [[ $RC -eq 0 ]]
  grep -qi 'Could not show the mounts folder' <<<"$OUT"
  is_mount_marked "$mounts_dir/one.01.mounted"
  [[ $(count_trackers) -eq 1 ]]
}

@test "--print-mountpoint puts the bare path on stdout" {
  run_squish -m one.sqsh --print-mountpoint
  [[ $RC -eq 0 ]]
  [[ $(grep -c "^${mounts_dir}/one.01.mounted$" <<<"$OUT") -eq 1 ]]
}

@test "--force drops a stale tracker and mounts again" {
  run_squish -m one.sqsh
  [[ $RC -eq 0 ]]
  unmark_mount "$mounts_dir/one.01.mounted"
  run_squish -m one.sqsh
  [[ $RC -ne 0 ]]
  grep -qi 'already mounted' <<<"$OUT"
  run_squish -m --force one.sqsh
  [[ $RC -eq 0 ]]
  grep -qi 'stale tracker' <<<"$OUT"
  [[ $(count_trackers) -eq 1 ]]
  [[ -d "$mounts_dir/one.01.mounted" ]]
}

@test "unmounts by the mountpoint path itself" {
  run_squish -m one.sqsh
  [[ $RC -eq 0 ]]
  run_squish -u "$mounts_dir/one.01.mounted"
  [[ $RC -eq 0 ]]
  grep -qi 'Unmounted successfully' <<<"$OUT"
  [[ $(count_trackers) -eq 0 ]]
}

@test "mounts an archive that has no checksum file when told to skip" {
  rm -f "$WORK/data/one.sqsh.sha256"
  run_squish -y -m one.sqsh
  [[ $RC -eq 0 ]]
  grep -qi 'verification skipped' <<<"$OUT"
  [[ $(count_trackers) -eq 1 ]]
}

@test "checksum mismatch blocks the mount" {
  printf 'deadbeef  one.sqsh\n' >"$WORK/data/one.sqsh.sha256"
  run_squish -m one.sqsh
  [[ $RC -ne 0 ]]
  grep -qi 'FAILED' <<<"$OUT"
  [[ $(count_trackers) -eq 0 ]]
}

@test "refuses a mount once a stem uses all 99 tracker slots" {
  printf 'payload\n' >"$WORK/data/packed.sqsh"
  for n in {01..99}; do : >"$XDG_RUNTIME_DIR/packed.${n}.mounted"; done
  run_squish -m packed.sqsh
  [[ $RC -ne 0 ]]
  grep -qi '99 tracker slots' <<<"$OUT"
}

@test "two trackers claiming one mountpoint report corrupt state and refuse" {
  run_squish -m one.sqsh
  [[ $RC -eq 0 ]]
  printf '%s\n%s\n' "$mounts_dir/one.01.mounted" "$WORK/data/other.sqsh" \
    >>"$XDG_RUNTIME_DIR/duplicate.02.mounted"
  run_squish -u "$mounts_dir/one.01.mounted"
  [[ $RC -ne 0 ]]
  grep -qi 'corrupt tracker state' <<<"$OUT"
}
