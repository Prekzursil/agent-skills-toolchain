---
title: RESCOPE
type: note
permalink: dqverify-repo-20261013/tools/mcp/mcp-http-host/rescope
---

# RESCOPE — mcp-proxy is the transport; #159 is the supervision layer

## TL;DR

The original #159 shipped a *hand-built* stdio→HTTP transport (`mcp_http_host.py`)
**plus** the operational scaffolding to run it as a shared, always-on service. This
re-scope splits those two concerns and keeps the one that is actually differentiated:

| Concern | Before (#159 as merged) | After (this re-scope) |
|---|---|---|
| **Transport** (stdio↔HTTP wire) | hand-built `mcp_http_host.py` | **`mcp-proxy` npm 6.5.4** (commodity, maintained) |
| **Supervision** (reap, health, always-on) | `run_host.ps1` (thin launcher) | **`run_host.ps1` (the value)** — drives mcp-proxy, adds reaping + status + logon task |
| **No-Node fallback** | — | `mcp_http_host.py` **unchanged**, behind `-Bridge stdlib` |

The bridge is not the moat — **supervision is**. mcp-proxy already solves the wire;
what an estate of many Claude/Codex sessions still lacks is *one supervised, reaped,
health-probed, always-on* instance per server. That is what this PR contributes.

## Why mcp-proxy for the transport

The Q3 decision this session: **mcp-proxy npm 6.5.4 was proven to front this box's
`cmd /c npx` stdio MCP servers** — a full MCP `initialize` + `tools/list` handshake
(8 tools) succeeded through it. Adopting it as the commodity transport retires the
motivation for a hand-rolled wire and inherits a maintained project's edge-case
handling (SSE + Streamable-HTTP, CORS, TLS, stateful sessions, graceful shutdown).

Verified **in this re-scope, on-box** (`npx.cmd -y mcp-proxy@6.5.4 --help`, 2026-07-24):

- `--host` defaults to **`::`** (IPv6) — it will *refuse* `127.0.0.1` clients, so the
  supervisor **PINS `--host 127.0.0.1`**. (This is the single most important flag; a
  bridge bound to `::` looks up but never answers the loopback registration.)
- `--shell` exists ("Spawn the server via the user's shell") — **required** so a
  `cmd /c npx -y <server>` child launches correctly on Windows. The supervisor always
  passes it in mcp-proxy mode.
- mcp-proxy serves **both** transports by default: an SSE endpoint (`--sseEndpoint`,
  default **`/sse`**) and a Streamable-HTTP endpoint (`--streamEndpoint`, default
  **`/mcp`**). That is why `apply_registration.py` now supports **both** `--transport
  http` (→ `/mcp`) and `--transport sse` (→ `/sse`) against the one running instance.

`UNVERIFIED in this task:` the "8 tools handshake through mcp-proxy" is the Q3 session
proof, cited here, not independently re-run in this re-scope — what was re-verified here
is mcp-proxy's CLI surface (above) and the supervision layer end-to-end (below). The
settling experiment is a one-shot `initialize`+`tools/list` POST to a live
`run_host.ps1 -Bridge mcp-proxy` instance.

## What #159 keeps — the supervision layer (`run_host.ps1`)

`mcp-proxy` is a foreground process with no notion of "run me once, forever, and clean
up after yourself". The supervisor adds exactly that, and nothing mcp-proxy already does:

- **`-Bridge mcp-proxy` (default):** launch mcp-proxy via `npx.cmd` with the pinned
  `--host 127.0.0.1 --shell` and the wrapped `-ChildCommand 'cmd /c npx -y <server>'`.
- **Port-scoped, children-first orphan reaping:** finds only the process(es) that *own
  the target port* (via `Get-NetTCPConnection`) and kills their descendants first, then
  the owner. **Never machine-wide** — it cannot touch a sibling session's bridge on
  another port. (The estate has been bitten by machine-wide reaps killing siblings;
  this is deliberately scoped.)
- **`-Status`:** the **spawn-count invariant** (exactly ONE bridge process should own
  the port — the whole point is S per-session copies collapsing to 1) plus `/healthz`
  when the stdlib host is the bridge (`child_spawn_count` must read 1).
- **`-InstallTask` / `-UninstallTask`:** a per-user logon Scheduled Task
  `McpHttpHost-<Port>`, mirroring the proven `MCPAgentMailSupervisor` pattern (hidden,
  no time limit, restart-on-failure, LIMITED run level) so the bridge is always-on.
- **`-DryRun`:** print the exact argv without launching.

## The stdlib host stays — as the no-Node fallback

`mcp_http_host.py` (and its 24 tests) is **unchanged**. It remains behind
`-Bridge stdlib` for the case where Node/npx is unavailable or undesirable, and it is
what `-Status`'s `/healthz` probe reads. It is no longer framed as *the* transport — it
is the fallback transport. Its shared-child invariant (`child_spawn_count == 1`) is the
same property the supervisor asserts for mcp-proxy via the port-owner count.

## How the pieces fit

```
                     ┌──────────────── run_host.ps1 (SUPERVISION) ────────────────┐
                     │  reap (port-scoped, children-first) · -Status · logon task │
                     └───────────────┬───────────────────────────┬───────────────┘
              -Bridge mcp-proxy      │                           │   -Bridge stdlib (no-Node fallback)
                                     ▼                           ▼
        npx.cmd -y mcp-proxy@6.5.4                    python mcp_http_host.py --eager
          --host 127.0.0.1 --shell                      --host 127.0.0.1 --port P
          --port P -- cmd /c npx -y <server>            -- python <hub>.py
                                     │                           │
      S sessions ─(type: http →/mcp | type: sse →/sse)─►  ONE shared child  ◄── apply_registration.py
```

`apply_registration.py --transport {http,sse}` flips a server's canonical `~/.mcp.json`
entry to point at whichever endpoint the running bridge serves — apply-when-closed,
dry-run by default, never touching `accounts.json` or any secret.