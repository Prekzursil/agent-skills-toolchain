---
name: research-ops
description: Thin operator entry for the research stack. Use when the user wants fresh facts, comparisons, enrichment, or an evidence-backed recommendation — it routes you to the right research skill rather than duplicating one.
origin: ECC
---

# Research Ops (thin pointer)

Operator wrapper around the repo's research stack. It does **not** duplicate those skills — it
tells you which to reach for. The synthesis engine is **`deep-research`**; escalate to it whenever
the answer needs multiple sources, citations, or confidence grading.

## Route To

- **`deep-research`** — the orchestrator: multi-source synthesis, numbered citations, confidence
  grading, basic-memory persistence. Default for anything non-trivial.
- **`exa` MCP** (`web_search_exa`) — fast current-web discovery for a single quick fact.
- **`market-research`** — when the outcome must be a ranked recommendation / decision memo.
- **`lead-intelligence`** — when the real ask is people/company targeting, not generic research.
- **`knowledge-ops`** — when the result should be stored in durable context afterward.
- **`search-first`** — SEPARATE domain (research-before-*coding*: find existing libs/patterns,
  invokes the `researcher` agent). Use it, not this, for implementation research.

## Discipline (applies whichever lane you pick)

- Don't answer current questions from stale memory when fresh search is cheap; don't spin up a
  heavyweight pass when local code/docs already hold the answer.
- Label every claim by evidence type: **sourced fact · user-supplied context · inference ·
  recommendation**. Freshness-sensitive answers carry concrete dates.
- If the same lookup will recur, say so and recommend a monitor/workflow instead of repeating it.

The full loop (scope → preflight → dispatch → synthesize → reflect → self-eval → deliver/persist),
untrusted-content rules, and output format live in **`deep-research`** — do not restate them here.
