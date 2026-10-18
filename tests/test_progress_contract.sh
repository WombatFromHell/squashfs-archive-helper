#!/usr/bin/env bash
# Pins the progress-line contract: squashfs-tools emitters -> yad/zenity gauge.
# The model emitter is checked against the real tools, then squish/unsquish run
# through run_with_dialog so the dialog receipt is asserted exactly.
set -uo pipefail

SRC="$(cd "$(dirname "$0")/../src" && pwd)"
fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "ok: $1"; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/stub" "$WORK/tree"
printf 'hello\n' >"$WORK/tree/a.txt"
: >"$WORK/receipt"
export RECEIPT="$WORK/receipt"

# Model of squashfs-tools progress output: bare integers on stdout, only when
# -percentage is given and -info is not (verified against the real tools below).
cat >"$WORK/stub/mksquashfs" <<'EOF'
#!/usr/bin/env bash
have_pct=0 have_info=0
for a in "$@"; do
  case "$a" in
    -percentage) have_pct=1 ;;
    -info) have_info=1 ;;
  esac
done
printf 'Parallel model emitter\nCreating filesystem.\n'
if [[ $have_pct -eq 1 && $have_info -eq 0 ]]; then printf '10\n50\n100\n'; fi
# An emitter that produces no archive would be a real error; model must write one.
[[ -e "$2" ]] || : >"$2"
exit 0
EOF
cat >"$WORK/stub/unsquashfs" <<'EOF'
#!/usr/bin/env bash
have_pct=0 have_info=0
for a in "$@"; do
  case "$a" in
    -percentage) have_pct=1 ;;
    -info) have_info=1 ;;
  esac
done
printf 'Parallel model extractor\n2 inodes to write\n'
if [[ $have_pct -eq 1 && $have_info -eq 0 ]]; then printf '100\n'; fi
exit 0
EOF
cat >"$WORK/stub/yad" <<'EOF'
#!/usr/bin/env bash
printf '@@dialog@@\n' >>"$RECEIPT"
while IFS= read -r line; do printf '%s\n' "$line" >>"$RECEIPT"; done
exit 0
EOF
chmod +x "$WORK/stub/mksquashfs" "$WORK/stub/unsquashfs" "$WORK/stub/yad"

#######################################
# 1. Model must agree with the real tools.
#######################################
count_ints() { grep -cE '^[0-9]+$' <<<"$1"; }
model_out() { "$WORK/stub/mksquashfs" "$WORK/tree" "$WORK/m.sqsh" -no-xattrs "$@" 2>/dev/null; }
real_out() { mksquashfs "$WORK/tree" "$WORK/r.sqsh" -no-xattrs "$@" 2>/dev/null; }
nonzero() {
  local flag
  for flag in "$@"; do [[ $flag == -info ]] && return 0; done
  for flag in "$@"; do [[ $flag == -percentage ]] && return 1; done
  return 0
}
compare_combo() {
  local model real
  model="$(model_out "$@")"
  real="$(real_out "$@")"
  if nonzero "$@"; then
    [[ $(count_ints "$model") -eq 0 && $(count_ints "$real") -eq 0 ]] ||
      fail "model and real both emitted integers for an -info/flagless combo: [$*]"
  else
    [[ $(count_ints "$model") -gt 0 && $(count_ints "$real") -gt 0 ]] ||
      fail "model and real disagree about percentage lines for [$*]"
  fi
}
compare_combo -percentage
compare_combo -progress -percentage
compare_combo -info -percentage
compare_combo -info -progress -percentage
compare_combo -info -progress
ok "emitter model matches squashfs-tools on all five flag combos"

#######################################
# 2. run_with_dialog plumbing, isolated.
#######################################
# shellcheck source=src/squish-common.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../src" && pwd)/squish-common.sh"
declare -i PIPE_MODE=0

dialog_blocks() { grep -c '@@dialog@@' "$RECEIPT"; }
first_block_ints() {
  awk '/^@@dialog@@$/{n++; next} n==1{print} n>1{exit}' "$RECEIPT" | grep -E '^[0-9]+$' | tr '\n' ' '
}

: >"$RECEIPT"
run_with_dialog "$WORK/stub/mksquashfs" "$WORK/tree" "$WORK/out.sqsh" -no-xattrs -percentage -- "$WORK/stub/yad" 2>"$WORK/err" ||
  fail "run_with_dialog lost the backend exit code"
[[ $(dialog_blocks) -eq 1 ]] || fail "dialog called $(dialog_blocks) times, expected 1"
[[ $(first_block_ints) == "10 50 100 " ]] ||
  fail "dialog did not receive 10 50 100 in order (got '$(first_block_ints)')"
grep -qE '^[0-9]+$' "$WORK/err" && fail "percentage line leaked to stderr"
grep -q 'model emitter' "$WORK/err" || fail "backend chatter not routed to stderr"
ok "run_with_dialog: numbers -> dialog, chatter -> stderr, no leakage"

cat >"$WORK/stub/failing" <<'EOF'
#!/usr/bin/env bash
printf 'Progress 7 done\n'
exit 7
EOF
chmod +x "$WORK/stub/failing"
run_with_dialog "$WORK/stub/failing" -- "$WORK/stub/yad" 2>/dev/null
[[ $? -eq 7 ]] || fail "backend exit code 7 not propagated"
ok "backend exit code propagates through the dialog"

cat >"$WORK/stub/cancelling" <<'EOF'
#!/usr/bin/env bash
exit 3
EOF
chmod +x "$WORK/stub/cancelling"
run_with_dialog "$WORK/stub/mksquashfs" x -- "$WORK/stub/cancelling" 2>/dev/null
[[ $? -eq 3 ]] || fail "dialog cancel exit code not propagated"
ok "dialog cancel exit code propagates"

#######################################
# 3. squish's own GUI compression must feed the gauge.
#######################################
export PATH="$WORK/stub:$PATH"
: >"$RECEIPT"
bash "$SRC/squish.sh" "$WORK/tree" -o "$WORK/e2e.sqsh" 2>"$WORK/e2e-err" >/dev/null ||
  fail "squish GUI compression failed"
grep -qE '^[0-9]+$' "$WORK/e2e-err" && fail "squish leaked percentage lines to stderr"
[[ $(first_block_ints) =~ [0-9] ]] ||
  fail "squish compression dialog received no percentage line (progress bar frozen)"
ok "squish GUI compression feeds its progress dialog"

#######################################
# 4. unsquish's own GUI extraction must feed the gauge.
#######################################
: >"$RECEIPT"
bash "$SRC/unsquish.sh" "$WORK/e2e.sqsh" -o "$WORK/e2e-out" 2>"$WORK/e2e-out-err" >/dev/null ||
  fail "unsquish GUI extraction failed"
grep -qE '^[0-9]+$' "$WORK/e2e-out-err" && fail "unsquish leaked percentage lines to stderr"
[[ $(first_block_ints) =~ [0-9] ]] ||
  fail "unsquish extraction dialog received no percentage line (progress bar frozen)"
ok "unsquish GUI extraction feeds its progress dialog"

echo "OK: $(basename "$0")"
