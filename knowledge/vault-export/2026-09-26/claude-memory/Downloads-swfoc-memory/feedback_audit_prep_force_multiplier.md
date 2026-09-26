---
name: Audit-Prep Force Multiplier Pattern
description: A 1-iter audit-prep doc preceding a periodic audit cadence trigger reduces
  the audit iter's cycle time by ~5-10 min. Prep iter surveys iter-since-last-audit
  for new visible wires, applies iter-368 codified rule to predict outcome, documents
  audit-readiness checklist. Audit iter then runs quickly with prediction validation.
  iter-366→367 reverse-orphan + iter-369→370 P2HP = 2 instances. Codified at 2/3 trigger
  per iter-359/363/368 Tier 4 precedent. Generalizes across audit categories.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-audit-prep-force-multiplier
---

**Rule:** When approaching a periodic audit cadence trigger (P2HP, reverse-orphan, or other), spend 1 iter (~5-10 min) on audit prep BEFORE the audit cadence iter. The prep iter:

1. Surveys iter-since-last-audit close-out docs for new visible wire additions
2. Applies iter-368 codified `feedback_audits_clean_when_no_new_wires.md` rule to predict outcome (CLEAN if 0 new wires; possible drift if N>0 new wires)
3. Documents audit-readiness checklist for the actual audit iter

This compounds across the audit cycle: the audit iter then runs in ~3-5 min (vs ~15-20 min unprepped) because the prediction is documented and the audit just empirically confirms or refutes it.

**Why:**

2 instances iter-366→367 + iter-369→370 demonstrate the pattern across distinct audit categories:

| Prep iter | Audit iter | Audit category | Iters covered | Predicted | Actual | Cycle time |
|---|---|---|---|---|---|---|
| iter-366 | iter-367 | Reverse-orphan | iter 273-364 (92 iters / 0 new wires) | CLEAN | CLEAN | ~3 min audit |
| iter-369 | iter-370 | P2HP | iter 358-368 (11 iters / 0 new wires) | CLEAN | CLEAN | ~5 min audit |

Both pairs ran in ~10-15 min total cycle time (prep ~10 min + audit ~3-5 min) vs the typical ~15-20 min for unprepped audits. The prep iter pays back time on the audit iter, AND surfaces forward-applicability validation as a side effect.

**Codified at 2/3 trigger per iter-359/363/368 Tier 4 precedent (meta-rules with forward applicability ≥2 instances).** The pattern is meta-level (about audit-iter organization), generalizes across audit categories, and compounds with iter-368 (which provides the prediction logic).

**How to apply:**

When approaching a periodic audit cadence trigger:

1. **Step 1 — Schedule the prep iter ~1-3 iters before the audit** (~5-10 min):
   - Read `knowledge-base/iter${PRIOR_AUDIT}_*.md` close-out for prior baseline
   - Survey iter-since-last-audit close-out docs for new visible wire additions (per iter-368 rule)
   - Apply iter-368 rule: 0 new wires → CLEAN prediction; N>0 → potential N drift catches
   - Document audit-readiness checklist (test command, expected result, drift triage steps)

2. **Step 2 — Schedule the audit iter at canonical cadence** (~3-15 min):
   - Run filtered test via iter-356 codified PowerShell wrapper
   - Confirm or refute prediction
   - If CLEAN: ship CLEAN close-out validating prep prediction
   - If DRIFT: triage per iter-323 playbook, update prep prediction model

3. **Step 3 — Optional cadence advance** (~0 min if predicted CLEAN with high confidence):
   - Per iter-368 rule + iter-370 advance precedent, audit cadence can advance by N iters when predicted CLEAN
   - Saves N iters of canonical-cadence wait time
   - Risk: if drift catch surfaces, cadence-advance was premature; budget extra triage time

4. **Step 4 — Update codification queue if pattern observations surface**:
   - Each prep→audit pair MAY surface meta-pattern observations
   - Track candidates per iter-352 backlog inventory pattern

**Honest break-out clause** — when this rule does NOT apply:

