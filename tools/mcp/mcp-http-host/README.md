# mcp-http-host — SUPERVISE a shared stdio→HTTP MCP bridge (the per-session-process cure)

**What this is (post-re-scope — see [RESCOPE.md](RESCOPE.md)):** the commodity
stdio↔HTTP **transport** is the maintained **`mcp-proxy` npm** package; the value here
is the **supervision layer** (`run_host.ps1`) that runs it as ONE reaped, health-probed,
always-on shared instance per server — so *all* Claude Code / Codex sessions dial the
**one** running bridge instead of each spawning its own stdio copy. The in-repo
stdlib host (`mcp_http_host.py`) is retained **unchanged** as a no-Node fallback
(`-Bridge stdlib`). The split — mcp-proxy = transport, #159 = supervision — is the
whole point of the re-scope.

## The problem it cures

Every Claude Code session spawns its **own** stdio child for every server in the
config. With `S` concurrent sessions and `H` stdio servers that is `S × H`
base processes — before each server's own lazy backends. This is the measured
driver of the estate's RAM/commit pressure that hangs sessions (basic-memory
note *"Commit exhaustion = the freeze root cause" 2026-07-19*: per-session stdio
MCP duplication, "shared HTTP MCP" named as the cure, measured **2037 → 633
processes** — that estate number is the owner's note, cited here, **UNVERIFIED**
by this work).

**Measured live during this build** (`Get-CimInstance Win32_Process`, 2026-07-23):
**6** concurrent `search-hub` stdio copies were running at once — **5** were
sibling sessions each running their own per-session copy (the multiplication,
caught in the act), plus this POC's 1 shared child. Two servers already prove the
shared-HTTP model works on this box: **agent-mail** (`serve-http` on :8812) and
**basic-memory** (:8765) are single shared HTTP services, not per-session stdio.

## The bridge: mcp-proxy (transport) + `run_host.ps1` (supervision)

The stdio↔HTTP wire is a solved, commodity problem — this session proved the
maintained **`mcp-proxy` npm 6.5.4** fronts this box's `cmd /c npx` stdio servers (a
full MCP `initialize` + `tools/list` handshake succeeded through it). So the bridge is
no longer hand-built; `run_host.ps1` **supervises** mcp-proxy and adds the operational
layer mcp-proxy lacks. Two modes:

- **`-Bridge mcp-proxy` (default)** — launch mcp-proxy via `npx.cmd` with a PINNED
  `--host 127.0.0.1` (mcp-proxy defaults to `::`/IPv6, which *refuses* loopback) and
  `--shell` (so a `cmd /c npx -y <server>` child spawns), wrapping the
  `-ChildCommand`. mcp-proxy serves **both** a Streamable-HTTP endpoint (`/mcp`) and an
  SSE endpoint (`/sse`) at once.
- **`-Bridge stdlib`** — the no-Node fallback: launch the in-repo `mcp_http_host.py`
  (below), **unchanged**, wrapping `tools/mcp/<Server>/hub.py`.

What the supervisor contributes on top of the transport:

| Capability | What it does |
|---|---|
| **port-scoped reap** | kills only the target port's owner **and its children first**, never machine-wide |
| **`-Status`** | the spawn-count invariant (exactly **1** bridge owns the port) + `/healthz` when stdlib |
| **`-InstallTask` / `-UninstallTask`** | a per-user logon Scheduled Task `McpHttpHost-<Port>` (mirrors `MCPAgentMailSupervisor`) for always-on |
| **`-DryRun`** | print the exact argv, launch nothing |

## Claude Code *can* dial a shared HTTP endpoint (this is the key enabling fact)

From the official docs (code.claude.com/docs/en/mcp):

- `claude mcp add --transport http <name> <url>` registers an HTTP server; add
  `--scope project` to write `.mcp.json`, `--scope user` to write `~/.claude.json`.
- In JSON the entry is `{"type": "http", "url": "http://127.0.0.1:<port>/mcp"}`.
  `type` accepts **`streamable-http`** as an alias for `http`.
- **`type` is mandatory:** an entry with a `url` but no `type` is a *config error*
  — Claude reads it as a stdio server and skips it. (This is why `apply_registration.py`
  always writes an explicit `"type"` — `"http"` for `--transport http`, `"sse"` for
  `--transport sse`.)
- Transport = MCP **Streamable HTTP** (spec revision 2025-11-25): the client POSTs
  JSON-RPC to one endpoint; the server answers `application/json` (single response)
  or `text/event-stream` (SSE), and may issue an `Mcp-Session-Id` on `initialize`.

So the migration is purely a **config swap** from `type: stdio` → `type: http`,
plus one long-lived shared host per migrated server.

