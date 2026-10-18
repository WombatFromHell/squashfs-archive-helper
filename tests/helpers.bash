# shellcheck shell=bash
# Sourced by every tests/*.bats file. bats gives errexit per test, but no
# scratch area: this resolves ../src from the test file and hands out a temp
# directory that bats removes when the run finishes (BATS_RUN_TMPDIR). bats
# runs the file's top level once per test, so every test gets its own WORK.
# The suites that drive squish.sh share this layout and the squish runner.
# shellcheck disable=SC2034
SRC="$(cd -- "$(dirname -- "${BATS_TEST_FILENAME:?set}")/../src" && pwd)"
WORK="$(mktemp -d "${BATS_RUN_TMPDIR:?set}/XXXXXX")"
mkdir -p "$WORK/stub" "$WORK/data" "$WORK/run"
export XDG_RUNTIME_DIR="$WORK/run"

run_script() { # $1 = working dir the script runs in, $2 = script name under SRC,
  # rest = arguments; sets OUT (stderr+stdout) and RC. Name inference reads the
  # working directory, so tests state it explicitly; mount placement does not.
  local dir="$1" script="$2"
  shift 2
  RC=0
  OUT="$(cd "$dir" && bash "$SRC/$script" "$@" 2>&1)" || RC=$?
}

run_squish_in() {
  local dir="$1"
  shift
  run_script "$dir" squish.sh "$@"
}
run_unsquish_in() {
  local dir="$1"
  shift
  run_script "$dir" unsquish.sh "$@"
}
run_squish() { run_squish_in "$WORK/data" "$@"; }

count_trackers() { find "$XDG_RUNTIME_DIR" -maxdepth 1 -name '*.[0-9][0-9].mounted' | wc -l; }
