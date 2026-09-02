# WAVE 4 - independent re-measurement of Phase 8 routing

STATUS: **COMPLETE.** All stages measured. Two of my own claims were REFUTED by my own
later probes; both corrections are recorded below rather than deleted.

COVERAGE: measured = crash reproduction · bytes@k on the lane's query set · bytes@k on two
independently built query sets · precision/recall/gold-hit per tier · bytes-per-correct-
selection · four both-states controls · holdout integrity · the 36-negative abstention
settling experiment · the false-fire mechanism · the platform suite re-count.
NOT measured = anything about the plugin, marketplace, D1 or D4 items (other lanes).

Artifacts, all under `command-center/`:

| script | artifact |
|---|---|
| `wave4_routing_probe.py` | `WAVE4-ROUTING-PROBE.json` (313.8 s, `status: COMPLETE`) |
| `wave4_holdout_leak_probe.py` | `WAVE4-HOLDOUT-LEAK.json` |
| `wave4_abstain_probe.py` | `WAVE4-ABSTAIN-PROBE.json` |
| `wave4_control_fix.py` | (patches the block above) |
| `wave4_ceiling_probe.py` | `WAVE4-CEILING-PROBE.json` |
| `wave4_ood_separation.py` | `WAVE4-OOD-SEPARATION.json` (**superseded - see §7**) |
| `wave4_ood_paraphrase.py` | `WAVE4-OOD-PARAPHRASE.json` |
| platform suite | `wave4_suite_after.log` |

**Not written by this unit:** `command-center/wave3_floor_audit.py`. Another lane was
editing it live (mtime 12:40:46 -> 12:48:39 during my read; its JSON rewritten 12:47:55
with a third, different crash). Reported to `main`; the measurement was delivered here
instead.

## 1. The crash, reproduced both states

| | |
|---|---|
| `semantic.SemanticModel.build` | raises `AttributeError: type object 'SemanticModel' has no attribute 'build'` - byte-identical to the reported crash |
| `semantic.SemanticModel.fit(idx)` | returns a fitted model, 40/40 records (`semantic.py:211`) |
| `Router.build(idx)` | EXISTS (`router.py:279`); only `SemanticModel.build` does not |

`both_states_valid: true`. The probe reached for the wrong class's factory.

## 2. Bytes per query - the lane's figures REPRODUCE EXACTLY

My accounting (`len("\n".join(cap.card).encode())`), my rebuilt held-out index, my own
walk. `Decision.injected_bytes` agreed with my count on **1,239 of 1,239 decisions, 0
disagreements**, so this is a reproduction and not a definitional coincidence.

| k | lane mean card B | MINE | delta | lane peak | MINE peak |
|---|---|---|---|---|---|
| 1 | 161.9 | **161.9** | 0.0 | 219 | **219** |
| 3 | 389.6 | **389.6** | 0.0 | 657 | **657** |
| 5 | 494.4 | **494.4** | 0.0 | 1043 | **1043** |
| 10 | 530.2 | **530.2** | 0.0 | 1322 | **1322** |

Measurement-stability note: the corpus is discovered from the LIVE harness trees, so
`sum(card_bytes)` is 146,354 today vs the 146,361 in the committed artifact (-7 B,
0.005%). Exact byte reproduction over time is not guaranteed; the per-k means happened to
be unaffected.

## 3. Precision / recall - 12 tier x k rows compared, 0 disagreements

Every L1/L2/L4 precision, recall and gold-hit figure at k=1,3,5,10 in
`platform/routing/MEASUREMENTS.json`, plus the L3 abstain rate 0.6667, reproduced exactly
by independent scoring code.

## 4. Two more query sets - the retrieval and paraphrase numbers hold up

**QS-B, mechanical, disjoint.** 45 leave-one-out queries over a stride-13 walk restricted
to records in no lane gold set; 45/45 holdouts positively verified absent; 4 excluded as
unanswerable and counted.

