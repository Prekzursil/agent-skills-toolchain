---
name: mcp-fleet-curation
description: Use when plugins, skills, or MCP servers keep REAPPEARING after you disable them, when de-bloating the Claude Code catalogue, or when the per-turn tool/token count creeps back up. The permanent cure - disable at USER scope (claude plugin disable name@mkt --scope user), NOT the UI toggle (which writes project scope and returns when the cwd changes) - plus periodic mcp_doctor audit to catch drift. Covers the two root causes (install = enabled-by-default, and scope mismatch), the reversible park/restore flow for MCP servers in the .mcp.json files, and the catalogue-tax model behind the bloat.
license: MIT
---

# MCP / Plugin / Skill Fleet Curation

> **Why your disabled plugins/MCPs keep coming back — and the one cure that
> sticks.** Two bugs, both fixed by disabling at **user scope**. The UI toggle
> lies to you (it writes *project* scope).

## When to use

- "I disabled this plugin/MCP and it came back."
- De-bloating the catalogue: too many listed tools/skills taxing every turn.
- `/context` shows a creeping always-on token cost.
- After any `claude plugin install` (curate it immediately — see the rule).

## Root cause (two bugs)

1. **Install = enabled-by-default.** A plugin in `installed_plugins.json` is ON
   unless an explicit `false` is recorded. Dozens were never explicitly disabled,
   so every reload re-affirmed them.
2. **Scope mismatch.** The `/plugin` UI and a bare `claude plugin disable` write
   **project** scope → the plugin returns the moment the cwd changes.

## The permanent cure

**Disable at user scope** (writes a durable `false` to `~/.claude/settings.json`,
proven to persist across cwd changes and restarts):

```bash
claude plugin disable <name>@<marketplace> --scope user
```

Never trust the UI toggle for a durable decision. Verify with `/context` after a
restart (plugin/MCP changes apply on the next CC start, not live).

## MCP servers: reversible park / restore

MCP servers live in `~/.mcp.json` (active) with a parking lot in
`~/.mcp.disabled.json`. To **park** a server: move its block out of `mcpServers`
in `~/.mcp.json` into `~/.mcp.disabled.json`. To **restore**: move the block
back. Takes effect on the **next** CC restart (servers load at session start;
already-open sessions keep their old set). Backups: `~/.mcp.json.bak-*`.

The project approval-list (`enabledMcpjsonServers` in `settings.local.json`) is a
second gate — trim cross-layer duplicates there too.

## mcp_doctor — catch drift before it snowballs

`~/.local/opt/re-harness/mcp_doctor.py` (+ `lib/mcp_doctor_core|mcp_inventory|mcp_procscan.py`,
budget in `mcp_budget.yaml`):

- `python mcp_doctor.py status` — liveness table for all servers.
- `python mcp_doctor.py audit` — drift vs the budget manifest (flags re-enabled /
  duplicate / heavy / per-session pile-up; surfaced docker×25, excel×25, frida×15).
- `python mcp_doctor.py reap` — registry-gated duplicate-killer (**GUI IDA :13337
  is protected**; dry-run by default).

Run `audit` periodically — that is the "curation keeps reappearing" early-warning.

## The catalogue-tax model (the core confusion)

- **Access = listed in the catalogue** → taxed **every turn**, used or not.
- **Use = invocation** (`Skill` tool / `ToolSearch`+call / `Agent` tool) → paid
  only when actually called.
- `ENABLE_TOOL_SEARCH=auto:5` already **defers** MCP tool schemas (they load on
  demand). So the remaining lever is **reducing the COUNT** of listed items —
  exactly what user-scope disabling does. Pair with `mcp-code-orchestrate` to
  keep *result* tokens down on fan-out, and `ToolSearch` to keep *schema* tokens
  down on single calls.

## Maintenance rule

Every new `claude plugin install` is immediately **kept** or
`disable --scope user`. Never leave it on default-on. Skills under
`~/.claude/skills` apply immediately (no restart); plugins/MCPs need a restart.

## Notes / gotchas

- `basic-memory` runs as a shared HTTP server on `:8765` (a single point of
  failure). If it shows disconnected, run `pwsh -File ~/.basic-memory/bm-http-server.ps1`
  to bring it up immediately; a 5-min scheduled task also self-heals it.
- `D:\basic-memory\.hf` (~14 GB) is the GLOBAL HF cache for media/OCR tools, NOT
  basic-memory's model — do **not** delete it.
- Authoritative state docs as of writing: `~/.claude/WORKSPACE-CURATION.md` and
  `~/.claude/MCP-FLEET-IMPROVEMENT-DECISIONS.md`; config backups under
  `~/.claude/_config-backups/`.
