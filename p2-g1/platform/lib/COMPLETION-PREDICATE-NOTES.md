# contracts/completion-predicate — measured results

State: **MEASURED** (was SKELETON; every row below is backed by a command whose output is quoted).
Measured 2026-08-09 at `main @53c37c6c`, repo root `C:/Users/Prekzursil/source/ast-integrate`.

One command reproduces everything:

```
python platform/lib/_verify_all.py
```

```
PASS schemas: completion-predicate-result.schema.json=VALID(2020-12/schema,Draft202012Validator) receipt.schema.json=VALID(2020-12/schema,Draft202012Validator)
PASS pytest: exit=0 :: 65 passed in 4.51s
PASS differential: exit=0 :: SUCCESS:predicate-differential A_gaps=0 B_schema_accepts=7/12 C_legacy_unenforced=[1, 3, 4, 6, 7, 8, 9, 10, 11, 12] C_tail_divergence=True
PASS real-units: exit=0 :: SUCCESS:predicate-real-units 3 real + 3 incomplete evaluated, 12/12 conditions published for all six, every deliberately-incomplete case blocked
PASS shadow-control: exit=0
PASS mutation-selfcheck: exit=0 :: SUCCESS:predicate-mutation-selfcheck 12/12 mutants killed
SUCCESS:contracts-completion-predicate 6/6 steps green
```

## Scope

Gate A only: the 12 per-unit conditions at `_USER-PROMPTS.md:10631-10644` (LF-only numbering),
transcribed in `command-center/COMPLETION-GATES.json` → `gate_a_unit_completion_predicate`. This is
**not** gate B (the 21-condition program stopping rule). They intersect only at gate B condition 21.

## Deliverables

| Path | What |
|---|---|
| `platform/lib/completion_predicate.py` | the reducer: 12 typed conditions, `PredicateOptions`, CLI |
| `platform/lib/test_completion_predicate.py` | 65 tests incl. the 12-mutation battery |
| `platform/schema/completion-predicate-result.schema.json` | the result contract (superset of `receipt.schema.json#/$defs/predicate_report.report`) |
| `platform/lib/_predicate_differential.py` | condition→function table · schema-only coverage · legacy differential |
| `platform/lib/_predicate_real_units.py` | 3 real + 3 incomplete units · EOL/digest census |
| `platform/lib/_mutation_selfcheck.py` | mutation test of the shipped evaluators |
| `platform/lib/_derive_size_floors.py` | derivation of the condition-3 byte floors |
| `platform/lib/_probe_platform_shadow.py` | both-states control for the `platform/` dir hazard |
| `platform/lib/_verify_all.py` | the one-command proof above |

`platform/schema/receipt.schema.json` is **owned by a sibling lane** and was NOT written by this
unit. It is consumed, not duplicated.

## Claims, each with its verdict

| Claim | Verdict | Evidence |
|---|---|---|
| All 12 conditions have a distinct implementing function | CONFIRMED | `A_gaps=0`, AST-derived table with a `file:line` per condition |
| 12/12 mutations caught, each naming exactly its condition | CONFIRMED | `unsatisfied == [n]` asserted for all 12 |
| The battery is not a no-op gate | CONFIRMED | `_mutation_selfcheck.py`: 12/12 mutants killed, each importable + exit 1 + unrelated control green |
| Both schemas are valid 2020-12 | CONFIRMED | `check_schema` under `Draft202012Validator` |
| Result validates against its own schema, for baseline + all 12 mutants | CONFIRMED | `test_emitted_report_validates_against_the_result_schema` |
| Result embeds as a `predicate_report` payload | CONFIRMED | `test_report_embeds_as_a_predicate_report_payload` |
| Baseline receipt satisfies the sibling receipt envelope | CONFIRMED | `test_baseline_receipt_validates_against_the_receipt_envelope_schema` |
| Exit code zero alone cannot return COMPLETE | CONFIRMED | `test_exit_code_zero_alone_cannot_be_success` |
| A file path in text is not accepted as proof of existence | CONFIRMED | `stat()` + a lying-receipt report |
| A plausible digest is rejected | CONFIRMED | re-hash, both EOL forms tried, then UNSATISFIED |
| The reducer never raises on hostile input | CONFIRMED | 6 hostile shapes, `evaluator_error` asserted absent |
| Program-wide adoption at the 7 named call sites | **NOT-CHECKED** | out of scope for this unit; `IMP-0417` owns the replacement of local checks |
| Cross-vendor adversarial review of this unit | **NOT-CHECKED** | the reducer's own condition 9 would report NOT-CHECKED for this unit today |

## HEADLINE: this wave built TWO gate-A reducers, and they disagree on 4 of 12 mutations

`platform/lib/` now holds two independent implementations of gate A:

* `platform/lib/completion_predicate.py::evaluate` (this unit)
* `platform/lib/receipt_schema_gate.py::evaluate_gate_a` (the receipt-envelope lane)

plus the partial `hooks/_shared/completion.py`. Run
`python platform/lib/_predicate_twin_differential.py` — both accept the identical baseline (control
passes), then over the identical twelve isolated mutations:

```
completeness_disagreements=[4, 5, 9, 11]   blamed_condition_disagreements=[1, 2, 4, 5, 7, 8, 9, 10, 11, 12]
```

Root causes, each confirmed by quoting the other reducer's own `basis` string, not inferred:

