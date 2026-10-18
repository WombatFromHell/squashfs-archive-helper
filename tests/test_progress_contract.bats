#!/usr/bin/env bats
# Pins the progress-line contract: squashfs-tools emitters -> yad/zenity gauge.
# The model emitter is checked against the real tools, then squish/unsquish run
# through run_with_dialog so the dialog receipt is asserted exactly.

source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/helpers.bash"
# shellcheck source=./stubs.bash
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
  ! grep -qE '^[0-9]+$' "$WORK/err"
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

@test "a cancelled dialog reports its own exit code" {
  cat >"$WORK/stub/cancelling" <<'EOF'
#!/usr/bin/env bash
exit 3
EOF
  chmod +x "$WORK/stub/cancelling"
  RC=0
  run_with_dialog "$WORK/stub/mksquashfs" x -- "$WORK/stub/cancelling" 2>/dev/null || RC=$?
  [[ $RC -eq 3 ]]
}

@test "squish GUI compression feeds its progress dialog" {
  use_stub_dir
  : >"$RECEIPT"
  bash "$SRC/squish.sh" "$WORK/tree" -o "$WORK/e2e.sqsh" 2>"$WORK/e2e-err" >/dev/null
  ! grep -qE '^[0-9]+$' "$WORK/e2e-err"
  [[ $(first_block_ints) =~ [0-9] ]]
}

@test "unsquish GUI extraction feeds its progress dialog" {
  use_stub_dir
  bash "$SRC/squish.sh" "$WORK/tree" -o "$WORK/e2e.sqsh" >/dev/null 2>&1
  : >"$RECEIPT"
  bash "$SRC/unsquish.sh" "$WORK/e2e.sqsh" -o "$WORK/e2e-out" 2>"$WORK/e2e-out-err" >/dev/null
  ! grep -qE '^[0-9]+$' "$WORK/e2e-out-err"
  [[ $(first_block_ints) =~ [0-9] ]]
}
