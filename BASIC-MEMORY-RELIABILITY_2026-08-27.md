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

## Post-fix MCP-surface probe (27.08.2026 ~06:48–08:34)

**Final verdict: ALIVE.** By ~08:34 the MCP surface is fully serving — a clean
JSON-RPC `initialize` POST returns **HTTP 200** with an SSE `event: message`
carrying a real result: `serverInfo {"name":"Basic Memory","version":"3.3.1"}`,
`protocolVersion 2025-03-26`, full `capabilities` (tools/resources/prompts/logging).
Port `127.0.0.1:8765` LISTENING (PID 33392). **But this is a recovery, not a
steady state** — for most of the probe window (06:43 → ~08:0x) it was BROKEN and
crash-looping; the scheduled-task restart loop is what eventually got a daemon to
survive. Timeline below.

**Interim state during the window (BROKEN — crash-looping):** for ~90 min the
port was unbound and the daemon died on every launch.

Probe used (per spec — a JSON-RPC `initialize` POST, not just a GET):

```powershell
curl.exe -s -X POST http://127.0.0.1:8765/mcp `
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" `
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}'
```

Evidence (all times local, UTC+3):

1. **06:48** — initialize probe: curl **exit 7** (failed to connect). No JSON, no SSE.
2. **~07:05** — `Start-ScheduledTask -TaskName 'BasicMemory-HTTP-MCP'` executed
   (supervisor log shows the matching `[launcher] starting` line at 07:04:18);
   waited 45 s; re-probe: **exit 7, HTTP_CODE 000** again.
3. **~07:15** — `netstat -ano | findstr 8765` → **empty** (port not bound).
   Task state `Ready`, `LastTaskResult 267009` (0x41301 = instance running),
   LastRunTime 07:14 — the launcher keeps being started, but nothing survives.
4. **~07:20** — final re-probe: **exit 7** again.
5. **Supervisor log** (`.agents\logs\basic-memory-supervisor.log`): `[launcher]
   starting basic-memory streamable-http` at **06:54, 07:00, 07:04, 07:09** —
   a ~5-min crash loop, preceded by watchdog strikes at 05:13/05:22 (force-recover)
   and 06:17/06:43 (DOWN → force-recover).
6. **Launcher log** (`.basic-memory\logs\bm-http-server.log`, tail): 07:30:14
   `daemon exited during startup (code -1)` + `did NOT bind in 60s - killing
   stale chain + exiting so a retry can run`. So the failure is the **daemon
   process itself crashing during startup** (consistent with chronic RAM
   pressure on this box), not the launcher or task plumbing.
   (`bm-direct.err.log` is stale — last entry 29.06 — so the daemon's startup
   stderr is not being captured anywhere current; capturing it would be the
   next diagnostic step.)

7. **~08:34** — clean initialize POST (body via file to avoid PowerShell
   quote-mangling): **HTTP 200**, SSE `event: message`, full `initialize` result
   (`Basic Memory 3.3.1`). Port `127.0.0.1:8765` bound (PID 33392). **ALIVE.**
   (A malformed inline-JSON probe at ~08:31 already got a JSON-RPC `-32700` parse
   error from the server — itself proof the MCP surface was back and parsing POSTs.)

**Reconciling the two earlier reports:** both were correct *at their own
timestamps* — this daemon flaps under chronic RAM pressure, so "healthy" and
"unusable" are both true at different minutes. The watchdog's "8765 healthy,
GET /mcp → 406" was measured ~05:0x when the server was genuinely up; the later
worker's "TCP listens but MCP surface unusable" matches the bound-but-hung
degraded strikes the supervisor log records (05:13→05:22, 06:17). Then 06:43 →
~08:0x it was strictly worse than either report (port unbound, daemon
crash-looping every ~5 min). The scheduled-task/watchdog restart loop
self-healed it, and by ~08:34 the initialize probe confirms a live MCP surface.
The `Start-ScheduledTask` I ran at ~07:05 did not recover it on its own (the
07:04 launcher attempt still died); a later cycle succeeded. **Net: the surface
is alive now but flaps — the underlying fragility (daemon dies under memory
pressure) is unchanged, so expect further watchdog recoveries.**

---

## Post-fix MCP-surface probe

**27.08.2026 08:29–08:44 (UTC+3) — full JSON-RPC `initialize` probes against `POST http://127.0.0.1:8765/mcp`.**

