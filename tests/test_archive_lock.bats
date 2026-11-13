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

# A lock names a pid, and a pid number is not proof of who owns it.
@test "--cancel refuses a lock pid that is not a squish run" {
  new_archive
  plant_lock "$WORK/a.sqsh" "$$" # this bats shell: alive, and not a squish run

  run_unsquish_in "$WORK" --cancel "$WORK/a.sqsh"
  [[ $RC -eq 1 ]]
  grep -q "not a squish run" <<<"$OUT"
  run ! grep -q "Cancelling" <<<"$OUT"
  kill -0 "$$" # the planted process survived
}

# kill -0 fails on a live process owned by someone else (EPERM), so it cannot be
# the staleness test: another user's run must read as busy, not stale.
@test "a lock naming a live pid we cannot signal is busy, not stale" {
  new_archive
  plant_lock "$WORK/a.sqsh" 1 # systemd: alive, EPERM for us

  run_unsquish_in "$WORK" --pipe "$WORK/a.sqsh" -o "$WORK/out1"
  [[ $RC -eq 3 ]]
  grep -q "is running (pid 1)" <<<"$OUT"
  [[ ! -e $WORK/out1 ]]
}

# The desktop path runs its backend inside a pipeline, so cancel has to reach the
# tool there too, and the run must report 'cancelled' (2), not a SIGPIPE code.
@test "--cancel stops a GUI build and exits 2" {
  mkdir -p "$WORK/plain"
  printf 'hello\n' >"$WORK/plain/a.txt"
  stub_slow_emitters
  stub_yad_receipt
  use_stub_dir

  start "$WORK" squish.sh "$WORK/plain" -o "$WORK/new.sqsh"
  wait_for_lock

  run_unsquish_in "$WORK" --cancel "$WORK/new.sqsh"
  [[ $RC -eq 0 ]]
  grep -q "Cancelling" <<<"$OUT"

  FIRST_RC=0
  wait "$START_PID" || FIRST_RC=$?
  [[ $FIRST_RC -eq 2 ]]
  [[ ! -e $WORK/new.sqsh ]]
  run ! grep -q 'end' "$RUNLOG" # the backend never reached its final line
  [[ $(lock_entries) -eq 0 ]]
}

# A signal during the build's hash must not go on to report a finished build.
@test "--cancel during the build's hash exits 2" {
  mkdir -p "$WORK/plain"
  printf 'hello\n' >"$WORK/plain/a.txt"
  SLEEP=0.4 stub_slow_emitters
  SLOWPV_SLEEP=2 stub_pv_slow
  use_stub_dir

  start "$WORK" squish.sh --pipe "$WORK/plain" -o "$WORK/new.sqsh"
  # Wait for the compression to finish, so the signal lands inside the hash.
  attempts=100
  while ((attempts-- > 0)) && [[ ! -e $WORK/new.sqsh ]]; do sleep 0.05; done
  [[ -e $WORK/new.sqsh ]]

  run_squish_in "$WORK" --cancel "$WORK/new.sqsh"
  [[ $RC -eq 0 ]]

  FIRST_RC=0
  wait "$START_PID" || FIRST_RC=$?
  [[ $FIRST_RC -eq 2 ]]
  run ! grep -q "Successfully created" "$WORK/run.out"
  [[ ! -e "$WORK/new.sqsh.sha256" ]]
  [[ -e $WORK/new.sqsh ]] # the completed archive is kept; only the run stopped
}

# The lock covers a mount against a build, but the mount outlives the mount
# command, so the build has to ask about live trackers itself.
@test "a build refuses while its output archive is mounted" {
  new_archive
  mount_model_fuse "$WORK/mark"
  stub_mksquashfs_argv
  use_stub_dir

  run_squish_in "$WORK" --pipe -m "$WORK/a.sqsh"
  [[ $RC -eq 0 ]]
  [[ $(count_trackers) -eq 1 ]]

  run_squish_in "$WORK" --pipe "$WORK/plain" -o "$WORK/a.sqsh"
  [[ $RC -eq 1 ]]
  grep -q "mounted at" <<<"$OUT"
  grep -q "Unmount first" <<<"$OUT"
  [[ ! -e $MKLOG ]] # mksquashfs never ran
  [[ $(count_trackers) -eq 1 ]]
}
# A GUI hash is the same defect as a GUI build: a foreground dialog defers the cancel
# trap, and a background child ignores SIGTERM, so the hash runs to the end.
@test "--cancel during a GUI hash stops the hash" {
  mkdir -p "$WORK/plain"
  printf 'hello\n' >"$WORK/plain/a.txt"
  stub_progress_emitters
  stub_yad_receipt
  export SLOWPV_SLEEP=3
  stub_pv_slow
  export RECEIPT="$WORK/receipt"
  : >"$WORK/receipt"
  use_stub_dir

  start "$WORK" squish.sh "$WORK/plain" -o "$WORK/new.sqsh"
  # The compression model is instant, so the cancel lands inside the hash.
  attempts=100
  while ((attempts-- > 0)) && [[ ! -e $WORK/new.sqsh ]]; do sleep 0.05; done
  [[ -e $WORK/new.sqsh ]]

  cancel_started=$SECONDS
  run_squish_in "$WORK" --cancel "$WORK/new.sqsh"
  [[ $RC -eq 0 ]]

  FIRST_RC=0
  wait "$START_PID" || FIRST_RC=$?
  [[ $FIRST_RC -eq 2 ]]
  [[ ! -e "$WORK/new.sqsh.sha256" ]]
  # The hash model holds for 3s: a run that waited for it did not cancel.
  ((SECONDS - cancel_started < SLOWPV_SLEEP))
  run ! pgrep -f "$WORK/stub/pv" >/dev/null
}

