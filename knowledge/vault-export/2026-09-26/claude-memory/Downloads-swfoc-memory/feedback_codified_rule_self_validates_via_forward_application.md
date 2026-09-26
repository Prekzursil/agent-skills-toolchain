---
name: Codified-Rule-Self-Validates-Via-Forward-Application Pattern
description: When a codified rule includes a "Prospective uses" section citing future
  cadence triggers as forward-applicability targets, those targets create empirical
  self-validation feedback loops. iter-359→360 (audit-compounds applied to reverse-orphan
  annotations) + iter-368→370 (audits-clean predicting P2HP outcome) demonstrate the
  pattern. Each codified rule's prospective-use section is testable at the next cadence
  trigger; matched predictions validate the rule, mismatched predictions refine it.
  Codified at 2/3 trigger per iter-359/363/368/371 Tier 4 precedent. Meta-meta pattern
  about codified rules' own self-test feedback loops.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-codified-rule-self-validates-via-forward-application
---

**Rule:** When codifying a meta-rule (Tier 3 or 4), include a **"Prospective uses" section** that:

1. Cites specific future iter numbers as forward-applicability targets
2. Predicts outcome at each target per the rule's logic
3. Documents what would refute the rule (the rule's falsifiability)

When the cadence trigger lands, the prospective-use section gets empirically tested:
- **Prediction matches outcome** → rule self-validates; codification was correct
- **Prediction mismatches outcome** → rule needs refinement; the failure mode informs Tier 5 thinking

This creates a self-test feedback loop at the codification layer: codified rules generate hypotheses about their own future use, and the future tests the hypotheses.

**Why:**

2 instances iter-359→360 + iter-368→370 demonstrate the pattern at the meta-meta layer:

| Codified rule | Forward-applied iter | Prediction | Actual outcome | Validation |
|---|---|---|---|---|
| `feedback_audit_compounds_via_rationale_extensions.md` (iter-359) | iter-360 (apply rule to pre-compound reverse-orphan annotations) | iter-329 extensions compound across audits | iter-358 + iter-367 both CLEAN with iter-329 extensions cited | **VALIDATED** |
| `feedback_audits_clean_when_no_new_wires.md` (iter-368) | iter-370 (apply rule to predict P2HP audit outcome) | 0 new visible wires → CLEAN | iter-370 audit empirically CLEAN | **VALIDATED** |

Both rules were codified with prospective-use sections; both predictions were validated at the next cadence trigger. The pattern is meta-meta because it's about codified rules' own forward-applicability sections (not about the rules' subject matter).

**Codified at 2/3 trigger per iter-359/363/368/371 Tier 4 precedent.** This is the 5th Tier 4 codification (cluster: iter-359/363/368/371/373). The audit-organization arc (iter 358-373) emerged this meta-meta pattern as natural consequence of codifying meta-rules with built-in falsifiability.

**How to apply:**

When codifying a Tier 3 or 4 rule:

1. **Step 1 — Identify forward-applicability targets** (~5-10 min):
   - List specific future iter numbers where the rule's logic applies (next audit cadence, next codification iter, etc.)
   - Be specific: "iter-375 P2HP audit predicted CLEAN per rule" not "future audits should be CLEAN"
   - Falsifiability: state what would refute the rule (e.g., "if iter-375 catches drift, rule's prediction logic needs refinement")

2. **Step 2 — Document prospective-use section** (~5 min):
   - Add 11-section template's "Prospective uses (iter-N+)" section
   - Cite specific target iters with predictions
   - Include cost-benefit ratio (asymmetric if prediction CLEAN saves time, costs nothing when wrong)

3. **Step 3 — Validate at next cadence trigger** (1-5 iters later):
   - When target iter lands, the prospective-use section gets empirically tested
   - If validated: ship close-out doc citing self-validation
   - If refuted: ship close-out doc explaining mismatch + propose rule refinement

4. **Step 4 — Track validation history**:
   - Each codified rule's "Why" section accumulates validation instances over time
   - Rules with multiple validations have stronger evidence base
   - Codification queue tracks validation count per rule

**Honest break-out clause** — when this rule does NOT apply:

- **Production patterns (Tier 1)**: prospective-use sections add little value because production patterns are validated by use-site count, not future predictions. Skip step 2 for Tier 1 codifications.
- **Toolchain rules (Tier 0)**: same as Tier 1 — toolchain rules validate via reproducibility, not predictions.
- **Rules without natural cadence triggers**: if the rule applies to one-off events (e.g., bridge dispatcher refactor), there's no next-cadence to validate against. Skip prospective-use section.
- **Rules with too-distant forward applicability**: if the next cadence trigger is >50 iters away, the prospective-use section becomes stale before validation. Cite multiple shorter-horizon targets instead.

**Edge cases worth flagging:**

- **Self-validation strengthens evidence**: each forward-applicability test adds to the rule's evidence base. Rules with 3+ validations should consider promotion (Tier 4 → Tier 3+ at higher confidence).
- **Refuted prediction is informative**: if forward-applied prediction is refuted, the rule's logic needs refinement. The failure surfaces Tier 5 thinking.
- **Bidirectional self-validation**: iter-368 → iter-370 + iter-359 → iter-360 are forward-applications. iter-370 → future audits become forward-applications of iter-370's confirmation. Self-validation chains compound.
- **Prospective-use section size**: keep to ~5-10 lines per target iter; bloating > 20 lines per target dilutes signal.
- **Multiple targets per prospective-use section**: cite 2-3 targets (next cadence + secondary cadence + Thread B/C/D/E kickoff). Diversifies validation.

**Cost-benefit ratio:**

- **Per-codification cost**: ~5-10 min to write prospective-use section
- **Per-validation savings**: ~0 min (validation is implicit at target iter; no extra work)
- **Per-validation evidence boost**: rule's "Why" section accumulates instances; future codification thresholds can use stronger evidence
- **Per-refutation cost**: ~10-15 min to ship refinement close-out (rule needs update); but refuted prediction is informative — failure surfaces Tier 5 thinking

**Memory-write triggers (2-instance evidence base):**

- **2 instances** iter-359→360 + iter-368→370 (~9-iter window). Both codified rules included prospective-use sections; both predictions validated.
- **iter-370 was the codification trigger at 2/3** per iter-359/363/368/371 Tier 4 precedent. Future incidents (instance #3+) should EXTEND this rule with new validation instances.
- **Predicted 3rd instance**: iter-371 → next audit cadence trigger (iter-389+ reverse-orphan or iter-387+ P2HP); iter-371 included prospective-use section. Validation expected.

**Prospective uses (iter-374+):**

When codifying future Tier 3/4 rules:

- **iter-374+ codification iters**: include prospective-use section per this rule
- **iter-389+ reverse-orphan audit**: validates iter-371 audit-prep-force-multiplier rule's prospective use of "next prep+audit pair"
- **iter-387+ P2HP audit**: validates iter-371's prospective use OR iter-368's continued forward applicability
- **NEW arc-class kickoff**: codifying patterns from new arcs should include prospective-use section per this rule

**Pattern reinforcement:**

This rule is the **self-test side** of:
- `feedback_codify_then_apply_then_verify_quad.md` (iter-363) — quad pattern's verify step is the empirical self-validation
- `feedback_audit_compounds_via_rationale_extensions.md` (iter-359) — first instance of forward-applicability validation
- `feedback_audits_clean_when_no_new_wires.md` (iter-368) — second instance with cross-category generalization
- `feedback_audit_prep_force_multiplier.md` (iter-371) — execution-side companion

Combined: when an audit cadence triggers, run iter-371 prep + iter-368 prediction + iter-373 self-validation tracking. Each codified rule generates hypotheses about its own future use; future tests validate or refine.

**Cross-link to related codified rules:**

- `feedback_audit_compounds_via_rationale_extensions.md` (iter-359) — 1st forward-applicability validation
- `feedback_audits_clean_when_no_new_wires.md` (iter-368) — 2nd forward-applicability validation
- `feedback_codify_then_apply_then_verify_quad.md` (iter-363) — quad pattern includes self-test step
- `feedback_audit_prep_force_multiplier.md` (iter-371) — companion execution-side rule
- `feedback_iter_strategy_preflight_stack.md` (iter-337) — preflight reads codified rules' prospective-use sections to gate iter design