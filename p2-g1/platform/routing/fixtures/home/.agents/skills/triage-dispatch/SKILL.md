---
name: triage-dispatch
description: Use when repairing an app with MULTIPLE bugs or broken user-journeys at once (not a single fix) — instead of edit-one-file / rerun-the-whole-suite / hope, first map the broken journeys with evidence, capture each REAL error (never infer the failing stage from surviving artifacts), build a defect graph, then dispatch parallel bounded-scope fix agents and verify only impacted regions before an outer full+e2e+mutation gate. NOT for a single well-understood one-line fix, and NOT a substitute for the held-out golden-journey done-signal.
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

### 3. Build the defect graph
### 4. Dispatch parallel fix agents — bounded scope, isolated
### 5. Inner-loop verify only impacted regions
### 6. Outer gate at the commit boundary
### 7. Independent acceptance review
### Anti-patterns this replaces
### Cross-links