| n | `receipt_schema_gate` basis | Divergence | Which reading the spec supports |
|---|---|---|---|
| 4 | `validates against receipt.schema.json` | it validates the **receipt**; this unit validates the **artifact** against its declared `output_schema` | line 10636 says "**artifact** parses against its schema", in a list whose 2/3/5 are all about the artifact → the artifact reading. But its receipt check is a real gate this unit lacks (see gap below). |
| 5 | `sentinel embeds IMP-0415` | it never opens the artifact, so a receipt whose artifact does **not** carry the sentinel passes | spec failure class line 11313: "an artifact that exists but carries no sentinel is INCOMPLETE" → this unit's reading |
| 11 | `registered in out/ARTIFACT-MANIFEST.json` | returns SATISFIED for an artifact **absent** from the very manifest it names (measured against a manifest whose `artifacts` array was emptied) | ARC-0084: "an artifact on disk but unregistered must fail the predicate" → this unit's reading |
| 9 | — | **NOT a defect in theirs.** This unit was run with `require_cross_vendor_review=True`; `evaluate_gate_a` has no such option, so it cannot know. Configuration difference, scoped as such. |

**Gap in THIS unit, found by the same differential:** `evaluate()` does not validate the receipt
against `receipt.schema.json`, while `evaluate_gate_a` does and blocks on it. Neither reducer is a
superset. A merge needs: artifact-schema validation AND receipt-schema validation AND
sentinel-in-artifact AND real manifest membership AND the cross-vendor option.

The twin differential is deliberately **not** wired into `_verify_all.py`: it depends on a sibling
lane's mid-flight file, so a rename there would turn this unit's proof bundle red for a reason
outside its control.

## Findings for the orchestrator

1. **A competing predicate is live.** `hooks/_shared/completion.py:2` calls itself *"the ONE shared
   completion predicate (C1) for this harness"*. Measured against the same 12 mutations it does not
   enforce **10 of 12** conditions (only 2 and 5). This is the seeded failure class *"two completion
   predicates disagree"* (`_USER-PROMPTS.md:11314`) already live, and it settles the
   `implementation_state: NOT-CHECKED` recorded in `COMPLETION-GATES.json`.
2. **The legacy predicate false-fails JSON artifacts.** It searches only the last
   `DEFAULT_SENTINEL_TAIL = 600` bytes for the sentinel. Measured: a 1,329-byte JSON artifact with
   its sentinel at byte 68 → `artifact_ok` returns `False`, `"sentinel ... absent from last 600B"`,
   while a whole-file window returns `True`. Both-states control discriminates. Since every
   catalogued unit declares a JSON `output_schema`, a harvester using it can score finished work as
   incomplete — the exact silent-work-loss family that module's own docstring exists to prevent.
3. **A manifest digest gate must be EOL-aware or it is 100% false-positive here.** Of the 13
   checkable entries in `command-center/ARTIFACT-MANIFEST.json`: **0** match working-tree bytes,
   **12** match only after CRLF→LF normalisation, **1** matches neither. This reducer therefore
   tries both forms and reports `digest_match_mode`.
4. **`command-center/WORK-UNIT-CATALOG.json` is the one entry matching neither EOL form** — real
   manifest drift, independently corroborating the `REACH-6` violation `validate.py` reports.
5. **Schema validation alone is not the gate.** The sibling receipt envelope rejects 5 of the 12
   mutations; it accepts conditions **2, 3, 4, 5, 6, 9, 11**. A caller that validates the schema and
   skips the reducer passes 7 of 12 violations.
6. **Never create `platform/__init__.py`.** Both-states control: without it `import platform`
   resolves to `C:\Python314\Lib\platform.py`; with it, to the repo directory and `hasattr(platform,
   'system')` becomes False — stdlib shadowing for every tool run from the repo root.
7. **`platform/lib/` has a concurrent-write race.** A `shutil.copytree` of it died with `WinError 2`
   on a sibling lane's `wfdsl/schemas.py.tmp.<pid>.<hash>`.
8. **Applicability belongs to the unit class, not the receipt.** A receipt that could declare its own
   conditions inapplicable is self-certifying, so `PredicateOptions` carries applicability and
   conditions 1,2,3,4,5,11,12 are non-waivable.

## Two detector failures I made and fixed (both would have shipped a false green)

* The differential's part C control read `FAILED` on the **known-good** case, so its "0
  disagreements" measured nothing. Root cause: the 600-byte tail window (finding 2). Fixed by
  running the coverage differential whole-file and measuring the tail window separately with its own
  both-states control.
* The mutation self-check reported **12/12 killed** while every mutant was an `IndentationError`
  (pytest exit 2, a collection error) — it measured a syntax error, not sensitivity. Then a `-k`
  expression collected zero tests (exit 5) and scored 12/12 **survived**. Fixed with AST-correct
  insertion, exact node ids, and a four-part kill criterion: importable **and** selected **and**
  exit 1 **and** an unrelated control still green.

## Condition 3 byte floors, derivation shown

`platform/lib/_derive_size_floors.py` over 28 real artifacts: floor = `max(64, min(class)/2)` →
json 1483 (min 2,967) · markdown 1051 (min 2,103) · jsonl 203 (min 406). These are DEFAULTS; a
receipt declares `min_bytes_threshold`, and a declaration below the absolute floor of 64 is raised
with `weak_threshold_declared: true` recorded, because ARC-0084 rejects a one-byte floor as "not a
real threshold".

## Residual

Condition 5 is UNSATISFIED for all three real ledger artifacts tested: they predate the sentinel
contract and carry no `SUCCESS:<ID>`/`SENTINEL:<ID>:<TOKEN>` token. Settling experiment: decide
whether the 13 Phase-0 ledger files are in scope for the sentinel contract, or whether condition 5
applies only to unit-produced receipts.
