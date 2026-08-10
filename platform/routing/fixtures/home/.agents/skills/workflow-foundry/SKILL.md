---
name: workflow-foundry
description: Use when RUNNING a multi-agent fan-out on this estate — dispatching N parallel work units, deciding barrier-vs-pipeline, gating fan-in, or judging whether a unit is actually done. The operating contract distilled from measured runs here, not generic advice: freeze the SHA and the spawn preamble before the first unit launches; fan in on RECEIPTS (Test-Path every contracted output BEFORE reading any digest — 3/3 agents once returned plausible digests for files that did not exist); UNIT-COMPLETE is a string the unit writes about itself, not proof; pipeline by default and use a barrier only when stage N genuinely needs ALL of stage N-1; write-as-you-go (a 70-minute unit produced 691 KB and wrote nothing, unrecoverable); both-states controls (a probe silent in the broken state measures nothing); never fan a MECHANICAL comparison out to LLM judgement (measured 86% accuracy with 100% of errors in the dangerous direction against an exact 40-line differ); per-needle deferral is the wrong LAYER and recurses, only a role-aware discriminator terminates; adversarial verifiers get siblings FULL text not digests; and most refutations are OVERCLAIMS where the code was right and the sentence was too wide — fix the sentence. Ships a runnable receipt gate with a built-in both-states self-test. Triggers include fan out N agents, gate the fan-in, is this unit done, my parallel phase deadlocked, an agent returned a digest for a missing file, design the work-unit decomposition, review the siblings adversarially. NOT for writing the workflow .mjs runtime code (use workflow-authoring), NOT for the cross-vendor Codex dispatch transport (use cross-vendor-dispatch and multi-ai-mingle), NOT for remote compute placement (use codex-databricks-fanout).
---

# workflow-foundry

The **run-time operating contract** for a fan-out on this estate. Ten laws, each one paid
for by a measured failure here. Every number below is MEASURED; do not re-derive it from
first principles and do not soften it because a run "looks fine".

**Where this sits.** `workflow-authoring` tells you how to WRITE the `.mjs` (the injected
`agent`/`parallel`/`phase` globals, the args-as-string gotcha, the `Date.now()` ban).
`cross-vendor-dispatch` owns the Claude→Codex transport. `codex-databricks-fanout` owns
remote compute placement. **This skill owns what happens between "launch" and "done".**

**The card catalogue is elsewhere.** 108 named blueprint cards live in
`~/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.md` (464 KB). This skill
is the contract those cards must satisfy, not a copy of them. Pick a card there; obey the
laws here.

Evidence anchors with access methods: `references/evidence-index.md`. Read it before citing
any rule path — the live `~/.claude/rules/common/` tree was measured EMPTY on 2026-08-08
while its content was still being injected into sessions, so the durable citation is the
repo copy, not the live path.

---

## L1 — Freeze before you fan out

Freeze **three** things the moment the first unit launches, and change none of them until
the cohort is dead:

1. the **commit SHA** every unit reads (record it in the preamble, so all N sets of
   `file:line` citations resolve against one tree),
2. the **spawn preamble**,
3. the **launcher**.

### L2 — Fan in on RECEIPTS, never on digests
### L3 — `UNIT-COMPLETE` is text, not proof
### L4 — Pipeline by default; a barrier only when stage N needs ALL of stage N-1
### L5 — Write as you go
### L6 — Both-states, or it does not count
### Independence must hold across TIME, not just mechanism
### L7 — Never fan a MECHANICAL comparison out to LLM judgement
### L8 — Per-needle deferral is the wrong LAYER; only a role-aware discriminator terminates
### L9 — Adversarial verifiers get siblings' FULL text, not digests
### L10 — Most refutations are OVERCLAIMS — fix the SENTENCE
### The spawn preamble is not inherited — restate it every time
### Windows transport (this box)