- **Prep iter would be wasted if audit cadence triggers immediately**: if the canonical cadence trigger lands in the SAME iter as the prep would run, skip the prep and run the audit directly.
- **First audit in a new category**: no prior baseline to compare against; prep iter has nothing to survey. First audit establishes the baseline; subsequent audits get prep benefit.
- **Audit category has frequent drift**: if drift catches happen >50% of audits, prep prediction would be CLEAN but actually drift; rule provides limited value. Wait until drift rate drops before applying.
- **Cadence trigger is dependency-driven, not periodic**: e.g., audit triggered by user request, not schedule. Prep doesn't help in dependency-driven mode.

**Edge cases worth flagging:**

- **Prep can advance audit cadence by N iters** when prediction confidence is high (per iter-368 rule + iter-367/iter-370 advance precedent). N=1 (iter-367) and N=5 (iter-370) both worked.
- **Prep iter itself can surface pattern observations**: iter-366's "drift correlates with regex-visible additions" finding seeded iter-368 codification. Prep iter can be net-positive on codification queue.
- **Wrong predictions are still informative**: if prep predicts CLEAN but audit catches drift, the pattern holds (drift catch caused by previously-uncatalogued visible wire addition; prep prediction model needs refinement).
- **Prep iter cycle time is fixed**: ~5-10 min regardless of audit complexity. Audit iter cycle time scales with drift triage; prep iter cycle time does not.
- **Multiple consecutive audits can share prep work**: if iter-367 + iter-370 both predicted CLEAN per same iter-368 rule, prep doc could be a single doc covering both audits. Consolidation pattern; not yet observed.

**Cost-benefit ratio:**

- **Per-prep cost**: ~5-10 min (1 iter)
- **Per-audit-cycle savings**: ~5-10 min (audit iter runs faster with prediction documented)
- **Break-even**: 1 audit (immediate)
- **ROI grows with audit count**: each subsequent audit benefits from same prep iter's pattern observations
- **Cadence-advance bonus**: when predicted CLEAN, audit can advance by N iters → save N iters of waiting

**Memory-write triggers (2-instance evidence base):**

- **2 instances** iter-366→367 + iter-369→370 (~3-iter gap between pairs). Pattern survived 2 distinct audit categories with same prep+audit shape.
- **iter-370 was the codification trigger at 2/3** per iter-359/363/368 Tier 4 precedent. Future incidents (instance #3+) should EXTEND this rule rather than create new ones — most likely add a row to the empirical-support table.
- **Predicted 3rd instance**: iter-372+ prep → iter-389+ reverse-orphan audit (next canonical 22-iter cadence) OR iter-376+ prep → iter-387+ P2HP audit (next canonical 17-iter cadence).

**Prospective uses (iter-372+):**

When approaching the next audit cadence:

- **iter-389+ reverse-orphan audit**: ship prep doc at iter-388 (1 iter ahead); apply iter-368 rule + this rule's force-multiplier
- **iter-387+ P2HP audit**: ship prep doc at iter-386 (1 iter ahead); same pattern
- **Future Thread B/C/D/E kickoff**: when wire-shipping rate spikes, prep doc becomes more valuable (drift catch likelihood higher; prep helps target the catch)

**Pattern reinforcement:**

This rule is the **execution-side companion** to:
- `feedback_audits_clean_when_no_new_wires.md` (iter-368 codified) — provides the prediction logic that prep iters apply
- `feedback_codify_then_apply_then_verify_quad.md` (iter-363 codified) — quad pattern with prep→audit as the 4-iter shape
- `feedback_audit_compounds_via_rationale_extensions.md` (iter-359 codified) — compounding effect across audit cycles
- `feedback_iter_strategy_preflight_stack.md` (iter-337 codified) — preflight stack runs BEFORE the prep iter to filter out non-applicable audit categories

Combined: when an audit cadence triggers, run iter-337 preflight → ship iter-371 prep doc → iter-368 rule predicts outcome → audit empirically validates → iter-359 rationale extensions compound for next cycle. Full chain provides predictable, low-friction audit cycles.

**Cross-link to related codified rules:**

- `feedback_audits_clean_when_no_new_wires.md` (iter-368) — the prediction logic prep iters apply
- `feedback_codify_then_apply_then_verify_quad.md` (iter-363) — 4-iter quad shape
- `feedback_audit_compounds_via_rationale_extensions.md` (iter-359) — post-resolution compounding
- `feedback_iter_strategy_preflight_stack.md` (iter-337) — preflight before prep
- `feedback_dotnet_test_hang_diagnosis.md` (iter-172) — toolchain rule for running audit tests