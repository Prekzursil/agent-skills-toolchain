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
