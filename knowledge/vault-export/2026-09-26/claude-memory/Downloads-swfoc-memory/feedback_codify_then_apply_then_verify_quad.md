---
name: Codify-Then-Apply-Then-Verify Quad Pattern
description: When an audit or surface identifies a codification opportunity, the natural
  shape is audit → codify → apply → verify (4 iters). iter 354-357 (warning cleanup)
  + iter 358-361 (audit-compounds + pre-compound) demonstrate this 4-iter arc. Codified
  at 2/3 trigger per iter-359 meta-rule + forward-applicability precedent. Each iter
  is independently testable; cumulative confidence grows monotonically.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-codify-then-apply-then-verify-quad
---

**Rule:** When an audit or systematic surface identifies a codification opportunity, organize the work as a **4-iter quad**:

1. **Audit (iter N+0)**: run periodic audit OR perform systematic survey; identify CLEAN OR action items
2. **Codify (iter N+1)**: if audit reveals codification opportunity, codify the lesson (memory rule, CLAUDE.md note, or pattern documentation)
3. **Apply (iter N+2)**: apply the codified rule forward to pre-compound future iters OR execute the rule on a current consumer
4. **Verify (iter N+3)**: confirm the application didn't break anything (test re-run, build re-run, filtered verification)

Each iter is independently testable; cumulative confidence grows monotonically across the quad.

**Why:**

2 instances iter 354-357 + iter 358-361 (~7-iter window) demonstrate the 4-iter shape:

| Quad | Audit (N+0) | Codify (N+1) | Apply (N+2) | Verify (N+3) | Total Cycle |
|---|---|---|---|---|---|
| iter 354-357 (warning cleanup) | iter-354 quiet-loop confirmed warning state | iter-355 surgical CS1570/CS8602 fixes (codify-by-doing) | iter-355 fixes applied across 9 files | iter-356 build verify + iter-357 test verify | ~70 min |
| iter 358-361 (audit-compounds + pre-compound) | iter-358 P2HP audit CLEAN | iter-359 codify `feedback_audit_compounds_via_rationale_extensions.md` | iter-360 pre-compound 2 reverse-orphan entries | iter-361 test re-run verify | ~70 min |

Both quads ran in 4 iters / ~70 min total cycle; both ended with empirically-verified GREEN gates.

**Codified at 2/3 trigger per iter-359 meta-rule + forward-applicability precedent.** The codify-apply-verify-quad pattern is a meta-pattern about how to organize codification arcs (audit cadence + codification iter + apply-forward iter + verify iter), not a production code pattern. iter-359 established that "meta-rules with forward applicability codify at ≥2 instances"; iter-363 extends this precedent to the codification-arc-organization layer.

**How to apply:**

When an audit or systematic surface identifies a codification opportunity:

1. **Step 1 — Schedule the audit (~5-25 min)**: 
   - Periodic audits (P2HP, reverse-orphan): run on canonical cadence
   - Systematic surveys (warning audit, MEMORY.md polish): run when staleness suggests it's time
   - Output: identify drift candidates OR confirm CLEAN

2. **Step 2 — Codify if applicable (~25-30 min)**:
   - If audit reveals a NEW pattern OR validates an EXISTING 2/3-trigger pattern, codify in next iter
   - Use the iter-345 11-section template
   - Add to MEMORY.md index
   - Bump Project Status entry codified-rules count

3. **Step 3 — Apply forward (~10-30 min, varies)**:
   - Mirror the iter-329-style rationale extension pattern
   - OR execute the rule on a current consumer (e.g., extract helper, refactor)
   - OR pre-compound a future audit
   - Estimated cost varies; smaller is fine (iter-360 was ~10 min for 2 entries vs predicted 25-35 min)

4. **Step 4 — Verify (~3-10 min)**:
   - Filtered test re-run for the modified files
   - Build re-run if source code touched
   - Confirm 0 regressions, 0 unintended behavior changes
   - Close the chain with empirical evidence

**Honest break-out clause** — when this rule does NOT apply:

- **Audit doesn't surface codification opportunity**: if audit is CLEAN (e.g., iter-272 reverse-orphan; iter-341 P2HP), skip steps 2-4. Quad collapses to single audit iter.
- **Codification candidate is at 1/3 trigger**: skip step 2 (premature); execute steps 3-4 only if pre-compounding is forward-applicable (e.g., iter-360 applied iter-359 rule forward; works because iter-359 was a meta-rule with forward applicability).
- **Application is trivial**: if step 3 is a 1-LoC change with obvious correctness, step 4 may be skipped. Use judgment: comment-only edits like iter-360 still benefit from verification because comments could break XML doc parsing.
- **Quad spans non-adjacent iters**: if intermediate iters (e.g., live SWFOC verify, or operator interruption) split the quad, the pattern still applies but cycle time stretches. Don't force the 4-iter sequence to be consecutive.

