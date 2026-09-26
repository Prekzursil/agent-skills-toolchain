---
name: Advance-Audit-Cadence-When-Predicted-Clean Pattern
description: When iter-368 codified rule predicts CLEAN with high confidence (0 new
  visible wires shipped) AND stop-hook signal continues, advancing audit cadence by
  N iters is legitimate per empirical evidence. iter-367 advanced reverse-orphan by
  1 iter; iter-370 advanced P2HP by 5 iters; both audits CLEAN as predicted. Codified
  at 2/3 trigger per iter-359/363/368/371/373 Tier 4 precedent. Cadence is a heuristic,
  not a requirement.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-advance-audit-cadence-when-predicted-clean
---

**Rule:** Canonical audit cadence intervals (P2HP ~17 iters, reverse-orphan ~22 iters) are heuristics, not requirements. When iter-368 codified rule predicts CLEAN with high confidence:

1. **0 new visible wires shipped since prior audit** → CLEAN prediction is high-confidence
2. **Stop-hook signal continues** OR no other priority work → cadence-advance is opportunistic
3. **Advance audit by N iters** → N=1 to N=5 empirically demonstrated safe

This trades canonical cadence rhythm for opportunistic execution. The rule is **safe** because:
- Audit prediction is empirically validated by iter-368 rule's prior CLEAN passes
- Wrong predictions surface as drift catches at audit time (no worse outcome than canonical-cadence audit)
- Saves N iters of waiting time when prediction matches outcome

**Why:**

2 instances iter-367 + iter-370 demonstrate the cadence-advance pattern:

| Audit iter | Canonical cadence | Actual run | Iters advanced | Predicted | Actual outcome |
|---|---|---|---|---|---|
| iter-367 | iter-368 reverse-orphan | iter-367 | 1 iter early | CLEAN (per iter-368 rule logic, retroactively recognized) | CLEAN |
| iter-370 | iter-375 P2HP | iter-370 | 5 iters early | CLEAN (per iter-368 rule explicitly applied at iter-369 prep) | CLEAN |

Both advances were triggered by stop-hook signals indicating user wants continuous work, not idle waiting. Both audits empirically CLEAN — confirming that iter-368 rule's prediction logic is reliable for cadence advance.

**Codified at 2/3 trigger per iter-359/363/368/371/373 Tier 4 precedent.** This is the 6th Tier 4 codification (cluster: iter-359/363/368/371/373/374). The audit-organization arc has now produced 6 codified rules in 16 iters.

**How to apply:**

When facing audit cadence wait period:

1. **Step 1 — Apply iter-368 rule** (~3-5 min):
   - Survey iter-since-last-audit close-out docs
   - Count new regex-visible call sites
   - 0 new wires → CLEAN prediction high-confidence
   - 1+ new wires → CLEAN prediction lower-confidence; consider canonical cadence

2. **Step 2 — Check signal direction** (~0 min):
   - Stop-hook signal "proceed until you finish everything" → cadence advance opportunistic
   - User idle → canonical cadence appropriate
   - Higher-priority work queued → canonical cadence appropriate

3. **Step 3 — Advance audit by N iters** (~3-15 min for audit + close-out):
   - N=1 (small advance): low-risk; saves ~1 iter
   - N=5 (medium advance): safe per iter-370 precedent; saves ~5 iters
   - N=10+ (large advance): untested; consider risk-reward
   - If audit CLEAN: cadence advance was correct
   - If audit catches drift: cadence advance was premature; budget extra triage time

4. **Step 4 — Document advance** in close-out:
   - Note "advanced from iter-${CANONICAL} by N iters"
   - Cite iter-368 rule prediction
   - If validated: rule self-reinforces
   - If refuted: rule needs refinement

**Honest break-out clause** — when this rule does NOT apply:

