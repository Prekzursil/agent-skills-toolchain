# Deploying the Basic Memory session-healing proxy (owner-approved step)

Status: the proxy is **built and tested** (`../bm_session_proxy.py`, 26 tests against the
fake daemon). **Deployment - moving the daemon off `:8765` so the proxy owns that port -
remains a separate owner-approved step**, because it changes who binds `:8765`
(`memory-contract.md`: "`:8765` stays bound only by its owner"). Nothing in this folder
runs by itself; every command below is for the owner to run on the Windows box.

Design record: [`docs/plans/2026-09-02-basic-memory-transport-decision.md`](../../../../docs/plans/2026-09-02-basic-memory-transport-decision.md) section 7.
Measured failure windows: [`.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md`](../../../../.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md).

```
Cursor / Claude / Codex ──http──► 127.0.0.1:8765  bm_session_proxy.py   (task BasicMemory-SessionProxy)
   every client keeps                 │  one upstream session per client session; heals 404/-32600,
   http://127.0.0.1:8765/mcp          │  503 + Retry-After while the daemon is dead, /healthz
                                      ▼
                                127.0.0.1:8766  basic-memory streamable-http   (task BasicMemory-HTTP-MCP, MOVED)
                                                 probed on :8766 by BasicMemory-Watchdog
```

## Files in this folder

| File | Deploy to | Wiring | Purpose |
|---|---|---|---|
| `bm-session-proxy.ps1` | `C:\Users\Prekzursil\.basic-memory\` | task `BasicMemory-SessionProxy` (logon + every 5 min, IgnoreNew, restart-on-failure) | Launcher in the style of `bm-http-server.ps1`: start-lock over the bind window, port-in-use idempotent skip, kill-stale **scoped to the proxy**, per-launch `logs\bm-session-proxy-<ts>.{out,err}.log` pruned to 8, relaunch marker re-stamped during the bind wait, `[proxy-launcher]` lines mirrored to `.agents\logs\basic-memory-supervisor.log`. Runs `C:\Python314\python.exe <toolchain>\tools\mcp\mcp-http-host\bm_session_proxy.py --port 8765 --upstream http://127.0.0.1:8766/mcp --restart-log C:\Users\Prekzursil\.agents\logs\bm-session-proxy.jsonl`. |
| `bm-session-proxy-watchdog.ps1` | `C:\Users\Prekzursil\.basic-memory\` | task `BasicMemory-SessionProxy-Watchdog` (logon + every 3 min) | Probes `GET http://127.0.0.1:8765/healthz` (15 s). Any HTTP answer = proxy alive. Acts only on **refused** (at once) or **bound-but-unresponsive** (two-strike rule), with the 75 s marker grace; force-recovers only the proxy. A daemon outage shows up as `upstream.state == "degraded"` in the body and is logged, never acted on - that is `BasicMemory-Watchdog`'s job on `:8766`. |
| `Register-BmSessionProxyTasks.ps1` | run from anywhere | - | Registers both tasks (mirrors `BasicMemory-HTTP-MCP` / `BasicMemory-Watchdog` settings: hidden, LIMITED, `pwsh -File`, no time limit for the proxy). `-WhatIf`, backs up existing task XML, `-Uninstall` removes both and reaps only the proxy. |
| `move_daemon_port.py` | run from the toolchain checkout | - | The exact daemon edit as an executable, dry-run-by-default, reversible step (below). |

The toolchain checkout the launcher runs from is `C:\Users\Prekzursil\source\agent-skills-toolchain`
(the *executed* checkout per `CLAUDE.md`); pull this branch there before the cutover.

## The exact edits (why approval is needed)

### 1. Daemon launcher and watchdog: every whole-number `8765` becomes `8766`

Files: `C:\Users\Prekzursil\.basic-memory\bm-http-server.ps1` and `bm-watchdog.ps1`.
In the tracked copies (`scripts/agentic-perfection/`) that is five tokens:

| File | Line (tracked copy) | Before | After |
|---|---|---|---|
| `bm-http-server.ps1` | `$Port = 8765` | daemon binds `:8765` | `$Port = 8766` |
| `bm-http-server.ps1` | kill-stale filter `Where-Object { $_.CommandLine -like '*basic-memory*8765*' }` | matches the daemon's own python | `'*basic-memory*8766*'` (must follow the daemon, or kill-stale silently stops finding it) |
| `bm-watchdog.ps1` | header comment `(127.0.0.1:8765)` | - | `(127.0.0.1:8766)` |
| `bm-watchdog.ps1` | `$Port = 8765` | watchdog measures `:8765` | `$Port = 8766` (the watchdog must measure the **daemon**, not the proxy) |
| `bm-watchdog.ps1` | kill-stale filter `'*basic-memory*8765*'` | - | `'*basic-memory*8766*'` |

The on-box copies were hardened on 2026-08-27 (HTTP `GET http://127.0.0.1:8765/mcp` probe,
240-cycle bind wait, per-launch daemon logs); the rule is the same for that shape - the probe
URL becomes `http://127.0.0.1:8766/mcp`. `move_daemon_port.py` applies exactly this rule
(whole-number tokens only: `18765` or `87650` would be left alone), keeps encoding / BOM /
CRLF byte-for-byte, backs up first, and can verify and roll back:

```powershell
$T = 'C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\mcp-http-host\deploy'
python "$T\move_daemon_port.py"            # DRY RUN: unified diff + count per file, writes nothing
python "$T\move_daemon_port.py" --apply    # backups\bm-http-server.ps1.bak_<date>-portmove, then edit
python "$T\move_daemon_port.py" --check    # SUCCESS when no 8765 is left in the two files
python "$T\move_daemon_port.py" --rollback # restore the newest -portmove backups
```

Nothing else in the daemon's arguments changes (`basic-memory mcp --transport streamable-http
--host 127.0.0.1 --port 8766 --path /mcp`); semantic search, `BASIC_MEMORY_HOME`, the vault
and the watchdog's two-strike / grace logic are untouched.

### 2. Consumers of `:8765` that must keep pointing at the daemon

| Consumer | Edit | Why |
|---|---|---|
| `hooks/mcp-liveness/critical.json` (deployed copy) | `basic-memory.url` -> `http://127.0.0.1:8766/mcp`, `port` -> `8766` | The liveness hook auto-restarts the **daemon** via `restart-basic-memory.ps1`. Left on `:8765` it would read a dead proxy as a dead daemon and force-recover a healthy daemon. Pointed at `:8766` it keeps measuring what it restarts. Optional second entry `basic-memory-proxy` (`url .../8765/mcp`, `port 8765`, `"auto_restart": false`) if you want the hook to *alert* on a dead proxy too. |
| `hooks/mcp-liveness/restart-basic-memory.ps1` | none required | Its `-KillCorpse` path only kills the `:8765` owner when the process positively matches `basic-memory`; the proxy (`python.exe ... bm_session_proxy.py`) does not, so it logs "NOT killing (safety)" and force-recovers the daemon task, which is the right action. Change its `$Port` to `8766` only if you want the corpse check to see the daemon again. |
| `hooks/heartbeat/heartbeat.py` | `BASIC_MEMORY_PORT=8766` in the hook environment, or leave it | It reports "is basic-memory listening"; on `:8765` it now reports the proxy (which is what clients experience). Owner's call. |
| `.agents/agents.json` | remove `x_cursor` from `mcp.servers.basic-memory`; keep `url` as is | Cursor returns to the direct URL, which is now the proxy - the uniform path (no shim per Cursor window). Optional: add a `processMatch: ["bm_session_proxy"]` entry with a small `maxPrivateBytes` (measured ~20-25 MiB) if the fleet supervisor should budget it. Then `pwsh -File C:\Users\Prekzursil\.agents\scripts\sync_shared_state.ps1`; `merge_generated_cursor_mcp.py --check` must read `drift=0`. |
| `memory-contract.md` (live-capture) | "`:8765` stays bound only by its owner" - the owner is now `bm-session-proxy` (task `BasicMemory-SessionProxy`); the daemon binds `:8766`; the client URL is unchanged | Contract amendment, one line. |

