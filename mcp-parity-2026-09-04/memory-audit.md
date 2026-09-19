# UNIT-COMPLETE: memory

**valid_as_of:** 2026-09-04
**stamp:** handoff re-probe after inventory
**provenance:** disk-verified (named files re-read; TCP+GET re-probed). Daemon was **not** started or restarted.
**receipt:** `C:\Users\Prekzursil\.agents\mcp-parity-2026-09-04\memory-audit.md`

## Goal

Audit the basic-memory path across Claude / Codex / Grok / Cursor / ZCode. Explain this Grok BM handshake failure (WorkerTransport / streamable HTTP) and why Cursor historically stayed red after watchdog restart. State whether memory currently works on each runtime.

## SSOT (re-read)

| Thing | Path / value |
|---|---|
| Contract | `C:\Users\Prekzursil\.agents\memory-contract.md` — only transport `http://127.0.0.1:18765/mcp`. Never `uvx` stdio. Never bind/restart BM unless the owner asks. |
| WHERE-map | `C:\Users\Prekzursil\.agents\memory-map.md` — vault `D:\basic-memory`; watchdog owns liveness; Cursor via `bm_cursor_http_session.py`. |
| Reliability | `C:\Users\Prekzursil\.agents\BASIC-MEMORY-RELIABILITY_2026-08-27.md` |
| Cursor shim | `C:\Users\Prekzursil\.agents\scripts\bm_cursor_http_session.py` — `DEFAULT_URL = http://127.0.0.1:18765/mcp`; parses SSE; re-initialize on `-32600 Session not found`. |
| Registry | `agents.json` `basic-memory` targets **codex, claude, zcode, hermes** (not grok). URL `:18765`. `x_cursor.stdio_bridge`. |
| Control plane | `VALID_TARGETS = {claude, codex, zcode, hermes}`. **No** `merge_generated_grok_mcp.py`. |
| Rail migrate | `C:\Users\Prekzursil\Cowork\output\rail-port-migrate-sota_2026-09-04.md` — Hyper-V excluded `:8765/:8812/:8317`. BM 8765→**18765**. Grok `config.toml` was not a migrate/sync target. |

## Live daemon (two independent probes, re-checked on handoff)

| Probe | `:8765` (Grok still dials) | `:18765` (SSOT) |
|---|---|---|
| TCP `TcpClient` | not connected | connected |
| `netstat` | no LISTENING on `127.0.0.1:8765` | `127.0.0.1:18765 LISTENING` PID **50552** |
| GET `/mcp` | connection **refused** | **HTTP 406** (healthy streamable-http without MCP Accept) |
| JSON-RPC `initialize` POST (`Accept: application/json, text/event-stream`) | not attempted (port dead) | **HTTP 200**, `Content-Type: text/event-stream`, `Mcp-Session-Id` present, SSE `event: message`, `serverInfo name=Basic Memory version=4.0.0b1`, protocol `2025-03-26` |

Processes: `basic-memory.exe` PID 32084 (~4.8 MiB stub) + listener Python 3.13 PID 50552 (~177 MiB). Launcher/watchdog `$Port = 18765`. Supervisor last start: `2026-09-04T22:27:47` `streamable-http on 127.0.0.1:18765`.

**Verdict:** shared BM MCP surface is **UP on :18765**. `:8765` is **dead**. Confidence: almost certain (~99%).

## Inventory receipt vs live (detector failure)

`mcp-parity-2026-09-04` claimed `BM-DOWN: 127.0.0.1:18765 TCP closed` and `GROK-BM-RAW-HTTP: raw HTTP to :18765`. Both strings are wrong as live facts.

Evidence in `mcp_runtime_parity_inventory.py`:

1. TCP map still probes **8765/8812/8317** (not 18765). Then `if not tcp["8765"]` emits a finding that **names 18765**. After migrate, 8765 is always closed, so the script **always** reports BM-DOWN even when 18765 is healthy. Hub GET to 18765 without MCP Accept is urllib `HTTPError` on **406**, which the reliability receipt already defines as alive.
2. Same script hardcodes the Grok finding as “raw HTTP to :18765” whenever transport is http/streamable-http. The same JSON records `memory.grok.url = http://127.0.0.1:8765/mcp`. Live `~\.grok\config.toml` is **8765**. Self-contradicting output = detector failure, not a port reading.

Treat inventory BM-DOWN / Grok-URL-18765 as **agent-claimed / buggy**, superseded by this disk-verified probe.

## Why this Grok session BM handshake failed (WorkerTransport / streamable HTTP)

**This session has no `basic-memory` tools.** Connected MCP here: cloudflare-docs, context7, deepwiki, firecrawl, google_drive, search-hub, tasks. That is the failed handshake, observed — not inferred.

Live Grok block (`C:\Users\Prekzursil\.grok\config.toml` lines 307–310):

```
[mcp_servers.basic-memory]
url = "http://127.0.0.1:8765/mcp"
type = "http"
enabled = true
```

Stacked causes:

1. **Sufficient, almost certain (~99%): wrong port.** Grok is **not** in `agents.json` targets / `VALID_TARGETS`; `sync_shared_state.ps1` never rewrites `.grok/config.toml`. The 04.09.2026 migrate updated contract, launcher, Cursor shim URL, Claude, Codex, ZCode — Grok kept the excluded `:8765`. WorkerTransport therefore opens streamable HTTP against a closed port (GET refused). G-11/G-99 keepers were BM+agent-mail; agent-mail is also stale (`url …:8812`, `enabled = false`).
2. **Second failure class, likely (~70%) even after a URL fix: raw HTTP client vs BM streamable-http.** Daemon is `basic-memory mcp --transport streamable-http`. Initialize is **SSE** (`text/event-stream`, `event: message` + JSON, plus `Mcp-Session-Id`). Cursor’s native HTTP client did **not** heal that; the estate added a stdio shim that parses SSE and re-`initialize`s on `-32600 Session not found`. Grok uses raw `type = "http"` with **no shim**. Inventory’s “WorkerTransport streamable HTTP” sentence is a **canned** finding (emitted whenever Grok BM transport is http/streamable-http), not a measured 18765 handshake. Grok was not pointed at 18765 in this audit. This session’s fail is fully explained by (1); (2) remains the reason a URL-only fix may still leave Grok red. Not independently reproduced on 18765 here.

Stale Grok stdio log `~\.grok\logs\mcp\basic-memory.stderr.log` is **07.08.2026** FastMCP **stdio** 3.3.1 — not this HTTP worker.

## Why Cursor historically stayed red after watchdog restart

Receipts: `BASIC-MEMORY-RELIABILITY_2026-08-27.md` + shim docstring + `merge_generated_cursor_mcp.py`.

1. Daemon dies under RAM / embedding stalls. Watchdog (`BasicMemory-Watchdog` ~3 min) + launcher (`BasicMemory-HTTP-MCP`) bring the port back. **Server recovery ≠ client recovery.**
2. Cursor **User-scope** MCP sat on stale `ECONNREFUSED 127.0.0.1:8765` after the port was healthy again; **project-scope** (same `~\.cursor\mcp.json` loaded twice because workspace root was `$HOME`) reconnected on its own. Server-fine-but-client-stale was reproduced the same morning as a valid initialize POST.
3. After a successful restart the new process issues a **new** `Mcp-Session-Id`. Cursor’s built-in HTTP client kept the old id → JSON-RPC `-32600 Session not found` while TCP/GET 406 looked green. Toggling MCP / reloading the window fixed the client; **restarting the daemon again did not**.
4. Fix (keep the benefit; do not strip HTTP): `x_cursor.stdio_bridge` runs `bm_cursor_http_session.py --stdio --url http://127.0.0.1:18765/mcp`. It never binds/kills the daemon; on Session not found it `initialize`s once more; it parses both JSON and SSE. Live Cursor mcp.json is that shim (G-6 core intact: agent-mail, basic-memory, chrome-devtools, context7, firecrawl, playwright).

## Per-runtime memory status (now)

Shared daemon: **WORKS** on `:18765`. Vault writer remains BM only (G-81). Cannot `write_note` from this Grok session (no BM tools).

| Runtime | Client config (disk) | Live handshake this audit | Works? |
|---|---|---|---|
| **Claude** | `.claude.json` `basic-memory` `type=http` `url=http://127.0.0.1:18765/mcp` | No Claude session in this process. Config matches SSOT. | **Path OK / live NOT-CHECKED.** Likely works in a Claude window that has already loaded MCP (~80%). |
| **Codex** | `.codex/config.toml` `[mcp_servers."basic-memory"]` `url=…:18765/mcp` `enabled=true` `startup_timeout_sec=10` | No Codex session probed. | **Path OK / live NOT-CHECKED.** |
| **Grok** | raw HTTP `type=http` **`:8765`**, enabled, not synced | This session: BM absent from tool inventory; `:8765` refused. | **NO. Broken in this session.** |
| **Cursor** | stdio shim → `:18765` | Cursor UI namespace not observed here. Daemon + shim path are the post-27.08 repair. After migrate, Cursor may still need one MCP refresh if the window cached the old URL/session. | **Path OK / live NOT-CHECKED.** Do not treat a red User-scope badge as daemon death. |
| **ZCode** | `~\.zcode\cli\config.json` `basic-memory.url=http://127.0.0.1:18765/mcp` | No ZCode session probed. **Second store:** `C:\Users\Prekzursil\.zcode\cli\memories\projects\` — 8 project dirs; `default-…/memory` **27** files; `phenibut-…/memory` **9** files; other six `memory/` dirs empty. Parallel local memory, not BM `write_note`. | **BM path OK / live NOT-CHECKED.** Native memories exist (G-81 adjacent second store). |

## Do not do

- Do not restart BasicMemory-HTTP-MCP / Watchdog from this finding.
- Do not rotate anything.
- A Grok fix is: point `[mcp_servers.basic-memory]` at `http://127.0.0.1:18765/mcp` **and** expect a session/SSE shim (or a Grok client that speaks streamable-http + session refresh). URL-only may not be enough. Out of scope for this unit.

SUCCESS:memory