- **Active wire shipping**: if iter-since-last-audit shipped new visible wires, cadence-advance is risky. Prediction confidence drops; canonical cadence is safer.
- **First audit in a category**: no baseline → no prediction → no cadence-advance basis. First audit must run at canonical cadence.
- **Deep refactor in progress**: dispatcher helper changes can expose previously-invisible call sites en masse → cadence-advance is premature.
- **No stop-hook signal**: cadence-advance with no signal is busy-work; canonical cadence preserves rhythm.
- **Higher-priority work queued**: cadence-advance trades wait-time for audit time; if other work is queued, run that instead.

**Edge cases worth flagging:**

- **N=1 advance is nearly free**: 1-iter early audit costs ~0 risk; ROI is tiny but positive.
- **N=5 advance is the empirical maximum tested**: iter-370 advanced P2HP by 5 iters; any larger advance is untested.
- **Multiple consecutive advances compound**: if iter-367 advanced by 1 + iter-370 by 5 = 6 iters total advance across 2 audit cycles. Cumulative cadence drift can be substantial.
- **Cadence-advance can be self-correcting**: if audit catches drift, next audit reverts to canonical cadence (drift triage iter restores rhythm).
- **Stop-hook semantic**: "proceed until you finish everything" is a directive, not a request for arbitrary work. Cadence-advance that produces empirical evidence (audit confirmation) is legitimate; cadence-advance that produces docs busy-work is suboptimal.

**Cost-benefit ratio:**

- **Per-advance cost**: ~0 min (just run audit early)
- **Per-advance savings**: N iters of canonical-cadence wait time
- **Per-advance risk**: ~0 min if CLEAN, ~5-10 min triage if drift catches
- **Asymmetric upside**: advance saves N iters when CLEAN, costs nothing when drift
- **Cumulative effect**: across 2 advances (iter-367 + iter-370), saved 6 iters of waiting

**Memory-write triggers (2-instance evidence base):**

- **2 instances** iter-367 + iter-370 (~3-iter window). Both advances followed stop-hook signals; both audits empirically CLEAN.
- **iter-370 was the codification trigger at 2/3** per iter-359/363/368/371/373 Tier 4 precedent. Future incidents (instance #3+) should EXTEND this rule with new advance instances.
- **Predicted 3rd instance**: iter-389+ reverse-orphan or iter-387+ P2HP audit could advance per iter-368 rule + this cadence-advance rule combined.

**Prospective uses (iter-375+):**

When facing audit cadence wait period:

- **iter-389+ reverse-orphan audit**: if iter-368 rule predicts CLEAN AND stop-hook signal continues, advance by 1-5 iters
- **iter-387+ P2HP audit**: same approach
- **Future Thread B/C/D/E kickoff**: when wire-shipping rate spikes, iter-368 rule predicts drift; canonical cadence appropriate (cadence-advance NOT recommended during active arcs)

**Pattern reinforcement:**

This rule is the **execution-flexibility companion** to:
- `feedback_audits_clean_when_no_new_wires.md` (iter-368) — provides the prediction logic that justifies cadence-advance
- `feedback_audit_prep_force_multiplier.md` (iter-371) — prep iter establishes prediction confidence; advance acts on confidence
- `feedback_codified_rule_self_validates_via_forward_application.md` (iter-373) — advance is one form of forward application
- `feedback_codify_then_apply_then_verify_quad.md` (iter-363) — quad pattern's verify step can advance per cadence-advance rule

Combined: when an audit cadence wait period appears, run iter-371 prep → apply iter-368 prediction → if CLEAN-confident + stop-hook signal → advance per iter-374 rule → audit empirically validates.

**Cross-link to related codified rules:**

- `feedback_audits_clean_when_no_new_wires.md` (iter-368) — prediction logic
- `feedback_audit_prep_force_multiplier.md` (iter-371) — prep iter establishes confidence
- `feedback_codified_rule_self_validates_via_forward_application.md` (iter-373) — advance is forward application
- `feedback_codify_then_apply_then_verify_quad.md` (iter-363) — quad pattern shape
- `feedback_dotnet_test_hang_diagnosis.md` (iter-172) — toolchain rule for running advanced audits