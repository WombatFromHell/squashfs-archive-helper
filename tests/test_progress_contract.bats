#!/usr/bin/env bats
# Pins the progress-line contract: squashfs-tools emitters -> yad/zenity gauge.
# The model emitter is checked against the real tools, then squish/unsquish run
# through run_with_dialog so the dialog receipt is asserted exactly.

# shellcheck source=tests/helpers.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/helpers.bash"
# shellcheck source=tests/stubs.bash
source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/stubs.bash"

mkdir -p "$WORK/tree"
printf 'hello\n' >"$WORK/tree/a.txt"
: >"$WORK/receipt"
export RECEIPT="$WORK/receipt"
stub_progress_emitters
stub_yad_receipt

# shellcheck source=src/squish-common.sh
source "$SRC/squish-common.sh"

# log() in the sourced file reads PIPE_MODE; shellcheck cannot see across files.
# shellcheck disable=SC2034
PIPE_MODE=0

count_ints() { grep -cE '^[0-9]+$' <<<"$1"; }
model_out() { "$WORK/stub/mksquashfs" "$WORK/tree" "$WORK/m.sqsh" -no-xattrs "$@" 2>/dev/null; }
real_out() { mksquashfs "$WORK/tree" "$WORK/r.sqsh" -no-xattrs "$@" 2>/dev/null; }
nonzero() { # true when the emitter model must print percentage lines
  local flag
  for flag in "$@"; do
    [[ $flag == -info ]] && return 0
  done
  for flag in "$@"; do
    [[ $flag == -percentage ]] && return 1
  done
  return 0
}

compare_combo() { # model and real emitters must agree on bare-integer lines
  local model real
  model="$(model_out "$@")"
  real="$(real_out "$@")"
  if nonzero "$@"; then
    if [[ $(count_ints "$model") -ne 0 || $(count_ints "$real") -ne 0 ]]; then
      printf 'both emitted integers for an -info/flagless combo: [%s]\n' "$*"
      return 1
    fi
  else
    if [[ $(count_ints "$model") -eq 0 || $(count_ints "$real") -eq 0 ]]; then
      printf 'model and real disagree about percentage lines for [%s]\n' "$*"
      return 1
    fi
  fi
}

@test "model matches real mksquashfs on -percentage" {
  compare_combo -percentage
}

@test "model matches real mksquashfs on -progress -percentage" {
  compare_combo -progress -percentage
}

@test "model matches real mksquashfs on -info -percentage" {
  compare_combo -info -percentage
}

@test "model matches real mksquashfs on -info -progress -percentage" {
  compare_combo -info -progress -percentage
}

@test "model matches real mksquashfs on -info -progress" {
  compare_combo -info -progress
}

dialog_blocks() { grep -c '@@dialog@@' "$RECEIPT"; }
first_block_ints() {
  awk '/^@@dialog@@$/{n++; next} n==1{print} n>1{exit}' "$RECEIPT" | grep -E '^[0-9]+$' | tr '\n' ' '
}

@test "run_with_dialog sends percentages to the dialog and chatter to stderr" {
  : >"$RECEIPT"
  run_with_dialog "$WORK/stub/mksquashfs" "$WORK/tree" "$WORK/out.sqsh" -no-xattrs -percentage -- "$WORK/stub/yad" --progress 2>"$WORK/err"
  [[ $(dialog_blocks) -eq 1 ]]
  [[ $(first_block_ints) == "10 50 100 " ]]
  run ! grep -qE '^[0-9]+$' "$WORK/err"
  grep -q 'model emitter' "$WORK/err"
}

@test "the backend exit code reaches the caller through the dialog" {
  cat >"$WORK/stub/failing" <<'EOF'
#!/usr/bin/env bash
printf 'Progress 7 done\n'
exit 7
EOF
  chmod +x "$WORK/stub/failing"
  RC=0
  run_with_dialog "$WORK/stub/failing" -- "$WORK/stub/yad" 2>/dev/null || RC=$?
  [[ $RC -eq 7 ]]
}