The proxy's argv contains none of the daemon's identity tokens (`basic_memory`,
`streamable-http`, `*basic-memory*<port>*`), pinned by `tests/test_deploy_assets.py`, so the
fleet supervisor's `processMatch` and the daemon's own kill-stale filters can never mistake
one for the other.

## Staging first (no daemon change, nothing owner-approval-bound)

Run the proxy on a spare port **in front of the live daemon** for a day and point one client at it:

```powershell
$T = 'C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\mcp-http-host'
python "$T\bm_session_proxy.py" --port 8767 --upstream http://127.0.0.1:8765/mcp --restart-log "$env:TEMP\bm-session-proxy-staging.jsonl"
# second terminal:
python C:\Users\Prekzursil\.agents\scripts\bm_cursor_http_session.py --health --url http://127.0.0.1:8767/mcp   # "ok": true via the proxy
Invoke-RestMethod http://127.0.0.1:8767/healthz | ConvertTo-Json -Depth 4
# point ONE Cursor entry (e.g. a project-scope mcp.json) at http://127.0.0.1:8767/mcp; watch the next watchdog restart:
Get-Content "$env:TEMP\bm-session-proxy-staging.jsonl" -Tail 20     # session_lost -> session_reinitialized; upstream_down -> upstream_recovered
```

A rehearsal with no real daemon at all: `python "$T\_fake_streamable_http_daemon.py" --port 8799 --mode sse --restart-every 20`
plus `--upstream http://127.0.0.1:8799/mcp`.

## Cutover (a quiet moment; the daemon is down for one warm-up, 2.5-4 min under load)

```powershell
$BM = 'C:\Users\Prekzursil\.basic-memory'
$T  = 'C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\mcp-http-host'
# 0. Deploy the two scripts beside the daemon's, register the tasks (registered, not started)
Copy-Item "$T\deploy\bm-session-proxy.ps1", "$T\deploy\bm-session-proxy-watchdog.ps1" $BM
pwsh -File "$T\deploy\Register-BmSessionProxyTasks.ps1" -WhatIf
pwsh -File "$T\deploy\Register-BmSessionProxyTasks.ps1"
# 1. Stop the daemon's supervision, then the daemon (order: watchdog first so it cannot relaunch mid-edit)
Stop-ScheduledTask 'BasicMemory-Watchdog'
Stop-ScheduledTask 'BasicMemory-HTTP-MCP'
Get-Process basic-memory -ErrorAction SilentlyContinue | Stop-Process -Force    # the launcher's own kill-stale step
# 2. The edit (dry run, apply, verify)
python "$T\deploy\move_daemon_port.py"
python "$T\deploy\move_daemon_port.py" --apply
python "$T\deploy\move_daemon_port.py" --check
# 3. Daemon back on :8766; wait for bind (2.5-4 min under load), then prove it with a real initialize
Start-ScheduledTask 'BasicMemory-HTTP-MCP'
python C:\Users\Prekzursil\.agents\scripts\bm_cursor_http_session.py --health --url http://127.0.0.1:8766/mcp   # "ok": true, serverInfo.name "Basic Memory"
# 4. Proxy on :8765 (upstream :8766), then prove the client-facing URL end to end
Start-ScheduledTask 'BasicMemory-SessionProxy'
Invoke-RestMethod http://127.0.0.1:8765/healthz | ConvertTo-Json -Depth 4       # status "ok", upstream.state "up"
python C:\Users\Prekzursil\.agents\scripts\bm_cursor_http_session.py --health   # default URL :8765, now via the proxy
Invoke-WebRequest -Uri http://127.0.0.1:8765/mcp -UseBasicParsing -TimeoutSec 15 # 406 = the old probe shape still holds
# 5. Supervision back on
Start-ScheduledTask 'BasicMemory-Watchdog'
Start-ScheduledTask 'BasicMemory-SessionProxy-Watchdog'
# 6. Consumers (section "exact edits" 2): critical.json -> :8766; registry: drop x_cursor; sync; --check drift=0; reload Cursor.
```

