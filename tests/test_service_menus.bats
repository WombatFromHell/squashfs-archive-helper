#!/usr/bin/env bats
# The service menus are data, not code, but kio quietly drops an id listed in
# Actions whose [Desktop Action] group is missing, so the pairing is asserted.

assets_dir() { echo "$BATS_TEST_DIRNAME/../assets"; }

@test "every action id in Actions has a group with a Name and Exec" {
  for file in "$(assets_dir)"/squashfs-*-actions.desktop; do
    local ids id
    ids="$(grep '^Actions=' "$file" | cut -d= -f2 | tr ';' ' ')"
    for id in $ids; do
      grep -q "^\[Desktop Action $id\]$" "$file"
      grep -A3 "^\[Desktop Action $id\]$" "$file" | grep -q '^Name='
      grep -A3 "^\[Desktop Action $id\]$" "$file" | grep -q '^Exec='
    done
  done
}

@test "Squish menus sit at the top level, not nested inside Actions" {
  # kio's selectList() only routes a named submenu to the main menu when
  # X-KDE-Priority is TopLevel; otherwise it lands in the Actions submenu.
  for file in "$(assets_dir)"/squashfs-*-actions.desktop; do
    grep -q '^X-KDE-Submenu=Squish$' "$file"
    grep -q '^X-KDE-Priority=TopLevel$' "$file"
  done
}

@test "squashfs files expose Verify through squish --check" {
  local file
  file="$(assets_dir)/squashfs-file-actions.desktop"
  grep -q '^Actions=verify-squashfs;' "$file"
  grep -A3 '^\[Desktop Action verify-squashfs\]$' "$file" | grep -q '^Exec=squish --check %f$'
}
