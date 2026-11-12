#!/usr/bin/env bats
# One operation per archive. squish and unsquish share a single lock keyed on the
# archive path, so a build, an extraction and a mount of the same archive never
# overlap. Busy means refused (exit 3), never queued.

# shellcheck source=tests/helpers.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/helpers.bash"
# shellcheck source=tests/stubs.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/stubs.bash"

export RUNLOG="$WORK/run.log"

new_archive() { # a real archive and its checksum, made before the stub dir is used
  mkdir -p "$WORK/plain"
  printf 'hello\n' >"$WORK/plain/a.txt"
  mksquashfs "$WORK/plain" "$WORK/a.sqsh" -no-progress >/dev/null
  (cd "$WORK" && sha256sum a.sqsh >a.sqsh.sha256)
}

start() { # $1 = working dir, $2 = script under SRC, rest = args; sets START_PID.
  # exec keeps $! the script itself, so a signal reaches the run, not a wrapper.
  local dir="$1" script="$2"
  shift 2
  (cd "$dir" && exec bash "$SRC/$script" "$@" >"$WORK/run.out" 2>"$WORK/run.err") &
  START_PID=$!
}

wait_for_lock() {
  local attempts=100
  while ((attempts-- > 0)); do
    [[ -n "$(find "$XDG_RUNTIME_DIR/squish-locks" -name pid -print -quit 2>/dev/null)" ]] && return 0
    sleep 0.05
  done
  return 1
}

# Locks are symlinks named pid; the directory that holds one stays behind.
lock_entries() { find "$XDG_RUNTIME_DIR/squish-locks" -name pid | wc -l; }

@test "a second extraction of the same archive is refused while the first runs" {
  new_archive
  stub_slow_emitters
  use_stub_dir

  start "$WORK" unsquish.sh --pipe "$WORK/a.sqsh" -o "$WORK/out1"
  wait_for_lock

  run_unsquish_in "$WORK" --pipe "$WORK/a.sqsh" -o "$WORK/out2"
  [[ $RC -eq 3 ]]
  grep -q "is running" <<<"$OUT"
  [[ ! -e $WORK/out2 ]]

  FIRST_RC=0
  wait "$START_PID" || FIRST_RC=$?
  [[ $FIRST_RC -eq 0 ]]
  [[ -f $WORK/out1/extracted.txt ]]
}

@test "a build and an extraction of one archive path refuse each other" {
  mkdir -p "$WORK/plain"
  printf 'hello\n' >"$WORK/plain/a.txt"
  stub_slow_emitters
  use_stub_dir

  start "$WORK" squish.sh --pipe "$WORK/plain" -o "$WORK/new.sqsh"
  wait_for_lock

  run_unsquish_in "$WORK" --pipe "$WORK/new.sqsh"
  [[ $RC -eq 3 ]]
  grep -q "is running" <<<"$OUT"

  FIRST_RC=0
  wait "$START_PID" || FIRST_RC=$?
  [[ $FIRST_RC -eq 0 ]]

  # The other way round: an extraction holding the archive blocks a build onto it.
  new_archive
  start "$WORK" unsquish.sh --pipe "$WORK/a.sqsh" -o "$WORK/out1"
  wait_for_lock

  run_squish_in "$WORK" --pipe "$WORK/plain" -o "$WORK/a.sqsh"
  [[ $RC -eq 3 ]]
  grep -q "is running" <<<"$OUT"

  FIRST_RC=0
  wait "$START_PID" || FIRST_RC=$?
  [[ $FIRST_RC -eq 0 ]]
}

@test "a mount refuses while an extraction of the same archive is running" {
  new_archive
  stub_slow_emitters
  mount_model_fuse "$WORK/mark"
  use_stub_dir

  start "$WORK" unsquish.sh --pipe "$WORK/a.sqsh" -o "$WORK/out1"
  wait_for_lock

  run_squish_in "$WORK" --pipe -m "$WORK/a.sqsh"
  [[ $RC -eq 3 ]]
  grep -q "is running" <<<"$OUT"
  [[ $(count_trackers) -eq 0 ]]

  FIRST_RC=0
  wait "$START_PID" || FIRST_RC=$?
  [[ $FIRST_RC -eq 0 ]]
}

@test "the lock is gone once a run finishes, so the next extraction proceeds" {
  new_archive
  stub_progress_emitters
  use_stub_dir

  run_unsquish_in "$WORK" --pipe "$WORK/a.sqsh" -o "$WORK/out1"
  [[ $RC -eq 0 ]]
  [[ $(lock_entries) -eq 0 ]]

  run_unsquish_in "$WORK" --pipe "$WORK/a.sqsh" -o "$WORK/out2"
  [[ $RC -eq 0 ]]
}

@test "a lock left by a killed run is reclaimed by the next run" {
  new_archive
  stub_slow_emitters
  use_stub_dir

  start "$WORK" unsquish.sh --pipe "$WORK/a.sqsh" -o "$WORK/out1"
  wait_for_lock
  kill -KILL "$START_PID"
  wait "$START_PID" 2>/dev/null || true

  [[ $(lock_entries) -gt 0 ]] # the kill left a stale lock behind

  run_unsquish_in "$WORK" --pipe "$WORK/a.sqsh" -o "$WORK/out2"
  [[ $RC -eq 0 ]]
}

@test "--cancel stops the run that holds the lock" {
  new_archive
  stub_slow_emitters
  use_stub_dir

  start "$WORK" unsquish.sh --pipe "$WORK/a.sqsh" -o "$WORK/out1"
  wait_for_lock

  run_unsquish_in "$WORK" --cancel "$WORK/a.sqsh"
  [[ $RC -eq 0 ]]
  grep -q "Cancelling" <<<"$OUT"

  FIRST_RC=0
  wait "$START_PID" || FIRST_RC=$?
  [[ $FIRST_RC -eq 2 ]]
  [[ ! -e $WORK/out1 ]]
  run ! grep -q 'end' "$RUNLOG" # the backend never reached its final line
  [[ $(lock_entries) -eq 0 ]]
}

@test "--cancel reports nothing to cancel" {
  new_archive
  run_unsquish_in "$WORK" --cancel "$WORK/a.sqsh"
  [[ $RC -eq 1 ]]
  grep -q "Nothing running" <<<"$OUT"
}
