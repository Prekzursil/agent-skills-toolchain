---
name: triage-dispatch
description: Use when repairing an app with MULTIPLE bugs or broken user-journeys
  at once (not a single fix) - instead of edit-one-file / rerun-the-whole-suite /
  hope, first map the broken journeys with evidence, capture each REAL error, build
  a defect graph, then dispatch parallel bounded-scope fix agents and verify only
  impacted regions before an outer full+e2e+mutation gate.
permalink: dqverify-repo-20261013/skills/triage-dispatch/skill
---

# triage-dispatch — audit → defect-graph → parallel bounded fixes → verify

The repair method that beats blind edit-one-file-then-rerun-the-whole-suite. It exists because
scattershot repair wastes tokens and expands SCOPE instead of precision (ProjDevBench ~138 turns /
4.81M tokens per end-to-end problem; the 20,574-session developer-agent study: agent edits grow the
change footprint, not the fix precision). Pair it with `two-tier-verify`, `seed-golden-journey`, and
`acceptance-review`.

## When to use
Multiple bugs / several broken journeys / a "held together with chewing gum" app where you'd otherwise
fix one thing, re-run everything, and chase symptoms. Skip it for a single, well-understood one-liner.

## The method

### 1. Audit-first — map the broken journeys with evidence
Enumerate the app's real user journeys and, for each, whether it works — with EVIDENCE (a run, a
produced artifact, a screenshot), not a guess. The output is a list of BROKEN journeys, each with a
concrete failing observation. Coverage/green units are not evidence here.

### 2. Capture the REAL error — never infer the stage from artifacts
For each broken journey, capture the actual error before touching code. A surviving artifact on disk
tells you which stage RAN, not which stage FAILED. If the failure is in a background job / sidecar whose
error is not surfaced, drive it directly and drain its stderr (e.g. spawn the sidecar over its JSON-RPC,
send the request, read notifications to done, collect the logged traceback). Inferring the stage costs
fix-the-wrong-thing detours.

### 3. Build the defect graph
Trace each symptom to its code site(s) and record dependencies between fixes (which must land before
which; which share a file; which are independent). A defect graph localizes work and reveals safe
parallelism (GraphLocator, FSE'26: +function-recall / +resolve-rate over blind localization). Note the
common-root clusters — several symptoms often share one cause (a CRLF line-ending, a Windows-path escape,
a teardown crash).

### 4. Dispatch parallel fix agents — bounded scope, isolated
For independent defect-subgraphs, dispatch one fix agent each, with a DECLARED file scope, in an isolated
worktree (so parallel edits can't collide). Re-anchor the original goal + the specific defect at the top
of each handoff (structured summary, never raw prior output). A bounded scope is the guard against the
scope-creep the misalignment study measured.

### 5. Inner-loop verify only impacted regions
Per fix, run only the affected/related tests + type + lint on touched files (see `two-tier-verify` inner
loop) — Ekstazi/TIA/CloudBees cut test time 32-70%. Do not re-run the whole suite per edit.

### 6. Outer gate at the commit boundary
Once fixes land: full suite + coverage + the held-out golden-journey/E2E + `mutation-check`, ONCE. On an
outer failure, map it back to the defect graph (git bisect / the one failing test) rather than re-auditing.

### 7. Independent acceptance review
Before declaring done, run `acceptance-review`: a fresh-context / cross-model reviewer over the diff +
the journeys + the real artifacts. SHIP only if every declared journey has a real post-change artifact.
Never self-certify.

## Anti-patterns this replaces
- Edit one file → rerun the entire suite → repeat (token churn, no localization).
- Inferring the failing stage from what landed on disk (fix-the-wrong-thing).
- One agent grinding all bugs serially in one context (scope creep, drift, degraded verification).
- "Green units / 100% coverage" cited as done (Goodhart — see `seed-golden-journey`).

## Cross-links
`seed-golden-journey` (the done-signal these fixes must satisfy) · `two-tier-verify` (the inner/outer
loops) · `acceptance-review` (the independent verifier) · `mutation-check` (test-strength at the gate) ·
`fresh-context-verify` (re-derive a load-bearing anchor in a clean context).