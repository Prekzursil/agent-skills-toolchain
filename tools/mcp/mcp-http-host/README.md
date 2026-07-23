# mcp-http-host — share ONE stdio MCP server across every session (the per-session-process cure)

A minimal, stdlib-only host that stands a **stdio** MCP server up as a **shared
Streamable-HTTP endpoint** so *all* Claude Code / Codex sessions dial the **one**
running instance instead of each spawning its own copy.

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

## Claude Code *can* dial a shared HTTP endpoint (this is the key enabling fact)

From the official docs (code.claude.com/docs/en/mcp):

- `claude mcp add --transport http <name> <url>` registers an HTTP server; add
  `--scope project` to write `.mcp.json`, `--scope user` to write `~/.claude.json`.
- In JSON the entry is `{"type": "http", "url": "http://127.0.0.1:<port>/mcp"}`.
  `type` accepts **`streamable-http`** as an alias for `http`.
- **`type` is mandatory:** an entry with a `url` but no `type` is a *config error*
  — Claude reads it as a stdio server and skips it. (This is why `apply_registration.py`
  always writes `"type": "http"`.)
- Transport = MCP **Streamable HTTP** (spec revision 2025-11-25): the client POSTs
  JSON-RPC to one endpoint; the server answers `application/json` (single response)
  or `text/event-stream` (SSE), and may issue an `Mcp-Session-Id` on `initialize`.

So the migration is purely a **config swap** from `type: stdio` → `type: http`,
plus one long-lived shared host per migrated server.

## How `mcp_http_host.py` works

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

## Proof (this is a PROVEN proof-of-concept)

- **34 tests pass**, 96–99% line coverage (`python -m pytest tests/`). Includes a
  CONTROL test asserting the status quo: **N direct stdio spawns → N distinct pids**.
- **Live HTTP handshake** against the real `search-hub` over this host:
  `initialize` → `{"serverInfo":{"name":"search-hub","version":"0.1.0"},
  "protocolVersion":"2025-06-18"}`; `tools/list` → **68 tools**.
- **Two clients, one process:** two separate `POST /mcp` `initialize` calls, then
  `GET /healthz` → same `child_pid=70804`, `child_spawn_count=1`, `requests_served=2`.
  Two HTTP clients were served by the ONE child, spawned exactly once.

## Quick start

```bash
# 1. Run the shared host (foreground) wrapping a hub:
python mcp_http_host.py --eager --port 8900 -- \
    C:/Python314/python.exe C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/search-hub/hub.py
# health:  curl http://127.0.0.1:8900/healthz

# 2. Point ~/.mcp.json at it (APPLY-WHEN-CLOSED — dry-run first):
python apply_registration.py --server search-hub --port 8900          # preview
python apply_registration.py --server search-hub --port 8900 --apply  # write + backup

# 3. Promote ~/.mcp.json to ~/.claude.json (your usual no-drift promote) and
#    restart Claude. Undo any time:  python apply_registration.py --revert-from <backup>
```

On Windows the launcher `run_host.ps1 -Server search-hub -Port 8900` wraps step 1;
for **always-on** register it as a logon Scheduled Task exactly like
`MCPAgentMailSupervisor` (see run_host.ps1 header).

## Alternative bridge: supergateway (batteries-included)

The same stdio→HTTP bridge without this repo's host, using the community
`supergateway` (Node): from its README,
`npx -y supergateway --stdio "<cmd>" --outputTransport streamableHttp --port 8000`
serves `http://localhost:8000/mcp` (`--stateful --sessionTimeout` for per-session
state; on Windows launch via `cmd /c npx`). `mcp-remote` is the inverse (dial a
remote HTTP MCP, expose it locally over stdio). This host is preferred here because
it is stdlib-only (no Node/npx — npx spawns were failing on this box), testable,
and matches the hubs' stdlib ethos; supergateway is the drop-in if you want the
maintained project.

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
| `mcp_http_host.py` | the shared stdio→HTTP host (run it, or `import build_server`) |
| `apply_registration.py` | apply-when-closed `~/.mcp.json` stdio→http editor (dry-run/apply/revert) |
| `run_host.ps1` | Windows launcher + always-on Scheduled-Task recipe |
| `smoke_stdio.py` | drive any stdio MCP command through the wrapper (serverInfo + tool count) |
| `_fake_mcp_server.py` | minimal stdio MCP server used as the deterministic test fixture |
| `tests/` | 34 tests: HTTP handshake, shared-child invariant, apply-tool round-trip |

## Dev

```bash
python -m pytest tests/ --cov=mcp_http_host --cov=apply_registration --cov-report=term-missing
uvx ruff@0.15.17 format --check . && uvx ruff@0.15.17 check .   # CI-pinned gate
```

## References

- Claude Code MCP transports/scopes: https://code.claude.com/docs/en/mcp
- MCP Streamable HTTP transport: https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- supergateway (stdio↔HTTP bridge): https://github.com/supercorp-ai/supergateway
- estate precedent (owner note, UNVERIFIED here): basic-memory `commit-exhaustion-root-cause-2026-07-19`
