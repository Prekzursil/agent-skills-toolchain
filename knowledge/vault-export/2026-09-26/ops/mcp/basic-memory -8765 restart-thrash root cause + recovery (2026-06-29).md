---
title: basic-memory :8765 restart-thrash root cause + recovery (2026-06-29)
type: report
permalink: main/ops/mcp/basic-memory-8765-restart-thrash-root-cause-recovery-2026-06-29
tags:
- basic-memory
- mcp
- ops
- thrash
- watchdog
- liveness
---

# basic-memory :8765 restart-thrash — root cause + recovery

**Symptom (2026-06-29):** Claude `/mcp` showed `basic-memory · ✘ failed`; nothing listening on 127.0.0.1:8765 despite a launcher pwsh alive. Watchdog log = relentless `:8765 DOWN -> restarting` every ~1-2 min; `liveness-restart.log` showed back-to-back (sometimes DOUBLE/concurrent) `[RESTART] begin` with `end (port :8765 owner now: )` **empty** — bind never succeeded.

## Root cause — NOT the daemon
`basic-memory.exe mcp --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp` run **directly** binds in ~5s and serves fine (FastMCP 3.3.1, uvicorn). The failure is a **restart THRASH loop**: redundant restart triggers race —
1. `BasicMemory-Watchdog` scheduled task (TCP-checks :8765 every few min, restarts task when down), AND
2. per-session `mcp-liveness` hook (`~/.claude/hooks/mcp-liveness/liveness.py`) across **many concurrent Claude/Codex sessions**, each firing `restart-basic-memory.ps1` once per down-episode.

Both call `restart-basic-memory.ps1` → `Stop+Start` the `BasicMemory-HTTP-MCP` task. The launcher `~/.basic-memory/bm-http-server.ps1` line ~38 does `Get-Process basic-memory | Stop-Process` whenever the port is free → a concurrent launch **kills another launch's freshly-started daemon** → never achieves a stable bind. Self-sustaining **only while down**; one stable bind ends it.

**The `MCP-Orphan-Reaper` is NOT the culprit** — `~/scripts/mcp-reaper.ps1` already allowlists `streamable-http|bm-http-server|...` (line ~58, added 2026-06-29), so it skips the shared daemon.

## Recovery (what worked)
1. Temporarily `Disable-ScheduledTask BasicMemory-Watchdog` + `MCP-Orphan-Reaper` to stop the thrash drivers.
2. Kill all `bm-http-server.ps1` launchers + `basic-memory` daemons; confirm :8765 free.
3. Start the daemon **directly + detached** (`Start-Process basic-memory.exe ... -WindowStyle Hidden -PassThru -RedirectStandardError <own log>`) — bypasses the flaky launcher; it holds the port so future launches bail on "port in use".
4. Re-enable watchdog + reaper. **Safe once a healthy daemon holds the port**: watchdog does a TCP check then `return` if up (never touches a live server); liveness only restarts on DOWN/dead-listening.
5. Verified: converged to a single stable daemon, **zero** new restart-log entries over 60s+, `liveness.py probe` → `SUCCESS:liveness all critical MCPs up`.

## Key facts for next time
- Run the daemon **directly** to test — proves binary health and decouples from launcher races.
- The thrash converges the moment ONE daemon binds stably; don't keep kill/restarting (that IS the churn — my own kill cycles fired the 14:28-14:31 liveness restarts).
- Env the daemon needs: `BASIC_MEMORY_HOME=D:\basic-memory`, `FASTEMBED_CACHE_PATH=D:\basic-memory\.models`, `DO_NOT_TRACK=1`.
- Design smell (future hardening, not yet done): 3 redundant restart authorities (logon task + watchdog + N session liveness hooks) with a launcher that kills-on-free-port → inherent race. A single restart authority or a launcher that never kills a live-or-binding daemon would remove the thrash class.

Relates to mcp_fleet_state (shared HTTP :8765 keep-semantic decision).