## Verify and observe

- `Get-Content C:\Users\Prekzursil\.agents\logs\basic-memory-supervisor.log -Tail 20` - `[proxy-launcher] bound on :8765`.
- `Get-Content C:\Users\Prekzursil\.agents\logs\bm-session-proxy.jsonl -Tail 20` - one JSON object per line:
  `proxy_started`, then per daemon restart `session_lost` -> `session_reinitialized`
  (with `upstream_session_old/new`), per dead window `upstream_down` -> `upstream_recovered`;
  `heal_rejected` would mean the daemon refused the proxy's own `initialize` (read the daemon log).
- `/healthz` always answers 200 while the proxy lives: `status` is `ok` / `degraded` /
  `starting`; `upstream` carries `state`, `last_error`, `consecutive_failures`,
  `downtime_windows`, `sessions_lost`, `reinitialized`; `sessions` the client/upstream/adopted
  counts; `?probe=1` refreshes the state with a bare upstream GET (no session is opened).
- On the next watchdog restart every client keeps its session id: Cursor stays green, a tool
  call during the warm-up gets a `503` with `Retry-After` and a readable JSON-RPC error, the
  next call succeeds. `bm-session-proxy.jsonl` shows the heal. Neither Cursor, Claude nor
  Codex needs a config change beyond the `x_cursor` removal.

## Rollback (reverses every step; no secret, no vault, no semantic-search setting involved)

```powershell
$BM = 'C:\Users\Prekzursil\.basic-memory'
$T  = 'C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\mcp-http-host'
# 1. Proxy tasks off (watchdog first) and the proxy process reaped - frees :8765
pwsh -File "$T\deploy\Register-BmSessionProxyTasks.ps1" -Uninstall
# 2. Daemon back to :8765: stop its supervision, restore both scripts, relaunch
Stop-ScheduledTask 'BasicMemory-Watchdog'; Stop-ScheduledTask 'BasicMemory-HTTP-MCP'
Get-Process basic-memory -ErrorAction SilentlyContinue | Stop-Process -Force
python "$T\deploy\move_daemon_port.py" --rollback        # or: Copy-Item "$BM\backups\bm-http-server.ps1.bak_<date>-portmove" "$BM\bm-http-server.ps1" (and the watchdog)
Start-ScheduledTask 'BasicMemory-HTTP-MCP'                 # wait for bind (2.5-4 min under load)
python C:\Users\Prekzursil\.agents\scripts\bm_cursor_http_session.py --health   # "ok": true directly on :8765
Start-ScheduledTask 'BasicMemory-Watchdog'
# 3. Consumers back: critical.json -> :8765; re-add x_cursor.stdio_bridge to agents.json if Cursor should
#    keep the per-window bridge (decision-record section 6), sync_shared_state.ps1, reload Cursor.
```

Clients keep working through the rollback the same way they did before the proxy: the URL
never changed. Partial rollback is also fine - the proxy on `:8765` in front of the daemon
on `:8766` is the *only* dependency between the two halves, so undo them in the order above.

## What the proxy deliberately does not do

- It never starts, stops, kills or session-probes the daemon (`?probe=1` is a bare GET that
  the daemon answers 406, the on-box watchdog's own probe shape).
- It does not serve discovery from a cache while the daemon is dead; that is a `503` by
  design (the task's requirement, and what keeps the client transport from entering its
  stuck state). The per-window stdio bridge from PR #305 keeps its cache behaviour and stays
  available as `x_cursor.stdio_bridge` if a client ever needs it.
- It binds loopback only (`--host` must be a loopback address), carries no credentials and
  writes nothing but its logs.
- A proxy death is a client-visible outage until the task's restart-on-failure (1 min) or
  the watchdog (3 min) relaunches it; the client session ids survive that because unknown ids
  are adopted with a fresh upstream session (`--no-adopt` turns that off).
