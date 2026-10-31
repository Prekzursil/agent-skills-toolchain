---
title: P2-BUILD-ROUND2
type: note
permalink: dqverify-repo-20261013/command-center/p2-wave/p2-build-round2
---

# P2 BUILD — ROUND 2 (re-entry after a confirmed adversarial refutation)

> ## REFUTED IN ROUND 3 — read this before citing anything below
>
> An adversarial verifier executed the round-2 fix and broke it, and I reproduced both defects with
> its own probes (`command-center/p2-wave/_av2_tmp/`) before changing a line:
>
> 1. **The vacuous-contract fallback was a ONE-KEY bypass.** `looks_like_schema_doc` checked for a
>    `$schema`/`$id` key plus `check_schema`, and `check_schema` accepts unknown keywords — so
>    adding one key to arbitrary garbage returned `delivered=True`, including for a bare
>    `{"$schema": ...}` of 59 bytes and for a 2,000-x blob. `BYPASS_PROVEN = True`. 23 units declare
>    a contract that cannot fail and were one key from a false green.
> 2. **The control shipped with that fix was silent in both states.** Its docstring claimed
>    two-sidedness against `{"type": 123, "required": "not-an-array"}` — a document carrying neither
>    key, so the KEY check rejected it and `check_schema` was never exercised by the control at all.
> 3. **Every non-`.json` artifact skipped the gate entirely** (`return True, "non-json-present"`),
>    so a 2,000-x file named `.md` was DELIVERED while the identical bytes named `.json` were
>    rejected. 120 units sit behind that branch — 0 of their artifacts exist, so the hole was latent
>    and no delivered count was ever wrong because of it.
> 4. **"Each delivered unit executable-proven against its declared contract" was wider than its
>    evidence.** IMP-0433's declared contract is a meta-schema that accepts arbitrary JSON, measured
>    0/12 garbage documents rejected. Its receipt is proven against `receipt.schema.json`, which is
>    discriminating — but NOT against the contract its own catalog row names.
>
> All four are fixed or correctly re-scoped in
> [`P2-BUILD-ROUND3.md`](P2-BUILD-ROUND3.md). The wording above is left in place deliberately.


STATUS: COMPLETE for this round. Every section carries a measurement or an explicit NOT-CHECKED;
nothing reads `UNKNOWN - not yet measured`.

COVERAGE: R0 measured · R1 measured · R2 measured · R3 measured · R4 measured · R5 measured ·
R6 measured-or-explicitly-NOT-CHECKED.

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

Order is the recorded owner ruling OQ-2: ascending INTEGER phase, then unblocking power. Round 1
took ranks 1,2,3,5,6 and skipped rank 4. Round 2 takes ranks **7 and 8** — the next two in that
order, both phase 0, both unblocking 3, both declaring a contract measured able to fail. Depth
over breadth: two units fully proven, not five stubs.

```
  IMP-0433 phase=0 unblocks=13  (round 1)     AUD-0020 phase=0 unblocks=3  (round 1)
  AUD-0041 phase=0 unblocks=8   (round 1)     AUD-0030 phase=0 unblocks=3  (round 1)
  AUD-0051 phase=0 unblocks=5   (round 1)  >> CC-0002  phase=0 unblocks=3  ROUND 2
  AUD-0001 phase=0 unblocks=3   BLOCKED    >> IMP-0440 phase=0 unblocks=3  ROUND 2
  CONTROL phase-sort: ['0','2','2A','10'] -> OK
```

### CC-0002 — create the receipt substrate every unit is contracted to write to

`command-center/receipts/CC-0002.json` (13,399 B blob) — `python command-center/p2-wave/_build_CC0002.py`

Premise **REFUTED on three of its four asserted absences**: `receipt.schema.json` is present
(5,882 B, git-tracked), `command-center/receipts/` exists with 4 receipts, and an emitter exists
(`p13_emit_receipt.py`, 42,480 B). The fourth — a committed `.gitkeep` — was genuinely absent and
is created by this unit.

