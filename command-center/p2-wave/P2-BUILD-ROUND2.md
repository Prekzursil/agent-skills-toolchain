# P2 BUILD — ROUND 2 (re-entry after a confirmed adversarial refutation)

STATUS: IN PROGRESS. Sections R0-R2 and R5 are MEASURED. R3 (new units) is UNKNOWN - not yet
measured. This file is rewritten at every milestone; whatever is on disk is truthful now.

COVERAGE: R0 measured · R1 measured · R2 measured · R3 UNKNOWN - not yet measured ·
R4 UNKNOWN - not yet measured · R5 measured · R6 partial.

---

## R0. Live partition, re-run as the first action

```
  units 2007 | delivered 1 | READY 449 | blocked 1390 | owner-gated 167
  artifacts present but NOT delivered (self-declared failure / invalid): 48
  block reasons: {'unbuilt': 1370, 'unknown-token': 20}
  first ready: ['ADV-0001','ADV-0003','ADV-0004','ADV-0005','ADV-0006','ADV-0007','ADV-0008','ADV-0009']

SUCCESS:ready-units partition sums correctly
```

Identical to the auditor's reading, so no sibling landed a unit between the two lanes. After the
round-2 fix the partition is byte-identical again (see R1) — the fix was designed to be strictly
stronger with zero collateral, and that was measured before it was written, not after.

---

## R1. The CONFIRMED defect — a declared contract that cannot fail

### R1.1 Reproduced, not read

