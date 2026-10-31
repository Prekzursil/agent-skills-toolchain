# D5 — `assigned_model_vendor_role` canonicalisation

Unit: `defect/d5-vendor-role-canonical`. Catalog: `command-center/WORK-UNIT-CATALOG.json`
(`work_units[]` = 2,007; the separate `items[]` = 103 register is untouched — measured
byte-equal to HEAD, and 0/103 of its entries ever carried this field).

COVERAGE: Q1-Q5 all MEASURED. Every number below was read off disk by a named command, not
recalled. One residual is UNRESOLVED and needs an owner decision — see Q6.

---

## Q1 — regression, or measurement change? **MEASUREMENT CHANGE (REFUTED as a regression)**

The briefed "128 → 1,879 regression" is a **polarity-inverted detector**, not a changed world.
Three mechanically independent signals:

1. **The two numbers are complements, not a before/after.** On disk at HEAD: 1,879 object-form
   + 128 string-form = 2,007 exactly. `1,879` counted the units in the **canonical** object
   form; `128` counted the non-canonical slash-triple string form.

2. **The Wave 2 audit already retracted its own number**, in the same JSON object that carries it
   (`command-center/WAVE2-FLOOR-AUDIT.json`, `check7_catalog_defect_deltas`):
   - `PASS4_DETECTOR_FAILURES_RECORDED[1]` = *"assigned_model_vendor_role polarity inverted:
     pass 4 called the 1,879 canonical object-form units non-canonical"*
   - `CORRECTED.assigned_model_vendor_role_object_form_CANONICAL` = `1879`
   - `CORRECTED.assigned_model_vendor_role_string_triple_NONCANONICAL` = `128`
   - `WAVE2-FLOOR-AUDIT.md:369` — `| non-canonical … (string-triple form) | 128 | **128** |`

   The brief was written from the audit's *uncorrected pass-4* field
   (`assigned_model_vendor_role_noncanonical_units: 1879`), which sits three keys above its own
   retraction. This is the "read your own instrument" failure, not a new defect.

3. **The project's own validator**, a different instrument from my hand-written classifier
   (jsonschema Draft202012 against `work-unit.strict.schema.json`), reported
   `assigned_model_vendor_role [type]: 128` in the strict `reason_histogram` — never 1,879.

Canonicality was never mine to invent: `work-unit.strict.schema.json:11` already said
*"canonical: the object form"*. Pass 4 measured the complement of the schema's own declaration.

**Verdict: 128 → 128 at HEAD, UNCHANGED. No regression occurred.**

The "518 distinct shapes" figure is the same artifact. Only **4** structural key-set
fingerprints existed in the entire corpus:

| count | fingerprint |
|---|---|
| 1,431 | `obj:model,role,vendor` |
| 320 | `obj:basis,model,role,vendor` |
| 128 | `obj:model,rationale,role,vendor` |
| 128 | `str` |

518/529 counts distinct *serialized values* — dominated by 310 distinct `role` strings. That is
a value census, not a shape census, and it cannot support a "518 shapes" claim.

## Q2 — canonical shape: **already expressible; nothing new invented**

`work-unit.schema.json` `$defs/assignment_object` — `required [model, vendor, role]`, optional
`basis`/`rationale`, `additionalProperties: false`. The strict profile narrows the field to
`type: object`, which selects that branch through the `allOf` chain, so the required keys are
enforced without strict restating them (verified: strict rejects a slash-triple string).

The base profile deliberately **keeps** accepting the string branch. Two reasons, both checked:
`test_profiles_are_strictly_ordered` (`platform/lib/wfdsl/test_schemas_and_examples.py:117`)
uses a slash-triple string as its structural-accepts / strict-rejects fixture; and the strict
profile's stated purpose is to render union shapes as *countable migration debt*. Only the
**catalog data** was normalised.

`defaults.assignment` (the documented alias, `resolve.py:24`) was already the object form.

