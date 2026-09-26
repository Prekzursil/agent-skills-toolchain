---
name: ce-pipe-discovery
description: CE 7.6 pipe API works via object methods on connectToPipe handle, not
  global functions
type: feedback
permalink: main/claude-memory/downloads-swfoc-memory/feedback-ce-pipe-discovery
---

CE 7.6 pipe communication DOES work — the previous sessions were using the wrong API.

**What works:**
- `connectToPipe("swfoc_bridge")` — returns a userdata handle (use SHORT name, CE prepends `\\.\pipe\`)
- Handle has rich methods: `writeByte`, `readByte`, `writeString`, `readString`, `writeBytes`, `readBytes`, `writeDword`, `readDword`, `destroy`
- The handle also has `acceptConnection` (server-side)

**What doesn't work:**
- `writeToPipe(handle, data)` — global function does NOT exist in CE 7.6
- `readFromPipe(handle, timeout)` — global function does NOT exist in CE 7.6
- `openFileMapping` / `mapViewOfFile` — do NOT exist as CE Lua globals
- `connectToPipe("\\\\.\pipe\swfoc_bridge")` — full path returns nil, use SHORT name only

**Why:** The v3 trainer used global functions `writeToPipe`/`readFromPipe` which don't exist. The correct pattern is `h = connectToPipe("name"); h:writeByte(b); h:readByte()`.

**Pipe gotcha:** The DLL pipe server is single-instance. If a client connects but never sends data, the server blocks in `ReadFile` forever. Need to add a read timeout in the DLL pipe thread, or use `PIPE_NOWAIT` mode.

**How to apply:** In shared_cmd.lua, use `connectToPipe` + handle methods. Each `bridge_send` creates a fresh connection (connect, write cmd + null, read response, destroy). The DLL pipe recycles after each command.