**QS-C, authored, disjoint.** 22 positives + 6 negatives. Mean leakage 0.0869 vs the
lane's L2 0.0293 - my set is **3x leakier and still scored no higher**, which is what makes
it corroboration rather than an easier test.

| | lane | mine |
|---|---|---|
| retrieval gold-hit@5 | L1 0.750 | **QS-B 0.867** (45 q) |
| paraphrase gold-hit@5 | L2 0.4286 | **QS-C 0.4091** (22 q) |
| abstain on negatives | L3 0.667 (4/6) | **QS-C 0.167 (1/6)** |

## 5. Anti-flooding: bytes per CORRECT selection (the lane does not report this)

| k | recall | mean B/query | correct | wasted | **B per CORRECT** |
|---|---|---|---|---|---|
| 1 | 0.363 | 161.9 | 23 | 26 | **403.8** |
| 3 | 0.485 | 389.6 | 31 | 90 | **719.0** |
| 5 | 0.546 | 494.4 | 35 | 121 | **805.3** |
| 10 | 0.546 | 530.2 | 35 | 132 | **861.6** |

Marginal: k=1->3 costs 1,625 B per extra correct selection; k=3->5 costs 1,474 B;
**k=5->10 costs 1,968 B and buys ZERO** (recall delta 0.0). On QS-B the ladder saturates
even earlier - k=3->5 and k=5->10 both buy zero.

Answer to "does recall improve because matching improved, or because more is injected?" -
**both, separably.** Within a fixed k the router is 4.21x the oracle floor and 133x cheaper
per correct selection than a flooding router, so it is not flooding. But ACROSS the k ladder
the extra recall is bought at a rising marginal price (404 B/correct average at k=1 vs
1,474-1,625 B per *additional* correct at k=3-5), and past k=5 the price is infinite. The
k=10 rung is pure context cost.

## 6. Controls - all four valid, both states

| control | result |
|---|---|
| shuffled gold | recall 0.5463 -> **0.0** - the metric reads the selection |
| flood-everything | recall 1.0 at **107,463.6 B per correct** vs 805.3 = **133x**; probe FIRES on the seeded flood, SILENT on the shipped router |
| query-blind top-k | recall 0.080 at **1,076 B/query, MORE than the real router's 494** - bytes alone cannot certify a router |
| gold oracle | 191.4 B per correct; the real router is **4.21x** the theoretical minimum |

**My own control was mis-specified and is corrected in place.** The floor sweep asserted
that `floor=0.0` must fire on every negative; it measured 0.0556. The assertion was wrong,
not the sweep: selection is `max(floor, mu+Z*sd)` (`router.py:431`), so the ADAPTIVE arm
still binds at floor 0. Corrected criterion `abstain(0.0) 0.0556 < abstain(default) 0.3333
< abstain(1.0) 1.0` holds, and both residual abstainers are bound by `adaptive`, not
`floor` - so the override is live.

## 7. The one divergence, settled: abstention does not generalise

