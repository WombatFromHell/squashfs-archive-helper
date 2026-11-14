#!/usr/bin/env bats
# Ctrl-C has to stop whatever tool the run is driving, whichever renderer answers it.
# The GUI paths run their child as a background job so the cancel trap can reach it;
# the cli path ran it in the foreground, where the trap only fires after the tool has
# already finished, and `set -m` gives that child its own process group.

# bats runs every test in its own subshell, so exporting a fixture variable is
# local to that test on purpose — the stub tools read it from the environment.
# shellcheck disable=SC2030,SC2031

# shellcheck source=tests/helpers.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/helpers.bash"
# shellcheck source=tests/stubs.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/stubs.bash"

export RUNLOG="$WORK/run.log"

cli_only_path() { # coreutils, no GUI: 'cli' is then the renderer the run really picks
  mkdir -p "$WORK/cli"
  local t path
  for t in bash realpath dirname basename awk sed head tail tr cut wc mktemp rm cat \
    grep kill date mkdir ln sleep stat sha256sum pgrep sort uniq touch find \
    chmod mkfifo readlink id; do
    path="$(command -v -- "$t")" || return 1
    ln -sf -- "$path" "$WORK/cli/$t"
  done
  export PATH="$WORK/stub:$WORK/cli"
}

start_run() { # $1 = script under SRC, rest = args; sets START_PID
  : >"$RUNLOG"
  : >"$WORK/run.out"
  # Monitor mode: without job control a background child inherits SIGINT ignored,
  # so its cancel trap could never fire and the test would not be Ctrl-C.
  set -m
  bash "$SRC/$1" "${@:2}" >"$WORK/run.out" 2>&1 &
  START_PID=$!
}

wait_for_backend() { # the run only becomes cancellable once its tool is in flight
  local attempts=100
  while ((attempts-- > 0)) && ! grep -q '^start' "$RUNLOG" 2>/dev/null; do sleep 0.05; done
  grep -q '^start' "$RUNLOG"
}

ctrl_c() { # aim a SIGINT at a running script the way a terminal does, record its code
  kill -INT "$1"
  RC=0
  wait "$1" || RC=$?
}

@test "Ctrl-C during a cli-rendered build stops mksquashfs and exits 2" {
  mkdir -p "$WORK/plain"
  printf 'hello\n' >"$WORK/plain/a.txt"
  stub_slow_emitters
  cli_only_path
  export SLEEP=4

  start_run squish.sh "$WORK/plain" -o "$WORK/new.sqsh"
  wait_for_backend
  ctrl_c "$START_PID"

  [[ $RC -eq 2 ]]
  run ! grep -q 'end' "$RUNLOG" # the backend never reached its final line
  [[ ! -e "$WORK/new.sqsh" ]]
  [[ $(find "$XDG_RUNTIME_DIR/squish-locks" -name pid | wc -l) -eq 0 ]]
}

@test "Ctrl-C during a yad-rendered build stops mksquashfs and exits 2" {
  mkdir -p "$WORK/plain"
  printf 'hello\n' >"$WORK/plain/a.txt"
  stub_slow_emitters
  stub_yad_hold
  use_stub_dir # 'yad' is on PATH, so this is the renderer the run really picks
  export SLEEP=4

  start_run squish.sh "$WORK/plain" -o "$WORK/new.sqsh"
  wait_for_backend
  ctrl_c "$START_PID"

  [[ $RC -eq 2 ]]
  run ! grep -q 'end' "$RUNLOG" # the backend never reached its final line
  [[ ! -e "$WORK/new.sqsh" ]]
  run ! pgrep -f "$WORK/stub/mksquashfs" >/dev/null # the tool is gone, not left to finish
  [[ $(find "$XDG_RUNTIME_DIR/squish-locks" -name pid | wc -l) -eq 0 ]]
}

@test "Ctrl-C during a cli-rendered extraction stops unsquashfs and exits 2" {
  printf 'archive content\n' >"$WORK/a.sqsh"
  sha256sum "$WORK/a.sqsh" | awk '{print $1 "  a.sqsh"}' >"$WORK/a.sqsh.sha256"
  stub_slow_emitters
  cli_only_path
  export SLEEP=4

  start_run unsquish.sh "$WORK/a.sqsh" -o "$WORK/out"
  wait_for_backend
  ctrl_c "$START_PID"

  [[ $RC -eq 2 ]]
  run ! grep -q 'end' "$RUNLOG" # the backend never reached its final line
  [[ ! -e "$WORK/out" ]]
  [[ $(find "$XDG_RUNTIME_DIR/squish-locks" -name pid | wc -l) -eq 0 ]]
}

stub_hash_slow() { # sha256sum model that holds, so a cancel lands inside the hash
  export SLOWHASH_SLEEP=3
  cat >"$WORK/stub/sha256sum" <<'SH'
#!/usr/bin/env bash
printf 'hash-start\n' >>"$RUNLOG"
sleep "${SLOWHASH_SLEEP:-3}"
printf '0000000000000000000000000000000000000000000000000000000000000000  %s\n' "${*: -1}"
SH
  chmod +x "$WORK/stub/sha256sum"
}

@test "Ctrl-C during a cli-rendered hash stops the hash and exits 2" {
  mkdir -p "$WORK/plain"
  printf 'hello\n' >"$WORK/plain/a.txt"
  stub_slow_emitters
  stub_pv_slow
  cli_only_path
  export SLEEP=0.2 SLOWPV_SLEEP=3

  start_run squish.sh "$WORK/plain" -o "$WORK/new.sqsh"
  # The compression model finishes at once, so the signal lands inside the hash.
  local attempts=100
  while ((attempts-- > 0)) && [[ ! -e "$WORK/new.sqsh" ]]; do sleep 0.05; done
  [[ -e "$WORK/new.sqsh" ]]
  cancel_started=$SECONDS
  ctrl_c "$START_PID"

  [[ $RC -eq 2 ]]
  # The hash model holds for 3s: a run that waited for it did not cancel.
  ((SECONDS - cancel_started < SLOWPV_SLEEP))
  [[ ! -e "$WORK/new.sqsh.sha256" ]]
  [[ -e "$WORK/new.sqsh" ]] # the completed archive is kept; only the run stopped
  run ! pgrep -f "$WORK/stub/pv" >/dev/null
  [[ $(find "$XDG_RUNTIME_DIR/squish-locks" -name pid | wc -l) -eq 0 ]]
}

@test "Ctrl-C during a hash with no pv stops the hash and exits 2" {
  printf 'archive content\n' >"$WORK/a.sqsh"
  sha256sum "$WORK/a.sqsh" | awk '{print $1 "  a.sqsh"}' >"$WORK/a.sqsh.sha256"
  stub_hash_slow
  cli_only_path # no pv in this PATH, so the hash is a plain sha256sum

  start_run squish.sh --check "$WORK/a.sqsh"
  local attempts=100
  while ((attempts-- > 0)) && ! grep -q 'hash-start' "$RUNLOG" 2>/dev/null; do sleep 0.05; done
  grep -q 'hash-start' "$RUNLOG"
  cancel_started=$SECONDS
  ctrl_c "$START_PID"

  [[ $RC -eq 2 ]]
  # The hash model holds for 3s: a run that waited for it did not cancel.
  ((SECONDS - cancel_started < SLOWHASH_SLEEP))
  grep -q 'cancelled' "$WORK/run.out"
  run ! pgrep -f "$WORK/stub/sha256sum" >/dev/null
}