@test "a dismissed dialog cancels the build: exit 2, and the tool dies with it" {
  export RUNLOG="$WORK/run.log"
  # squish.sh runs under `set -m`; without monitor mode bash hands a background job no
  # process group of its own, so the cancel kill would hit nothing.
  set -m
  for code in 0 1 252; do # dialog gone mid-build: a WM close answering 0, Cancel, or Esc
    stub_slow_emitters    # the model holds, and writes 'end' only if it runs to completion
    cat >"$WORK/stub/dismissing" <<DIALOG
#!/usr/bin/env bash
read -r line # like the real dialog: it waits for progress, then the user closes it
exit $code
DIALOG
    chmod +x "$WORK/stub/dismissing"
    RC=0
    run_with_dialog "$WORK/stub/mksquashfs" "$WORK/tree" "$WORK/x.sqsh" -- "$WORK/stub/dismissing" 2>/dev/null || RC=$?
    [[ $RC -eq 2 ]]
    grep -q '^start' "$RUNLOG"
    run ! grep -q '^end' "$RUNLOG"                    # the backend never reached its final line
    run ! pgrep -f "$WORK/stub/mksquashfs" >/dev/null # the tool is gone, not left to finish
  done
}

@test "a failing backend still reports its own code after the dialog closes" {
  cat >"$WORK/stub/failing" <<'EOF'
#!/usr/bin/env bash
printf 'Progress 7 done\n'
exit 7
EOF
  cat >"$WORK/stub/closed" <<'EOF'
#!/usr/bin/env bash
exit 1 # yad's Cancel button, pressed after the tool died
EOF
  chmod +x "$WORK/stub/failing" "$WORK/stub/closed"
  RC=0
  run_with_dialog "$WORK/stub/failing" -- "$WORK/stub/closed" 2>/dev/null || RC=$?
  [[ $RC -eq 7 ]]
}

@test "squish GUI compression feeds its progress dialog" {
  use_stub_dir
  : >"$RECEIPT"
  bash "$SRC/squish.sh" "$WORK/tree" -o "$WORK/e2e.sqsh" 2>"$WORK/e2e-err" >/dev/null
  run ! grep -qE '^[0-9]+$' "$WORK/e2e-err"
  [[ $(first_block_ints) =~ [0-9] ]]
}

@test "unsquish GUI extraction feeds its progress dialog" {
  use_stub_dir
  bash "$SRC/squish.sh" "$WORK/tree" -o "$WORK/e2e.sqsh" >/dev/null 2>&1
  : >"$RECEIPT"
  bash "$SRC/unsquish.sh" "$WORK/e2e.sqsh" -o "$WORK/e2e-out" 2>"$WORK/e2e-out-err" >/dev/null
  run ! grep -qE '^[0-9]+$' "$WORK/e2e-out-err"
  [[ $(first_block_ints) =~ [0-9] ]]
}

# The percentages must arrive as they are produced, not all at the end: a buffered
# stage in the chain would leave the gauge frozen at 0% for the whole build.
@test "percentages reach the dialog while the backend is still working" {
  export RUN_END="$WORK/end" RECORD="$WORK/rec"
  cat >"$WORK/stub/slow" <<'EOF'
#!/usr/bin/env bash
printf '10\n'; sleep 0.4
printf '50\n'; sleep 0.4
printf '100\n'
date +%s.%N >"$RUN_END"
EOF
  cat >"$WORK/stub/timed" <<'EOF'
#!/usr/bin/env bash
while IFS= read -r line; do printf '%s %s\n' "$(date +%s.%N)" "$line"; done >"$RECORD"
EOF
  chmod +x "$WORK/stub/slow" "$WORK/stub/timed"

  run_with_dialog "$WORK/stub/slow" -- "$WORK/stub/timed" 2>/dev/null

  awk -v end_file="$WORK/end" '
    FNR == 1 { getline end < end_file }
    $2 == 50 { mid = $1 }
    END { exit (mid != "" && mid <= end - 0.3) ? 0 : 1 }
  ' "$RECORD"
}
