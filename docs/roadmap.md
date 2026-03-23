# Roadmap

## Now

- Keep the existing live ops, recovery, transcript, and repo-quality skills intact.
- Build out the Windows-first orchestration stack on top of that existing base.
- Keep the primary execution surfaces separated:
  - `.agents/skills/`
  - `tools/mcp/`
  - `tools/web/`
- Keep `skills/` only as a temporary compatibility layer until the migration is complete.
- Retain `tools/editor/` as a bounded editor-local surface.
- Keep the root install path warning-free.
- Keep the Codex orchestration lane and PromptBridge talk-only lane separate.

## Active deliverables

### Existing live specialist skills

- `quality-gate-automation-architect`
- `quality-zero-platform-control-plane`
- `format-codex-sessions`
- the existing Windows / WSL / VMware / Codex recovery skill wave
- the explicit `agent-lanes-*` lane-selection skills

### `codex-orchestrator`

- Windows-first Codex bootstrap, status, probe, and self-test flow
- multi-agent orchestration tools with one shared result schema
- profile defaults plus per-call overrides

### `promptbridge-talk-lane`

- PromptBridge/Agentify talk-only tools
- session status and configuration APIs
- explicit curation/discussion boundary

### New skill pack

- beginner quickstart
- PromptBridge consultation setup and diagnostics
- core orchestration wrappers
- workflow wrappers for audit, triage, fix, and governance
- explicit post-plan execution choice (subagent-driven recommended, inline allowed)

## Next

- add richer operator docs for IDE-side smoke testing and failure classification
- add more orchestration profiles and curated defaults
- keep the editor-local surface explicit instead of folding it into MCP or web tooling
- add release-layer packaging without polluting the root runtime graph
- decide whether the repo stays private permanently or becomes publishable later

## Non-goals

- turning PromptBridge into the execution authority
- hiding MCP, editor, and web tooling under one generic bucket
- keeping two active Codex homes in normal operation
- reintroducing WSL-first assumptions into the main workflow
- dropping the existing live specialist skills while the new orchestration layer is added
