#!/usr/bin/env bash
# Integration self-check for the mount/unmount/tracker subsystem.
# The FUSE tools are stubbed on PATH: no real filesystem is mounted, a marker
# file models "is this path mounted", so the tracker bookkeeping is what gets
# asserted.
set -uo pipefail

SRC="$(cd "$(dirname "$0")/../src" && pwd)"
fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "ok: $1"; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/stub" "$WORK/data/src" "$WORK/run" "$WORK/marks"
printf 'hello\n' >"$WORK/data/src/a.txt"
mksquashfs "$WORK/data/src" "$WORK/data/one.sqsh" -no-xattrs >/dev/null 2>&1
( cd "$WORK/data" && sha256sum one.sqsh ) >"$WORK/data/one.sqsh.sha256"

# Model of the mount state: squashfuse marks the path, unmount clears it,
# mountpoint reports it. Mount paths contain slashes, so keys are sanitised.
keyed() { local p="$1"; printf '%s' "${p//\//_}"; }
cat >"$WORK/stub/squashfuse" <<EOF
#!/usr/bin/env bash
mp="\${@: -1}"
: >"\$MARKS/\$(printf '%s' "\${mp//\//_}")"
exit 0
EOF
cat >"$WORK/stub/umount" <<EOF
#!/usr/bin/env bash
mp="\${@: -1}"
rm -f "\$MARKS/\$(printf '%s' "\${mp//\//_}")" 2>/dev/null
exit 0
EOF
cat >"$WORK/stub/fusermount" <<EOF
#!/usr/bin/env bash
mp="\${@: -1}"
rm -f "\$MARKS/\$(printf '%s' "\${mp//\//_}")" 2>/dev/null
exit 0
EOF
cat >"$WORK/stub/mountpoint" <<EOF
#!/usr/bin/env bash
mp="\${@: -1}"
[[ -e "\$MARKS/\$(printf '%s' "\${mp//\//_}")" ]]
EOF
cat >"$WORK/stub/yad" <<'EOF'
#!/usr/bin/env bash
cat >/dev/null
exit 0
EOF
for tool in squashfuse umount fusermount mountpoint yad; do
  chmod +x "$WORK/stub/$tool"
done
export MARKS="$WORK/marks"
export PATH="$WORK/stub:$PATH"
export XDG_RUNTIME_DIR="$WORK/run"

tracker_dir="$XDG_RUNTIME_DIR"
mounts_dir="$WORK/data/squish-mounts"
mounted_marker() { printf '%s' "${1//\//_}"; }
count_trackers() { find "$tracker_dir" -maxdepth 1 -name '*.[0-9][0-9].mounted' | wc -l; }

#######################################
# 1. Mount writes a tracker and creates a mountpoint.
#######################################
( cd "$WORK/data" && bash "$SRC/squish.sh" -m one.sqsh ) >"$WORK/m1.log" 2>&1 ||
  fail "mount failed: $(tail -3 "$WORK/m1.log")"
grep -q 'Mounted successfully' "$WORK/m1.log" || fail "mount did not report success"
[[ $(count_trackers) -eq 1 ]] || fail "tracker count is $(count_trackers), expected 1"
tracker="$(find "$tracker_dir" -maxdepth 1 -name '*.[0-9][0-9].mounted')"
[[ $(head -n1 "$tracker") == "$mounts_dir/one.01.mounted" ]] || fail "tracker line 1 is not the mountpoint"
[[ $(tail -n1 "$tracker") == "$WORK/data/one.sqsh" ]] || fail "tracker line 2 is not the archive"
[[ -d "$mounts_dir/one.01.mounted" ]] || fail "mountpoint directory not created"
[[ -e "$WORK/marks/$(mounted_marker "$mounts_dir/one.01.mounted")" ]] ||
  fail "squashfuse did not mark the path as mounted"
ok "mount: tracker written, mountpoint created, marked mounted"

#######################################
# 2. Mounting twice refuses while the mount is live.
#######################################
( cd "$WORK/data" && bash "$SRC/squish.sh" -m one.sqsh ) >"$WORK/m2.log" 2>&1 &&
  fail "double mount accepted (should refuse)"
grep -qi 'already mounted' "$WORK/m2.log" || fail "double mount did not say already mounted"
[[ $(count_trackers) -eq 1 ]] || fail "double mount leaked a tracker"
ok "double mount refused, no tracker leak"

#######################################
# 3. Unmount clears tracker, mountpoint, and mount state.
#######################################
( cd "$WORK/data" && bash "$SRC/squish.sh" -u one.sqsh ) >"$WORK/u1.log" 2>&1 ||
  fail "unmount by archive failed: $(tail -3 "$WORK/u1.log")"
grep -q 'Unmounted successfully' "$WORK/u1.log" || fail "unmount did not report success"
[[ $(count_trackers) -eq 0 ]] || fail "tracker still present after unmount"
[[ ! -d "$mounts_dir" ]] || fail "mountpoint tree left behind"
[[ ! -e "$WORK/marks/$(mounted_marker "$mounts_dir/one.01.mounted")" ]] ||
  fail "mount state not cleared"
ok "unmount by archive: tracker, mountpoint, and mount state cleared"

#######################################
# 4. --list-mounts reports archive -> mountpoint pairs.
#######################################
( cd "$WORK/data" && bash "$SRC/squish.sh" -m one.sqsh ) >/dev/null 2>&1 ||
  fail "remount for the list case failed"
bash "$SRC/squish.sh" --list-mounts >"$WORK/l1.log" 2>&1 ||
  fail "--list-mounts failed: $(tail -3 "$WORK/l1.log")"
grep -qF "$WORK/data/one.sqsh -> $mounts_dir/one.01.mounted" "$WORK/l1.log" ||
  fail "--list-mounts did not print the archive -> mountpoint pair"
ok "--list-mounts prints the pair"

#######################################
# 5. A tracker whose mount died is stale; --force cleans and remounts.
#######################################
rm -f "$WORK/marks/$(mounted_marker "$mounts_dir/one.01.mounted")"
( cd "$WORK/data" && bash "$SRC/squish.sh" -m one.sqsh ) >"$WORK/m3.log" 2>&1 &&
  fail "mount refused a stale tracker without --force"
grep -qi 'already mounted' "$WORK/m3.log" ||
  fail "stale tracker not reported without --force: $(tail -3 "$WORK/m3.log")"
( cd "$WORK/data" && bash "$SRC/squish.sh" -m --force one.sqsh ) >"$WORK/m4.log" 2>&1 ||
  fail "--force mount failed: $(tail -3 "$WORK/m4.log")"
grep -qi 'stale tracker' "$WORK/m4.log" || fail "--force did not report stale tracker removal"
[[ $(count_trackers) -eq 1 ]] || fail "--force left $(count_trackers) trackers"
[[ -d "$mounts_dir/one.01.mounted" ]] || fail "--force did not recreate the mountpoint"
ok "--force drops the stale tracker and mounts again"

#######################################
# 6. Unmount by the mountpoint path itself.
#######################################
( cd "$WORK/data" && bash "$SRC/squish.sh" -u "$mounts_dir/one.01.mounted" ) >"$WORK/u2.log" 2>&1 ||
  fail "unmount by mountpoint failed: $(tail -3 "$WORK/u2.log")"
grep -qi 'Unmounted successfully' "$WORK/u2.log" || fail "unmount by mountpoint did not report success"
[[ $(count_trackers) -eq 0 ]] || fail "tracker left after unmount by mountpoint"
ok "unmount by mountpoint path"

#######################################
# 7. -y mounts an archive with no checksum file.
#######################################
rm -f "$WORK/data/one.sqsh.sha256"
( cd "$WORK/data" && bash "$SRC/squish.sh" -y -m one.sqsh ) >"$WORK/y1.log" 2>&1 ||
  fail "mount with -y and no checksum failed: $(tail -3 "$WORK/y1.log")"
grep -qi 'verification skipped' "$WORK/y1.log" || fail "-y did not report skipped verification"
[[ $(count_trackers) -eq 1 ]] || fail "-y mount left no tracker"
ok "-y mounts an unchecksummed archive"

#######################################
# 8. A checksum mismatch blocks the mount.
#######################################
( cd "$WORK/data" && bash "$SRC/squish.sh" -u one.sqsh ) >/dev/null 2>&1 ||
  fail "cleanup unmount before the mismatch case failed"
printf 'deadbeef  one.sqsh\n' >"$WORK/data/one.sqsh.sha256"
( cd "$WORK/data" && bash "$SRC/squish.sh" -m one.sqsh ) >"$WORK/v1.log" 2>&1 &&
  fail "mount accepted an archive whose checksum mismatched"
grep -qi 'FAILED' "$WORK/v1.log" || fail "mismatch did not report FAILED"
[[ $(count_trackers) -eq 0 ]] || fail "mismatched mount leaked a tracker"
ok "checksum mismatch blocks mount, no tracker leak"

#######################################
# 9. One stem cannot use more than 99 tracker slots.
#######################################
mksquashfs "$WORK/data/src" "$WORK/data/packed.sqsh" -no-xattrs >/dev/null 2>&1
for n in $(seq -f '%02g' 1 99); do : >"$tracker_dir/packed.${n}.mounted"; done
( cd "$WORK/data" && bash "$SRC/squish.sh" -m packed.sqsh ) >"$WORK/full.log" 2>&1 &&
  fail "mount with 99 tracker slots succeeded"
grep -qi '99 tracker slots' "$WORK/full.log" || fail "exhaustion message missing"
ok "99 slots for a stem is refused with a clear message"

#######################################
# 10. Two trackers claiming one mountpoint is corrupt state.
#######################################
( cd "$WORK/data" && sha256sum one.sqsh ) >"$WORK/data/one.sqsh.sha256"
( cd "$WORK/data" && bash "$SRC/squish.sh" -m one.sqsh ) >/dev/null 2>&1 ||
  fail "mount for the corrupt-state case failed"
: >"$tracker_dir/duplicate.02.mounted"
printf '%s\n%s\n' "$mounts_dir/one.01.mounted" "$WORK/data/other.sqsh" >>"$tracker_dir/duplicate.02.mounted"
( cd "$WORK/data" && bash "$SRC/squish.sh" -u "$mounts_dir/one.01.mounted" ) >"$WORK/corrupt.log" 2>&1 &&
  fail "corrupt tracker state was accepted"
grep -qi 'corrupt tracker state' "$WORK/corrupt.log" ||
  fail "corrupt tracker state not reported: $(tail -5 "$WORK/corrupt.log")"
ok "duplicate mountpoint trackers report corrupt state and refuse"

echo "OK: $(basename "$0")"
