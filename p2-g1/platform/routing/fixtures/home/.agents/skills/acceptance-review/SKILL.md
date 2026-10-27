---
name: acceptance-review
description: Use at the "done" boundary of an app change — before claiming a feature/app works, before a PR, or when a repair session says "fixed / it works now / shorts generate". Dispatches an INDEPENDENT, ideally CROSS-MODEL reviewer (Codex or Gemini CLI, else a fresh-context Claude subagent) that adversarially judges whether the real end-to-end user journey actually works or is green-but-broken — over the DIFF + declared golden-journeys + on-disk artifact evidence the journeys ran. Returns a structured SHIP / BLOCK verdict with the unproven journeys and concrete gaps. Do NOT use for ordinary code-quality review (use code-review) or for in-context self-checking (that is the biased judge this skill exists to replace).
---

# Acceptance Review — the cross-model "does it actually work?" verdict

The external-signal verifier for the "done" boundary. A capable model optimizes its
own done-signal — coverage, "tests pass" — and stops, while the real product is
broken (dead buttons, "shorts don't generate", a severed A→B→C flow). The signal is
gameable because the *same context that wrote the code certifies it*: intrinsic
self-correction degrades (Huang, ICLR'24), verifier↔generator errors couple
("Verification Mirage"), and judges prefer their own output (Panickssery, NeurIPS'24).
This skill breaks that loop with **verifier separation** — an evaluator that did NOT
write the code and, when possible, is a **different model** (VeriMAP / MetaGPT), which
demands the real artifact and is forbidden from trusting coverage.

It complements the always-on functional-acceptance hooks (`claim-guard`,
`test-tamper-guard`, `journey-coverage`): those *gate silently on static signals*; this
is the human/orchestrator-facing reviewer that *judges the running-app evidence and
returns a verdict*. See `docs/agentic-perfection/AGENTIC-REPAIR-RELIABILITY.md`
(NORTH-STAR REPAIR FLOW: "fresh-context / cross-model acceptance review over the real
running app").

## When to run
- Before claiming an app/feature is done, works, or ships; before opening a PR.
- At the end of a repair session — especially after an assertive "fixed / it works now".
- Whenever "coverage is green" is the only evidence offered that the journey works.


### Procedure
### The adversarial contract (baked into the prompt)
### Guardrails
### Files
