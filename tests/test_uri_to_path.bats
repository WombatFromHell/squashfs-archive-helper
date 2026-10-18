#!/usr/bin/env bats
# Assert uri_to_path() in src/squish-common.sh against KIO file:// URIs.

source "$(dirname -- "${BATS_TEST_FILENAME:?set}")/helpers.bash"
source "$SRC/squish-common.sh"

# log() in the sourced file reads PIPE_MODE; shellcheck cannot see across files.
# shellcheck disable=SC2034
PIPE_MODE=0

@test "leaves a plain local path alone" {
  [[ "$(uri_to_path "/plain/local/path")" == "/plain/local/path" ]]
}

@test "leaves a relative non-uri alone" {
  [[ "$(uri_to_path "relative/path/no%20uri")" == "relative/path/no%20uri" ]]
}

@test "strips the file scheme and keeps spaces" {
  [[ "$(uri_to_path "file:///home/user/my docs/data.txt")" == "/home/user/my docs/data.txt" ]]
}

@test "decodes percent escapes" {
  [[ "$(uri_to_path "file:///home/user/100%25%20percent")" == "/home/user/100% percent" ]]
}

@test "decodes an encoded slash" {
  [[ "$(uri_to_path "file:///home/user/UPPER%2Fcase")" == "/home/user/UPPER/case" ]]
}
