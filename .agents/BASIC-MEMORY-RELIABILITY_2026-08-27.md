# Basic-Memory Reliability — 27.08.2026

Receipt for the reliability pass after the morning incident (Cursor User-scope
basic-memory MCP red with `ECONNREFUSED 127.0.0.1:8765`, project-scope entry
reconnected ~04:08, manual restart was needed).

## Recovery status

The previously canceled attempt left **no artifacts** (no doc file, no script in
`.agents\scripts\`), so this was a fresh run — but discovery found that a full
supervision stack **already existed since June 2026**. It was repaired/hardened,
not duplicated. No `BasicMemorySupervisor` task was created: creating a third
restarter alongside the existing pair would reintroduce the launch races the
existing scripts explicitly guard against.

## What already existed (unchanged names)

| Task | Trigger | Action |
|---|---|---|
| `BasicMemory-HTTP-MCP` | logon + every 5 min (IgnoreNew, restart-on-failure) | `pwsh -File C:\Users\Prekzursil\.basic-memory\bm-http-server.ps1` — hardened launcher (lockfile mutex, kill-stale, 60s bind wait) |
| `BasicMemory-Watchdog` | every 3 min | `pwsh -File C:\Users\Prekzursil\.basic-memory\bm-watchdog.ps1` — probe + force-recover if down |
| `BasicMemory-Vault-Backup` | (untouched) | vault backup |
| `MCPAgentMailSupervisor` | logon | reference pattern, port 8812 — untouched |

The watchdog **was working**: `bm-watchdog.log` shows near-daily force-recovers
(the daemon dies regularly under RAM pressure), including 27.08 at 02:12 and
03:00. The server was healthy and serving writes by 04:37. The remaining
"unnoticed red" was Cursor-side (see below).

## Root cause of the 27.08 incident

1. The daemon dies under memory pressure (chronic on this box). The watchdog
   restarts it within ~3 min + up-to-60s bind. That worked.
2. Cursor's **User-scope** MCP client did not reconnect to the restarted server
   and sat on the stale `ECONNREFUSED` error; the project-scope client
   reconnected on its own (~04:08). The server was up while Cursor showed red.

## What was changed on 27.08.2026 (backups first)

Backups: `C:\Users\Prekzursil\.basic-memory\backups\bm-watchdog.ps1.bak_2026-08-27`
and `bm-http-server.ps1.bak_2026-08-27`.

1. **`bm-watchdog.ps1` probe upgraded** from raw TCP connect to a real
   `HTTP GET /mcp` (any HTTP status incl. 406 = alive). A bound-but-hung server
   is now detected. Probe timeout is **30s** (measured 27.08: under heavy load a
   healthy answer took >15s). Bound-but-HTTP-unresponsive uses a **two-strike rule**
   (state file `%TEMP%\bm-http-degraded.strike`) so one slow probe on this
   RAM-starved box never thrash-kills a busy-but-healthy server;
   connection-refused still recovers immediately. Anti-thrash startup-grace
   marker logic unchanged.
2. **Restart visibility:** every restart decision (watchdog) and every daemon
   (re)start (launcher) is now mirrored to
   `C:\Users\Prekzursil\.agents\logs\basic-memory-supervisor.log`
   (directory created). Detailed logs remain in `C:\Users\Prekzursil\.basic-memory\logs\`.
3. **`BasicMemory-Watchdog` task got a LogonTrigger** in addition to its 3-min
   time trigger (verified post-edit: `PT3M` repetition retained).

Verified live 27.08 ~05:0x: new watchdog runs clean against the healthy server
(exit 0, no false restart); `GET http://127.0.0.1:8765/mcp` → **HTTP 406**
(healthy answer from the streamable-http endpoint).

## Health probe

```powershell
# 406 = healthy (endpoint requires MCP Accept headers; any HTTP status = serving)
Invoke-WebRequest -Uri 'http://127.0.0.1:8765/mcp' -Method GET -UseBasicParsing -TimeoutSec 15
```

## Force-restart

```powershell
Start-ScheduledTask -TaskName 'BasicMemory-HTTP-MCP'          # idempotent: skips if port already bound
# full force-recover (kills stale procs first, only acts if server is down):
pwsh -NoProfile -File 'C:\Users\Prekzursil\.basic-memory\bm-watchdog.ps1'
```

## Cursor duplicate-scope note (User red vs project green)

`basic-memory` is defined once, in `C:\Users\Prekzursil\.cursor\mcp.json`
(`"url": "http://127.0.0.1:8765/mcp"`). The duplicate entries exist because the
workspace root **is** the home directory, so Cursor loads that same file twice —
once as User scope, once as project scope. **No mcp.json edit was made**: the
fix is not unambiguous — removing the entry would kill both scopes, and the
User scope is required for every other workspace on this machine.

**Recommendation:** keep the file as-is. The project-scope duplicate appears
only in home-dir workspaces and is harmless. After a server restart, if the
User-scope entry stays red while 8765 answers (verify with the health probe
above), it is a stale Cursor client connection — use the refresh/toggle on that
server in Cursor Settings → MCP (or reload the window); do not restart the
server for it.