**Edge cases worth flagging:**

- **Audit + codify can collapse to 1 iter** when the pattern emerges retroactively (e.g., iter-361 retroactively recognized that iter 354-357 had been a quad). The 4-iter shape doesn't require explicit pre-planning — it can emerge organically.
- **Apply iter can have smaller scope than predicted** when prior work has inadvertently pre-compounded most of the surface (iter-360 found 96% already pre-compounded by iter-191-215 NOTE-block surfacing arc; only 2 entries needed enhancement).
- **Verify iter can be ~3 min total** when filtered tests are fast (iter-357: 67/67 PASSED in 17 ms; iter-361: 1/1 PASSED in <1 ms). Don't over-budget verification.
- **Cumulative confidence grows monotonically**: each step builds on the prior. Audit alone = identification; +codify = abstraction; +apply = action; +verify = empirical confirmation. Skipping any step weakens the chain.
- **The 4-iter shape mirrors the iter-308-321 LocateByConvention plugin set extension shape** (~11 iters; surface→codify→apply→verify pattern at larger scale). The quad is the canonical short version.

**Cost-benefit ratio:**

- **Per-quad cost**: ~70 min total (audit ~5-25 + codify ~25-30 + apply ~10-30 + verify ~3-10)
- **Per-quad value**: 1 codified rule + N applied consumers (typically 1-9 in current project) + N verified GREEN gates
- **Quad ROI vs ad-hoc work**:
  - Without quad structure: codify + apply + verify steps may be skipped or done partially; lose cumulative confidence
  - With quad structure: each step independently testable; failures surface at the right granularity; final state empirically verified
- **2-instance ROI demonstration**: iter 354-357 + iter 358-361 = 14 iters total / 2 codified rules + ~22 fixes (iter-355) + 2 entries pre-compounded (iter-360) + 4 verification gates passed = high-value-per-iter cycle

**Memory-write triggers (2-instance evidence base):**

- **2 instances** iter 354-357 + iter 358-361 (~7-iter window). Pattern survived 2 distinct codification arcs.
- **iter-361 was the codification trigger at 2/3** per iter-359 meta-rule precedent. Future incidents (instance #3+) should EXTEND this rule rather than create new ones — most likely add a row to the table above.
- **Predicted 3rd instance**: any future audit-driven codification arc (iter-368 reverse-orphan audit if it surfaces drift + codification opportunity; OR next memory-rule codification iter).

**Prospective uses (iter-364+):**

When the next audit surfaces a codification opportunity:

- **iter-368 reverse-orphan audit** (5 iters away): if it surfaces drift OR codification opportunity, follow the quad shape directly
- **Next memory-rule codification iter**: when one of the 5 candidates at 2/3 trigger advances to 3/3, follow the quad
- **NEW arc-class kickoff** (deferred per iter-271): when shipped, will likely produce a codification arc that fits the quad shape

**Pattern reinforcement:**

This rule is the **arc-organization companion** to:
- `feedback_audit_compounds_via_rationale_extensions.md` (iter-359 codified) — the audit-side pattern about WHY rationale extensions compound
- `feedback_iter_strategy_preflight_stack.md` (iter-337 codified) — the iter-strategy preflight stack that should run BEFORE entering a quad
- `feedback_codification_value_proven_by_next_iter.md` (1/3 trigger; iter-338) — codification value proven by next iter ≈ codify→apply where apply happens immediately

Combined: when an audit surfaces codification opportunity, run the quad → the codify-apply-verify chain validates the rule + applies it forward + provides empirical verification. The iter-337 preflight stack runs BEFORE the quad to catch existing infra. The iter-359 audit-compounds rule applies WITHIN the quad as the codified meta-pattern.

**Cross-link to related codified rules:**

- `feedback_audit_compounds_via_rationale_extensions.md` (iter-359) — the meta-rule the iter 358-361 quad codified
- `feedback_iter_strategy_preflight_stack.md` (iter-337) — preflight should run BEFORE quad
- `feedback_resolver_injection_at_composition_root.md` (iter-345) — pattern with HIGHEST evidence (8 instances) provides codification template
- `feedback_engine_already_does_this.md` (iter-302) — 6-instance precedent; quad pattern at 2-instance trigger uses iter-359 meta-rule justification
- `feedback_dotnet_test_hang_diagnosis.md` (iter-172) — toolchain rule for running the verify-step tests