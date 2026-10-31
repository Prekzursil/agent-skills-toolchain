---
title: BP5-STATUS
type: note
permalink: dqverify-repo-20261013/platform/workflows/bp5-status
---

# Unit `blueprints/bp-5` - workflow blueprints 49-60 of 96

Phase 2B/7. Status: **DELIVERED, 12 of 12**. Every number below was produced by a command
recorded in this file, not estimated.

## Range resolution (a decision, stated because it was not given)

The spawn brief says "blueprints 49-60 of 96". The design corpus
`09-WORKFLOW-BLUEPRINT-LIBRARY.md` holds **108** cards, not 96 - its own header says so
("Honest count: 108 blueprints. Not rounded to a target. The mega-prompt floor is 96"). Cards
49-60 in the library's own ordering are exactly two complete families:

| range | family | n |
|---|---|---|
| 49-53 | D10-code-review (`BP-CRV-01`..`05`) | 5 |
| 54-60 | D11-testing (`BP-TST-01`..`07`) | 7 |

That is a clean 12 with no partial family, which is why the index is read this way. Verified by
counting the `### \`BP-...\`` headings in library order (D1..D9 = 48 cards precede `BP-CRV-01`).

## The 12, as delivered

All under `C:/Users/Prekzursil/source/ast-integrate/platform/workflows/`.

| card | file (`<id>.json`) | category (primary, secondary) | flagship | stages | gates | stop rules |
|---|---|---|---|---|---|---|
| 49 | `crv.split-role-reviewer-panel` | collective-intelligence-and-meta, engineering | **YES** | 7 | 2 | 2 |
| 50 | `crv.differential-change-review-with-history` | security-governance-and-risk, engineering | no | 8 | 3 | 2 |
| 51 | `crv.refactor-equivalence-proof` | engineering-and-reliability | no | 8 | 3 | 2 |
| 52 | `crv.bug-class-variant-sweep` | security-governance-and-risk, engineering | **YES** | 9 | 3 | 2 |
| 53 | `crv.overclaim-scoping-review` | research-and-evidence, engineering | **YES** | 10 | 4 | 2 |
| 54 | `tst.smallest-check-ladder` | engineering-and-reliability | **YES** | 7 | 4 | 2 |
| 55 | `tst.diff-scoped-mutation-gate` | engineering-and-reliability | **YES** | 10 | 4 | 2 |
| 56 | `tst.spec-blind-test-synthesis` | engineering-and-reliability | no | 9 | 3 | 3 |
| 57 | `tst.ui-invariant-walk` | product-design-and-strategy, engineering | no | 10 | 4 | 2 |
| 58 | `tst.packaged-artifact-golden-journey-smoke` | engineering-and-reliability | **YES** | 8 | 4 | 2 |
| 59 | `tst.fail-first-red-proof-certification` | engineering, research-and-evidence | **YES** | 9 | 4 | 2 |
| 60 | `tst.hook-event-reachability-conformance` | engineering, collective-intelligence-and-meta | **YES** | 11 | 4 | 2 |

106 top-level stages, 292,274 bytes. Stage kinds exercised: task 49, gate 42, fanout 6, loop 4,
repair_loop 2, human_checkpoint 2, subworkflow 1.

Every blueprint carries typed `params`, `roles`, `gates`, `stages`, `tool_policy` (deny-by-default),
`stopping_rules`, `retry_policy`, `failure_policy`, `resume`, `replay`, `cache`, `dry_run`,
`estimate`, `portability`, `lineage`, `outputs`, and an `x_extensions.worked_example`.

## Validator output - the acceptance criterion

