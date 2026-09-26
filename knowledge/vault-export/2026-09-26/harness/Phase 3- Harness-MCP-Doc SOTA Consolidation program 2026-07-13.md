---
title: 'Phase 3: Harness/MCP/Doc SOTA Consolidation program 2026-07-13'
type: project
permalink: main/harness/phase-3-harness-mcp-doc-sota-consolidation-program-2026-07-13
tags:
- harness
- mcp
- config-drift
- consolidation
- enforcement
- program
- agent-skills-toolchain
---

⭐ BIG expansion of the centralization program (owner ask 2026-07-13, ultracode). Continues [[reconcile-committed-2026-07-13-enshrine-runtime-config]] + [[config-drift-audit-auto-compact-fix-2026-07-13]]. The ask's OWN theme is anti-amnesia: this program keeps getting lost/re-derived across sessions — the fix is centralized, enforced, single-source knowledge.

## The 9 threads
1. **MCP single-source-of-truth** — every session → ONE canonical config, no duplicates/fragments/divergent pointers. `~/.mcp.json` vs `~/.claude.json` (user scope) vs `D:\research` MCP configs DIVERGE → unify robustly (NOT the failed "sync"). **Resurfaced dropped MCPs** (codacy, deepsource) — a prior session dropped them for a SOTA MCP strategy/skills; they came BACK → that harness mechanism may be broken; investigate (recall the SOTA-MCP-strategy doc) + fix. Prune duplicates/superseded.
2. **MCP user-scope + centralization** — prefer USER scope over project for every MCP that doesn't genuinely need per-project (avoid duplicate deployments + concurrent-session request failures). ALL MCPs in ONE folder that MIRRORS the toolchain repo, not scattered across disk/partitions.
3. **Config/skill/tool/hook centralization** — nothing spread across disk/partitions; all in the toolchain repo (one place); portable across sessions regardless of launch dir.
4. **Cleanup enforcement** (hook/rule/harness) — force cleanup after work; no stale code/work in random dirs (they get lost → documented work reruns). Worktree isolated copies OK (parallel/safety) but MUST be cleaned up + organized.
5. **Stale local-branch reconciliation** — find unmerged/uncommitted branches across ALL repos; check they're not another session's LIVE work (don't interfere); analyze each (salvage good work / superseded / scope-changed-partial-salvage / stale) → offer resolution. Enforce checking these.
6. **Doc reconciliation + enforcement** (hook/rule) — ALWAYS reconcile/update docs w/ SOTA practice; avoid: duplicate docs, new-plan-when-update-needed, loose superseded docs, scattered-truth-across-files, which-doc-is-current confusion. A hook to force cleanliness + organization.
7. **Scattered-harness-doc reconciliation** — find ALL the (hundreds of) forgotten harness analysis/.md/research docs across subsubfolders from other sessions (partly-implemented, contradictory OR corroborating/expanding); reconcile them ALL; THEN evaluate present harness → make it completely SOTA. Never again decentralized chaos.
8. **Harness-change-documentation enforcement** (hook) — MANDATORY: any harness change (skills/mcps/hooks/config/agents) documented in the CENTRAL place (all sessions aware, don't break each other) + ALWAYS PR/commit to the toolchain repo + sync. Nothing lost.
9. **Harness-works-perfectly verification** — rigid thorough enforcement that the harness works, nothing conflicts, nothing silently fails/gets lost/rewritten.

## Process (owner-requested)
/deep-research + /gem-hunt + /council (4-5 Opus 4.8) + /brainstorm → discovery; then /grill-me-extensive (UNLIMITED questions — surface options + new features found during research, confirm-don't-guess); then a thorough ultracode BUILD Workflow. Use ALL skills, max quality.

## Status 2026-07-13
- DISCOVERY Workflow launching now (inventory current state: scattered docs / MCP divergence / stale branches / config scatter / harness SOTA audit + SOTA research + 5-Opus council → decision-queue). READ-ONLY.
- Codex-native-mechanism Workflow (Phase 2b, wzljmf3er) still RUNNING (separate concern).
- NEXT: grill the owner (grounded by discovery) → build. Heavy build (config mutation + MCP user-scope promote, which needs Claude CLOSED) + the 900k auto-compact window both favor a RESTART for the build phase.
- Branch `chore/enshrine-runtime-config` (3 commits: 5d2fca2 enshrine, f351403 config_drift fix, 9bb3f04 enforcement) NOT pushed — awaiting owner.

Relations:
- continues [[reconcile-committed-2026-07-13-enshrine-runtime-config]]
- relates_to [[config-drift-audit-auto-compact-fix-2026-07-13]]