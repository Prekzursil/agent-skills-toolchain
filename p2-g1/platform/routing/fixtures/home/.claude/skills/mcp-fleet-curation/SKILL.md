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

### mcp_doctor — catch drift before it snowballs
### The catalogue-tax model (the core confusion)
### Maintenance rule
### Notes / gotchas
