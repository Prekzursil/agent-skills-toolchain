---
title: CyberStrike HexStrike full and Sliver MCP 2026-09-02
type: note
permalink: main/tools/cyber-strike-hex-strike-full-and-sliver-mcp-2026-09-02
status: active
valid_as_of: '2026-09-02'
tags:
- cyberstrike
- hexstrike
- sliver
---

- [decision] Wired HexStrike AI v6.0 **full FastMCP** (151 `@mcp.tool` definitions via the framed launcher) into CyberStrike global `mcp.hexstrike-ai`. Timeout 300000. Server remains `127.0.0.1:8888`.
- [fact] HexStrike `/health?full=1` on this Windows host: 23/127 *host binaries* present. MCP still exposes the full tool list; missing binaries fail at execution, not at handshake. `cyberstrike mcp list` reported hexstrike-ai connected.
- [decision] There is no Bishop Fox product named Sliver 2. Installed **Sliver v1.7.6** (latest, MCP-capable) to `~/.local/opt/sliver`. Multiplayer daemon **loopback only** `127.0.0.1:31337`. No implant/HTTP/DNS/WG listeners were started.
- [decision] Two CyberStrike MCP entries: `sliver` = official `sliver-client mcp` (filesystem-oriented); `sliver-full` = x746b/sliver-mcp 0.2.4 (~74 tools: exec, armory, listeners, implants). Operator cfg path only, never inlined. Operator name `cyberstrike` with `--permissions all` for local estate use.
- [fact] Both Sliver MCP servers report **connected** only while `sliver-server daemon` is listening. Ensure with `pwsh -File C:\Users\Prekzursil\.local\opt\sliver\ensure-daemon.ps1`. Connecting without the daemon yields MCP error -32000 Connection closed.
- [fact] sliver-mcp needed `mcp>=1.2,<2` (mcp 2.x removed FastMCP). Do not start public C2. Authorized engagement still required before generate/listener/session use.
- relates_to [[CyberStrike]]
See also [[CyberStrike default GLM-5.3 and Codex invoke 2026-09-02]].