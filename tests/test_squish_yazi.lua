#!/usr/bin/env luajit
-- Self-check for squish.yazi/main.lua. Loads the plugin with stubbed yazi
-- globals and drives every entry action. build/extract run the REAL squish
-- scripts (no FUSE needed); mount/unmount/unmount-tracked run dry so command
-- strings are asserted without needing a real mount.

local script = arg[0] or "tests/test_squish_yazi.lua"
local tests_dir = script:match("(.*)/") or "."
do
  local h = io.popen("cd " .. tests_dir .. " && pwd")
  tests_dir = h:read("*l"); h:close()
end
local ROOT = tests_dir .. "/.."
local SRC = ROOT .. "/src"
local YAZI = ROOT .. "/squish.yazi"

local fails = 0
local function assert(cond, msg)
  if cond then
    print("ok: " .. msg)
  else
    print("FAIL: " .. msg)
    fails = fails + 1
  end
end

local function shquote(s)
  return "'" .. tostring(s):gsub("'", "'\\''") .. "'"
end

-- The suite runs the real scripts, which need a writable lock/tracker root. Inheriting the
-- caller's XDG_RUNTIME_DIR made `make test` pass in a login session and fail wherever that
-- directory is read-only (sandbox, CI, cron) — and the failure blamed a busy archive.
local RUNTIME = os.tmpname()
os.remove(RUNTIME)
os.execute("mkdir -p " .. shquote(RUNTIME))
local ENV_PREFIX = "XDG_RUNTIME_DIR=" .. shquote(RUNTIME) .. " "

-- ── yazi runtime stubs ───────────────────────────────────────────────────────
local NOTIFS = {}
local LEVELS = {}
local IDS = {}
local EMITS = {}
local DRY = false
local RECORDED = {}
local FAKE_POPEN
local FAKE_STATUS
local TICK = 0
-- The plugin's status throttle reads the clock; the suite supplies it so a burst of
-- lines can still produce one message per step.
os.time = function() return TICK end