## Q3 — multi-vendor expressibility: **REAL GAP, closed additively**

6 units packed prose into `model`:

| units | `model` | `vendor` | nature |
|---|---|---|---|
| ADV-0005, ADV-0009 | `opus + gpt-5-codex (>=2 vendors, run independently, results compared not merged)` | `mixed` | genuine 2-vendor |
| ARC-0069, ARC-0076 | `opus + codex-cli-default (>=2 vendors, model-diverse)` | `mixed` | genuine 2-vendor |
| WFA-0074, WFA-0117 | `codex-cli-default (gpt-5.x class, whatever the mounted codex mcp-server resolves)` | `openai` | single vendor + qualifier |

`vendor: "mixed"` recorded *that* vendors differed but not *which*, and nothing read it (grepped
`platform/lib`: zero consumers of the value `"mixed"`). Two optional keys were added to
`assignment_object` rather than flattening to a lossy single value:

- **`co_assignments[]`** — additional `{model, vendor, role?}` entries. `model`/`vendor`/`role`
  stay the PRIMARY assignment, so every existing single-valued reader keeps working; each extra
  vendor is individually addressable instead of parsed out of `" + "`.
- **`multi_vendor_policy`** — enumerated combination semantics:
  `independent-compared-not-merged` · `independent-merged` · `model-diverse-panel`. The
  AGENTS.md cross-vendor-independence constraint survives as data, not prose.
- **`dependentRequired: {co_assignments: [multi_vendor_policy]}`** — declaring a second vendor
  without saying how the vendors combine is rejected, because that is exactly the information
  the prose form was carrying and losing.

The original string is preserved verbatim in `rationale` on all 6 units, so the transform is
**non-lossy and auditable**.

Both-states control on the new keys (all 7 probes behaved):

| probe | result |
|---|---|
| `co_assignments` + `multi_vendor_policy` | ACCEPT |
| `co_assignments` **without** `multi_vendor_policy` | REJECT |
| unknown `multi_vendor_policy` token | REJECT |
| `co_assignment` missing `vendor` | REJECT |
| empty `co_assignments` array | REJECT |
| plain single-vendor canonical | ACCEPT |
| legacy slash-triple (structural / strict) | ACCEPT / REJECT |

## Q4 — normalisation: before/after, read off disk

**134 units changed** — 128 `string-triple-to-object`, 4 `prose-model-to-co-assignments`,
2 `prose-model-to-basis`. No unit renumbered, added or dropped (asserted in-process AND
re-verified against the HEAD blob).

| measure | BEFORE (HEAD) | AFTER (disk) |
|---|---|---|
| `work_units[]` | 2,007 | 2,007 |
| non-canonical (string form) | **128** | **0** |
| canonical (object form) | 1,879 | **2,007** |
| structural key-set fingerprints | 4 | 5 |
| distinct serialized values | 529 | 525 |
| distinct `object.model` strings | 9 (3 of them prose) | **6** (all clean tokens) |
| units with prose/compound `model` | 6 | **0** |
| units with `vendor: "mixed"` | 4 | **0** |
| units with structured `co_assignments` | 0 | **4** |
| strict profile pass / fail | 1,679 / 328 | **1,694 / 313** |
| strict `assigned_model_vendor_role [type]` | **128** | **0** (key absent) |
| normative pass / fail | 1,790 / 217 | 1,790 / 217 (unchanged) |
| structural pass / fail | 2,007 / 0 | 2,007 / 0 (unchanged) |
| SEM-001…SEM-011 | — | **all 11 unchanged, delta +0** |

Strict failures fell by 15, not 128, and that is the honest number: 113 of the 128 string-form
units (the `IMP-0385+` block) also fail strict on `tests_required`, `failure_classification` and
`completion_sentinel`, so only 15 became fully strict-clean. Those three remain open defects
owned elsewhere.