```
$ python platform/lib/wfdsl/validate.py workflow platform/workflows/crv.*.json platform/workflows/tst.*.json
validator EXIT=0
  crv.bug-class-variant-sweep                      schema_valid=True  violations=0 advisories=0
  crv.differential-change-review-with-history      schema_valid=True  violations=0 advisories=0
  crv.overclaim-scoping-review                     schema_valid=True  violations=0 advisories=0
  crv.refactor-equivalence-proof                   schema_valid=True  violations=0 advisories=0
  crv.split-role-reviewer-panel                    schema_valid=True  violations=0 advisories=0
  tst.diff-scoped-mutation-gate                    schema_valid=True  violations=0 advisories=0
  tst.fail-first-red-proof-certification           schema_valid=True  violations=0 advisories=0
  tst.hook-event-reachability-conformance          schema_valid=True  violations=0 advisories=0
  tst.packaged-artifact-golden-journey-smoke       schema_valid=True  violations=0 advisories=0
  tst.smallest-check-ladder                        schema_valid=True  violations=0 advisories=0
  tst.spec-blind-test-synthesis                    schema_valid=True  violations=0 advisories=0
  tst.ui-invariant-walk                            schema_valid=True  violations=0 advisories=0
all_valid= True  n= 12
```

Per-file JSON: `command-center/BP5-VALIDATOR-OUTPUT.json`. **12 of 12 delivered; 0 withheld.**

## Tests

```
$ python -m pytest platform/lib/workflows/test_bp5_slice.py platform/lib/workflows/test_crv_*.py platform/lib/workflows/test_tst_*.py -q
215 passed in 8.70s

$ python -m pytest platform/lib/wfdsl -q          # pre-existing baseline, untouched
97 passed in 39.30s

$ python platform/lib/wfdsl/validate.py all       # program-level contract gate
RESULT: SUCCESS:contracts/workflow-dsl
```

8 flagships, each with a dedicated `test_<name>.py` (the slice test asserts that mapping, so a
flagship claim cannot outrun its test file). 8 of 12 = 67%, above the spec's pro-rata floor of
5 (40 of 96).

Tests read the JSON **from disk**, never from the builder: a test that imported the generator
would prove the generator self-consistent while a stale file on disk went unchecked.

### Three test layers, and the both-states control at each

1. **Schema** - draft-2020-12 against `platform/schema/workflow-dsl.schema.json`.
2. **Semantic** - DSL-SEM-001..014, zero violations, zero advisories.
3. **Executed** - every expression in every document is *evaluated* against the worked
   example's context under `strict=True`, so an unmeasured metric raises rather than quietly
   reading false. Each blueprint declares `expected_gate_pass` / `expected_stop` (must evaluate
   TRUE) and a `negative_control` (an override set that must flip its named gate to FALSE).

Both-states controls, three kinds:

- **expression-level**: the negative control must flip the gate false, *and* the gate must be
  true in the healthy state - a gate false in both states measures nothing.
- **mechanism-level**: each flagship replaces its load-bearing gate expression with a tautology
  and asserts the bad state now *passes*. That proves the specific conjunct does the work, not
  merely that a gate with the right name exists.
- **document-level**: every gate stage is dropped in turn and the real validator must reject the
  result (`test_dropping_any_single_gate_stage_is_rejected`, all 12 blueprints).

## A defect this unit's own mutation control found, and fixed

`test_MUTATION_dropping_the_defect_police_gate_is_rejected` initially FAILED with
`MUTATION SURVIVED`. Root cause: a **terminal gate** - the last gate in a chain - has no
downstream dependent, so deleting it produces no schema error and no DSL-SEM-002 violation, and
it gates nothing because the workflow's artifact was already emitted upstream of it. Same shape
as failure class 2 (a guard that fails open).

**6 of the 12 originally ended in such a gate**: cards 50, 51, 53, 55, 56, 57. Fixed
structurally, not by weakening the test: `_bp5_terminal.py` appends a terminal verdict task stage
that depends on *every* previously-terminal gate, so the artifact now exists only downstream of
all gates and dropping any gate breaks the graph. Generator output:

```
crv.differential-change-review-with-history: terminal gates 1 -> 0 (anchored ['introduced-separated'] to emit-differential-verdict)
crv.refactor-equivalence-proof:              terminal gates 1 -> 0 (anchored ['advisory-only'] to record-advisory-verdict)
crv.overclaim-scoping-review:                terminal gates 1 -> 0 (anchored ['defect-not-softened'] to emit-scoping-verdict)
tst.diff-scoped-mutation-gate:               terminal gates 1 -> 0 (anchored ['mutation-source-restored'] to emit-mutation-verdict)
tst.spec-blind-test-synthesis:               terminal gates 1 -> 0 (anchored ['shadow-only'] to record-shadow-verdict)
tst.ui-invariant-walk:                       terminal gates 1 -> 0 (anchored ['shadow-only'] to record-walk-verdict)
```

