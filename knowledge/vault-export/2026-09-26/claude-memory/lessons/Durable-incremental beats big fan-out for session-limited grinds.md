---
title: Durable-incremental beats big fan-out for session-limited grinds
type: note
permalink: main/claude-memory/lessons/durable-incremental-beats-big-fan-out-for-session-limited-grinds
tags:
- workflow
- orchestration
- coverage
- session-limit
- lesson
- momentstudio
---

# Durable-incremental beats big fan-out for session-limited grinds

**Failure observed (2026-06-27):** momentstudio's frontend coverage grind (~41%→100%, ~10k-statement debt) ran TWICE inside the fleet workflow as a single big parallel fan-out (40 per-file test-writers → ONE integrate at the end). Each run hit the account session limit (~5h rolling window) mid-fan-out and died. Result: **~15M tokens burned, 0 cov/ sub-branches pushed, ZERO durable progress** — because the window closed before the writers finished/pushed and the single end-of-run integrate step never executed, so nothing accumulated and the next run re-measured the same ~41% and re-ground the same files.

**Why:** a big fan-out with integrate-at-end has its only durability checkpoint at the very END. If the budget/window can't cover the whole fan-out + integrate, you get nothing. The 40-wide simultaneous spawn also means all writers compete for budget at once and none reach their push.

**Fix (durable-incremental design):** process in SMALL batches (e.g. 8 files), and MERGE each batch to a persistent integration branch IMMEDIATELY AFTER that batch (not once at the end). Each writer also pushes its own sub-branch right after writing. So progress commits durably every batch — even if the window closes after batch 3, batches 0-2 are merged and the next resume continues from the raised coverage. Loop batches until target or budget.

**General rule:** for ANY autonomous grind that may outlast a session/budget window (large coverage debt, mass migration, fleet-wide sweep), checkpoint progress to a durable artifact (merged branch / committed files / written records) at FREQUENT INTERVALS, not once at completion. Prefer many small durable commits over one big terminal integrate. Also: one repo = one workflow (don't let a giant sub-task like momentstudio's coverage block a whole fleet workflow from completing — give it its own workflow so the fleet can finish). Relates to [[feedback_workflow_orchestration]].