#!/usr/bin/env bats
# The renderer decision and the one door that uses it. Nothing else in the run
# re-asks which GUI exists, so these assertions are the whole contract for
# resolve_renderer and show_progress.

source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/helpers.bash"
# shellcheck source=./stubs.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/stubs.bash"
# shellcheck source=src/squish-common.sh
source "$SRC/squish-common.sh"

# log() in the sourced file reads PIPE_MODE; shellcheck cannot see across files.
# shellcheck disable=SC2034
PIPE_MODE=0

stub_progress_emitters

emitter_args() {
  BACKEND_ARGS=("$WORK/stub/mksquashfs" "$WORK/tree" "$WORK/m.sqsh" -no-xattrs "$@")
}

@test "pipe mode outranks an available GUI" {
  PIPE_MODE=1
  stub_dialog_ready yad zenity
  use_stub_dir
  resolve_renderer
  [[ $RENDERER == pipe ]]
}

@test "yad outranks zenity when both are available" {
  PIPE_MODE=0
  stub_dialog_ready yad zenity
  use_stub_dir
  resolve_renderer
  [[ $RENDERER == yad ]]
}

@test "zenity is chosen when yad is absent" {
  PIPE_MODE=0
  stub_dialog_ready zenity
  PATH="$WORK/stub"
  resolve_renderer
  [[ $RENDERER == zenity ]]
}

@test "cli is chosen when neither GUI exists" {
  PIPE_MODE=0
  PATH="$WORK/stub"
  resolve_renderer
  [[ $RENDERER == cli ]]
}

@test "show_progress refuses to render without a resolved renderer" {
  PIPE_MODE=0
  local out
  # log error goes to stderr, and a run with no renderer must not reach the backend.
  out="$(show_progress 'SquashFS Archival' 'Compressing...' 2>&1 || :)"
  grep -q 'no progress path' <<<"$out"
  [[ $out != *Parallel* ]]
}

@test "pipe rendering prints the percentages and opens no dialog" {
  PIPE_MODE=1
  stub_dialog_ready yad
  stub_yad_receipt
  export RECEIPT="$WORK/receipt"
  : >"$RECEIPT"
  use_stub_dir
  resolve_renderer
  emitter_args -percentage
  local out
  out="$(show_progress 'SquashFS Archival' 'Compressing...')"
  grep -q '^100$' <<<"$out"
  ! grep -q 'Parallel model emitter' <<<"$out"
  [[ ! -s "$RECEIPT" ]]
}

@test "the yad gauge is fed the emitter percentages" {
  PIPE_MODE=0
  stub_yad_receipt
  export RECEIPT="$WORK/receipt"
  : >"$RECEIPT"
  use_stub_dir
  resolve_renderer
  emitter_args -progress -percentage
  show_progress "SquashFS Archival" "Compressing to m.sqsh..."
  grep -q '^100$' "$RECEIPT"
  ! grep -q 'Parallel model emitter' "$RECEIPT"
}