`test_no_gate_is_silently_deletable` is the standing regression guard, parametrized over all 12.

**Blast radius, checked**: the other 6 blueprints end in a task or human_checkpoint, so no gate
anywhere in this slice is terminal now (asserted, not assumed). NOT-CHECKED whether sibling
slices' blueprints have the same shape - the invariant is a 6-line test and is worth porting; I
did not edit sibling files.

A second self-inflicted detector failure, also found and fixed: my secret-shape test asserted
`"sk-" not in blob` and fired on the literal string **`"risk-classification"`**. Replaced with
token-boundary patterns plus `test_the_secret_shape_detector_fires_on_a_known_present_sample`,
which proves the matcher finds four planted shapes (assembled at run time from inert fragments,
so this repo holds no credential-shaped literal) and does *not* fire on the measured false
positive.

## Material distinctness - computed, not asserted

Each blueprint declares an `x_extensions.mechanism_fingerprint` over 7 axes: `subject`, `oracle`,
`execution_required`, `mutation_target`, `comparison_axis`, `output_type`, `information_barrier`.
Distinctness is decided by an **exact set comparison** on the 4-tuple
(`subject`, `oracle`, `comparison_axis`, `output_type`) - a mechanical question gets a mechanical
answer rather than LLM judgement.

```
exact 4-key collisions: 0
closest pair: crv.bug-class-variant-sweep / crv.refactor-equivalence-proof = 43% of 7 axes
```

`test_closest_pair_still_differs_on_a_majority_of_fingerprint_fields` asserts the closest pair
stays under 75% agreement, so a future near-duplicate is caught even when the exact key differs.

**0 merged, 0 split, 12 in and 12 out.** No pair was a mechanism duplicate, so nothing was
merged - and nothing was split, because splitting a non-duplicate purely to keep a count at 12
would manufacture exactly the false coverage the brief forbids.

The pair worth naming is the one a reviewer will challenge: **card 56 (spec-blind synthesis) vs
card 59 (red-proof certification)** both execute a test suite across two tree states. They differ
on test PROVENANCE, which is a mechanism and not a wording difference: 56 requires a *synthesiser
role under an enforced information barrier* (no git tool, no diff in its input manifest, a
blocking `diff-blindness` gate and a `leak-auditor` veto role) and can return `SPEC-MISS`; 59 has
no generative step at all, runs the *author's own named* tests, and can return `REFUSED`. Neither
verdict is reachable from the other's mechanism.

## Honest scope of the tests (an inline residual, not a trailing caveat)

These tests certify the **blueprint definitions**: schema conformance, semantic conformance,
executed decision logic (gate and stopping expressions really evaluate on a worked context), and
mutation resistance of the documents. They do **NOT** execute the workflows against a live runner
- no runner exists yet in this repo - so no claim here is evidence that a blueprint *runs*.
Settling experiment: once a runner lands, replay each `worked_example.params` through it and
compare the emitted artifacts against each blueprint's declared `outputs`.

`basis: "static-declared"` on all 12 estimates, asserted by
`test_no_estimate_claims_a_measured_basis_without_a_measurement`: none of these has been run, so
`historical-measured` would be a measured label on a guess.

## Category span

| category | n |
|---|---|
| engineering-and-reliability | 12 |
| collective-intelligence-and-meta | 2 |
| security-governance-and-risk | 2 |
| research-and-evidence | 2 |
| product-design-and-strategy | 1 |
| data-science-knowledge-and-creative | **0** |

The zero is correct and disclosed rather than padded: this slice IS code-review plus testing, so
`data-science-knowledge-and-creative` has no honest member here. The spec requires the **96** to
span the six categories, not each 12-card slice; cards 72-76 (D14-data) and 82-86 (D16-docs) sit
in other units' ranges. Category slugs are imported from `bp7_common` so all slices use one
vocabulary.

## Reuse rather than a parallel implementation

