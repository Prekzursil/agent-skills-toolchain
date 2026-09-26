---
title: Hooks Candidate Adversarial Triage 2026-06-15
type: note
permalink: main/decisions/hooks-candidate-adversarial-triage-2026-06-15
tags:
- hooks
- triage
- decision
- anti-overfit
---

# Hooks Candidate Adversarial Triage (2026-06-15)

Evaluated 7 hook candidates against the curated ~6-hook stack + hard philosophy (external-anchor law, anti-overfit, non-nagging, fail-open).

## Verdicts
- **claude-guard-hooks** — ADOPT. Net-new OUTPUT guard: Stop-turn gated on on-disk command ledger when model asserts "tests pass"/"fixed"/"not found". Mechanizes AGENTS.md §7 + "NEVER self-certify". event-ledger records turns but does NOT gate Stop on claim/evidence. Caveat: claim-phrase guards can false-positive; pilot first.
- **redline** — MAYBE. Fresh Codex model reviews uncommitted diff at Stop, diff-hash gated. True external anchor BUT overlaps codex-review/council + security-guidance baseline-diff (#7). Net-new = auto trigger vs model-invoked. Second-model luxury; #7 fills the always-on slot.
- **context-diet** — ADOPT. Deterministic tool-output compressor; cross-call Read DEDUPE is net-new vs harness-trim (system-noise only). No LLM, fail-open.
- **TaskOutput guard (secondcircle)** — ADOPT. Intercepts full-transcript TaskOutput re-dumps per poll. Exactly the Ralph-loop/council fan-out burn channel nothing in stack covers. Needs Windows temp-path edit.
- **guardian** — MAYBE. Only the budget/action-count kill-switch (user has NO cost circuit-breaker, dropped beads). VERIFIED: event-ledger uses sha256 only for dir slug, NOT chained audit, so guardian's chain IS a real upgrade — but integrity theater they likely don't need. Cherry-pick budget cap; reject policy-gate/blocklist (dup sonar-secrets, anti-overfit).
- **ctxguard** — REJECT. Pre-Read low-signal warner overlaps context-diet cleanup; per-Read injection drifts toward nagging. 3 context-budget tools (diet/taskoutput/ctxguard) violates anti-overfit — pick output-side compressors.
- **security-guidance baseline-diff** — ADOPT (already allow-listed). Lift the baseline-diff mechanic (git stash create @ submit -> diff @ Stop -> advance baseline, Haiku review, exit 2). External-anchored Stop-time floor; makes redline redundant.

## Key fact
event-ledger/ledger.py line 35: sha256 is a non-crypto dir slug only. No per-entry hash chain. (Relevant to guardian's "stronger integrity" claim — true but low-value.)
