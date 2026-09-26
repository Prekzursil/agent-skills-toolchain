---
name: Audits-Clean-When-No-New-Wires Pattern
description: Periodic catalog audits (P2HP, reverse-orphan) reliably stay CLEAN when
  the iter range covered shipped 0 new bridge wires. Drift catches correlate with
  regex-visible wire-shipping rate, not iter count. iter-358 P2HP CLEAN + iter-367
  reverse-orphan CLEAN both during NON-A1.x quiet wire period (iter 273-364 = 92 iters
  / 0 new visible wires). Codified at 2/3 trigger per iter-359/iter-363 Tier 4 precedent.
  Generalizes across audit categories.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-audits-clean-when-no-new-wires
---

**Rule:** Periodic catalog audits (Phase2HookPending, reverse-orphan, and likely future audit categories) reliably stay CLEAN when the iter range covered (since the prior audit) shipped 0 new bridge wires. Drift catches correlate with **regex-visible wire-shipping rate**, NOT total iter count. Predict audit outcome by surveying iter-since-last-audit for new wire additions:

- **0 new visible wires shipped → CLEAN PASS** (high confidence)
- **N new visible wires shipped → 0 to N drift catches possible** (audit surfaces them)

Use this rule to (a) calibrate audit cadence (more frequent during active wire shipping; less frequent during NON-A1.x quiet periods), and (b) prepare audit iters by predicting outcome ahead of time (per iter-366 prep pattern).

**Why:**

2 instances iter-358 P2HP + iter-367 reverse-orphan (~9-iter window between audits) demonstrate the pattern across distinct audit categories:

| Audit iter | Category | Iters since prior audit | New visible wires | Drift catches | Result |
|---|---|---|---|---|---|
| iter-358 | Phase2HookPending | 17 (since iter-341) | 0 | 0 | CLEAN |
| iter-367 | Reverse-orphan snapshot | 21 (since iter-346) | 0 | 0 | CLEAN |

