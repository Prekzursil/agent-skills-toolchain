---
name: execution-grounded-bon
description: Use when you have SEVERAL candidate patches/solutions for the same task — typically from a cross-vendor Claude+Codex worktree fan-out — and must pick the best one WITHOUT trusting an LLM to judge them (JudgeBench shows model-opinion rerank ≈ chance). Synthesize distinguishing inputs where the candidates diverge, execute all candidates on them, cluster by behavior (behavioral-diff), knock out crashers/timeouts, and select by EXECUTION-CONSENSUS — where an independent Claude candidate and an independent Codex candidate agree, that agreement is the signal (cross-vendor = independent failures). A BoN-MAV aspect jury ranks within the winning cluster. Distinct from A3 fail-first (validates ONE author's own tests) and diff-blind-test-synth (one patch vs spec-derived tests). Ships SHADOW: observe + log only, never blocks. Evidence: MASTER A4, COUNCIL C3; arXiv 2502.14382 (S*), 2409.08692 (B4), 2503.15223 (PatchDiff), 2207.10397 (CodeT).
---

# Execution-Grounded Best-of-N + Behavioral-Diff Reranker

When N agents produce N candidate patches for the same task, the naive rerank is to ask a model "which is best?" — and that is proven near-worthless: an LLM judge over candidate code lands around chance on adversarial selection (JudgeBench), and it is exactly the same-context self-grading the whole Theme-A verification program exists to route around (Goodhart + the intrinsic self-correction ceiling, Huang ICLR'24). The done-signal must be **external and agent-inauthorable**.

Execution is that signal. Instead of an opinion, run every candidate on inputs chosen to make them disagree, watch what they actually *do*, and let their behavior cluster them. Candidates that crash or hang eliminate themselves. Candidates that independently converge on the same behavior — especially across two different vendors — are the ones to trust: two independent samples agreeing is the classic oracle-free consensus signal (CodeT), and cross-vendor agreement makes the two samples' blind spots independent (a Claude bug and a Codex bug are unlikely to be the *same* bug).

Grounded in: **S\*** (2502.14382, distinguishing-input synthesis for candidate selection), **B4** (2409.08692, Bayesian best-selection over execution results), **PatchDiff** (2503.15223, behavioral patch differencing), **CodeT** (2207.10397, dual-execution agreement without a ground-truth oracle). MASTER A4 / COUNCIL C3 both mandate: gate on executable evidence, **never model opinion**.

### When to run
### What makes this distinct (do not conflate)
### The bus this rides (do not rebuild)
### Protocol
### The reranker: `rerank.mjs`
### precomputed: manifest already carries candidates[].observations[]
### execute: run each candidate's cmd once per probe to build the behavior matrix
### machine-readable (pure JSON on stdout; terminal marker goes to stderr)
### prove the logic on this machine (13 embedded assertions)
### Manifest schema
### Pipeline (all stages pure & execution-derived — no model opinion)
### Verdict (excerpt)
### SHADOW mode (per COUNCIL C5 — always ship observe-only)