`platform/schema/WORKFLOW-DSL-VALIDATION.json` was updated **surgically** (4 values) rather than
regenerated: a full regeneration also swept in pre-existing staleness that is not mine — the
committed snapshot predates `SEM-008`…`SEM-011` in `semantics.py` and omits them entirely, and
regenerating rewrites the `catalog` path string. Reported, not silently absorbed. Its three
profile pass/fail pairs and the full strict histogram now match a live validator run exactly.

### Serialisation trap, caught before writing

The catalog is `indent=1`, `sort_keys=False`, **CRLF**, **no trailing newline**. A naive
`json.dumps(indent=2)` + `write_text` would have rewritten all 5.3 MB as a whitespace diff. The
shipped writer emits bytes and is guarded by a byte-identity assert; both-states control:

```
shipped serializer  == disk : True
  broken[indent=2            ] == disk : False
  broken[LF instead of CRLF  ] == disk : False
  broken[trailing newline    ] == disk : False
  broken[sort_keys=True      ] == disk : False
```

Actual diff surface: **686 insertions / 138 deletions** attributable to D5, not a whole-file
rewrite. CRLF preserved (100,082 CRLF / 0 bare LF), no trailing newline. Second `--check` run
reports `changed=0` and byte-for-byte round-trip → idempotent.

**Own-detector failure recorded:** the round-trip assert initially read
`raw.encode("utf-8")` after `raw` became `bytes`, so it raised `AttributeError` and, because it
sat behind `if not changes:`, **never executed on the `--apply` run**. The write went out
unverified. Found on the second run, fixed, and re-proved in both states. The write happened to
be correct, but the guard was not protecting it — a guard that never runs is not a guard.

## Q5 — suite: **3,064 passed / 14 skipped / 0 failed**

`cd platform && python -m pytest -q` → `3064 passed, 14 skipped in 212.88s (0:03:32)`.
D5-relevant modules run directly: `wfdsl/test_catalog_conformance.py` +
`wfdsl/test_schemas_and_examples.py` → **109 passed**.

An earlier run of the same command during this unit reported `1 failed, 2996 passed, 14 skipped`;
that failure was `test_wave1_files_are_untouched` and it is now gone — see Q6 for why, because a
red-to-green flip I did not cause is a signal to investigate, not a result to bank.

The pinned baseline (2,767 passed / 14 skipped / 0 failed) is **no longer the right comparison
frame**: 3,078 tests are now collected, ~297 more than the baseline, added by sibling units in
this same wave. Passed count went UP and failures are 0; the honest statement is "0 failures and
no D5-attributable regression", not "2,767 preserved".

Lint under CI's pinned ruff **0.15.17** (not the ambient one): `ruff check` → *All checks
passed*; `ruff format --check` → *3 files already formatted*. All three new scripts are LF,
matching the repo's tracked `.py` blobs.

Lint under CI's pinned ruff **0.15.17** (not the ambient one): `ruff check` → *All checks
passed*; `ruff format --check` → *3 files already formatted*. All three new scripts are LF, matching
the repo's tracked `.py` blobs.

## Q6 — RESOLVED by a sibling lane, independently verified — **no owner decision needed**

`test_wave1_files_are_untouched` no longer exists. A concurrent sibling lane (DEFECT D1/D3, see
`platform/DEFECT-D3-TEST-MUTATES-TREE.md:166-179`) hit the same collision and replaced it with
exactly the re-scoping recommended below, arriving at it independently.

I verified the replacement is a real guard and not a weakened no-op — the failure mode that
matters here is a guard that turns a bug into a green:

- `test_catalog_contract_is_intact_for_what_this_unit_reads` asserts unit count 2,007, the
  **ordered** id list, the **ordered** `output_schema` list, and `items[]` == 103.
- `test_catalog_contract_guard_fires_on_a_destructive_edit` is its both-states control and
  proves it still reds on a deleted unit, a renamed id, a rewritten `output_schema`, and a
  dropped `items[]` entry — while deliberately staying silent on an unrelated field addition.
