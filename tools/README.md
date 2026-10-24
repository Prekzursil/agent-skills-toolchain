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
- [`tools/account-hopper`](account-hopper/README.md) — stdlib per-account budget ledger and account hopper over Modal accounts you fund; records spend, names the next account to hop to, no network, never switches accounts itself; ships `hopper_launch.ps1`, the PowerShell auto-rotation launcher that acts on its answers
- [`tools/durable-checkpoint`](durable-checkpoint/README.md) — stdlib durable checkpoint mirror for jobs that outlive their container; atomic writes, a final checkpoint on SIGINT/SIGTERM, and verify-before-resume so a torn mirror is refused rather than loaded; no network, no provider SDK

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
