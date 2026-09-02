# Basic Memory transport: decision record and reverse-proxy proposal (2026-09-02)

**Decision:** Cursor talks to the shared Basic Memory daemon through a
**registry-declared per-session stdio bridge** (`x_cursor.stdio_bridge` on the
`basic-memory` entry, rendered by `merge_generated_cursor_mcp.py`). Claude and
Codex keep the direct URL. The always-on session-healing reverse proxy that would
own `:8765` is written up below as a **proposal** that needs the owner's explicit
approval; Basic Memory's stateless mode and "direct URL only" are ruled out on
evidence. Nothing here touches the daemon, `:8765`, semantic search or a secret.

## 1. The problem, with the evidence it rests on

| Fact | Source |
|---|---|
| The daemon dies under RAM pressure near-daily; the watchdog restarts it (3-min cycle), and a relaunch takes **2.5-4 min** to bind under load. | `.agents/BASIC-MEMORY-RELIABILITY_2026-08-27.md` ("Flap root cause", "10-min stability probe") |
| After a restart Cursor's User-scope client **sat on a stale `ECONNREFUSED`** while the port was already serving; a stale `mcp-session-id` yields **`-32600 Session not found`** while the port is healthy. | same receipt, "Root cause of the 27.08 incident" and "Client-side check" |
| The MCP Python SDK (FastMCP, therefore Basic Memory 3.x) answers a stale id with **HTTP 404** whose body is `{"jsonrpc":"2.0","id":null,"error":{"code":-32600,"message":"Session not found"}}`; newer SDKs also expire idle sessions (`session_idle_timeout`, 30 min default). | [py.sdk.modelcontextprotocol.io/troubleshooting](https://py.sdk.modelcontextprotocol.io/troubleshooting/), `streamable_http_manager.py` |
| The TypeScript SDK's `StreamableHTTPClientTransport` (Cursor's and Claude Code's client family) does **not** clear the session or re-initialize on that 404: "the client is stuck until it's destroyed and recreated". Issue **open** since 2026-03-19; fix PRs #1718 (closed, unmerged) and #2150 (open) had not shipped when this was written. | [typescript-sdk#1708](https://github.com/modelcontextprotocol/typescript-sdk/issues/1708), verified with `gh issue view` on 2026-09-02 |
| The estate doctrine: basic-memory `:8765` is **one shared HTTP service, not per-session stdio**; per-session *server* copies are what exhausted commit (2037 -> 633 processes). | `tools/mcp/mcp-http-host/README.md` |
| The memory contract: the **only** transport is `http://127.0.0.1:8765/mcp`; never spawn a second daemon; never bind `:8765` yourself; never disable semantic search; `:8765` stays bound only by its owner. | `memory-contract.md` on `live-capture/2026-09-02` |
| PR #293 made the Cursor merge registry-authoritative and rendered the **bare URL**; the working interim on the box - `scripts/bm_cursor_http_session.py --stdio` - was off-registry and untracked, so `--check` flagged it as drift forever. | [PR #293](https://github.com/Prekzursil/agent-skills-toolchain/pull/293); `tests/test_bm_cursor_http_session.py` on `live-capture/2026-09-02` |
| Basic Memory's CLI exposes **no stateless flag**: `bm mcp` takes `--transport/--host/--port/--path/--project` and constructs `FastMCP(name=..., instructions=..., lifespan=...)` without `stateless_http`. | `src/basic_memory/cli/commands/mcp.py`, `src/basic_memory/mcp/server.py` (upstream main) |

Two windows therefore have to be survived, and both are **client-side** defects
against a server that is behaving per spec:

1. **Stale-session window** - port healthy, every session id from before the
   restart answers 404/-32600. A compliant client re-initializes; Cursor's does not.
2. **Dead-port window** - 3 to 7 minutes of `ECONNREFUSED` (watchdog cycle plus
   warm-up), plus the "bound but HTTP-unresponsive" strikes while embeddings
   starve the event loop. Cursor's client marks the server red and stays red.

## 2. Candidates against the criteria

| Criterion | (a) registry-declared per-session bridge | (b) session-healing proxy owning `:8765` | (c) Basic Memory stateless mode | (d) direct URL only |
|---|---|---|---|---|
| Survives stale-session window | **yes** - re-initialize + replay once (tested) | yes - same logic, one place | yes (no session ids) - but see "supported" | **no** (typescript-sdk#1708) |
| Survives dead-port window | **yes** - `initialize`/`tools/list`/`ping` from cache, `tools/call` returns a readable `isError`, heals on next call or by probe (tested) | yes - clients never see `ECONNREFUSED` on `:8765` | **no** - port still dead during warm-up | **no** (measured 27.08) |
| No discovery loss | **yes** - cached discovery + `tools/list_changed` after recovery | yes - same cache in the proxy | no | no |
| RAM (measured/estimated, see section 5) | ~17 MiB private per Cursor window; **never** spawns a daemon | ~20-25 MiB private, one process | 0 client-side; per-request session construction on the daemon (CPU) | 0 |
| Registry-authoritative | **yes** - `x_cursor.stdio_bridge`, URL single-sourced, `--check` green | yes - URL unchanged | yes | yes |
| Uniform across Cursor/Claude/Codex | Cursor only; the same shim is declarable per target if Claude shows the symptom (short-lived CLI sessions have not) | **yes**, no client config change | yes | yes |
| Moving parts added | 1 script per Cursor window; **no** port move, task or daemon edit | 1 always-on process + 1 scheduled task + **daemon port move** + 2 owner-script edits + contract amendment | daemon launcher patch off the supported CLI path | 0 |
| Owner approval needed | no (registry + merge, rollback is one key) | **yes** - changes who binds `:8765` | yes - daemon config change | no |
| Testable here | **yes** - 26 tests against the fake daemon | yes (same fixture; not built) | no (needs a live daemon; unsupported anyway) | n/a |

**Why (a) wins now.** It is the only candidate that survives both windows *and*
is deployable by the owner with a registry edit already tracked in `main`,
without touching who owns `:8765`. Its one cost - a small process per Cursor
window - is the client-side shim, not a second server: it dials
`http://127.0.0.1:8765/mcp` and nothing else, never binds a port, never
starts or kills a daemon, and matches none of the daemon's `processMatch`
tokens (pinned by test), so the doctrine's actual concern (per-session *server*
copies at ~843 MiB each) is untouched. PR #293's finding that the bridge
"inverts the doctrine" was about it being off-registry and force-enabled by the
merge; both holes are closed here (the registry declares it, `--check` is green
with it and red without it).

**Why (b) is a proposal, not a change.** It is the better end-state for
uniformity - one process heals every client and no client config changes - but
it moves the daemon off `:8765`, hands the port to a new process, and needs the
watchdog probe and the memory contract rewritten to name the new owner. The
contract says `:8765` stays bound only by its owner; that is an owner decision.
Section 7 gives it deploy and rollback steps so it can be approved as written.

**Why (c) is out.** Not a supported configuration of Basic Memory (no CLI flag,
`FastMCP(...)` constructed without `stateless_http`); it would need a custom
launcher importing the server object and pinning FastMCP internals across
upgrades. And it does nothing for the dead-port window, which is the longer one.
It also drops server->client notifications (no GET stream in stateless mode).

**Why (d) is out.** It is the measured failure state (27.08 receipt) and the
state PR #293 rendered.

## 3. What this PR implements

- **Registry shape** (`.agents/agents.json`): `basic-memory.x_cursor.stdio_bridge =
  {command: C:\Python314\python.exe, args: [C:\Users\Prekzursil\.agents\scripts\bm_cursor_http_session.py, --stdio]}`.
  `mcp_control_plane.validate_registry` enforces a closed schema (only
  `stdio_bridge`; http servers only; command required; args a string list; no
  headers/bearer; no literal credential). Rationale lives in
  `.provenance/.agents/agents.json.md`, not in the manifest.
- **Renderer** (`merge_generated_cursor_mcp.py`): renders
  `{"command": ..., "args": [..., "--url", "<registry url>"]}` - the URL is
  appended from the registry and never repeated, so the shim can only point at
  the daemon the registry declares. `--check` treats the bare URL *and* the
  pre-registry hand edit (no `--url`) as drift; `--write` normalizes either.
  Rendering is OS-independent, so `--check` agrees on this entry from Linux too.
  Claude/Codex renderers ignore the key.
- **Bridge** (`.agents/scripts/bm_cursor_http_session.py`, tracked from
  `live-capture/2026-09-02` then hardened): SSE parsed event by event with
  preludes relayed; `TransportUnavailable` (an `OSError`) on refused/reset/hung
  with one quick handshake retry for fast failures only (a 30 s timeout is not
  retried at once); discovery cache in `%TEMP%`; local answers while down and a
  5 s post-failure cooldown for cheap requests (`tools/call` always tries, it is
  the healing path); `tools/list_changed` after healing; background recovery probe;
  GET server->client stream held and relayed, its EOF used as the early
  "restarted" signal; `DELETE` on exit; `--health` beside `--call`.
- **Fixture** (`tools/mcp/mcp-http-host/_fake_streamable_http_daemon.py`): the
  SDK's session semantics over `_fake_mcp_server.handle()` - sessions, the exact
  404 body, `restart()`, `stop()`/`start()` refused window on the same port,
  JSON and chunked SSE with preludes, GET streams (406 without the SSE Accept,
  like the on-box probe), `DELETE`. 12 pinning tests; runnable standalone.

Tests: `.agents/tests` **63 passed, 8 skipped** (26 bridge, 8 new control-plane);
`tools/mcp/mcp-http-host` **52 passed**. The bridge suite was stable across 61
sequential and 24 concurrent runs.

## 4. Known limits of the chosen design

- One shim per Cursor window (the RAM row above). Two windows ~35 MiB private.
- The shim serializes Cursor's requests to the daemon (one at a time), like the
  interim did; a long `search_notes` delays a concurrent `ping` by that much.
- A server->client *request* (`roots/list`, sampling, elicitation) arriving
  **inside** a tool call's own SSE stream cannot be answered until that call
  returns (single stdio loop). Basic Memory issues none today; the GET-stream
  path (outside a call) is fully relayed and answered.
- The GET stream is held with a 300 s read timeout and reconnects; if the real
  daemon ever answers it with 409 loops, `--no-stream` in
  `x_cursor.stdio_bridge.args` turns it off with no other change.
- Claude and Codex are unchanged. If Claude Code (same SDK family) shows the
  stale-session symptom, declaring the same shim per target is a renderer-only
  change; it is deliberately not done without evidence.

## 5. Memory per approach

Measured on this runner (CPython 3.12.3, Linux) with the bridge serving a
Cursor-like session against the fake daemon (initialize, tools/list, 50 tool
calls, then a restart, a refused window and a recovery):

| Process | RSS | PSS | Private | Notes |
|---|---|---|---|---|
| empty `python3` | 10 MiB | 5 MiB | 3 MiB | baseline |
| `import urllib.request` | 23 MiB | 16 MiB | 12 MiB | the stdlib HTTP stack pulls `ssl` |
| **bridge, steady state** | **29.8 MiB** | ~19 MiB | **~16-17 MiB** | 2 threads (GET stream + stdio loop); `--no-stream` saves nothing measurable |
| bridge after restart/refused/recover | 29.9 MiB | - | - | `VmHWM == VmRSS`: no growth across the failure cycle |

"Private" is the figure comparable to the Windows *private bytes* the fleet
supervisor budgets; Windows CPython 3.14 is expected in the same band (+/-5 MiB).

| Approach | Client-side RAM | Daemon-side | Comment |
|---|---|---|---|
| (a) bridge | ~17 MiB private per Cursor window (~30 MiB RSS) | 0 | measured above; 2 windows ~35 MiB; 2-4% of the daemon's own ~843 MiB |
| (b) proxy on `:8765` | ~20-25 MiB private, one process (bridge stack + `http.server`; ~0.1 MiB per open client stream thread) | 0 | estimate: bridge measurement + `mcp_http_host.py`'s ThreadingHTTPServer; cheaper than (a) only from the second Cursor window |
| (c) stateless | 0 | a fresh server session per request (CPU, RAM-neutral) | unsupported by the BM CLI |
| (d) direct | 0 | 0 | fails both windows |

The daemon itself is unchanged in every case (registry `maxPrivateBytes`
1 GiB, measured warm ~843 MiB).

## 6. Deploy and rollback on the Windows box - chosen design (a)

The live SSOT is `C:\Users\Prekzursil\.agents` (registry, scripts); fold the
four changed files from `main` into it the usual way (`agents.json`,
`scripts\bm_cursor_http_session.py`, `scripts\merge_generated_cursor_mcp.py`,
`scripts\mcp_control_plane.py`). Then, in `pwsh`:

```powershell
$A = 'C:\Users\Prekzursil\.agents'
# 0. Preflight, read-only. Exit 1 = daemon down: wait for the watchdog, do not restart it.
python "$A\scripts\bm_cursor_http_session.py" --health           # "ok": true, serverInfo.name "Basic Memory"
python "$A\scripts\merge_generated_cursor_mcp.py" --check        # expect FAILED drift=1 servers=basic-memory (hand edit lacks --url)

# 0b. Optional rehearsal with no real daemon involved (second terminal):
#   python <toolchain>\tools\mcp\mcp-http-host\_fake_streamable_http_daemon.py --port 8799 --mode sse --restart-every 20
#   python "$A\scripts\bm_cursor_http_session.py" --health --url http://127.0.0.1:8799/mcp

# 1. Apply: validates the registry, publishes views, merges Codex/Claude/Cursor, backs up mcp.json.bak-<ts>.
pwsh -File "$A\scripts\sync_shared_state.ps1"
#    (or only the Cursor file:  python "$A\scripts\merge_generated_cursor_mcp.py" --write)

# 2. Verify
python "$A\scripts\merge_generated_cursor_mcp.py" --check        # SUCCESS drift=0 managed=6
Get-Content "$env:USERPROFILE\.cursor\mcp.json" | Select-String -Context 0,6 '"basic-memory"'   # command + args ending in --url http://127.0.0.1:8765/mcp
# Cursor: Settings -> MCP -> basic-memory: refresh/toggle, or reload the window. Tools list populates.
Test-Path "$env:TEMP\bm-cursor-http-session-cache.json"          # True after the first tools/list

# 3. Observe the next watchdog restart
Get-Content "$A\logs\basic-memory-supervisor.log" -Tail 20      # a [watchdog] force-recover + [launcher] starting
# Cursor stays green; a tool call during warm-up returns the "not reachable ... retry shortly" isError text; the next call succeeds.
```

Rollback (one key, no daemon/port/task/secret involved):

```powershell
# Either restore the automatic backup:
Copy-Item "$env:USERPROFILE\.cursor\mcp.json.bak-<ts>" "$env:USERPROFILE\.cursor\mcp.json"
# or remove "x_cursor" from mcp.servers.basic-memory in $A\agents.json and re-render:
python "$A\scripts\merge_generated_cursor_mcp.py" --write        # Cursor is back on {"url": "http://127.0.0.1:8765/mcp"}
# then reload the Cursor window. `--check` is green again against the reverted registry.
```

Contract compliance: the shim dials `http://127.0.0.1:8765/mcp` only, never
binds `:8765`, never starts or kills the daemon, never touches semantic search.
The `--stdio` shim is Cursor's MCP *client adapter*, not a stdio spawn of
basic-memory.

## 7. Proposal (b): session-healing reverse proxy owning `:8765` - NOT DONE

Status: **proposal only.** It changes who binds `:8765`, so it needs the
owner's explicit approval before anything below is executed. Nothing in this PR
implements or deploys it.

### Design

```
Cursor / Claude / Codex ──http──► 127.0.0.1:8765  bm-session-proxy (always-on, supervised)
                                        │  one upstream BmHttpSession per client session
                                        ▼
                                  127.0.0.1:8766  basic-memory streamable-http (moved)
```

- **Client-facing sessions are stable.** The proxy issues its own
  `Mcp-Session-Id` and keeps it valid for the client's lifetime. Each maps to an
  upstream session that the proxy re-initializes transparently on 404/-32600,
  reset or refused, replaying the request once (the `BmHttpSession` class
  already does this; it is the upstream leg).
- **Nobody sees `ECONNREFUSED` on `:8765` again.** During the dead-port window
  the proxy answers `initialize` / `tools/list` / `ping` from the same discovery
  cache and returns `tools/call` as a readable `isError` result; the TS SDK
  client therefore never enters its stuck state. On recovery it pushes
  `notifications/tools/list_changed` to every client GET stream when the list
  changed.
- **GET streams are decoupled.** The client's GET stream stays open across
  upstream restarts; the proxy re-opens its upstream GET quietly and relays.
- **DELETE** terminates both legs. `405` upstream is tolerated.
- Lives in `tools/mcp/mcp-http-host/` (the shared-HTTP-service lane), supervised
  by the lane's `run_host.ps1 -InstallTask` pattern (per-user logon task,
  restart-on-failure, port-scoped reap). ~400 lines plus tests that reuse the
  fake daemon: everything the bridge suite proves, plus N concurrent clients
  and client-stream continuity across an upstream restart.