- The `receipt.schema.json` pin was likewise narrowed to a *named authorized delta* with its own
  four-mutation control, and asserts the D1 layer is POSITIVELY present so a revert cannot pass.

D5 satisfies every clause, measured against the HEAD blob via `git cat-file -p` (never
`git archive`): count `True`, ordered ids `True`, ordered `output_schema` `True`, `items[]`
`True`. `python -m pytest test_schema_resolver.py -k "catalog_contract or authorized_delta"` →
**3 passed**.

Recording this because it is load-bearing for the green: the suite went red→green without any
edit of mine, and HEAD did **not** move (still `0aa6f8fa`) and both files still differ from HEAD
— so the green comes from a *narrowed but still-toothed* guard, not from the tree reverting.

### Original finding, retained (the defect class is the durable part)

The one failing test (`platform/lib/test_schema_resolver.py:252`) byte-pins **two** files to
committed HEAD:

```python
for rel in ("platform/schema/receipt.schema.json",
            "command-center/WORK-UNIT-CATALOG.json"):
    ...
    assert committed == working, f"{rel} DIFFERS from HEAD; this unit must not modify it"
```

The second path is the catalog **this unit was chartered to normalise**. Facts, measured:

- The reported failure names **`receipt.schema.json`** — the loop's first element, modified by a
  **sibling agent** (202 insertions), not by me. **The test is red with or without D5.**
- It would also fire on the catalog. Both files are non-byte-identical to HEAD right now.
- Everything the pin actually protects is preserved by D5: unit count 2,007, id sequence,
  `items[]`, `output_path` set, `output_schema` set, `contract` block, `schema_version` — all
  verified identical to the HEAD blob via `git cat-file -p` (never `git archive`).

This is the anti-pattern the estate's own rule names: *"equality to a pinned SHA is a
self-falsifying safety check"*. It encodes "the schema_resolver unit must not modify these
files" as "no unit may ever modify these files", which contradicts the strict profile's premise
that migration debt gets paid down.

**I did not edit it.** Three units had a legitimate claim on that assertion (D5, the receipt
editor, the SEM-009/010/011 fixer); rewriting a shared guard so my own change goes green is the
"guard that converts a bug into a green" hazard in the social direction. My recommendation was:
replace the catalog byte-pin with the semantic invariants above (count + id sequence +
`output_schema` resolution), keep the `receipt.schema.json` pin for its owner. **Settling
experiment named at the time:** apply that re-scoping and confirm the test goes green on the
catalog while still failing if a unit id or an `output_schema` reference is mutated. The sibling
lane ran exactly that experiment; both halves now pass, so the recommendation is CONFIRMED rather
than merely proposed.

## Concurrency hazard observed (report, not a D5 defect)

A sibling agent wrote to `WORK-UNIT-CATALOG.json` concurrently with this unit. Attribution
against the HEAD blob:

| author | field | units |
|---|---|---|
| D5 (this unit) | `assigned_model_vendor_role` | 134 |
| sibling | `owner_approval_required` | 23 |
| sibling | `tool_permissions` | 9 |
| sibling | `execution_substrate` | 2 |

**Overlap: 0 units.** My change is intact (census: 2,007 object-form, 0 string-form, 4
`co_assignments`). No clobber occurred — but both units do whole-file read-modify-write on one
5.3 MB JSON, so a clobber was available and only interleaving avoided it. The sibling's fields
map exactly onto SEM-009 (30) / SEM-011 (10) / SEM-010 (2).

---

## Reproduce

```
python command-center/d5_measure.py                          # shape census off disk
python command-center/d5_normalize_assignment.py --self-test # both-states control
python command-center/d5_normalize_assignment.py --check     # idempotence + round-trip
python command-center/d5_preflight.py                        # before/after profile counts
cd platform/lib && python -m wfdsl.validate catalog ../../command-center/WORK-UNIT-CATALOG.json
cd platform && python -m pytest -q
```
