---
name: codex-fleet-github
description: Use when dispatching, sweeping, monitoring, or planning autonomous Codex-on-GitHub runs across the private fleet via the codex-fleet-github MCP server. Drives the Wave-1 workflow_dispatch runner (codex-runner.yml) with propose-only draft PRs and a fail-closed auth model. Covers the four tools (fleet_dispatch, fleet_sweep, fleet_status, fleet_orchestrate), token setup, and the pre-PR-68 runner-branch caveat. Do NOT use for local Codex CLI consultation (use codex-consult) or for editing the runner workflow itself.
---

# codex-fleet-github — Autonomous Codex-on-GitHub Fleet Connector

A local FastMCP (stdio) server that lets a Claude Code or Codex agent drive the
private Wave-1 Codex runner (`codex-runner.yml`) on `agentuser/agent-skills-toolchain`.
It fans out coding tasks to any repo in the curated fleet, each run producing a
**draft PR** — nothing is ever merged autonomously.

Server subtree: `tools/mcp/codex-fleet-github/` · FastMCP name: `codex-fleet-github`.

## When to use

- "Dispatch Codex to fix X in repo Y" → `fleet_dispatch`.
- "Run this task across the whole fleet" → `fleet_sweep`.
- "What Codex runs / draft PRs are open?" → `fleet_status`.
- "Break this plan into per-repo work" → `fleet_orchestrate`.

Do NOT use for local Codex CLI consult/curate/review (that is the `codex-consult`
skill), nor for editing `codex-runner.yml` (edit the workflow directly).

## The four tools

| Tool | What it does | Writes? |
|------|--------------|---------|
| `fleet_dispatch(repo, task, model?, effort?, max_changed_files?)` | Fires ONE `gh workflow run codex-runner.yml` against `target_repo=repo`. Returns the run URL (best-effort) plus the Actions URL. | Yes — one dispatch, one draft PR |
| `fleet_sweep(task, repos?, model?, effort?, max_changed_files?)` | Dispatches the same task to many repos (default: enabled repos in `codex-targets.yml`; built-in fallback fleet). Serialized by the runner's concurrency group. | Yes — many dispatches |
| `fleet_status(limit?)` | Lists recent codex-runner runs and open codex-runner **draft** PRs across the fleet (`gh run list` / `gh search prs`). | No — read-only |

### Safety model (propose-only + fail-closed)
### Auth & setup
### Env overrides (advanced)
### Verify
