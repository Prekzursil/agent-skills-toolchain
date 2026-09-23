---
title: Is the context "fast eater" pure cost, or also a quality lever?
date: 2026-09-23
status: OPEN - needs measurement, not assertion
relates_to: deep-thoughts/2026-09-23-harness-ossification-and-insight-decay.md (DT-3)
---

# Question (owner intent)
Is loading the full skill/tool surface SOTA-but-expensive, i.e. purely a cost
tradeoff? With infinite usage would we always load everything? Or does a big
surface also HURT performance via overload?

# Answer: BOTH cost and quality, pointing the same way.
"Infinite usage -> load everything" is FALSE. Even free, loading everything
likely makes sessions worse.

## Two independent effects of a large upfront skill/MCP surface
1. COST (usage burn): every skill listing + tool schema is input on every turn
   until compaction. Linear, visible. The "fast eater".
2. QUALITY DEGRADATION (the non-obvious half):
   - Tool-selection accuracy falls as the candidate set grows (more mis-picks).
   - Attention dilution ("lost in the middle"): task goal competes with a wall
     of capability text.
   - Latency rises with input size, compounding across a session.
   - Earlier autocompaction: a fat baseline hits the threshold sooner, losing
     working context more often -> worse continuity.

## Consequence
"More available = more capable" is wrong for LLM tool use past a point. Optimum
is NOT "load all" but "load the RIGHT skills on demand".

## Right architecture (what the harness implements when wired)
Lazy load via a router; discovery via router/ToolSearch, not exhaustive listing.
Decouples "how many skills you HAVE" from "how many you pay for + get distracted
by per turn". Strong router -> afford a LOW listing budget.

## 0.04 vs 0.01 (skillListingBudgetFraction)
Lower = cheaper + less dilution, BUT too low + weak router = model cannot find a
skill it needs (false "I do not have that"). Optimum is COUPLED to router
quality. HOME runs 0.04 (pre-router crutch? or measured? unknown).

## Decision
Ported 0.04 for parity; did not silently change it. Resolution: MEASURE - run a
few sessions at 0.01 with the router live, check discovery still works, then set
the SAME value on both machines. A/B, not assertion.

## Meta (ties to DT-1 anti-ossification)
"0.04 is a 4x anti-pattern" (a research subagent claim) is itself the kind of
idempotent dismissal DT-1 warns about. Force a RE-TEST with a review date; do not
accept it as settled.

## Harness defect found this session
The PreToolUse secret-guard (Bash and PowerShell) refused a git add because the
COMMAND TEXT contained the word "token". It substring-matches "token" instead of
matching secret-file NAMES/paths or real secret value patterns (sk-, ghp_, high
entropy). Over-broad; blocks legitimate writing about context budgets. FIX: scope
the guard to filenames/paths and value-shaped secrets, not the English word.