## The stdlib fallback — how `mcp_http_host.py` works (`-Bridge stdlib`)

This is the **no-Node** transport, kept unchanged as the fallback for when npx is
unavailable; it is also what `-Status`'s `/healthz` probe reads.

```
S sessions ──HTTP──►  [ mcp_http_host ]  ──one stdio pipe──►  [ one hub child ]
   (type: http)         (127.0.0.1:PORT)                        (spawned ONCE)
```

- Spawns **one** stdio child and keeps it alive; a reader thread pumps its stdout
  into a queue so a hung backend surfaces as a bounded `TimeoutError`, never a
  stuck lock (the failure mode `../social-hub/hub.py` designs around).
- `POST /mcp` forwards a JSON-RPC request to the child and returns its response as
  `application/json`; a notification (no `id`) returns `202 Accepted`.
- `GET /healthz` reports `host_pid`, `child_pid`, `child_spawn_count`,
  `requests_served` — `child_spawn_count` is the load-bearing invariant: it stays
  **1** no matter how many clients connect.
- stdlib only (`http.server` + `subprocess` + `threading`), UTF-8 pipes, binds
  `127.0.0.1` only. Runs on the bundled `C:\Python314\python.exe`.

### Process delta

For one migrated server across `S` sessions: **`S` stdio copies → `1` shared
child** (removes `S − 1` copies, and its lazy backends spawn once instead of once
per session). Migrating the three hubs (`cloud-hub`, `social-hub`, `search-hub`)
across `S` sessions removes `3·(S − 1)` hub base processes; at the `S = 5` observed
live that is **12 fewer** hub processes, growing with every session — plus the
backend fan-out those hubs spawn is de-duplicated from per-session to once.

## Proof (the stdlib fallback is a PROVEN proof-of-concept)