Both audits ran during the NON-A1.x quiet wire period (iter-269 lesson #2: pivot from A1.x deferred to broader UX/docs work). iter 273-364 = 92 iters / 0 new regex-visible bridge wires beyond iter-343 (which surfaced at iter-346 reverse-orphan audit). Both audits passed in <1 ms or <20 min cycle time.

**Empirical support across all audits**:

| Audit category | All audits | CLEAN | DRIFT CAUGHT | Drift rate | Visible wires shipped between drift catches |
|---|---|---|---|---|---|
| Phase2HookPending | 7 (iter-132/221/250/266/323/341/358) | 4 | 3 | 43% | iter-221 ~85; iter-250 ~6; iter-323 ~5 |
| Reverse-orphan | 6 (iter-238/255/263/272/346/367) | 5 | 1 | 17% | iter-346 1 (iter-343's `SWFOC_GetTypeLua`) |

Drift catches always correlate with new visible wires in the iter range. CLEAN passes always correlate with 0-or-low new visible wires. Pattern holds across both audit categories.

**Codified at 2/3 trigger per iter-359 + iter-363 Tier 4 precedent (meta-rules with forward applicability ≥2 instances).** The pattern is meta-level (about audit-cadence + wire-shipping-rate correlation), not a production code pattern. Generalizes across audit categories — strongest evidence shape for tier-4 codification.

**How to apply:**

When approaching a periodic audit cadence trigger:

1. **Step 1 — Survey iter range for new visible wires** (~3-5 min):
   - List iters since prior audit
   - For each iter, check close-out doc for "LIVE flip #N" or "NEW SWFOC_X wire shipped" mentions
   - Count new regex-visible call sites added (`$"return SWFOC_X(...)"` form, `BuildXxx("SWFOC_X")` is regex-invisible)

2. **Step 2 — Predict audit outcome** (~1 min):
   - **0 new visible wires** → predict CLEAN (high confidence)
   - **1-3 new visible wires** → predict 0-3 drift catches; targeted re-investigation
   - **4+ new visible wires** → predict possible cluster; budget extra time for audit triage

3. **Step 3 — Run audit at canonical cadence** (~3-15 min):
   - Use `run_editor_tests_v2.ps1` filter (iter-356 codified pattern)
   - Result confirms or refutes prediction

4. **Step 4 — Adjust audit cadence per prediction confidence** (optional, multi-audit horizon):
   - During NON-A1.x quiet periods: audits can run at extended cadence (~30 iters) without missing drift
   - During active wire shipping: audits should run more frequently (~10-15 iters) to catch drift early

**Honest break-out clause** — when this rule does NOT apply:

- **String-literal call site additions are NOT visible**: `BuildUnitLuaNoArgCall("SWFOC_X", ...)` and `BuildUnitLuaMethodCall("SWFOC_X", ...)` are regex-invisible. Pattern only catches drift when wires are added via `$"return SWFOC_X(...)"` or direct call form.
- **Catalog entry deletions are not predicted**: this rule only addresses no-longer-unwired drift. Newly-unwired drift (from deletions) is a separate failure mode and not predicted by wire-shipping rate.
- **Deep refactor that changes dispatcher helper shapes**: would expose previously-invisible call sites to regex visibility en masse; rule does NOT predict outcome accurately during refactor iters.
- **Cross-arc deferred drift surfacing**: iter-346's drift catch was iter-343's call site delayed by 3 iters of cadence overrun. Rule predicts CLEAN if iter-since-last-audit shipped 0 wires, but doesn't account for prior-audit deferral.

**Edge cases worth flagging:**

- **Drift catch lag time**: iter-343's regex-visible call site landed at iter-343, but reverse-orphan audit (which catches it) didn't run until iter-346. Lag = ~3 iters. Rule predicts CLEAN until next audit, then drift surfaces all at once.
- **Cadence overrun increases drift catch probability**: iter-346 had 74-iter gap from iter-272; that's ~3.3× canonical 22-iter cadence. Longer windows = more accumulated drift potential.
- **NON-A1.x pivot creates extended CLEAN windows**: iter-273-364 = 92 iters of 0 new visible wires → all audits during this window stay CLEAN.
- **Quiet wire periods aren't permanent**: when next NEW arc-class kickoff lands (Thread B/C/D/E per iter-269 lesson #2), wire-shipping rate spikes → drift catch frequency spikes accordingly.
- **Rule extends to future audit categories**: if a 3rd audit category is introduced (e.g., simulator coverage audit, ledger entry audit), this rule should generalize. Wait for empirical confirmation before claiming.

**Cost-benefit ratio:**

- **Per-prediction cost**: ~3-5 min survey (iter-since-last-audit close-out doc scan)
- **Per-audit cycle savings (if CLEAN predicted)**: ~5-10 min saved on audit triage (no drift to investigate)
- **Per-audit cost penalty (if DRIFT predicted but actual CLEAN)**: ~0 min (prediction was conservative)
- **Per-audit cost penalty (if CLEAN predicted but actual DRIFT)**: ~5-10 min for triage at audit time (no extra cost vs unprepped audit)
- **Asymmetric upside**: prediction CLEAN saves time when correct; prediction CLEAN does NOT cost extra time when wrong

**Memory-write triggers (2-instance evidence base):**

- **2 instances** iter-358 P2HP + iter-367 reverse-orphan (~9-iter window). Pattern survived 2 distinct audit categories with same NON-A1.x quiet wire period as substrate.
- **iter-367 was the codification trigger at 2/3** per iter-359/iter-363 Tier 4 precedent. Future incidents (instance #3+) should EXTEND this rule rather than create new ones — most likely add a row to the empirical-support table.
- **Predicted 3rd instance**: iter-375 P2HP audit (next canonical 17-iter cadence) OR iter-389+ reverse-orphan audit (next canonical 22-iter cadence) — both predicted CLEAN under continued NON-A1.x window.

**Prospective uses (iter-369+):**

When the next audit cadence triggers:

- **iter-375 P2HP audit**: predict CLEAN (iter 358-374 = 17 iters; expect 0 new wires per NON-A1.x continuation)
- **iter-389+ reverse-orphan audit**: predict CLEAN (iter 367-388 = 22 iters; expect 0 new wires per NON-A1.x continuation)
- **Future Thread B/C/D/E kickoff**: when wire-shipping rate spikes, drift catch frequency spikes accordingly. Use rule to ANTICIPATE the catch (not avoid it).
- **Audit cadence reform**: if all post-NON-A1.x audits stay CLEAN, propose extending cadence from canonical 17/22 iters to 30+ iters during quiet periods. Rule provides empirical justification.

**Pattern reinforcement:**

This rule is the **prediction-side companion** to:
- `feedback_audit_compounds_via_rationale_extensions.md` (iter-359 codified) — the post-drift-resolution side; rationale extensions compound across audits to reduce per-audit triage time
- `feedback_codify_then_apply_then_verify_quad.md` (iter-363 codified) — the audit-arc-organization side; quad pattern for codification arcs initiated by audit results
- `feedback_iter_strategy_preflight_stack.md` (iter-337 codified) — the iter-strategy side; preflight survey before iter design

Combined: when an audit cadence triggers, run preflight (iter-337) → predict outcome via wire-shipping rate (iter-368 codified) → if drift predicted/caught, run codify-apply-verify quad (iter-363) → ship docs cleanup that compounds for next audit (iter-359). Full chain provides predictable, low-friction audit cycles.

**Cross-link to related codified rules:**

- `feedback_audit_compounds_via_rationale_extensions.md` (iter-359) — post-resolution rationale-extension compounding
- `feedback_codify_then_apply_then_verify_quad.md` (iter-363) — audit-arc 4-iter quad shape
- `feedback_iter_strategy_preflight_stack.md` (iter-337) — preflight before iter design
- `feedback_dotnet_test_hang_diagnosis.md` (iter-172) — toolchain rule for running audit tests
- `feedback_resolver_injection_at_composition_root.md` (iter-345) — pattern with HIGHEST evidence (8 instances) provides codification template