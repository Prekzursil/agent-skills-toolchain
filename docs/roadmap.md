# Roadmap

## Now

- Keep the existing live ops, recovery, transcript, and repo-quality skills intact.
- Build out the Windows-first orchestration stack on top of that existing base.
- Keep the primary execution surfaces separated:
  - `.agents/skills/` — the canonical skill root
  - `skills/` — the shipping projection of `.agents/skills/`; `scripts/sync-skills.ps1` deploys
    from it (`sync-skills.ps1:45`). The projection is **not complete**: measured 2026-08-13,
    3 skill names live only in `skills/` and 12 only in `.agents/skills/`, so each root holds
    content the other lacks. `ci/check_skill_dual_write.py` (including `--strict-parity`) is a
    DIFF guard over changed paths, not a tree-parity guard — it stops the divergence growing but
    does not close the backlog, which pre-dates it (those 3 landed 2026-07-18/19, the guard
    2026-07-21). REFUTED 2026-08-13: an earlier revision of this bullet called `skills/` "the
    generated projection" of `.agents/skills/`, said `--strict-parity` "holds the two in
    lockstep", and concluded it is "a permanent surface, not a temporary compatibility layer".
    All three are false while any name is one-sided; that wording came from counting one
    direction only. Both one-sided counts are gated by
    `ci/tests/test_docs_executable_claims.py`, so when they reach 0 this bullet must be upgraded
    rather than left understated.
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
