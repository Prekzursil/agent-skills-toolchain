# Roadmap

## Now

- Keep the existing live ops, recovery, transcript, and repo-quality skills intact.
- Build out the Windows-first orchestration stack on top of that existing base.
- Keep the primary execution surfaces separated:
  - `.agents/skills/` — the canonical skill root
  - `skills/` — the generated projection of `.agents/skills/` that ships; `scripts/sync-skills.ps1`
    deploys from it (`sync-skills.ps1:45`) and `ci/check_skill_dual_write.py --strict-parity` holds
    the two in lockstep, so it is a permanent surface, not a temporary compatibility layer
  - `tools/mcp/`
  - `tools/web/` — reserved and currently empty; see [`tools/web/README.md`](../tools/web/README.md)
- Retain `tools/editor/` as a bounded editor-local surface.
- Keep the root install path warning-free.
- Reach Codex through the official `codex mcp-server` rail (`mcp__codex__codex` /
  `mcp__codex__codex-reply`) rather than a repo-local orchestration server.

## Active deliverables

### Existing live specialist skills

- `quality-gate-automation-architect`
- `quality-zero-platform-control-plane`
- `format-codex-sessions`
- the existing Windows / WSL / VMware / Codex recovery skill wave

### Retired 2026-08-09 — the ChatGPT-web lane

`codex-orchestrator`, `promptbridge-talk-lane`, `agent-lanes-codex`,
`agent-lanes-chatgpt-web` and `agentify-desktop` were deleted. They were a repo-local MCP
server plus an Electron app that drove the ChatGPT web UI; the official `codex mcp-server`
covers the orchestration half natively, and the web half is not being rebuilt. The
`agent-lanes-*` lane-selection skills went with them. Reusable pieces (path containment,
workspace detection, review-packet building, an idempotency ledger, a loopback-only address
allowlist, Windows Codex-binary resolution) survive in [`tools/lib/`](../tools/lib/README.md).

### New skill pack

- beginner quickstart
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

- rebuilding a browser-mediated ChatGPT lane, or giving any talk-only lane execution authority
- hiding MCP, editor, and web tooling under one generic bucket
- keeping two active Codex homes in normal operation
- reintroducing WSL-first assumptions into the main workflow
- dropping the existing live specialist skills while the new orchestration layer is added
