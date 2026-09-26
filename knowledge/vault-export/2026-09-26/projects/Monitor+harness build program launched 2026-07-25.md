---
title: Monitor+harness build program launched 2026-07-25
type: report
permalink: main/projects/monitor-harness-build-program-launched-2026-07-25
tags:
- compaction-checkpoint
- monitor-harness
- unified-cockpit
- build
- loop
---

# Monitor + harness build program — LAUNCHED (2026-07-25, /loop autonomous)

User corrected the loop scope: the real targets are **the workflow harness (the grilled one) + the unified agent monitor** = the `~/.claude/monitor-harness-ultracode-2026-07-18/` program (MASTER-QUEUE.md). The 3-way adoption (cyberstrike/hacktricks/workflow-authoring) was a SEPARATE, now-complete thread (main f22c256).

## The plan (already grilled + review-gated — MASTER-QUEUE is the consolidated impl plan)
- monitorcore ALREADY exists+merged on main (21 modules: codex_source, agent_state, contract, export, timeline, watchdog, dbx_*, etc.). This UPGRADES it — the interactive board (WU2/3/5/7 modules) does NOT exist yet.
- Monitor Phase 1 = WU0-8 (scaffold+ansi+ctx -> feed+groups+responsive -> nav+stall+export+integrate), coverage-gated (pytest --cov=monitorcore --cov-branch --cov-fail-under=100 + vendor-drift diff -r tools/monitorcore/monitorcore skills/workflow-monitor/monitorcore + basedpyright 1.39.8), DUAL-WRITE both dirs. Phase 2 (WU9-13) = live-trace-gated, DEFER.
- Harness Tier-1 = T1-1..T1-9 (fold hooks into _dispatch, managed-MCP apply [OWNER-only, Claude closed], skill-vault reconcile, CLAUDE.md routing, native Monitor lane, StopFailure matcher, ultracode quick-wins, retire 43 hook dirs).
- Doctrine skill = commit codex-mixed-workflow-doctrine (D3 doc, 656 lines) as ONE skill (no separate codex-fanout).

## RUNNING NOW (both offloaded, background, auto-notify)
- **Agent ab7690512ef699da2** — doctrine skill (dual-write) + Tier-0 T0-6/T0-7 rule captures -> focused PR.
- **Workflow wf_6ea5d249-f33** (task wa6j72mzm) — monitor cockpit Phase-1 board, staged serial worktree TDD (Substrate->BoardRender->Interactive->Verify), opens a PR but does NOT self-merge (I merge after reviewing the critic + 100% coverage gate).

## NEXT (after the two land)
1. Review monitor PR (critic PASS + gate 100% + scope monitorcore-only) -> merge. Review doctrine PR -> merge.
2. Harness Tier-1, SEQUENCED (skill-index/marketplace.json is a shared single-writer -> do NOT run index-touching Tier-1 items in parallel with each other or the doctrine Agent). T1-3 managed-MCP apply is OWNER-only (all Claude closed) -> hand back.
3. Tier-0 live-harness (T0-1 deploy sync to ~/.agents, T0-2 hook repoint) AFTER the monitor board merges (deploy the final version). Some Tier-0 already done (T0-5 single-signal rule exists).

## Stale/superseded (do NOT rebuild): branches feat/monitorcore-codexsource, feat/variant4-increment1-dbx-monitor (their codex_source/dbx work already on main via other PRs); chore/wu4-enforcement-scaffold-port is empty.
