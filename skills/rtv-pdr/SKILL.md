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

`self_reported_confidence` in each rollout summary is logged for observability only — **it is never used to select the winner**.

## Invocation

Run the workflow from the Claude Code Workflow runner by selecting `rtv-pdr` and passing args:

```
args:
  task: "<full description of the hard coding work-unit>"
  repo_context: "<relevant repo context, file paths, constraints>"
  n: 4          # number of parallel rollouts (2-5, default 4)
  pdr_mode: false  # set true to run a PDR refine pass after the tournament
```

### ESE-gated invocation pattern

Only invoke after ESE confirms high semantic entropy:

```
1. Run ESE gate on the work-unit.
2. If ESE verdict == HIGH_ENTROPY:
     Invoke rtv-pdr workflow with args.task, args.repo_context, args.n=4
3. If ESE verdict == LOW_ENTROPY:
     Use standard single-agent implementation (do not pay RTV cost).
```

### PDR mode

Set `args.pdr_mode: true` when a previous attempt has already failed and you have failure context to exploit. PDR runs one additional refine rollout conditioned on:
- The tournament winner's distilled summary
- All losers' `failure_modes` (structured, not raw history)

The refine result is then judged against the tournament winner by a fresh agent. Use sparingly — it adds ~2 Opus calls.

## Output shape

```json
{
  "winner": { "id": "R2", "summary": { ...ROLLOUT_SCHEMA... } },
  "runner_up": { "id": "R0", "summary": { ...ROLLOUT_SCHEMA... } },
  "rounds": 2,
  "rationale": "Winner R2 selected by tournament after 2 round(s). ..."
}
```

`runner_up` is the finalist that lost the final match (`null` if fewer than 2 rollouts succeeded).

## Workflow location

`workflows/rtv-pdr.js` in this toolchain repo.