ya = {
  sync = function(fn) return fn end,
  sleep = function() end,
  notify = function(t)
    NOTIFS[#NOTIFS + 1] = t.content
    LEVELS[#LEVELS + 1] = t.level
    IDS[#IDS + 1] = t.id
  end,
  emit = function(event) EMITS[#EMITS + 1] = event end,
  quote = shquote,
  input = function() return "/tmp/extract_pick_dir", 1 end,
  which = function() return 1 end,
}

fs = {
  cha = function(url)
    local s = tostring(url)
    if io.open(s) then return { is_dir = false } end
    if os.execute("test -d " .. shquote(s)) then return { is_dir = true } end
    return nil
  end,
}

Url = function(s)
  local parent = tostring(s):match("(.*)/[^/]*$") or "."
  return setmetatable({ url = s, parent = parent },
    { __tostring = function(self) return self.url end })
end

cx = { active = { selected = {}, current = { hovered = nil } } }

-- Command stub: mirrors yazi's `Command("sh"):arg({"-c", cmd})` — cmd is a
-- single argv element, so we run `sh -c '<cmd>'`. The plugin always passes
-- --pipe, so squish/unsquish never enter their YAD/Zenity GUI codepath.
local real_popen = io.popen
io.popen = function(cmd)
  if FAKE_POPEN then
    local lines, i = FAKE_POPEN, 0
    return {
      lines = function()
        return function()
          i = i + 1
          return lines[i]
        end
      end,
      close = function() end,
    }
  end
  return real_popen(cmd)
end

Command = setmetatable({}, {
  __call = function(_, name)
    local obj = { argv = { name } }
    function obj.arg(self, a)
      for _, v in ipairs(a) do self.argv[#self.argv + 1] = v end
      return self
    end
    function obj.stdout(self) return self end
    function obj.stderr(self) return self end
    function obj.spawn(self)
      local cmd
      for i, v in ipairs(self.argv) do
        if v == "-c" then cmd = self.argv[i + 1]; break end
      end
      cmd = cmd or table.concat(self.argv, " ")
      if FAKE_STATUS then
        -- A canned exit code, so a suite can assert how one code is reported.
        return {
          read_line = function() return nil, 2 end,
          wait = function() return { success = FAKE_STATUS == 0, code = FAKE_STATUS } end,
          wait_with_output = function()
            return { status = { success = FAKE_STATUS == 0, code = FAKE_STATUS }, stderr = "", stdout = "" }
          end,
        }
      end
      if DRY then
        RECORDED[#RECORDED + 1] = cmd
        return {
          read_line = function() return nil, 2 end,
          wait = function() return { success = true } end,
          wait_with_output = function()
            return { status = { success = true }, stderr = "", stdout = "" }
          end,
        }
      end
      local outf, errf, codef = os.tmpname(), os.tmpname(), os.tmpname()
      os.execute(ENV_PREFIX .. "sh -c " .. shquote(cmd)
        .. " > " .. shquote(outf) .. " 2> " .. shquote(errf)
        .. "; printf %d $? > " .. shquote(codef))
      local function rd(f)
        local h = io.open(f); if not h then return "" end
        local c = h:read("*a"); h:close(); os.remove(f); return c
      end
      local out, err, ec = rd(outf), rd(errf), tonumber(rd(codef)) or 1
      local q = {}
      -- yazi's read_line keeps the trailing newline; a matcher that anchors on `$`
      -- has to see the same shape the real plugin sees.
      for l in (out .. "\n"):gmatch("(.-)\n") do q[#q + 1] = { l .. "\n", 0 } end
      for l in (err .. "\n"):gmatch("(.-)\n") do q[#q + 1] = { l .. "\n", 1 } end
      q[#q + 1] = { "", 2 }
      local i = 0
      return {
        read_line = function()
          -- One second per line: the plugin throttles status messages to one per
          -- second, which a real run only reaches because progress is slow.
          i = i + 1
          TICK = TICK + 1
          local e = q[i]; if not e then return nil, 2 end
          return e[1], e[2]
        end,
        wait = function() return { success = ec == 0 } end,
        wait_with_output = function()
          return { status = { success = ec == 0 }, stderr = err, stdout = out }
        end,
      }
    end
    return obj
  end,
})
Command.PIPED = "PIPED"

-- ── load plugin ──────────────────────────────────────────────────────────────
local M = dofile(YAZI .. "/main.lua")
-- yazi hands setup(context, opts); opts must land in the second slot, or the
-- plugin keeps its defaults and the suite drives whatever `squish` is on PATH.
M.setup(nil, { squish_cmd = SRC .. "/squish.sh", unsquish_cmd = SRC .. "/unsquish.sh", timeout = 1 })

local function reset()
  NOTIFS, EMITS, RECORDED, LEVELS, IDS = {}, {}, {}, {}, {}
  cx.active.selected, cx.active.current.hovered = {}, nil
end
local function last_cmd() return RECORDED[#RECORDED] end
local function last_level() return LEVELS[#LEVELS] end
local function notif_has(sub)
  for _, c in ipairs(NOTIFS) do if c:find(sub, 1, true) then return true end end
  return false
end

-- ── build: single source ────────────────────────────────────────────────────
reset()
local d1 = os.tmpname(); os.remove(d1); os.execute("mkdir -p " .. shquote(d1))
local f = io.open(d1 .. "/x.txt", "w"); f:write("hi"); f:close()
cx.active.selected = { d1 }
M.entry(nil, { args = { "build" } })
assert(notif_has("Built"), "build (single) notifies success")
assert(fs.cha(d1 .. ".sqsh") ~= nil, "build (single) created <src>.sqsh")
assert(fs.cha(d1 .. ".sqsh.sha256") ~= nil, "build (single) created checksum")

-- ── build: multiple sources -> archive-YYYYMMDD.sqsh in parent ──────────────
reset()
local parent = os.tmpname(); os.remove(parent); os.execute("mkdir -p " .. shquote(parent))
local a = parent .. "/a"; local b = parent .. "/b"
os.execute("mkdir -p " .. shquote(a) .. " " .. shquote(b))
cx.active.selected = { a, b }
M.entry(nil, { args = { "build" } })
local arch = parent .. "/archive-" .. os.date("%Y%m%d") .. ".sqsh"
assert(fs.cha(arch) ~= nil, "build (multi) created archive-<date>.sqsh")
assert(notif_has("Built"), "build (multi) notifies success")

-- ── build: empty selection ──────────────────────────────────────────────────
reset()
cx.active.selected = {}
M.entry(nil, { args = { "build" } })
assert(notif_has("No item selected"), "build (empty) rejects with NO_SELECTION")

-- ── extract (default dir): uses the multi-build archive whose default
-- extract dir is free; extract-pick (below) covers an explicit path. ──────────
reset()
cx.active.current.hovered = { url = arch, name = "archive.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "extract" } })
assert(notif_has("Extracted successfully"), "extract notifies success")
assert(fs.cha(parent .. "/archive-" .. os.date("%Y%m%d") .. "/a") ~= nil,
  "extract produced expected file in default dir")

-- ── extract-pick: uses ya.input value as target ─────────────────────────────
reset()
os.execute("rm -rf /tmp/extract_pick_dir")
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "extract-pick" } })
local d1name = d1:match("([^/]+)$")
assert(fs.cha("/tmp/extract_pick_dir/" .. d1name .. "/x.txt") ~= nil, "extract-pick used input path")

-- ── mount / unmount: dry, assert generated command ─────────────────────────
DRY = true
reset()
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "mount" } })
assert(last_cmd():match("squish%.sh%s+%-%-pipe%s+%-m%s+'" .. d1 .. "%.sqsh'"), "mount command built as `squish --pipe -m <file>`")
assert(notif_has("Mounted successfully"), "mount notifies success")

reset()
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "unmount" } })
assert(last_cmd():match("squish%.sh%s+%-u%s+'" .. d1 .. "%.sqsh'"), "unmount command built as `squish -u <file>`")
DRY = false

-- ── non-.sqsh hovered for extract -> NEED_SQSH ──────────────────────────────
reset()
cx.active.current.hovered = { url = d1 .. "/x.txt", name = "x.txt", cha = { is_dir = false } }
M.entry(nil, { args = { "extract" } })
assert(notif_has("Select a .sqsh file"), "extract on non-sqsh rejects NEED_SQSH")

-- ── unmount-tracked: parse --list-mounts, build unmount for selection ───────
DRY = true
reset()
FAKE_POPEN = { "/home/u/archive.sqsh -> /tmp/squish-mounts/archive.01.mounted" }
M.entry(nil, { args = { "unmount-tracked" } })
assert(last_cmd():match("squish%.sh%s+%-u%s+'/home/u/archive%.sqsh'"),
  "unmount-tracked parses mounts and builds `squish -u <archive>`")
FAKE_POPEN = nil
DRY = false

-- ── jump: emits tab_create with mountpoint ─────────────────────────────────
reset()
FAKE_POPEN = { "/home/u/archive.sqsh -> /tmp/squish-mounts/archive.01.mounted" }
M.entry(nil, { args = { "jump" } })
assert(EMITS[#EMITS] == "tab_create", "jump emits tab_create")
FAKE_POPEN = nil

-- ── hash phase shows up, and a second phase restarts the counter ────────────
-- A fixture emitter stands in for squish/unsquish so the phase lines are exact:
-- hash 10/50/100, then extract 30/100. Without a per-phase reset, the extract
-- 30 would be suppressed by the hash run's last_pct.
local emitter = os.tmpname()
local ef = io.open(emitter, "w")
ef:write("#!/bin/sh\nprintf 'phase hash\n10\n50\n100\nphase extract\n30\n100\n'\n")
ef:close()
os.execute("chmod +x " .. shquote(emitter))
M.setup(nil, { squish_cmd = emitter, unsquish_cmd = emitter, timeout = 1 })

reset()
local d2 = os.tmpname(); os.remove(d2); os.execute("mkdir -p " .. shquote(d2))
cx.active.selected = { d2 }
M.entry(nil, { args = { "build" } })
assert(notif_has("Hashing: 40%"), "build shows hash progress")
assert(notif_has("Hashing: 100%"), "build shows hash completion")
assert(notif_has("Built"), "build (emitter) still notifies success")

reset()
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "extract" } })
assert(notif_has("Hashing: 40%"), "extract shows the verify-hash phase")
assert(notif_has("Extracting: 20%"), "extract restarts its counter after hashing")
assert(notif_has("Extracted successfully"), "extract (emitter) still notifies success")
local hash_at, extract_at = 0, 0
for i, c in ipairs(NOTIFS) do
  if c:find("Hashing", 1, true) and hash_at == 0 then hash_at = i end
  if c:find("Extracting", 1, true) and extract_at == 0 then extract_at = i end
end
assert(hash_at > 0 and hash_at < extract_at, "hash progress comes before extract progress")

reset()
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "mount" } })
assert(notif_has("Hashing: 40%"), "mount shows hash progress instead of a stray dialog")
assert(notif_has("Mounted successfully"), "mount (emitter) notifies success")

