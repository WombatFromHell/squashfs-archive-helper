#!/usr/bin/env bats
# Closing or cancelling the YAD hash dialog must not be reported as corruption.
# Asserts on the text handed to the dialog (what the user sees) and on what
# squish says on stderr. The stub yad records its argv, so the dialog text is
# inspectable; YAD_EXIT models the user closing the window.

source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/helpers.bash"
# shellcheck source=./stubs.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/stubs.bash"

export DIALOGLOG="$WORK/dialog-args.log"
stub_yad_argv
use_stub_dir

make_archives() { # clean pair plus the same pair with one byte appended.
  # This suite never opens an archive as SquashFS (mount is refused before
  # squashfuse runs), so the archive half is a plain file: hashing, copying and
  # tampering are what the assertions exercise.
  printf 'payload\n' >"$WORK/data/good.sqsh"
  ( cd "$WORK/data" && sha256sum good.sqsh ) >"$WORK/data/good.sqsh.sha256"
  cp "$WORK/data/good.sqsh" "$WORK/data/bad.sqsh"
  cp "$WORK/data/good.sqsh.sha256" "$WORK/data/bad.sqsh.sha256"
  printf 'tampered\n' >>"$WORK/data/bad.sqsh"
}

# bats runs the file top level once per test, so the fixture is declared here
# and every test gets its own fresh copy in its own WORK.
make_archives

dialog_says_failed() { grep -qi 'FAILED' "$DIALOGLOG"; }

@test "honest dialog verifies a clean archive" {
  export YAD_EXIT=0
  run_squish --check good.sqsh
  [[ $RC -eq 0 ]]
  [[ "$OUT" == *VERIFIED* ]]
}

@test "honest dialog reports FAILED for a corrupted archive" {
  export YAD_EXIT=0
  run_squish --check bad.sqsh
  dialog_says_failed
  [[ $RC -ne 0 ]]
}

@test "cancelled hash dialog reports cancellation, not corruption" {
  export YAD_EXIT=3
  : >"$DIALOGLOG"
  run_squish -m good.sqsh
  [[ $RC -ne 0 ]]
  ! dialog_says_failed
  grep -qi 'cancel' <<<"$OUT"
  [[ $(count_trackers) -eq 0 ]]
  [[ ! -e "$XDG_RUNTIME_DIR/squish-mounts/good.01.mounted" ]]
}

@test "check with a cancelled dialog is not reported as corruption" {
  export YAD_EXIT=3
  : >"$DIALOGLOG"
  run_squish --check good.sqsh
  ! dialog_says_failed
  [[ $RC -ne 0 ]]
}