- **08:29** — probe returned a complete, valid SSE initialize result: `serverInfo: {"name":"Basic Memory","version":"3.3.1"}`, full capabilities block. **Server ALIVE** at that instant — the crash loop documented above had ended (a launcher start between 07:54 and 08:04 evidently survived).
- **08:40** — same probe: **connection refused** (curl exit 7). Supervisor log context: `bound but HTTP unresponsive` strikes at 08:04 and 08:27, `force-recover` 08:29:12, relaunch 08:34 that had not bound by 08:40.
- **08:43** — after `Start-ScheduledTask 'BasicMemory-HTTP-MCP'` + 40 s wait: initialize probe **succeeded again** (identical valid v3.3.1 result, curl exit 0). **Current verdict: server ALIVE**, but *flapping* under RAM pressure, not stably up.
- **Client-side check (the earlier-incident pattern, confirmed again):** in the very same minutes the raw port served a correct initialize (08:29), the Cursor session's `user-basic-memory` MCP namespace reported `error: failed during live tool discovery / tools unavailable` — i.e. **server-fine-but-client-stale is real and currently reproducible**. Worker "MCP namespace down / Not connected" reports are therefore NOT reliable evidence of server death.

**Reconciling the three conflicting reports:** all three were correct at their own timestamps against a *flapping* server. (1) Watchdog "8765 healthy, 406 on GET" — measured in a genuinely-up window. (2)+(3) Worker "MCP namespace down / Not connected" — a mix of the real down/crash-loop windows (06:43–~07:54, again ~08:29–08:43) and client-stale namespace state that persists even while the server answers (proven above). Practical rule going forward: only a raw `initialize` POST to the port is authoritative; Cursor namespace status alone proves nothing about the server, and a single point-in-time probe proves nothing about stability — this daemon flaps on a several-minute timescale under memory pressure. (Next diagnostic step remains capturing daemon startup stderr — `bm-direct.err.log` is stale since 29.06.)

---

## Flap root cause (27.08.2026 ~09:00–09:55, diagnosis + mitigation pass)

### Root causes — two distinct mechanisms, both evidenced

**1. PROVEN — the 08:0x "bound but unresponsive → kill" flap: oversized-entity
embedding stall.** The daemon keeps per-PID logs at
`C:\Users\Prekzursil\.basic-memory\basic-memory-<PID>.log` (nobody had read
them). `basic-memory-24568.log` shows the smoking gun for the 08:04/08:27
strike window:

- 07:57:21 `Slow file sync detected: path=sessions/sessions-catalog-2026-08-27.md … 15984ms`
  — the new session-catalog material entering the vault.
- 08:05:06 `Vector sync oversized entity detected: entity_id=1690
  pending_jobs_total=1482 shard_size=256 shard_count=6` — the **378 KB
  `session-catalog.md`** (created 07:05, the 1,452-session catalog) became one
  entity with **1,482 embedding chunks**, processed at `batch_size=2` on a
  RAM-starved box.
- 08:05:54 FastEmbed model loads, log goes silent — the daemon grinds
  embeddings, the MCP surface stops answering (strike 1 08:04, strike 2 08:27),
  watchdog kills it 08:29, restart resumes the pending queue → stall again.
  Self-perpetuating. (By the 08:42 restart the backlog had ground down from
  1,482 to 133 pending chunks across kill cycles: `14107 embeddings / 14240
  chunks`.)

