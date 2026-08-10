---
name: rubric-verifier
description: Use AFTER N candidate patches exist (from codex council / /multi-execute / external-tools Codex+Gemini fan-out) and BEFORE running tests, to select the best candidate execution-free. A fresh-context reviewer builds a repo-grounded rubric — a weighted checklist of issue-specific criteria — then scores every candidate diff against it and returns a ranked pick with rationale. ADVISORY only: the ranked pick is a recommendation, not a gate; the 100%-coverage VALIDATE step remains the blocking authority. Skip when only one candidate exists, or when the issue is trivially localised and any diff that compiles is correct. Based on "Agentic Rubrics as Contextual Verifiers" (arXiv:2601.04171, Scale AI).
metadata:
  version: 0.1.0
  compatibility: claude-code codex cursor gemini-cli opencode
  source: https://arxiv.org/abs/2601.04171
  upstream_authors: Scale AI
---

# Rubric Verifier — execution-free candidate selector

Select the best among N candidate patches **without running any tests**, by having a
fresh-context reviewer build a repo-grounded rubric and score each candidate against
it.  The output is a ranked advisory list; the coverage gate remains the hard blocker.

## Why this exists

After `/multi-execute`, `codex council`, or an external-tools (Codex + Gemini) fan-out
you have N candidate diffs for the same task.  The current pipeline has no principled
execution-free SELECT step:

| Existing skill | What it does | Gap |
|---|---|---|
| `fresh-context-verify` | re-derives one load-bearing value | single-value, not N-candidate ranking |
| VALIDATE (metaswarm) | runs tests | execution required; expensive to run N times |
| `code-review` | hunts for bugs in one diff | not a multi-candidate rubric scorer |

This skill fills the SELECT point: pick the best candidate before spending test-runner
cycles on all N.

## Trigger

Run this skill **after** N ≥ 2 candidate diffs exist and **before** VALIDATE, when:
- A `/multi-execute` or `codex council` run has produced N patches in a manifest file
  (default: `.multi-execute/candidates/` or `.council/candidates/`), **or**
- External-tools (Codex CLI + Gemini CLI) have each produced a patch and you need to
  pick one before committing to the VALIDATE loop.

Skip when:
- Only one candidate exists (nothing to rank).
- The issue is trivially localised (one-liner typo fix) — any diff that compiles is fine.

### Composition with existing gates
### Phase 1 — Rubric Construction (FRESH context)
### Inputs to pass to the fresh-context Task
### Fresh-agent exploration protocol
### Rubric format (agent output)
### Phase 2 — Scoring (same or new Task per candidate)
### Scorer prompt template
### Parallelism option
### Phase 3 — Aggregate and Report
### Rubric Verifier — Advisory Ranking
### Ranking
