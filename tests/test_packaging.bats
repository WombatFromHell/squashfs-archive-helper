# The packaged scripts must report the Makefile's version, not the source's "dev".

setup() {
  bats_require_minimum_version 1.5.0
  SRC="$(cd -- "$(dirname -- "${BATS_TEST_FILENAME:?set}")/../src" && pwd)"
  WORK="$(mktemp -d "${BATS_RUN_TMPDIR:?set}/XXXXXX")"
  stage="$WORK/build"
  mkdir -p "$stage"
  # Everything `make build` installs, staged so the repo's own dist/ is untouched.
  cp "$SRC/../Makefile" "$SRC/../LICENSE" "$SRC/../README.md" "$stage/"
  cp -R "$SRC" "$SRC/../assets" "$SRC/../squish.yazi" "$stage/"
  version="$(sed -n 's/^VERSION = //p' "$stage/Makefile")"
}

@test "make build stamps the Makefile version into the packaged scripts" {
  run make -C "$stage" build
  [[ $RC -eq 0 ]]

  local dist="$stage/dist/squashfs-archive-helper"
  for script in squish.sh unsquish.sh; do
    grep -q "^declare -r VERSION=\"$version\"\$" "$dist/$script"
    run ! grep -q 'VERSION="dev"' "$dist/$script"
  done
}