# A keyboard cancel cannot name the output of a multi-item build (archive-<date>.sqsh, and
# archive-<date>-N.sqsh after a collision), so --cancel with no argument asks the lock root
# who is running. One run gets stopped; several are refused and named, never guessed.
@test "--cancel with no argument stops the single run in flight" {
  new_archive
  stub_slow_emitters
  use_stub_dir

  start "$WORK" unsquish.sh --pipe "$WORK/a.sqsh" -o "$WORK/out1"
  wait_for_lock

  run_unsquish_in "$WORK" --cancel
  [[ $RC -eq 0 ]]
  grep -q "Cancelling" <<<"$OUT"

  FIRST_RC=0
  wait "$START_PID" || FIRST_RC=$?
  [[ $FIRST_RC -eq 2 ]]
  [[ ! -e $WORK/out1 ]]
  [[ $(lock_entries) -eq 0 ]]
}

@test "--cancel with no argument reports nothing running" {
  run_unsquish_in "$WORK" --cancel
  [[ $RC -eq 1 ]]
  grep -q "Nothing running" <<<"$OUT"
}

@test "--cancel with no argument refuses to guess between two live runs" {
  new_archive
  cp "$WORK/a.sqsh" "$WORK/b.sqsh"
  cp "$WORK/a.sqsh.sha256" "$WORK/b.sqsh.sha256"
  stub_slow_emitters
  use_stub_dir

  start "$WORK" unsquish.sh --pipe "$WORK/a.sqsh" -o "$WORK/out1"
  wait_for_lock
  FIRST_PID=$START_PID
  start "$WORK" unsquish.sh --pipe "$WORK/b.sqsh" -o "$WORK/out2"
  attempts=100
  while ((attempts-- > 0)) && [[ $(lock_entries) -lt 2 ]]; do sleep 0.05; done
  [[ $(lock_entries) -eq 2 ]]

  run_unsquish_in "$WORK" --cancel
  [[ $RC -eq 1 ]]
  grep -q "operations are running" <<<"$OUT"
  grep -q "$WORK/a.sqsh" <<<"$OUT"
  grep -q "$WORK/b.sqsh" <<<"$OUT"
  run ! grep -q "Cancelling" <<<"$OUT"

  # Neither run was signalled: the refusal names them and leaves both alone.
  kill -0 "$FIRST_PID"
  kill -0 "$START_PID"
  kill -TERM "$FIRST_PID" "$START_PID"
  wait "$FIRST_PID" "$START_PID" 2>/dev/null || true
}

# Without a session runtime directory the fallback must be per-user: a shared
# /tmp root is owned by whoever creates it first, so every other user's lock,
# tracker and temp file would fail.
@test "the runtime fallback is per-user" {
  local root
  root="$(env -u XDG_RUNTIME_DIR bash -c "source '$SRC/squish-common.sh'; runtime_root")"
  [[ $root == "/tmp/squish-$(id -u)" ]]
}

# A lock root that cannot be created is not a busy archive. Pointing the runtime dir at a
# read-only directory (or one another user created first) currently falls through to the
# busy branch and tells the user to retry an operation nobody is holding, forever.
@test "an unwritable lock root fails instead of reporting busy" {
  mkdir -p "$WORK/plain"
  printf 'hello\n' >"$WORK/plain/a.txt"
  chmod 0500 "$WORK/run"
  run_squish_in "$WORK" --pipe "$WORK/plain" -o "$WORK/new.sqsh"
  chmod 0700 "$WORK/run"
  [[ $RC -eq 1 ]]
  [[ "$OUT" == *"Cannot create the lock directory"* ]]
  [[ "$OUT" != *"is starting"* ]]
  [[ ! -e "$WORK/run/squish-locks" ]]
  [[ ! -e "$WORK/new.sqsh" ]]
}

# The scratch dir holds the lock root; bats deletes the run tmpdir, so the mode must not
# stay read-only even when an assertion above fails.
teardown() {
  chmod 0700 "$WORK/run" 2>/dev/null || true
  # A failed assertion must not leave a run holding the runtime dir.
  local pid
  for pid in "${START_PID:-}" "${FIRST_PID:-}"; do
    [[ -n $pid ]] && kill -TERM "$pid" 2>/dev/null || true
  done
  return 0
}
