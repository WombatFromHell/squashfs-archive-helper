#!/usr/bin/env bash
# Assert-based self-check for uri_to_path() in squish-common.sh.
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../src" && pwd)/squish-common.sh"
declare -i PIPE_MODE=0

fail() {
  printf 'FAIL: uri_to_path(%q) = %q, expected %q\n' "$1" "$2" "$3" >&2
  exit 1
}

check() {
  local got
  got="$(uri_to_path "$1")"
  [[ $got == "$2" ]] || fail "$1" "$got" "$2"
}

check "file:///home/user/my docs/data.txt" "/home/user/my docs/data.txt"
check "file:///home/user/100%25%20percent" "/home/user/100% percent"
check "file:///home/user/UPPER%2Fcase" "/home/user/UPPER/case"
check "/plain/local/path" "/plain/local/path"
check "relative/path/no%20uri" "relative/path/no%20uri"

echo "OK: $(basename "$0")"
