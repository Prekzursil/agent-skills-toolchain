# Roadmap

## Now

- Keep the existing live ops, recovery, transcript, and repo-quality skills intact.
- Build out the Windows-first orchestration stack on top of that existing base.
- Keep the primary execution surfaces separated:
  - `.agents/skills/` — the canonical skill root
  - `skills/` — the shipping projection of `.agents/skills/`; `scripts/sync-skills.ps1` deploys
    from it (`sync-skills.ps1:45`). The projection is **complete by name**: measured
    2026-09-01, 0 skill names live only in `skills/` and 0 only in `.agents/skills/` — the
    2026-08-28 SSOT fold (`15905d35`) closed the backlog, and `ci/skill-inventory-baseline.txt`
    (shrink-only) now holds zero grandfathered pins. Two guards keep it there:
    `ci/check_skill_dual_write.py --strict-parity` is a DIFF guard over changed paths (it stops a
    divergence being introduced), and `ci/check_skill_inventory_parity.py` is the TREE-parity
    guard (it reports any one-sided name at HEAD). Name-parity is not byte-parity: 2 files
    still differ between the two roots (`reconcile-flags/import-2026-08-28/`), and `skills/`
    remains the deploy source, so it is still a projection rather than a second canon.
    HISTORY, kept because the gate below replays it: measured 2026-08-13 the counts were 3 and
    12, and an earlier revision called `--strict-parity` a lockstep guard — false while any
    name was one-sided, and the reason the tree-parity arm was built. Both one-sided counts
    are gated by `ci/tests/test_docs_executable_claims.py`; this bullet was upgraded when they
    reached 0, as its previous wording required.
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