- **52 tests pass** (`python -m pytest tests/`) — 24 for the stdlib host (96–99% line
  coverage), 16 for the apply tool (incl. the `--transport sse` path), 12 pinning the
  fake Streamable-HTTP daemon below. Includes a CONTROL test asserting the status quo:
  **N direct stdio spawns → N distinct pids**.
  (The mcp-proxy *transport* is proven separately by this session's live handshake;
  the supervisor's reap / `-Status` / `-DryRun` were verified on-box — see RESCOPE.md.)
- **Live HTTP handshake** against the real `search-hub` over this host:
  `initialize` → `{"serverInfo":{"name":"search-hub","version":"0.1.0"},
  "protocolVersion":"2025-06-18"}`; `tools/list` → **68 tools**.
- **Two clients, one process:** two separate `POST /mcp` `initialize` calls, then
  `GET /healthz` → same `child_pid=70804`, `child_spawn_count=1`, `requests_served=2`.
  Two HTTP clients were served by the ONE child, spawned exactly once.

## Quick start

```powershell
# 1. Supervise the bridge. DEFAULT = mcp-proxy transport (foreground). -DryRun previews argv.
.\run_host.ps1 -Port 8900 -ChildCommand 'cmd /c npx -y <server>'
#    no-Node fallback:  .\run_host.ps1 -Bridge stdlib -Server search-hub -Port 8900
#    status + health:   .\run_host.ps1 -Port 8900 -Status
#    always-on (logon): .\run_host.ps1 -Port 8900 -ChildCommand 'cmd /c npx -y <server>' -InstallTask
```

```bash
# 2. Point ~/.mcp.json at it (APPLY-WHEN-CLOSED — dry-run first). mcp-proxy serves BOTH
#    endpoints, so register whichever transport you want:
python apply_registration.py --server search-hub --port 8900                          # http → /mcp (preview)
python apply_registration.py --server search-hub --port 8900 --apply                  # write + backup
python apply_registration.py --server search-hub --port 8900 --transport sse --apply  # sse  → /sse

# 3. Promote ~/.mcp.json to ~/.claude.json (your usual no-drift promote) and
#    restart Claude. Undo any time:  python apply_registration.py --revert-from <backup>
```

## Why mcp-proxy (and not supergateway or a hand-built host as *the* transport)

`mcp-proxy` npm 6.5.4 is the adopted commodity transport: it was proven this session to
front this box's `cmd /c npx` stdio servers, serves SSE **and** Streamable-HTTP at once,
and is maintained — so there is no reason to hand-maintain the wire. The community
**`supergateway`** (`npx -y supergateway --stdio "<cmd>" --outputTransport streamableHttp
--port 8000`) is an equivalent drop-in transport; `mcp-remote` is the inverse (dial a
remote HTTP MCP, expose it locally over stdio). The in-repo **`mcp_http_host.py`** is no
longer positioned as *the* transport — it is the **`-Bridge stdlib`** fallback for when
Node/npx is unavailable (npx spawns were failing on this box earlier), and it is what the
supervisor's `/healthz` status probe reads. In every case the differentiated part is the
**supervision** (`run_host.ps1`), not the wire.

## Scope & honest caveats

- **Best fit: stateless / session-agnostic servers.** The hubs answer `initialize`
  / `tools/list` from committed caches and hold no per-connection state, so one
  shared child serving many clients is safe. A strongly **stateful** server should
  instead expose its **own native** streamable-HTTP mode (like agent-mail /
  basic-memory) and be run once — don't share a stateful stdio child. `likely`
  (55-80%) that all three current hubs are safe to share; verify per server before
  flipping it.
- **Single pipe ⇒ serialized round-trips.** Requests to the one child are lock-
  serialized (correct, but not parallel within a child). Fine for interactive MCP
  call rates; a throughput-bound server wants native HTTP concurrency.
- **`Mcp-Session-Id` is advisory** here — issued on `initialize`, not used to route
  (one shared child). Server→client server-initiated notifications are not
  multiplexed (the hubs don't send any).
- **Apply-when-closed.** `~/.claude.json` is rewritten live every ~30s; never hand-
  edit it. Edit the canonical `~/.mcp.json` (this tool does) and promote/restart.
- **Not auto-flipped.** This PR ships the host + tests + apply tool; it does **not**
  change the live config. The owner runs `apply_registration.py --apply` when ready.

## Files

| File | Purpose |
|---|---|
| `run_host.ps1` | **the supervisor**: `-Bridge mcp-proxy`/`stdlib` modes, port-scoped children-first reap, `-Status`, `-DryRun`, `-InstallTask`/`-UninstallTask` logon task |
| `RESCOPE.md` | why the pivot: mcp-proxy = transport, #159 = supervision |
| `mcp_http_host.py` | the **stdlib fallback** stdio→HTTP host (run it, or `import build_server`) |
| `apply_registration.py` | apply-when-closed `~/.mcp.json` stdio→{http,sse} editor (`--transport`, dry-run/apply/revert) |
| `smoke_stdio.py` | drive any stdio MCP command through the wrapper (serverInfo + tool count) |
| `_fake_mcp_server.py` | minimal stdio MCP server used as the deterministic test fixture |
| `_fake_streamable_http_daemon.py` | the same fixture behind the MCP Python SDK's Streamable-HTTP session semantics (sessions, 404 + `-32600 Session not found` on a stale id, `restart()`, refused window, JSON/SSE, GET stream) — the stand-in for the Basic Memory `:8765` daemon |
| `tests/` | 52 tests: HTTP handshake, shared-child invariant, apply-tool round-trip incl. `--transport sse`, fake-daemon contract |

## Basic Memory (`:8765`): the shared daemon that restarts under you

The daemon on `:8765` is already the shared-HTTP model this lane argues for — and it
dies under RAM pressure near-daily, so its *clients* need to survive a restart.
Cursor's does not (stale `mcp-session-id` → `-32600 Session not found`; stale
`ECONNREFUSED`). The decision, the measured criteria matrix, the memory numbers and
the deploy/rollback steps are in
[`docs/plans/2026-09-02-basic-memory-transport-decision.md`](../../../docs/plans/2026-09-02-basic-memory-transport-decision.md):

- **Chosen (shipped):** a registry-declared per-session stdio shim for Cursor,
  `.agents/scripts/bm_cursor_http_session.py`, rendered by
  `merge_generated_cursor_mcp.py` from `x_cursor.stdio_bridge` and tested against
  `_fake_streamable_http_daemon.py` here.
- **Proposed (needs owner approval, not built):** a session-healing reverse proxy in
  *this* lane that owns `:8765` with the daemon moved behind it — uniform healing
  for Cursor, Claude and Codex with one process and no client config change, at the
  price of changing who binds `:8765`.

Rehearse a client against a restarting daemon without touching the real one:
`python _fake_streamable_http_daemon.py --port 8799 --mode sse --restart-every 20`.

## Dev

```bash
python -m pytest tests/ --cov=mcp_http_host --cov=apply_registration --cov-report=term-missing
uvx ruff@0.15.17 format --check . && uvx ruff@0.15.17 check .   # CI-pinned gate
```

## References

- Claude Code MCP transports/scopes: https://code.claude.com/docs/en/mcp
- MCP Streamable HTTP transport: https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- mcp-proxy (adopted stdio↔HTTP transport): https://github.com/punkpeye/mcp-proxy
- supergateway (equivalent stdio↔HTTP bridge): https://github.com/supercorp-ai/supergateway
- estate precedent (owner note, UNVERIFIED here): basic-memory `commit-exhaustion-root-cause-2026-07-19`