-- ── hash file phases reach the user ────────────────────────────────────────
-- The hash file is read before the hash in a verify and written after it in a build.
-- Neither step streams percentages, so a bare `phase` marker has to notify on its own.
local build_emitter = os.tmpname()
local bf = io.open(build_emitter, "w")
bf:write("#!/bin/sh\nprintf 'phase hash\\n10\\n50\\n100\\nphase hashfile-write\\n'\n")
bf:close()
os.execute("chmod +x " .. shquote(build_emitter))
local check_emitter = os.tmpname()
local cf = io.open(check_emitter, "w")
cf:write("#!/bin/sh\nprintf 'phase hashfile-read\\nphase hash\\n10\\n50\\n100\\n'\n")
cf:close()
os.execute("chmod +x " .. shquote(check_emitter))

M.setup(nil, { squish_cmd = build_emitter, unsquish_cmd = build_emitter, timeout = 1 })
reset()
cx.active.selected = { d2 }
M.entry(nil, { args = { "build" } })
assert(notif_has("Hashing: 100%"), "build (hash-file emitter) still reports hash progress")
assert(notif_has("Writing hash file"), "build reports the hash file being written")
local hash_at, write_at = 0, 0
for i, c in ipairs(NOTIFS) do
  if c:find("Hashing", 1, true) and hash_at == 0 then hash_at = i end
  if c:find("Writing hash file", 1, true) then write_at = i end
