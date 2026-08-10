# Phase 2B/7 — Workflow Blueprints 25-36 of 96 (unit `blueprints/bp-3`)

STATUS: **MEASURED**. Every row below was produced by a command whose output is quoted.

## Range assignment (how 25-36 was resolved)

`09-WORKFLOW-BLUEPRINT-LIBRARY.md` contains **108** blueprint cards, not 96. Doc-order positions
25-36 (`grep -n '^### \`BP-'` then index) are:

| # | design card | family |
|---|---|---|
| 25 | `BP-REQ-03` EVPI-Gated Clarification | D5-requirements |
| 26 | `BP-REQ-04` Assumption-Ledger Elicitation | D5-requirements |
| 27 | `BP-REQ-05` Intent-to-PRD with Reviewer | D5-requirements |
| 28 | `BP-ARC-01` Architecture Tournament | D6-architecture |
| 29 | `BP-ARC-02` Architect-to-Editor Split Build | D6-architecture |
| 30 | `BP-ARC-03` Anti-Overfit Architecture Audit | D6-architecture |
| 31 | `BP-ARC-04` Failure-Domain Mapping Workshop | D6-architecture |
| 32 | `BP-ARC-05` Vendor-Neutral Workflow Spec Emission | D6-architecture |
| 33 | `BP-PLN-01` Mechanical Plan-Lint then Adversarial Trio | D7-planning |
| 34 | `BP-PLN-02` File-Disjoint Work-Unit Decomposition | D7-planning |
| 35 | `BP-PLN-03` Multi-PR Stacking-Order Planner | D7-planning |
| 36 | `BP-PLN-04` Resume-Safe Program Checkpointing | D7-planning |

Consistency check with the sibling split: positions 1-12 = D1 (6) + D2 (5) + BRN-01; 13-24 =
BRN-02..04 + CNC-01..07 + REQ-01..02. So 25-36 falls out cleanly. **12 designs, 12 delivered.**

## Deliverables — all validated

| # | blueprint id | validator | semantic viol | flagship | test file |
|---|---|---|---|---|---|
| 1 | `bp-req-03.evpi-gated-clarification` | schema_valid=True | 0 | yes | `test_bp_req_03.py` |
| 2 | `bp-req-04.assumption-ledger-elicitation` | schema_valid=True | 0 | yes | `test_bp_req_04.py` |
| 3 | `bp-req-05.intent-to-prd-with-reviewer` | schema_valid=True | 0 | yes | `test_bp_req_05.py` |
| 4 | `bp-arc-01.architecture-tournament` | schema_valid=True | 0 | yes | `test_bp_arc_01.py` |
| 5 | `bp-arc-02.architect-to-editor-split-build` | schema_valid=True | 0 | yes | `test_bp_arc_02.py` |
| 6 | `bp-arc-03.anti-overfit-architecture-audit` | schema_valid=True | 0 | yes | `test_bp_arc_03.py` |
| 7 | `bp-arc-04.failure-domain-mapping-workshop` | schema_valid=True | 0 | yes | `test_bp_arc_04.py` |
| 8 | `bp-arc-05.vendor-neutral-workflow-spec-emission` | schema_valid=True | 0 | yes | `test_bp_arc_05.py` |
| 9 | `bp-pln-01.mechanical-plan-lint-then-adversarial-trio` | schema_valid=True | 0 | yes | `test_bp_pln_01.py` |
| 10 | `bp-pln-02.file-disjoint-work-unit-decomposition` | schema_valid=True | 0 | yes | `test_bp_pln_02.py` |
| 11 | `bp-pln-03.multi-pr-stacking-order-planner` | schema_valid=True | 0 | yes | `test_bp_pln_03.py` |
| 12 | `bp-pln-04.resume-safe-program-checkpointing` | schema_valid=True | 0 | yes | `test_bp_pln_04.py` |
| S1 | `shared.pairwise-overlap-matrix` (SUBWORKFLOW, not counted) | schema_valid=True | 0 | no | `test_mechanisms.py` |
| S2 | `shared.write-as-you-go-artifact` (SUBWORKFLOW, not counted) | schema_valid=True | 0 | no | `test_mechanisms.py` |

## Category span — FOUR of six, stated honestly

`product-design-and-strategy` (REQ-03/04/05) · `security-governance-and-risk` (REQ-04, ARC-03,
ARC-04) · `engineering-and-reliability` (ARC-01/02/03/05, PLN-01..04) ·
`collective-intelligence-and-meta` (ARC-01, ARC-05, PLN-01).

**NOT covered by this range: `research-and-evidence` and `data-science-knowledge-and-creative`.**
Doc-order 25-36 is exactly requirements + architecture + planning; those two categories live in
sibling ranges (D1-deep-research is positions 1-6, D14-data is a later range). Relabelling a
planning blueprint as data-science to tick six boxes would be manufactured coverage, so it was not
done. `test_bp3_catalog.py::test_category_span_is_reported_honestly_not_padded` asserts the
four-category set exactly and asserts the two absences.