Prior art was EXECUTED before anything was written. `platform/lib/receipt_schema_gate.py` already
ships schema validation plus the 12-condition predicate, so it was run against the four mutants
the row names:

```
fixture                       schema-only  full-gate
golden (TST-0334)                    rc=0       rc=1
m1-missing-sentinel                  rc=1       rc=1
m2-empty-evidence                    rc=1       rc=1
m3-unit-id-not-in-catalog            rc=0       rc=1   <-- ACCEPTED: `SCHEMA-VALID:ZZZ-9999`
m4-unparseable                       rc=1       rc=1
```

Two facts fall out, and the row needs both. **The hole:** a receipt whose `unit_id` is not one of
the 2,007 catalog units validates with exit 0. `WORK-UNIT-CATALOG` and `work_units` appear
nowhere in that file, so the cross-reference is genuinely absent, not a use-vs-mention miss.
**The layer confusion:** the full gate rejects the GOLDEN receipt too (correctly — it is
state=BLOCKED on the reviewer gate), so layer 2 cannot be the accept/reject instrument the row's
"a golden receipt validates" test requires. Admission and completion are different questions.

Shipped `command-center/receipt_validate.py`: an ADMISSION check that IMPORTS the existing gate
rather than reimplementing it and adds C3, the catalog cross-reference. Single-bit ACCEPT/REJECT,
never a score — a score becomes the next thing to optimise (the Goodhart result the grounding
lane's own external research predicts). It fails closed on an empty walk.

```
  CONTROL golden                     want=ACCEPT got=ACCEPT OK  C1 parses; C2 schema-valid; C3 unit is in the catalog; C4 sentinel binds
  CONTROL m1-missing-sentinel        want=REJECT got=REJECT OK  C2 schema-invalid (1): 'sentinel' is a required property
  CONTROL m2-empty-evidence          want=REJECT got=REJECT OK  C2 schema-invalid (1): evidence: [] should be non-empty
  CONTROL m3-unit-id-not-in-catalog  want=REJECT got=REJECT OK  C3 unit_id 'ZZZ-9999' is not one of the 2007 catalog units
  CONTROL m4-unparseable             want=REJECT got=REJECT OK  C1 unparseable JSON: JSONDecodeError
SUCCESS:receipt-validate self-test 1 golden ACCEPTED, 4 mutants REJECTED each on its own condition
```

All 6 receipts on disk pass admission. `python command-center/receipt_validate.py` with no
arguments exits 1 — an empty walk is not a pass.

### IMP-0440 — single blob-bytes helper, and removal of the archive recipe everywhere

`command-center/receipts/IMP-0440.json` (15,418 B blob) — `python command-center/p2-wave/_build_IMP0440.py`

Premise **PARTLY REFUTED**: `tools/measure-guard/blobread.py` (8,757 B) already IS the helper and
refuses the archive route by measurement rather than by comment; its function is
`read_blob(path, rev)` rather than the row's `blob_bytes(rev, path)` — same capability, different
name and argument order. Its suite passes (8 tests). The migration itself was already performed
by `command-center/fix_blob_recipe.py`.

Three-route comparison on TWO committed files, so a single-file artefact cannot explain it:

| target | `git archive`+tar | `git cat-file -p` | `git show <rev>:<path>` | identical after LF-norm |
|---|---|---|---|---|
| `command-center/ready_units.py` | 19,927 B / **437 CRLF** | 19,490 B / 0 | 19,490 B / 0 | True |
| `tools/measure-guard/blobread.py` | 8,974 B / **217 CRLF** | 8,757 B / 0 | 8,757 B / 0 | True |

`git show <rev>:<path>` is byte-identical to `git cat-file -p`. The program floor's claim that
BOTH return CRLF is false; only `git archive` converts. That matches the correction the
orchestrator issued and `rules/common/windows-shell.md:8b`.

Census answering the row's exact question — *how many call sites and documents prescribe the wrong
recipe, and are all of them corrected?*

```
263 hits | 2 real invocations | 2 legitimate whole-tree packaging | 0 provenance prescriptions remaining
CONTROL plant-one: detector FOUND the planted recipe=True; silent after removal=True
```

The 2 survivors are `--format=tar` / `--output=` whole-tree materialisation (a cohort tarball and
a sanitized staging tree). That is the CORRECT use of `git archive`; "fixing" them would break
packaging.

**T5 is recorded as FAIL, not hidden.** The row also demands every provenance path route through
ONE helper. 37 executable files still implement their own `git cat-file -p` read. They are all
CORRECT, so this is duplication rather than a defect — but it is not what the row asks for, and
re-routing them means editing `platform/`, `tools/` and `command-center` files this lane does not
own while sibling lanes are writing the same tree. Reported, not narrowed away.

### Both units, independently re-verified from the committed blob

```
unit        blob B  CRLF  parses  declared  can-fail effective contract                        VALID  ctl  state
IMP-0433     17774     0    True         0     False command-center/schema/receipt.schema.json   YES   OK  BLOCKED
AUD-0041     77871     0    True         0      True .../audit-inventory.schema.json             YES   OK  BLOCKED
AUD-0051     29935     0    True         0      True .../audit-metric-baseline.schema.json       YES   OK  BLOCKED
AUD-0030     23565     0    True         0      True .../audit-graph.schema.json                 YES   OK  BLOCKED
AUD-0020     34300     0    True         0      True .../audit-inventory.schema.json             YES   OK  BLOCKED
CC-0002      13399     0    True         0      True command-center/schema/receipt.schema.json   YES   OK  BLOCKED
IMP-0440     15418     0    True         0      True command-center/schema/receipt.schema.json   YES   OK  BLOCKED
SUCCESS:r2-verify 7/7 committed blobs validate against a contract PROVEN able to fail, each with
its own two-sided control
```

Partition after the round: `units 2007 | delivered 1 | READY 449 | blocked 1390 | owner-gated 167`,
with `artifacts present but NOT delivered` moving 48 → **50** — exactly the two new receipts, both
honestly `BLOCKED` on the reviewer gate rather than counted as delivered.

---

## R4. Blocked units, with the precise blocker

`python command-center/p2-wave/_b1r2_blockers.py` (its own two-sided control: `validator_for:
known-good -> resolves; known-bad -> UnknownSchemaError`):

```
B1 contract unresolvable      : 0
B2 cloud-batch substrate      : 55      (NOT-CHECKED reachability, not "unavailable")
B3 off-limits input           : 0 automatic
B4 reviewer_requirement set   : 449 of 449 (100%)
substrate histogram over READY: {worktree-isolated 86, local-parallel 157, local-serialized 151, cloud-batch 55}
```

Per-unit blockers for what this round did not build:

| unit | rank | blocker |
|---|---|---|
| AUD-0001 | 4 | Declared inputs walk `~/Documents/GitHub`, the parent of a directory this program is forbidden to touch, and its `reviewer_requirement` is cross-vendor-mandatory. Unchanged from round 1; re-stated, not re-litigated. |
| IMP-0440 (T5 half) | 8 | Consolidating 37 independent `cat-file` implementations into the one helper needs edit authority over `platform/`, `tools/` and shared `command-center` files that sibling lanes are actively writing. |
| CC-0002, IMP-0440, and all 5 round-1 units | — | `reviewer.verdict=PASS` + `independent=true`. CC-0002's is structurally unsatisfiable from inside the build lane: it asks for a reviewer who writes a FIFTH mutant *the author did not anticipate*. |
| 55 cloud-batch units | — | Substrate reachability NOT-CHECKED. No probe was run, so this is "unmeasured", not "unavailable". |
| 23 meta-declaring units | — | Not blocked, but their declared contract cannot fail; delivered() now routes them through a type-appropriate fallback and the census is published in `READY-UNITS.json`. |

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

### Controls on the two new units

- **CC-0002 mutation control:** 4/4 mutants REJECTED *and* the golden ACCEPTED. The accept side is
  asserted deliberately — a validator that rejects everything is as useless as one that accepts
  everything, and only the two-sided form distinguishes them.
- **CC-0002 absent-input control:** no-argument invocation exits 1. A gate that exits 0 when given
  nothing to check is the `ci-hygiene` no-op in its purest form.
- **CC-0002 prior-art control:** the EXISTING validator was executed against all four mutants
  first; it accepted m3, so only the m3 gap was built. Skipping this control is how a duplicate
  validator gets shipped.
- **IMP-0440 plant-one control:** a wrong recipe was planted inside the scanned tree, found by the
  census, removed, and the census re-run silent. A grep returning 0 without this is
  indistinguishable from a broken pattern — and it caught two of my own detector failures.
- **IMP-0440 byte-compare control:** the three-route comparison must show a DIFFERENCE
  (archive != blob) *and* agreement between the two blob routes. All-equal would be consistent
  with a broken reader.

### TWO DETECTOR FAILURES OF MY OWN THIS ROUND — disclosed, not dropped

1. **The census counted mentions as uses.** First version: any non-comment line matching
   `git archive` was an invocation. It reported ~19 "remaining prescriptions", all prose inside
   JSON strings (`"evidence": "The grounding pack states: \"On Windows, git archive ...\""`).
   That is the exact use-vs-mention failure this program has already paid for four times, and I
   reproduced it while writing the unit whose whole job is that distinction. Replaced with a
   per-file-kind classifier: Python by **AST** (a string only counts when it reaches a subprocess
   argv — `blobread.py` names the recipe eleven times precisely because it refuses it), shell/CI
   by non-comment line, markdown by fenced-code-block membership, data files excluded with the
   reason stated rather than silently dropped.
2. **The fixed classifier still counted 3.** All three were lines PRESCRIBING the correct recipe
   while naming the wrong one in a TRAILING comment: `git show <final-sha>:<path>   # NOT git
   archive`. My comment rule only looked at the start of a line. Fixed by stripping trailing
   comments before matching and treating an explicit negation before the token as a mention.

Both survived only because the plant-one control existed. Neither would have been caught by a
green number. My round-1 report already disclosed two detector failures; that is four in two
rounds, which is the honest prior for anything here that is not behind a two-sided control.

3. **A third, smaller one:** the first IMP-0440 run measured the three-route comparison on
   `command-center/receipt_validate.py`, which was not yet committed, so all three routes returned
   0 bytes and "identical after LF-normalisation" read False. An all-zero comparison is a
   self-contradicting output, not a finding. Retargeted to a committed file and the builder now
   returns its real `rc` instead of "did the file get written".

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
- **PARTIAL — IMP-0440 T5.** 37 executable files hold their own correct `cat-file` read; the
  single-helper consolidation the row demands is NOT done, and the receipt records that test as
  FAIL. Settling action: a lane with edit authority over `platform/`, `tools/` and shared
  `command-center` files re-routes them through `tools/measure-guard/blobread.read_blob`.
- **PARTIAL — the IMP-0440 classifier.** The plant-one control proves the census detects the
  canonical wrong recipe; it does not prove it detects every phrasing. Settling experiment named
  in the receipt: plant a PowerShell `git -C $x archive`, a Makefile rule and a YAML `run:` step
  and require all three to be found.
- **NOT CLAIMED:** that any of these seven artifacts is CORRECT. No independent reviewer ran. What
  is claimed and proven is narrower: each is non-empty, parses, carries 0 CRLF in the stored blob,
  validates against a contract measured able to reject garbage, and every headline number in it
  is behind a control shown to fire on a known-broken state. Four of my own detectors were wrong
  on first run across two rounds and only the controls caught them.
- **Environment notice, surfaced not actioned:** two report-only `POTENTIAL-CREDENTIAL` sweep
  notices fired while writing `_r2_verify_committed.py` and editing `_b1r2_verify_committed.py`
  (ids `sha256:0f667e93eafb`, `sha256:9b69183fa43b`). Both files contain only sha256 hex literals
  and a 2,000-character `"x"` garbage probe; no credential was read, printed or modified. Reported
  for the owner per AGENTS.md §9; no agent action clears these.