end
assert(hash_at > 0 and write_at > hash_at, "the hash file write is reported after the hash")
-- Same notification id overwrites: percentages would erase the hash-file message.
assert(IDS[write_at] ~= IDS[hash_at], "the hash file write gets its own notification")

M.setup(nil, { squish_cmd = check_emitter, unsquish_cmd = check_emitter, timeout = 1 })
reset()
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "verify" } })
assert(notif_has("Reading hash file"), "verify reports the hash file being read")
assert(notif_has("Hashing: 40%"), "verify streams hash progress instead of a silent wait")
assert(notif_has("Checksum verified"), "verify (emitter) notifies verified")
local read_at, vhash_at = 0, 0
for i, c in ipairs(NOTIFS) do
  if c:find("Reading hash file", 1, true) then read_at = i end
  if c:find("Hashing", 1, true) and vhash_at == 0 then vhash_at = i end
end
assert(read_at > 0 and read_at < vhash_at, "the hash file read is reported before the hash")
assert(IDS[read_at] ~= IDS[vhash_at], "the hash file read gets its own notification")

-- yazi keeps three notifications alive and drops anything beyond that, so a burst of
-- status lines must collapse into one and leave room for the result.
local real_time = os.time
os.time = function() return 1 end
reset()
cx.active.selected = { d2 }
M.entry(nil, { args = { "build" } })
os.time = real_time
assert(notif_has("Reading hash file"), "the hash file step is stated even inside a burst")
assert(notif_has("Built"), "the build result still reaches the user")
local burst_pcts = 0
for _, c in ipairs(NOTIFS) do
	if c:match("%d%%") then
		burst_pcts = burst_pcts + 1
	end
end
assert(burst_pcts <= 1, "percentages collapse into one status line inside a burst")

-- ── cancel: `unsquish --cancel <file>`, and exit code 2 reads as cancelled ──
-- Code 2 is what unsquish returns when a run is stopped; telling the user
-- "Extraction failed" over a partial directory they just cancelled is a lie.
-- The emitter fixture above overwrote the commands, so name the real ones again.
M.setup(nil, { squish_cmd = SRC .. "/squish.sh", unsquish_cmd = SRC .. "/unsquish.sh", timeout = 1 })
DRY = true
reset()
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "cancel" } })
assert((last_cmd() or ""):match("unsquish%.sh%s+%-%-cancel%s+" .. shquote(d1 .. ".sqsh")),
  "cancel command built as `unsquish --cancel <file>`")
DRY = false

reset()
FAKE_STATUS = 2
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "extract" } })
assert(notif_has("Cancelled"), "a cancelled extraction notifies Cancelled")
assert(notif_has("Extracted successfully") == false, "a cancelled extraction is not a success")
assert(last_level() == "info", "a cancelled extraction is not an error")
FAKE_STATUS = nil