## Distinctness self-check by MECHANISM

Mechanised, not asserted in prose: `test_bp3_catalog.py::test_no_two_blueprints_share_a_mechanism_fingerprint`
computes, per blueprint, `(stage-kind multiset, gate expression set, stopping expression set)` and
requires all 12 to be distinct. Result: **12 distinct fingerprints, 0 collisions.** A control
(`test_the_fingerprint_detector_can_actually_collide`) proves the check fires when fed two
identical documents.

**One genuine near-duplicate was found and resolved by FACTORING, not merging.** BP-PLN-02 and
BP-PLN-03 both compute a pairwise file-overlap matrix. Merging them would have been wrong — PLN-02
decides *concurrency admission* over PREDICTED footprints (with adverse inference on an unknown
footprint), PLN-03 decides *merge order* over MEASURED git refs (with byte-identity, a throwaway
merge probe and revision containment) — so the shared primitive was extracted into
`_shared/shared.pairwise-overlap-matrix.subworkflow.json`, which both reference by
`workflow_id`. `test_the_two_overlap_matrix_callers_are_not_near_duplicates` asserts both
reference it and that their gate sets are disjoint.

**No compensating SPLIT was forced, and that is deliberate.** The two candidates were rejected on
evidence: splitting `BP-ARC-03`'s DISARMED-vs-unused probe would duplicate `BP-DBG-05`
(Silent-Disarm Hunt, doc-order 47, a sibling's range) — the exact false-coverage trap; splitting
`BP-PLN-04`'s write-as-you-go half would create a 13th blueprint numbered outside the doc's ID
space, risking a sibling collision. Both were instead handled as *shared subworkflows*, which is
the engineering-correct factoring: a primitive used by 2+ callers is a subworkflow, not a
blueprint. Result: **12 blueprints + 2 subworkflows**, subworkflows explicitly NOT counted.

## Flagship claim — precisely scoped

All 12 are marked `flagship: true` and each has a dedicated end-to-end test.
**What "end-to-end" covers:** load the shipped JSON → validate against
`workflow-dsl.schema.json` + all 14 semantic rules → assert the mechanism-bearing invariants by
READING thresholds out of the document → EXECUTE the blueprint's declared worked example through
the real primitive in `mechanisms.py` → execute the declared negative controls → run a both-states
mutation control proving the invariant assertions FAIL on a mutated copy.
**What it does NOT cover, inline and not in a footnote: no live agent, model, or tool is invoked.**
There is no workflow RUNNER in this repo yet, so no test can execute a blueprint against real
subagents. These tests verify the DEFINITION and its mechanical decision procedure. Anyone citing
"flagship" as evidence of runtime behaviour is citing it wrongly.

## Measured results

```
$ python platform/lib/wfdsl/validate.py workflow <the 12 blueprints + 2 subworkflows>
VALIDATOR_EXIT=0
files=14 all_schema_valid=True total_violations=0 total_advisories=0
   (per-file: every one of the 14 reports schema_valid=True viol=0 adv=0)

$ python platform/lib/workflows/_verify_bp3.py
SUCCESS:verify-bp3 documents=14 all_valid=True controls_fired=5/5

$ python -m pytest workflows/test_bp3_catalog.py workflows/test_mechanisms.py \
      workflows/test_bp_{req_03,req_04,req_05,arc_01,arc_02,arc_03,arc_04,arc_05,pln_01,pln_02,pln_03,pln_04}.py
253 passed in 4.90s

$ python -m pytest wfdsl/ councilspec/ council_protocols/ test_completion_predicate.py \
      test_receipt_schema_gate.py test_schema_resolver.py
475 passed in 103.34s          # pre-existing baseline, unchanged by this unit

$ python -m ruff check <the 15 bp-3 source files>
All checks passed!
```

## Semantic-rule coverage — "0 violations" is only meaningful on a rule that RAN

Aggregate `checked` counts across the 14 documents. A rule with `checked=0` and `violations=0` has
measured nothing, so the two such rules are named rather than folded into the pass:

```
DSL-SEM-001 checked=111  DSL-SEM-002 checked=107  DSL-SEM-003 checked=107
DSL-SEM-004 checked= 49  DSL-SEM-005 checked= 40  DSL-SEM-006 checked=  3
DSL-SEM-007 checked= 97  DSL-SEM-008 checked=  4  DSL-SEM-009 checked=  2
DSL-SEM-010 checked=  3  DSL-SEM-011 checked=104  DSL-SEM-012 checked=  3
DSL-SEM-013 checked=  1  DSL-SEM-014 checked=  0   <-- NOT EXERCISED
rules_exercised = 13/14 ; violations = 0 on every exercised rule
```

- **DSL-SEM-013 was initially `checked=0` too.** That was a real modelling gap, not a detector gap:
  `bp-pln-03` shells to `gh`, which authenticates with a forge credential, and the blueprint never
  declared it. It now declares `forge_token` as a `secret_ref`, which is what makes the
  export-redaction rule checkable. Both-states probe run on it:

  | state | schema errors | SEM-013 |
  |---|---|---|
  | shipped | 0 | checked=1, violations=0 |
  | `redact_secrets` removed | 1 | **violations=1** — *"declares secret params ['forge_token'] but export.redact_secrets is not true"* |
  | `redact_secrets = False` | 1 | **violations=1** (same message) |
  | secret param removed AND `False` | 1 | checked=0 — correctly silent, so the guard is the secret param and not luck |

  So SEM-013 is genuinely armed, and the schema's `const: true` is a second, independent layer.
  The credential is referenced by NAME only; nothing in this unit reads, prints or rotates it.
- **DSL-SEM-014 is NOT-APPLICABLE to this range and was deliberately left unexercised.** It
  cross-checks a `council` stage's stopping-rule text against the councilspec parser, and doc-order
  25-36 contains no council blueprint — councils are family D4 (positions 13-19), a sibling's range.
  Adding a council stage to one of these twelve purely to light up the rule would be
  detector-gaming and would manufacture overlap with that sibling. Reported as a coverage gap owned
  by the council range, not closed here.

## Defects this unit found in its OWN work (each fixed, each caught by a probe not by reading)

1. `reviewer_requirement="the rater"` (9 chars) against `minLength: 10` — and because draft
   2020-12 discards annotations from a failed subschema, it cascaded into a misleading
   `unevaluatedProperties` error at the *stage* level. Fixed.
2. `model_target.vendor` has **no `"any"` member**, while `role_spec.vendor` does. Four blueprints
   plus one subworkflow routed a deterministic script to `vendor: "any"`. Fixed by deleting those
   routes: a script is not a model target, so it is now expressed only as a ROLE with
   `vendor: "any"` and no route. Inventing a vendor for a script would be a lie in the one field a
   router reads.
3. `lineage.derived_from[].relation="ADAPT"` — `ADAPT` belongs to the *acquisition-route*
   vocabulary, not the *lineage-relation* vocabulary. Corrected to `GENERALIZE`, which is what the
   change actually is (the source workflow hardcoded one PR landscape; this parameterises it).
4. `retry_policy="none"` (4 chars) against `minLength: 10`. Fixed.
5. A both-states control was failing with `KeyError` instead of `AssertionError` — i.e. reporting a
   crash rather than a measured failure. Fixed to `.get()`.
6. `test_bp3_catalog` originally asserted that `platform/workflows/` contains **only** this range's
   12 files. That is wrongly scoped: the directory is SHARED with sibling ranges (measured: 92 JSON
   files present). Rescoped to a subset assertion plus a new cross-range id-collision test.

## Scope and residual (UNVERIFIED items are inline, next to the claim they qualify)

- `platform/workflows/` and `platform/lib/workflows/` are shared with sibling blueprint units.
  Measured at the time of this run: `test_bp4_blueprint_set.py` and `test_bp5_slice.py` each have
  **1 failing test**, both asserting the existence of *their own* flagship test files that are not
  yet written. Neither failure touches this unit's files; running this unit's 14 test modules in
  isolation gives 252 passed / 0 failed. No sibling file was edited.
- The two shared subworkflows are referenced by `workflow_id` + a `source` path; the DSL validator
  does not resolve `source` on disk, so this unit asserts it separately
  (`test_bp_pln_02.py::test_it_references_the_shared_overlap_primitive_rather_than_carrying_a_copy`
  does a real `is_file()`).
- Every `estimate.basis` is `static-declared`. **No run of any of these 12 blueprints has been
  measured**, so claiming `historical-measured` would require naming runs that do not exist;
  `test_no_blueprint_declares_a_measured_estimate_it_cannot_name` enforces this.
- UNVERIFIED (inline in `bp-pln-04`'s `x_extensions.unverified_inline`): that the
  `pipeline()`-re-runs-its-first-stage defect still behaves as recorded on the current runtime.
  The blueprint carves around it unconditionally, which is safe either way. Settling experiment:
  wrap one unit in a pipeline, stop it, resume, and observe whether stage one re-runs — as a
  both-states probe, not a single reading.
- Two owner decisions were RECORDED rather than silently answered: `bp-arc-01` (is a tournament
  worth 3-5x a design council) and `bp-arc-03` (may an audit propose removing a security-bearing
  component — `allow_security_removal` defaults to `false`). `bp-arc-05` goes further and
  mechanises its two: `max_threads` and `worker_model_floor` are REQUIRED params with **no
  default**, so the blueprint refuses to run until the owner resolves the live
  lifecycle-vs-standing-preference conflicts.
