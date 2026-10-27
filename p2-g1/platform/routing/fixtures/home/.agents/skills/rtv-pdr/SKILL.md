---
name: rtv-pdr
description: Use when a hard coding work-unit has failed once, is contentious, or scores HIGH on the ESE (Ensemble Semantic Entropy) gate — spawns N parallel Opus rollouts, runs a recursive tournament where fresh judge agents (never contestants) pick the winner, then optionally runs a PDR refine pass. Expensive; do NOT fire on routine tasks.
---

# RTV+PDR — Recursive Tournament Voting + Parallel-Distill-Refine

Test-time-compute scaling for hard coding work-units.
Based on the methodology in arXiv:2604.16529.

**Research caveat:** The cited paper reports gains for Claude Opus 4.5 on SWE-bench Verified (70.9→77.6) and Terminal-Bench v2.0 (46.9→59.1). Results are model-version-specific and benchmark-specific; gains on arbitrary user tasks are not guaranteed.

## When to use

Fire this workflow **only** when all of the following hold:

- The work-unit is **hard or contentious** (prior attempt failed, or high disagreement among reviewers).
- The ESE (Ensemble Semantic Entropy) escalation gate has **flagged** the unit as high-entropy.
- You have **budget headroom** — each invocation runs N Opus-class agents (rollouts + judges + optional refine).

Do NOT use for routine implementation, boilerplate, or tasks with an obvious single solution.

## Cost profile

| N | Rollout calls | Tournament judges (worst case) | PDR refine | Total (approx) |
|---|---|---|---|---|
| 3 | 3 Opus | 2 Opus | 1 Opus + 1 judge | 7 Opus |
| 4 | 4 Opus | 3 Opus | 1 Opus + 1 judge | 9 Opus |
| 5 | 5 Opus | 4 Opus | 1 Opus + 1 judge | 11 Opus |

`CLAUDE_CODE_FORK_SUBAGENT` fork-cache is used automatically for parallel rollouts, cutting warmup cost.

Judges use `model: opus` by default (best verdict quality). To reduce cost, you may edit the judge calls to `model: 'sonnet'`; document this tradeoff if you do.

## Judge independence guarantee

**Judges are never contestants.** Each pairwise comparison is run by a fresh agent that received no prior context from either rollout. This closes the self-choice bias gap identified in the RTV design.

### Invocation
### ESE-gated invocation pattern
### PDR mode
### Output shape
### Workflow location
