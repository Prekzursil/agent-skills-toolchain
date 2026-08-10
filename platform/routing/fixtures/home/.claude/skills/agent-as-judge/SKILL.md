---
name: agent-as-judge
description: Advisory, evidence-citing Agent-as-a-Judge. Use when you want a second opinion on whether a completion meets its Definition of Done AFTER the deterministic verification cluster (typed receipts, fail-first red-proof, execution-consensus, golden-journey oracle) has run — it decomposes the DoD into falsifiable YES/NO items, cites a ledger-event or evidence-hash per item (chain-of-custody), execute-to-confirms every would-be-blocking finding, and scores against the ICD-203 nine analytic standards. Its opinion NEVER gates or grants "done" (COUNCIL C3): only a re-run executable receipt could ever block and that path is deferred indefinitely, so it is 100% ADVISORY and ships in SHADOW mode (observe + log, never blocks, never nags). Imports passk-stats (F5) for kappa/e-value calibration vs the owner's claude-reflect corrections; stays advisory while kappa < 0.6 and auto-demotes on decay. NOT a done-gate, NOT terminal authority; a same-vendor judge shares the fixer's blind spots so prefer a cross-vendor Codex second judge on contested calls. Do NOT use to BLOCK a merge/completion, and do NOT use it in place of the deterministic gates.
---

# Agent-as-a-Judge (advisory, evidence-citing)

A tool-using LLM judge that annotates the **subjective residue** of a Definition of Done — the
items the deterministic gates cannot decide ("is the artifact actually correct?", "does this
match intent?"). It is **advisory this wave**: its opinion never gates, and it ships in SHADOW
mode. The subagent contract lives in `agents/agent-as-judge.md`; this skill is the operator guide
plus the reference implementation the judge runs.

**Evidence:** MASTER-DECISION-QUEUE A5 (`gem-hunt-2026-07-12`); COUNCIL-VERDICT C3
(*"opinion never gates, only a cited executed receipt can block — deferred indefinitely"*).
Research: Agent-as-a-Judge (arXiv 2410.10934); ICD-203 Analytic Standards; EvalGen (2404.12272);
JudgeBench (LLM judges ~chance) — the empirical basis for the advisory-until-calibrated stance.

## Where it sits in the pipeline (read this first)

```
   deterministic cluster (carries ALL blocking weight, no calibration needed)
   ┌─────────────┬──────────────┬────────────────────┬─────────────────────┐
   │ A1 typed    │ A3 fail-first│ A4 execution-      │ C4 golden-journey   │
   │ receipts    │ red-proof    │ consensus          │ oracle (keystone)   │
   └─────────────┴──────────────┴────────────────────┴─────────────────────┘
                                   │  green?
                                   ▼
              ┌─────────────────────────────────────────────┐
              │  Agent-as-a-Judge  (THIS)  — runs AFTER      │
              │  ADVISORY · SHADOW · annotates SUBJECTIVE DoD │

### When to use
### When NOT to use
### The contract in one screen
### Protocol (four steps)
### Calibration harness (passk-stats / F5)
### Shadow-mode logging (COUNCIL C5)
### Reference implementation
### Honest limits