reset()
FAKE_STATUS = 1
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "extract" } })
assert(notif_has("Extraction failed"), "a real failure still reports failure")
assert(last_level() == "error", "a real failure is an error")
FAKE_STATUS = nil

-- ── build cancel: a hovered .sqsh names the archive; anything else asks the CLI ──
-- Async plugin contexts are isolated, so a cancel job cannot remember the build a
-- different job started, and a multi-item build's dated output may not exist yet.
-- The lock root knows who is running, so a bare --cancel is the honest question.
DRY = true
reset()
local bdir = os.tmpname()
os.remove(bdir)
os.execute("mkdir -p " .. shquote(bdir))
cx.active.current.hovered = { url = bdir, name = "bdir", cha = { is_dir = true } }
M.entry(nil, { args = { "cancel" } })
assert((last_cmd() or ""):match("unsquish%.sh%s+%-%-cancel$"),
  "cancel with no archive under the cursor sends a bare --cancel")
reset()
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "cancel" } })
assert((last_cmd() or ""):match("unsquish%.sh%s+%-%-cancel%s+" .. shquote(d1 .. ".sqsh")),
  "cancel of a hovered .sqsh names that archive")
DRY = false

-- A bare cancel with nothing running is a failure the user hears, not a silent no-op.
reset()
cx.active.current.hovered = nil
M.entry(nil, { args = { "cancel" } })
assert(notif_has("Nothing running"), "a bare cancel with nothing running reports it")
assert(last_level() == "error", "a cancel that stopped nothing is an error")

-- ── verify: `squish --check <file>` ───────────────────────────────────────────
-- KDE's context menu has Verify; without this the plugin has no way to check a
-- checksum it did not just write.
DRY = true
reset()
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "verify" } })
assert((last_cmd() or ""):match("squish%.sh%s+%-%-pipe%s+%-%-check%s+" .. shquote(d1 .. ".sqsh")),
  "verify command built as `squish --pipe --check <file>`")
DRY = false

reset()
FAKE_STATUS = 0
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "verify" } })
assert(notif_has("Checksum verified"), "a matching checksum notifies verified")
assert(last_level() == "info", "a verified checksum is not an error")
FAKE_STATUS = nil

reset()
FAKE_STATUS = 1
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "verify" } })
assert(notif_has("Checksum mismatch"), "a failed checksum notifies mismatch")
assert(last_level() == "error", "a failed checksum is an error")
FAKE_STATUS = nil

-- Code 2 from the CLI means the user stopped the verify, not that the archive is corrupt.
reset()
FAKE_STATUS = 2
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "verify" } })
assert(notif_has("Cancelled"), "a cancelled verify notifies Cancelled")
assert(notif_has("Checksum mismatch") == false, "a cancelled verify is not corruption")
assert(last_level() == "info", "a cancelled verify is not an error")
FAKE_STATUS = nil

-- ── unknown action / missing action ───────────────────────────────────────
reset()
M.entry(nil, { args = {} })
assert(notif_has("Usage:"), "missing action shows USAGE")
-- USAGE is the only place a user learns the actions exist; it must name every one.
assert(notif_has("unmount-tracked") and notif_has("jump") and notif_has("verify"),
  "USAGE lists every action the plugin accepts")
reset()
M.entry(nil, { args = { "bogus" } })
assert(notif_has("Unknown action: bogus"), "unknown action reported")

-- Real archives, real extracts and the lock root all live under /tmp; leaving them
-- behind means a suite run dirties the machine and a later run sees an earlier archive.
os.execute("rm -rf " .. shquote(RUNTIME) .. " " .. shquote(d1) .. " " .. shquote(d1 .. ".sqsh") .. " " ..
  shquote(d1 .. ".sqsh.sha256") .. " " .. shquote(parent) .. " " .. shquote(d2) .. " " ..
  shquote(d2 .. ".sqsh") .. " " .. shquote(emitter) .. " " .. shquote(build_emitter) .. " " ..
  shquote(check_emitter) .. " " .. shquote(bdir) .. " /tmp/extract_pick_dir")

if fails == 0 then
  print("OK: " .. arg[0]:match("[^/]+$"))
else
  print(fails .. " FAILURE(S)")
  os.exit(1)
end
