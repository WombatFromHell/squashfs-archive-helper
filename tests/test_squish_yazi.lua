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

-- ── yazi runtime stubs ───────────────────────────────────────────────────────
local NOTIFS = {}
local EMITS = {}
local DRY = false
local RECORDED = {}
local FAKE_POPEN

ya = {
  sync = function(fn) return fn end,
  notify = function(t) NOTIFS[#NOTIFS + 1] = t.content end,
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
      os.execute("sh -c " .. shquote(cmd)
        .. " > " .. shquote(outf) .. " 2> " .. shquote(errf)
        .. "; printf %d $? > " .. shquote(codef))
      local function rd(f)
        local h = io.open(f); if not h then return "" end
        local c = h:read("*a"); h:close(); os.remove(f); return c
      end
      local out, err, ec = rd(outf), rd(errf), tonumber(rd(codef)) or 1
      local q = {}
      for l in (out .. "\n"):gmatch("(.-)\n") do q[#q + 1] = { l, 0 } end
      for l in (err .. "\n"):gmatch("(.-)\n") do q[#q + 1] = { l, 1 } end
      q[#q + 1] = { "", 2 }
      local i = 0
      return {
        read_line = function()
          i = i + 1; local e = q[i]; if not e then return nil, 2 end
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
M.setup({ squish_cmd = SRC .. "/squish", unsquish_cmd = SRC .. "/unsquish", timeout = 1 })

local function reset()
  NOTIFS, EMITS, RECORDED = {}, {}, {}
  cx.active.selected, cx.active.current.hovered = {}, nil
end
local function last_cmd() return RECORDED[#RECORDED] end
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
assert(last_cmd():match("squish%s+%-m%s+'" .. d1 .. "%.sqsh'"), "mount command built as `squish -m <file>`")
assert(notif_has("Mounted successfully"), "mount notifies success")

reset()
cx.active.current.hovered = { url = d1 .. ".sqsh", name = "x.sqsh", cha = { is_dir = false } }
M.entry(nil, { args = { "unmount" } })
assert(last_cmd():match("squish%s+%-u%s+'" .. d1 .. "%.sqsh'"), "unmount command built as `squish -u <file>`")
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
assert(last_cmd():match("squish%s+%-u%s+'/home/u/archive%.sqsh'"),
  "unmount-tracked parses mounts and builds `squish -u <archive>`")
FAKE_POPEN = nil
DRY = false

-- ── jump: emits tab_create with mountpoint ─────────────────────────────────
reset()
FAKE_POPEN = { "/home/u/archive.sqsh -> /tmp/squish-mounts/archive.01.mounted" }
M.entry(nil, { args = { "jump" } })
assert(EMITS[#EMITS] == "tab_create", "jump emits tab_create")
FAKE_POPEN = nil

-- ── unknown action / missing action ───────────────────────────────────────
reset()
M.entry(nil, { args = {} })
assert(notif_has("Usage:"), "missing action shows USAGE")
reset()
M.entry(nil, { args = { "bogus" } })
assert(notif_has("Unknown action: bogus"), "unknown action reported")

if fails == 0 then
  print("OK: " .. arg[0]:match("[^/]+$"))
else
  print(fails .. " FAILURE(S)")
  os.exit(1)
end