36 negatives (the lane's 6 verbatim + 30 authored here), one measurement:

| population | abstain rate |
|---|---|
| the lane's 6 (its L3) | 0.667 (4/6) - reproduces exactly |
| my 30 | **0.267 (8/30)** |
| **all 36** | **0.333 (12/36)** |

So the router **false-fires on 24 of 36 everyday non-tasks**, and 16 of those 24 carry the
confidence band **"likely"** - the calibrated label `router.py:226` exists precisely so a
caller can trust it. 18 of 24 are bound by the FLOOR arm (0.18) with median top score
0.3404, i.e. nearly 2x the floor.

**Not a threshold problem.** The floor sweep (36 negatives x 76 positives):

| floor | abstain@36 | gold-hit@76 | mean B |
|---|---|---|---|
| 0.18 (shipped) | 0.333 | 0.645 | 476.4 |
| 0.26 | 0.528 | 0.447 | 223.0 |
| 0.35 | 0.694 | 0.355 | 126.9 |
| 0.40 | 0.833 | 0.237 | 80.0 |

No floor buys abstention without gutting recall.

**Mechanism: PARTIAL, half my hypothesis REFUTED.** I predicted low ceiling AND high
saturation. Measured medians - firing negatives / abstaining negatives / positives:
ceiling **10.19 / 19.94 / 25.45** (confirmed, and it separates *within* the negatives);
saturation **0.880 / 0.377 / 1.021** (**refuted** - firing negatives saturate LESS than
positives, not more). The arm that survived is vocabulary coverage: median
`frac_tokens_known` **0.500** on firing negatives vs **1.000** on L1, L2 and L4 and 0.958
on QS-C.

**I then overclaimed on that, and refuted it myself.** `WAVE4-OOD-SEPARATION.json` reported
a `frac_known >= 0.85` pre-gate suppressing 24/24 false fires at zero true-positive cost -
measured on 20 positives that were all L1, whose vocabulary IS corpus vocabulary by
construction, so a vocabulary gate could not possibly cost anything there. Re-measured on
the honest population (L2 + L4 + QS-C, `WAVE4-OOD-PARAPHRASE.json`):

| cut | false fires suppressed | paraphrase wins lost | L1 wins lost |
|---|---|---|---|
| 0.55 | **15/24 (62.5%)** | **0/21 (0%)** | 0/28 |
| 0.70 | 20/24 (83.3%) | 1/21 (4.8%) | 0/28 |
| 0.85 | 24/24 (100%) | **3/21 (14.3%)** | 0/28 |
| 0.90 | 24/24 | 8/21 (38.1%) | 0/28 |

Correctly scoped: a 0.55 cut suppresses 62.5% of false fires at zero measured paraphrase
cost; the 0.85 cut I first reported costs 14.3% of paraphrase wins. Residual, inline: 21
paraphrase winners is a small denominator (0/21 gives a ~14% upper bound on the true loss
rate by the rule of three), and the negatives are one author's. Settling experiment: a
negative set authored by someone who has not read `router.py`, and the sweep re-run over
every labelled positive. **This is a measured trade for the routing lane to decide, not a
change to ship from an audit probe.**

## 8. Defect in the experiment (not the router)

`command:compute-monitor` / `L1b-command-04`: the lane's own `queries.holdout_index` leaves
the cleaned query sentence in `routing_text` (it strips one occurrence; the sentence appears
twice), so **1 of 28 L1 queries is circular**. Confirmed by a mechanically different probe
with a known-present control (28/28 sentences present before the strip). Impact bound:
<= 1/28 = 0.036 of L1 gold-hit. Fix: replace ALL occurrences and assert absence.

Larger, same family: building the router on the RAW index - what the crashed Wave-3 probe
did (`Router.build(inv)` vs `metrics.py:563`'s `holdout_index`) - inflates recall@5 from
0.5463 to **0.6759** and gold-hit@5 from 0.6111 to **0.7407**. Had it not crashed it would
have over-reported by +0.13 absolute.

## 9. Non-regression

| | |
|---|---|
| suite, measured 13:02-13:12 | **3,847 passed / 14 skipped / 0 failed**, exit 0 (`python -m pytest platform -q`) |
| the pinned baseline (3,026/14) | **stale by 821 tests** - the Wave-3 audit already logged 3,830/14 at 12:03 (`wave3_audit_suite_baseline.log`) |
| `platform/_d3_final_suite.txt` (07:01) | 3 failed / 3,064 passed - those 3 `test_work_unit_authorization` failures are GONE at 13:12 |
| files I added | all under `command-center/`; **none under `platform/`**, none named `test_*`, so the suite delta is not mine |
| caveat | other lanes modified 5 platform files and deleted 1 workflow DURING the run, so 3,847 is a snapshot of a moving tree, not an invariant |