### What changes on the box (why approval is needed)

1. `C:\Users\Prekzursil\.basic-memory\bm-http-server.ps1`: daemon port `8765 -> 8766`.
2. `C:\Users\Prekzursil\.basic-memory\bm-watchdog.ps1`: probe URL `-> :8766` (the
   watchdog must measure the daemon, not the proxy).
3. New logon task `McpHttpHost-8765` running the proxy (upstream `:8766`).
4. `memory-contract.md`: "`:8765` stays bound only by its owner" - the owner
   becomes the proxy; the client URL stays `http://127.0.0.1:8765/mcp`.
5. Registry: remove `x_cursor` from `basic-memory` (Cursor returns to the direct
   URL, which is now the proxy); optionally `processMatch` for the proxy so the
   fleet supervisor budgets it.

### Deploy (after approval)

```powershell
$BM = 'C:\Users\Prekzursil\.basic-memory'
# 0. Backups first, the receipt's convention
Copy-Item "$BM\bm-http-server.ps1" "$BM\backups\bm-http-server.ps1.bak_<date>"
Copy-Item "$BM\bm-watchdog.ps1"    "$BM\backups\bm-watchdog.ps1.bak_<date>"
# 1. Staging: run the proxy on :8767 in front of the live :8765 for a day; point ONE Cursor
#    entry at http://127.0.0.1:8767/mcp; verify with bm_cursor_http_session.py --health --url ...:8767/mcp
# 2. Cutover, in this order (a quiet moment; the daemon is down for one warm-up):
Stop-ScheduledTask 'BasicMemory-Watchdog'; Stop-ScheduledTask 'BasicMemory-HTTP-MCP'
#    edit bm-http-server.ps1 (port 8766) and bm-watchdog.ps1 (probe :8766)
Start-ScheduledTask 'BasicMemory-HTTP-MCP'         # wait for bind (2.5-4 min under load)
python <toolchain>\.agents\scripts\bm_cursor_http_session.py --health --url http://127.0.0.1:8766/mcp
#    start the proxy task on :8765 (upstream :8766); then
python <toolchain>\.agents\scripts\bm_cursor_http_session.py --health   # via the proxy on :8765
Start-ScheduledTask 'BasicMemory-Watchdog'
# 3. Registry: drop x_cursor, run sync_shared_state.ps1, reload Cursor. --check must read drift=0.
```

### Rollback

```powershell
# stop the proxy task; restore both .ps1 backups (port 8765, probe :8765);
Start-ScheduledTask 'BasicMemory-HTTP-MCP'; Start-ScheduledTask 'BasicMemory-Watchdog'
# re-add x_cursor.stdio_bridge in agents.json if Cursor should keep the bridge; sync; reload Cursor.
```

### Risks to weigh

- The proxy is a new single point in every client's path; it is tiny and
  allocation-free at rest, but it must be supervised as carefully as the daemon
  (the lane's task pattern) or a proxy death is a total outage.
- A lower-approval variant exists: proxy on a **new** port with the daemon left
  on `:8765`. It avoids the port move and the launcher/watchdog edits but changes
  the client URL for all three clients and still amends the contract line
  "the only transport is `:8765`".
- RAM: one process ~20-25 MiB private vs (a)'s ~17 MiB per Cursor window - a
  saving only from the second window; the reason to do (b) is uniformity, not RAM.