**2. BEST-EVIDENCE — the 06:54–07:54 ~5-min "crash loop": supervision killing
its own slow warm-ups.** Measured twice today: launch→uvicorn-bind takes
**2.5–4 minutes** under load (08:39:48→08:42:14; 09:27:27→09:31:22). The
launcher's bind-wait gave up at nominally 60 s and **killed the warming chain**
(`did NOT bind in 60s - killing stale chain`, e.g. 07:30:14), and the
watchdog's 75 s marker grace expired long before a warm-up completed, so its
3-min cycle force-recovered (= killed) warming daemons too. Every ~5 min the
task retried, warmed, got killed — reading as a "crash loop". Windows event
logs 06:30–08:45 show **zero** Resource-Exhaustion (2004) or app-crash
(1000/1001) records: no OS-level OOM kill; the terminations were our own
supervision plus the embedding stall. (RAM pressure is still the amplifier —
it is why warm-up takes minutes and why embedding starves the event loop.)

### Changes made (backups in `.basic-memory\backups\`: `bm-http-server.ps1.bak_2026-08-27b`, `index-ai-sessions.py.bak_2026-08-27`, `sessions-catalog-note.bak_2026-08-27.md`)

1. **Catalog moved out of the vault** (kills mechanism 1): `D:\basic-memory\sessions\session-catalog.md`
   → `C:\Users\Prekzursil\.agents\session-catalog.md`. Pointer note
   `sessions/sessions-catalog-2026-08-27.md` updated with the new path + why.
   Indexer `~\.agents\scripts\index-ai-sessions.py` `DEFAULT_CATALOG` now
   points at `.agents\` so a re-run cannot regress the vault.
2. **`bm-http-server.ps1`** (kills mechanism 2 + captures evidence):
   - Daemon stdout/stderr now go to **per-launch timestamped files**
     `logs\daemon-YYYYMMDD-HHmmss.{out,err}.log` (pruned to newest 8 each).
     Previous fixed-name `Start-Process` redirect TRUNCATED on every launch,
     destroying each crash's stderr and clobbering the launcher's own log.
   - Bind-wait extended 60 → **240 cycles** (warm-up is 2.5–4 min here).
   - The bind-wait loop now **re-stamps `%TEMP%\bm-relaunch.marker` every
     cycle**, so the watchdog's 75 s grace keeps deferring for as long as a
     launcher is genuinely mid-start — a warming daemon can no longer be
     force-recovered to death. Verified live: watchdog at 09:31:20 logged
     `down but relaunched -4s ago - DEFER` four minutes into a warm-up.
   - Lockfile/mutex, kill-stale, and both scheduled tasks unchanged.
3. **Watchdog untouched** — its 30 s probe / two-strike / 75 s grace values are
   fine once the marker stays fresh during warm-up.

### 10-min stability probe (full JSON-RPC `initialize`, body from `.basic-memory\probe-initialize.json`)

Task force-restarted 09:27:13 through the new launcher; uvicorn up 09:31:22.

| Probe | Time | Result |
|---|---|---|
| 1 | 09:36:40 | valid initialize (v3.3.1), curl exit 0 |
| 2 | 09:44:07 | valid initialize, exit 0 |
| 3 | 09:51:56 | valid initialize, exit 0 |

Same PID the whole window (basic-memory 20360, started 09:27:31 — no restarts,
no watchdog strikes). Notably it stayed responsive **while** running a
7.1-minute `full_deletions` scan + reconciling 99 stale
`compaction-checkpoints/*` entities (long-deleted files whose DB rows were
finally cleaned once the catalog move triggered the first full deletion scan
in a while) — load that would previously have been read as "hung".

### Watch next

- ~133 orphaned embedding chunks from the deleted catalog entity may linger in
  `memory.db`; harmless, but if `_log_embedding_status` chunk counts stay
  mismatched for days, a one-off `basic-memory` reindex would tidy it.
- If "bound but HTTP unresponsive" strikes recur, read the **newest
  `logs\daemon-*.err.log` + `basic-memory-<PID>.log` first** — the evidence
  now survives the crash. Look for another `Vector sync oversized entity`
  warning: any future large single file in the vault reproduces mechanism 1
  (rule of thumb: keep machine-generated files >~100 KB out of `D:\basic-memory`,
  point a small note at them instead).
- `batch_size=2` embedding on this box is extremely slow by design (RAM over
  speed). If flap returns during embedding of *normal* notes, consider
  `semantic_search_enabled` scheduling or a batch-size bump as the next lever.
