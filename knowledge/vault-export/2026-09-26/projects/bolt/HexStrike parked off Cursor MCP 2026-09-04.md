---
title: HexStrike parked off Cursor MCP 2026-09-04
type: note
permalink: main/projects/bolt/hex-strike-parked-off-cursor-mcp-2026-09-04
status: active
valid_as_of: '2026-09-04'
tags:
- hexstrike
- cursor
- mcp
- masscan
---

- [decision] HexStrike is parked off Cursor MCP (Fable/Composer OOM). :8888 stays up. Grok/Hermes keep hexstrike-ai-hub. Owner asked 04.09.2026.
- [fact] ~/.cursor/mcp.json has no hexstrike-ai-hub. CURSOR_RETIRED_SERVERS includes hexstrike-ai and hexstrike-ai-hub. Parked catalog has both stdio and HTTP hub.
- [fact] masscan 1.3.2 runs via WSL user-prefix (deb extract, no sudo) and ~/.local/bin/masscan.cmd. hydra Win32 shim unchanged.
- [fact] Cursor was not killed (19 procs). CS TUI :4096 200.
- relates_to [[Hermes HexStrike COMPLETE was false 2026-09-04]]
Receipt: D:\\bolt\\analysis\\HEXSTRIKE-CURSOR-PARK_2026-09-04.md
