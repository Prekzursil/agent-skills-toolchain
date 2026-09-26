---
title: Live in-session MCP control PROVEN via stream-json control channel (2026-07-18)
type: reference
permalink: main/reference/mcp/live-in-session-mcp-control-proven-via-stream-json-control-channel-2026-07-18
valid_as_of: '2026-07-18'
supersedes: main/reference/mcp-live-toggle-verdict-2026-07-06
build_verified: Claude Code 2.1.214 Windows 11
tags:
- mcp
- live-control
- breakthrough
- claude-code
- '2026-07-18'
- supersedes
---

# Live in-session MCP control — PROVEN (2026-07-18)

**valid_as_of: 2026-07-18 · build: Claude Code 2.1.214, Windows 11.**
**SUPERSEDES the 2026-07-06 "DEFINITIVE: no live MCP toggle exists" verdict** — that verdict is now
WRONG for this build. Live add / remove / disable / reconnect all work programmatically, with **zero
interactive slash commands and zero keystrokes**.

## The mechanism: the stream-json control channel
A session started with `--input-format stream-json` accepts `control_request` frames on **stdin** —
the same first-class, schema-documented channel the Agent SDK drives. Nothing is patched or bypassed.

```json
{"type":"control_request","request_id":"<uuid>","request":{"subtype":"mcp_status"}}
-> {"type":"control_response","response":{"subtype":"success","request_id":"<uuid>",
    "response":{"mcpServers":[...]}}}
```

### MCP control subtypes (extracted from the binary, all exercised live)
| subtype | effect |
|---|---|
| `mcp_status` | list every server + scope + status |
| `mcp_set_servers` | **replace the dynamically-managed server set** -> `{added[],removed[],errors{}}` |
| `mcp_reconnect` | reconnect a named server — **and re-reads config from disk** |
| `mcp_toggle` | live enable/disable, **any scope** |

Also present: `mcp_authenticate`, `mcp_clear_auth`, `mcp_oauth_callback_url`,
`set_mcp_permission_mode_override`, `reload_plugins`.

## Proven capability matrix
| Operation | Mechanism | Scope | Evidence |
|---|---|---|---|
| **ADD** (ephemeral) | `mcp_set_servers` | `dynamic` | `added:["b3-probe-alpha"]`, model then genuinely CALLED the new tool (unique token returned) |
| **ADD** (persistent) | `claude mcp add` / write `.mcp.json` **+ `mcp_reconnect`** | user / project | `picked_up_after_reconnect: true` |
| **REMOVE** | `mcp_set_servers` omitting entry | `dynamic` only | model answers "NO" for the tool afterwards |
| **DISABLE** (the removal lever for config scopes) | `mcp_toggle enabled=false` | **any** | `user/connected -> user/disabled` |
| **RECONNECT** | `mcp_reconnect` | any | success |

Full lifecycle proven in one session: `add -> reconnect -> disable -> enable -> remove` (11/11 steps).

## The startup gotcha (cost two dead runs)
A stream-json-input session does **NOT** emit `system/init` until it receives its **first user
message**. Waiting for `init` before writing to stdin **deadlocks forever** — kick the session with a
trivial turn first.

## What was FALSIFIED (do not retry these)
- **No file watcher** for MCP config: `watchMcp` / `mcpConfigChanged` / `reloadMcp` / `reloadConfig` =
  0 hits. `chokidar` IS bundled but watches SKILL files, not MCP config. (Matches open issue #24057.)
- **`SIGHUP` kills the session** (`process.on("SIGHUP", () => process.exit())`) — it is not a reload.
- **Hooks cannot reload MCP**: `reloadMcpFromHook`/`hookMcp`/`mcpReload` = 0 hits; `hookSpecificOutput`
  exposes no MCP surface.
- `claude mcp add` alone does NOT affect a running session — **only when paired with `mcp_reconnect`**.

## The search-hub mystery, answered
Servers added to `~/.mcp.json` appearing mid-session was **a reconnect re-reading config from disk**,
NOT a watcher. `/mcp reconnect` in the UI is the interactive skin over the same `mcp_reconnect`
control request — now issuable programmatically.

## Why it matters
This unblocks a REAL "restart/add/remove MCP" control in the unified cockpit
([[unified-monitor-cockpit-program-session-learnings-2026-07-18]] X17/X18) — an honest live button
instead of a `[next-session]` badge. Code + evidence:
`~/.claude/monitor-harness-ultracode-2026-07-18/mcp-live-control/` (`B3-reconnect-trigger.md`,
`mcp_live.js`, `live_session.js`, `b3-results-*.json`).

Related: [[reference_session_learnings_2026-07-18]].
