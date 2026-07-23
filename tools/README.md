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

- [`tools/mcp/agent-lanes-codex`](mcp/README.md)
- [`tools/mcp/codex-orchestrator`](mcp/README.md)
- [`tools/mcp/workstation-codex-bundle`](mcp/README.md)
- [`tools/web/agent-lanes-chatgpt-web`](web/README.md)
- [`tools/web/promptbridge-talk-lane`](web/README.md)
- `tools/editor/` currently has no promoted runnable project, but remains the bounded home for future editor-local tooling
