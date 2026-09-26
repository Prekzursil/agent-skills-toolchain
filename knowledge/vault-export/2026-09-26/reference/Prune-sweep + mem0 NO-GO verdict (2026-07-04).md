---
title: Prune-sweep + mem0 NO-GO verdict (2026-07-04)
type: note
permalink: main/reference/prune-sweep-mem0-no-go-verdict-2026-07-04
tags:
- prune
- mem0
- gem-hunt
- bloat
- skill-drop
- basic-memory
- decision
---

9-agent prune-sweep Workflow (wf_6714d4a2-bd3, 2026-07-04). Headline: **workspace is BLOAT-BOUND, not capability-starved** — 9/9 prunes + 7/10 adopts are config/text edits; only 2 real builds. Context-bloat → skill-description DROP (earlier /doctor: "329 skill descriptions dropped") is the likely cause of "other sessions naive / not using skills".

**⭐ mem0/OpenMemory ≥7B = NO-GO (HIGH, re-confirmed):** ≥7B makes mem0 FUNCTIONAL not ADDITIVE (same embed+vector layer as basic-memory); 32-day production audit = 97.8% junk + STRONGER model made it WORSE (extraction prompt is the bottleneck); OpenMemory reintroduces 3 REJECTED components (vector-DB/KG, mem0-as-store, Docker). Keep rejected, do NOT re-litigate. Only distinct slice = A10 write-time lexical contradiction gate.

**PRUNE queue (reversible):** P1⭐ gate per-Read PowerShell secret-scan to sensitive paths (~841ms/Read; native permissions.deny already blocks) · P2 shrink eager MCP fleet (hexstrike×18 etc→on-demand) · P3 park ralph-orchestrator (verify FSM superseded) · P4 move 7 heavy servers user→project scope · P5 retire 12 double-loaded skills · P6 checkpoint reconcile (keep edit-checkpoints, retire native-shadowed cmds) · P7⭐ drop 3 superseded MEMORY.md bullets · P8 disable 4 niche connectors+Parallel_Search · P9⭐ hygiene GC (17 .bak, 10.5MB bash-commands.log=secret-leak, cost-tracker.log, cleanupPeriodDays 365→30).

**ADOPT:** A1 flip intent-drift-sentinel+loop-operator→Opus (still Sonnet) · A2⭐ hook-health drift telemetry (139 live vs 99 CI) · A5 basic-memory OS restart-on-fail+PID-peak-log · A8 parallel-barrier watchdog(GATE) · A9 NEWS2 fused responder(GATE) · A10 lexical contradiction gate. **SKIP:** mem0 any-model, vector code-index, bash-sandbox(Win), cost-breaker, trained managers.

**basic-memory auto-replay FIXED** (PR#24 → main 61fb723): replay.py shells `basic-memory tool write-note` direct-to-vault (bypasses flappy MCP server), --spawn detached SessionStart slot. Relates to [[Session learnings 2026-07-03 (MCP vendoring + harness)]], [[Figma MCP seat facts + figma-rest decision (2026-07-03)]].