`python command-center/p2-wave/_av_probe1.py` (the verifier's own probe, re-executed by me):

```
=== Q4: DECISIVE -- is `delivered` one word away? MUTANT state=SUCCESS ===
   IMP-0433   real: delivered=False (self-declared:BLOCKED)   state=SUCCESS mutant: delivered=True   <<< FALSE GREEN
   AUD-0041   real: delivered=False (self-declared:BLOCKED)   state=SUCCESS mutant: delivered=False (schema-invalid:3)
   AUD-0051   real: delivered=False (self-declared:BLOCKED)   state=SUCCESS mutant: delivered=False (schema-invalid:4)
   AUD-0030   real: delivered=False (self-declared:BLOCKED)   state=SUCCESS mutant: delivered=False (schema-invalid:3)
   AUD-0020   real: delivered=False (self-declared:BLOCKED)   state=SUCCESS mutant: delivered=False (schema-invalid:3)
```

Root cause, read off the catalog row (`_r2_row.py IMP-0433`): `output_schema` is
`command-center/schema/meta/json-schema-draft.json` — an alias of the draft-2020-12 meta-schema,
which accepts any JSON object. So condition 4 of `artifact_delivered()` can never fail for that
unit and the predicate collapses to the forgeable `state` field.

Blast radius, measured over all 2,007 units:

| | |
|---|---|
| distinct declared contracts in the catalog | 367 |
| reject all 3 garbage probes (discriminating) | **364** |
| reject none (vacuous) | **3** |
| reject 1 or 2 (ambiguous) | **0** — the split is clean, so the threshold is not a judgement call |
| units declaring one of the 3 | **23** |
| of those, meta-schema is type-APPROPRIATE (`output_path` really is a schema) | 21 |
| of those, category error (`output_path` is a receipt / research doc) | 2 — IMP-0433, RES-0001 |
| currently READY | 3 — CNF-0001, IMP-0433, RES-0001 |

The three vacuous declarations: `https://json-schema.org/draft/2020-12/schema` (21 units),
`command-center/schema/meta/json-schema-draft.json` (1), and
`command-center/schema/_meta/json-schema-2020-12.json` (1).

**And the hollow one nobody had noticed:** WFA-0001 — the program's *single* `delivered=1` unit —
is meta-gated too (`_av_probe2.py` Q5: `GARBAGE validates with errors = 0 -> condition-4
discriminates: False`). The only delivered unit in a 2,007-unit program was certified by a gate
that cannot fail.

### R1.2 The fix, designed against measurements taken first

`command-center/p2-wave/_r2_design.py` measured every assumption BEFORE any code was written:

```
P1 receipt.schema.json vs the state=SUCCESS mutant  -> errors=3      (it CAN reject it)
   receipt.schema.json vs the 3 garbage probes      -> 11 / 11 / 10  (it discriminates)
P2 looks_like_schema_doc: WFA-0001 pack=True | IMP-0433 receipt=False | 3x garbage=False
                          | structurally-broken schema {"type":123,"required":"not-an-array"}=False
P3 vacuity census: 364 reject 3/3, 3 reject 0/3, 0 in between
P4 partition movement over the 49 artifacts on disk: verdict CHANGES = 0
P4b OLD predicate on the mutant: delivered=True   NEW: delivered=False
```

Shipped in `command-center/ready_units.py`:

1. **condition 4b — contract-vacuity guard.** `contract_discriminates()` validates three garbage
   probes against the declared contract; a contract that accepts all three cannot certify
   anything. The probes are the two shapes that fooled an earlier verifier in this program (a doc
   asserting 999999 passing tests; a 2,000-character blob) plus the empty object.
2. **type-appropriate fallback**, keyed on the DOCUMENT not the path (a path-keyed fallback would
   give the self-test fixture a different verdict than the receipt it mirrors — a control that
   measures its own location): a JSON Schema document (`$schema`/`$id` + `check_schema`) is
   accepted; anything else must satisfy `command-center/schema/receipt.schema.json`; otherwise
   `contract-vacuous:no-type-appropriate-fallback`.
3. **fail closed on a validator exception.** `except Exception: pass` at the old line 111 silently
   skipped condition 4. Census that day: **0 of 367** declarations raise, so closing it moves
   nothing — it removes a latent silent-pass rather than fixing a live one. Stated at that scope.
4. **`--self-test` gains two controls and a column** (see R5).
5. **the census is published** into `READY-UNITS.json` (`contract_vacuity`) and printed each run.

Result — partition after the fix, unchanged as predicted by P4:

```
  units 2007 | delivered 1 | READY 449 | blocked 1390 | owner-gated 167
  contract-vacuity: 3 declarations cannot fail, declared by 23 units (checker=live)
SUCCESS:ready-units partition sums correctly
```

### R1.3 The round-1 verifier was the instrument that missed it

`_b1r2_verify_committed.py` validated against the catalog-declared contract and printed
`schema-VALID YES` for IMP-0433 — a green from a gate that cannot fail — and ran its corruption
control on AUD-0020 only while its SUCCESS line spoke for all five. It is marked SUPERSEDED
in place (kept as the record of what round 1 ran) and replaced by `_r2_verify_committed.py`,
which adds a `can-fail` column, the fallback, and a PER-UNIT two-sided control:

```
unit        blob B  CRLF  parses  declared  can-fail effective contract                        VALID   ctl  state
IMP-0433     17774     0    True         0     False command-center/schema/receipt.schema.json   YES    OK  BLOCKED
AUD-0041     77871     0    True         0      True .../audit-inventory.schema.json             YES    OK  BLOCKED
AUD-0051     29935     0    True         0      True .../audit-metric-baseline.schema.json       YES    OK  BLOCKED
AUD-0030     23565     0    True         0      True .../audit-graph.schema.json                 YES    OK  BLOCKED
AUD-0020     34300     0    True         0      True .../audit-inventory.schema.json             YES    OK  BLOCKED
SUCCESS:r2-verify 5/5 committed blobs validate against a contract PROVEN able to fail, each with
its own two-sided control
```

---

## R2. Sentence repairs — refuted wording recorded, not deleted

Three edits to `P2-BUILD-ROUND1.md`, each leaving the original text in place with an inline
`REFUTED` block beside it (plus a summary block at the top of that file):

| # | original claim | verdict | correctly-scoped replacement |
|---|---|---|---|
| R1 | "each delivered unit executable-proven against its declared contract" (C5 heading + DoD 3 PASS) | **REFUTED for 1 of 5** | 4 of 5 proven against a contract measured able to reject garbage; IMP-0433 proven against `receipt.schema.json` (which the emitter *did* apply via `also=[...]`) + its 12+1 fixture matrix. The PROOF was vacuous; the ARTIFACT was always fine. |
| R2 | "A `state` field alone is forgeable by a one-word edit … Schema validation cannot be satisfied that cheaply" | **REFUTED for 23 units** | True for the 364 discriminating declarations; false for the 3 vacuous ones, where T3 collapses to T2. |
| R3 | "delivered 1" presented as the strict predicate's headline | **hollow, now disclosed** | WFA-0001 is meta-gated too; it survives via the schema-document fallback, and `--self-test` now prints which path certified it. |

Following the program's own finding that overclaims outnumber real defects ~5:3, I checked
whether these were overclaims or broken code. R1 and R3 are **overclaims** — the artifacts and
the emitter were correct, the sentences were wider than the evidence. R2 is a **real defect** in
the predicate, now fixed and controlled.

---

## R3. New units delivered this round

UNKNOWN - not yet measured.

## R4. Blocked units with precise blockers

UNKNOWN - not yet measured.

---

## R5. Detector controls (every count above is gated behind one)

`python command-center/ready_units.py --self-test` — EXIT 0:

```
  CONTROL contract_discriminates(known-VACUOUS): want=False got=False -> OK
  CONTROL contract_discriminates(known-DISCRIMINATING): want=True got=True -> OK
  CONTROL WFA-0001: want=True got=True (delivered(schema-document fallback; declared contract is
      vacuous)) | legacy-exists-predicate=True | pre-4b-predicate=True -> OK
  CONTROL ADV-0031: want=False got=False (self-declared:BLOCKED) | legacy-exists-predicate=True
      | pre-4b-predicate=False -> OK
  CONTROL VACUOUS (state:=SUCCESS mutant): want=False got=False
      (contract-vacuous:no-type-appropriate-fallback(receipt-errors=3)) | pre-4b-predicate=True
      -> OK (guard fires on the broken state)
```

The load-bearing column is `pre-4b-predicate`. For the VACUOUS control it reads **True** — the
predicate shipped in round 1 accepted that document — so the new guard is measured firing on a
state where the old one was silent. That is the both-states test applied to the fix itself, not
to the thing the fix inspects. The self-test asserts the old column is True and FAILS if the
fixture ever stops being a known-broken state.

The vacuity detector is itself controlled two-sided before any verdict that depends on it uses
it (`contract_discriminates` rows above), because a vacuity checker that answered "vacuous" for
everything would silently route all 2,007 units through the fallback.

Fixture provenance: `_r2_mkfixture.py` regenerates the mutant and asserts it differs from the
real receipt in **exactly one field** and that the source receipt does not already say SUCCESS
(which would make the control inert).

---

## R6. Residual / NOT-CHECKED

- **The reviewer gate is unchanged and still binding.** 449/449 READY units carry a
  `reviewer_requirement`, and `receipt_core` forbids `state: SUCCESS` without
  `reviewer.verdict=PASS` + `independent=true`. Round 1's five artifacts remain `BLOCKED` on it;
  so will anything this round produces. A build lane cannot legitimately close a unit alone.
  Measured, not asserted: the IMP-0433 mutant is rejected by `receipt.schema.json` with 3 errors
  precisely because its `reviewer.verdict` is `NOT-REVIEWED`.
- **21 of the 23 meta-declaring units are a catalog-design question, not a bug.** For a unit whose
  output really is a schema, the meta-schema is the right KIND of contract; it simply cannot
  reject unrelated JSON. The fallback covers them; tightening their catalog rows is an owner call.
- **NOT-CHECKED:** whether the fallback is the right contract for the 2 category-error units
  (IMP-0433, RES-0001) or whether their rows should be corrected. Correcting a catalog row is
  re-scoping a unit, which this lane is forbidden to do.
- **NOT-CHECKED:** cloud-batch substrate reachability (55 READY units) — no probe run.
- **NOT-CHECKED:** repo-wide coverage — round 1 measured that no enforcement command in this tree
  emits a coverage table.