A dup-guard hook flagged my first draft of a policy-builder module. It was deleted; this slice
imports `artifact`, `tool_policy`, `work_unit` (STRICT shape), `portability`, `failure_policy`,
`resume`, `replay_deterministic`, `cache`, `dry_run`, `estimate`, `lineage`, `card`, `gate_expr`,
`write_blueprint` and the six `CAT_*` constants from the sibling-owned
`platform/lib/workflows/bp7_common.py`. Only two slice-local things remain in `_bp5_ids.py`:
`unit_id` (bp7's minter hard-raises outside cards 73-84) and this slice's id namespace.

**Coupling risk, disclosed**: `bp7_common.py` is owned by a concurrently running sibling. If its
signatures change, `_gen_bp5.py` breaks loudly at build time rather than emitting a wrong
document. Re-run `python platform/lib/workflows/_gen_bp5.py` after any `bp7_common` change.

## Reference integrity

- **35 distinct `work_unit_ref` values, all resolving** to real ids in
  `command-center/WORK-UNIT-CATALOG.json` (asserted by
  `test_every_work_unit_ref_resolves_to_a_real_catalog_unit`).
- **24 inline work units minted**, prefixes `CRV-49xx..53xx` and `QLT-54xx..60xx`. The catalog's
  13 prefixes are **re-measured** by the test (`ADV ARC AUD BLD CC CNF CNL IMP REL RES SYN TST
  WFA`); `CRV` and `QLT` are absent from it. `TST` was rejected as a prefix precisely because it
  IS a catalog prefix, so `TST-5401` would read like a catalog unit that does not exist.
- Every inline `completion_sentinel` opens with `SUCCESS:<its own id>`, asserted - this slice adds
  nothing to the catalog's measured debt of 96 sentinels that do not name their own unit.
- Every `output_schema` / `schema_ref` points at a file that exists under
  `command-center/schema/` (231 shims + control plane, closed by the substrate unit).

## Files

Deliverables (12 JSON blueprints): `platform/workflows/{crv,tst}.*.json`

Source and gates, all under `platform/lib/workflows/`:
`_bp5_ids.py`, `_bp5_crv_a.py`, `_bp5_crv_b.py`, `_bp5_tst_a.py`, `_bp5_tst_b.py`,
`_bp5_terminal.py`, `_bp5_selfcheck.py`, `_bp5_testkit.py`, `_gen_bp5.py`

Tests (9 files, 215 tests): `test_bp5_slice.py`, `test_crv_split_role_reviewer_panel.py`,
`test_crv_bug_class_variant_sweep.py`, `test_crv_overclaim_scoping_review.py`,
`test_tst_smallest_check_ladder.py`, `test_tst_diff_scoped_mutation_gate.py`,
`test_tst_packaged_artifact_golden_journey_smoke.py`,
`test_tst_fail_first_red_proof_certification.py`,
`test_tst_hook_event_reachability_conformance.py`

Regenerate: `python platform/lib/workflows/_gen_bp5.py` (refuses to write unless all five gates
pass). Ruff 0.15.17: clean on all 15 files.

## Owner decisions surfaced (not taken)

- **Card 52** `graduate_to_ci`: promote a validated sweep pattern to a *blocking* CI rule, an
  advisory one, or keep it a one-off sweep. Encoded as an owner-only `human_checkpoint` with
  `on_timeout: escalate`, because a blocking gate needs an owner and a maintenance budget.
- **Card 60** WIRE-or-RETIRE: the library card marks this `OWNER-DECISION: YES`. Two handlers are
  implemented and unreachable. Encoded as an owner-only checkpoint whose options include
  `defer-with-recorded-risk`, since a security guard under a non-existent event is a silent hole -
  leaving it is not a neutral option. The blueprint reports; it cannot decide.

## Sibling test failures observed, and why they are not mine

A full `pytest platform/lib` run showed 4 failures, then 1 on a re-run minutes later with no
change from me. All name `bp_cnc_*` / `bp_req_*` / `bp7_*` modules; none names a bp5 file. Two
independent signals that they are concurrent sibling work in flight, not regressions from this
unit: (a) the failing assertion lists only other slices' expected module names, and (b) the list
*shrank* 4 -> 1 between runs while this unit changed nothing. `test_bp7_slice.py`'s failure also
does not reproduce in isolation (1 passed), i.e. it is ordering-dependent within that sibling's
own suite. I did not edit any sibling file.