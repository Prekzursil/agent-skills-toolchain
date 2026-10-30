# Tools

This repo keeps three integration-specific tool surfaces separate on purpose:

- `mcp/` for MCP-native orchestration tools and other server-side integrations
- `editor/` for editor-local tools such as VS Code extensions
- `web/` for browser- or session-mediated tooling

Standalone repository utilities that do not belong to an integration surface live
directly under `tools/`, such as `triage-router/`.

The split is not cosmetic. These surfaces have different runtime, auth, packaging,
and validation models. Keeping them separate prevents drift and keeps review
boundaries understandable.

## Standalone utilities

- [`tools/triage-router`](triage-router/README.md) — stdlib model-tier routing CLI used by `/model-route` and `/start-task`
- [`tools/longhaul`](longhaul/README.md) — stdlib tool for long cloud jobs on accounts you fund: per-account pause lines plus a global ceiling over measured (high-water) or recorded spend, a preemption-safe watchdog that pauses before the cap, and generation checkpoints with verify-on-read; the profile is always the caller's explicit choice (no automatic hop)

## Current live projects

- [`tools/mcp/workstation-codex-bundle`](mcp/README.md)
- [`tools/lib`](lib/README.md) — dependency-free shared ES modules reused across tool surfaces
- `tools/web/` currently has no promoted runnable project, but remains the bounded home for future browser- or session-mediated tooling
- `tools/editor/` currently has no promoted runnable project, but remains the bounded home for future editor-local tooling

The full `tools/mcp/` project list lives in [`mcp/README.md`](mcp/README.md); this section
only pins the surfaces referenced from elsewhere in the repo.

Retired 2026-08-09: the ChatGPT-web / Codex-orchestrator lane (`tools/web/agentify-desktop`,
`tools/web/promptbridge-talk-lane`, `tools/web/agent-lanes-chatgpt-web`,
`tools/mcp/codex-orchestrator`, `tools/mcp/agent-lanes-codex`) was deleted. Its reusable
survivors were extracted into `tools/lib/` before the delete.

Retired 2026-10-30: `tools/account-hopper` (#396, #397) was folded into `tools/longhaul`,
together with the unmerged modal-budget-ledger measured layer and the closed durable-checkpoint
PR (#398). Its `select`/`hop` rotation and `hopper_launch.ps1` were dropped on purpose; see
[`longhaul/MIGRATION.md`](longhaul/MIGRATION.md).
