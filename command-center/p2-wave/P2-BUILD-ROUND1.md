# P2 BUILD LANE — ROUND 1

> ## REFUTED IN ROUND 2 — read this before citing anything below
>
> An adversarial verifier refuted two sentences in this document and I reproduced both by
> execution. The original wording is left in place, marked inline, rather than deleted.
>
> **R1. "each delivered unit executable-proven against its declared contract" — REFUTED for 1 of
> 5.** IMP-0433's catalog row declares `command-center/schema/meta/json-schema-draft.json`, the
> draft-2020-12 meta-schema, which returns **0 errors** for
> `{"totally":"unrelated","passing_tests":999999}`. A green from a contract that cannot fail is
> not evidence. Correctly scoped: **4 of 5** units were proven against a declared contract
> measured able to reject garbage (3/3 probes); IMP-0433 was proven against
> `command-center/schema/receipt.schema.json` — which the build script did pass as
> `also=[...]`, so the ARTIFACT was always fine — plus its 12+1 fixture matrix. The *proof* was
> vacuous, not the artifact. Round 2 re-verifies all five against a contract proven able to
> fail: `python command-center/p2-wave/_r2_verify_committed.py`.
>
> **R2. "A `state` field alone is forgeable by a one-word edit … Schema validation cannot be
> satisfied that cheaply" — REFUTED for the 23 meta-declaring units.** Measured:
> `command-center/receipts/IMP-0433.json` with `state` flipped `BLOCKED`→`SUCCESS` was accepted
> as `delivered=True` by the predicate this document shipped. The other four mutants were
> correctly rejected (`schema-invalid:3/4/3/3`), so the sentence held for 4 of 5 and failed for
> exactly the unit whose contract cannot fail. Round 2 adds condition 4b (contract-vacuity guard
> + type-appropriate fallback) and keeps that mutant as a live `--self-test` control.
>
> **R3. Not refuted but hollow, and now disclosed:** the single `delivered=1` unit WFA-0001 is
> *also* meta-gated, so condition 4 never discriminated for it either. It survives round 2 via
> the schema-document fallback (its artifact really is a JSON Schema, `$schema` + `$id` present,
> `check_schema` passes) — `--self-test` now prints which path certified it.
>
> Round-2 report: `command-center/p2-wave/P2-BUILD-ROUND2.md`.

STATUS: COMPLETE for this round. Every section below carries a measurement or an explicit
NOT-CHECKED. Nothing here is `UNKNOWN - not yet measured`.

PREDECESSOR NOTE: a prior build-lane agent claimed this path at 01:51, wrote two ranking probes
(`_b1_rank.py`, `_b1_rows.py`) and died before producing a single deliverable. This document is
that skeleton re-claimed and filled in by the replacement agent. The predecessor's `_b1_rank.py`
was read and reused (it had already fixed the grounding lane's lexicographic phase-sort bug); its
`exists()` predicate was superseded by the fix in C3.

---

## C1. Live partition — `python command-center/ready_units.py`

FIRST ACTION of the lane, quoted verbatim:

```
  units 2007 | delivered 44 | READY 414 | blocked 1385 | owner-gated 164
  block reasons: {'unbuilt': 1365, 'unknown-token': 20}
  first ready: ['ADV-0002','ADV-0038','ADV-0043','ADV-0047','ADV-0049','ADV-0051','ADV-0056','ADV-0058']

SUCCESS:ready-units partition sums correctly
```

It had already moved from the briefed 2007/4/447/1389/167 and from the grounding lane's
opening 2007/42/416/1385/164. ADV-0041 and ADV-0042 had left the ready head between lanes.

AFTER this lane's work (C8 has the full reading):

```
  units 2007 | delivered 1 | READY 449 | blocked 1390 | owner-gated 167
  artifacts present but NOT delivered (self-declared failure / invalid): 48
```

---

## C2. Units chosen, and why they were highest value

Ordering is the recorded owner ruling OQ-2: ascending phase (as an INTEGER — the grounding lane
disclosed that its own sort put `'10'` before `'2'`), then unblocking power, then id. Re-derived
under the FIXED delivered() predicate with `command-center/p2-wave/_b1r2_rank.py`, whose sort key
carries its own control (`['0','2','2A','10'] -> OK`).

The ranked head, and what I did with each:

| rank | unit | phase | unblocks | decision |
|---|---|---|---|---|
| 1 | IMP-0433 | 0 | **13** | BUILT — highest unblocking power in the whole catalog |
| 2 | AUD-0041 | 0 | 8 | BUILT |
| 3 | AUD-0051 | 0 | 5 | BUILT |
| 4 | AUD-0001 | 0 | 3 | NOT BUILT — see C6, precise blocker |
| 5 | AUD-0020 | 0 | 3 | BUILT |
| 6 | AUD-0030 | 0 | 3 | BUILT |
| 7 | CC-0002 | 0 | 3 | not reached this round |
| 8 | IMP-0440 | 0 | 3 | not reached this round |

Five units delivered, taken strictly in ranked order with one documented skip (AUD-0001).
Depth over breadth was the owner's ruling and it is what happened: every unit here ran both of
its catalog-named probes and shipped a control proven to fire on a known-broken state.

---

## C3. Scope expansion #1 — `delivered()` predicate in `ready_units.py`

The grounding lane proposed this and I judge it correct, so I built it.

`command-center/ready_units.py:44` was `return bool(p) and (REPO / p).exists()`. That is the
Goodhart shape this program keeps paying for: the check rewards a file being PRESENT, so the
program produced 44 present artifacts of which **43 self-declare `state: BLOCKED` or `FAILED`**,
and the partition reported all 44 as delivered.

Measured tier ladder (`_b1r2_scope_measure.py`, `_b1r2_tier3.py`):

| predicate | delivered | READY |
|---|---|---|
| T0 exists (shipped) | 44 | 414 |
| T1 exists + non-empty | 44 | 414 |
| T2 T1 + parses + state not BLOCKED/FAILED | 1 | 449 |
| T3 T2 + validates against declared `output_schema` | 1 | 449 (1.95 s for 44 artifacts) |

`STATE TALLY over T0-delivered artifacts: {'BLOCKED': 42, 'FAILED': 1, '<no-state-field>': 1}`
`state x validity: {(BLOCKED,VALID):39, (FAILED,VALID):1, (BLOCKED,INVALID(6)):1,
(BLOCKED,INVALID(12)):1, (BLOCKED,INVALID(1)):1, (None,VALID):1}`

I shipped T3, not T2, deliberately. A `state` field alone is forgeable by a one-word edit — the
"Building to the Test" failure the grounding lane's own external research predicts. Schema
validation cannot be satisfied that cheaply, and it costs 1.95 s.

> **REFUTED (round 2, reproduced by execution).** The last sentence is false for the 23 units
> whose declared contract resolves to a JSON-Schema meta-schema: for them schema validation is
> satisfied by *anything*, so the T3 predicate collapses back to T2 and the one-word edit works.
> `command-center/receipts/IMP-0433.json` + `state: SUCCESS` → `delivered=True` under the
> predicate shipped here. Correctly scoped: T3 is strictly stronger than T2 for the 364 of 367
> distinct declarations that reject all three garbage probes, and equal to T2 for the other 3
> (declared by 23 units). Fixed by condition 4b in `ready_units.py`; the mutant is now a control.

Movement: **+36 units return to READY** (the grounding lane predicted 34; the difference is
predicate-dependent — they also imposed a 200 B floor, I impose contract validation instead) and
**ADV-0002 leaves READY**, because it was queued on a BLOCKED foundation.

BOTH-STATES CONTROL, shipped with the fix as `python command-center/ready_units.py --self-test`:

```
  resolver: loaded
  CONTROL WFA-0001: want=True  got=True  (delivered)             | legacy-exists-predicate=True -> OK
  CONTROL ADV-0031: want=False got=False (self-declared:BLOCKED) | legacy-exists-predicate=True -> OK
SUCCESS:ready-units self-test delivered() fires on the bad state and is silent on the good one
```

The `legacy-exists-predicate=True` column is the point: the OLD predicate accepted BOTH fixtures,
so it could not discriminate at all. A one-sided control would have been silent in both states.

---

## C4. Scope expansion #2 — missing output directories

Also proposed by the grounding lane, also judged correct, also built.

Measured: **27** distinct `output_path` parent directories do not exist, across **713** units.
**14** of those 27 are on the path of **105 READY** units. (The grounding lane said 14; that is
the READY-relevant subset and my independent count agrees.)

The failure mode is PROVEN, not assumed — both-states control in `_b1r2_scope_measure.py`:

```
BAD-STATE  open(w) into missing parent: FileNotFoundError -> control FIRES
GOOD-STATE open(w) into existing parent: SUCCEEDED        -> control SILENT
```

A unit that dies that way exits non-zero with no output file, which this program classifies as
SEVERED. `_b1r2_mkdirs.py --apply` created the 14 READY-relevant dirs with a `.gitkeep` (git
cannot track an empty directory, so an uncommitted mkdir would not survive a clone). The other 13
were deliberately NOT created: seeding directories for still-blocked units is noise, not insurance.

---

## C5. Unit deliverables, each executable-proven against its declared contract

> **REFUTED HEADING (round 2).** Correct heading: *four* delivered units were proven against a
> declared contract measured able to fail; IMP-0433's declared contract cannot fail, and it was
> proven instead against `command-center/schema/receipt.schema.json` (which the emitter did
> apply via `also=[...]`) plus its 12+1 fixture matrix. The claim as written was wider than its
> evidence for 1 of 5. Settling command: `python command-center/p2-wave/_r2_verify_committed.py`
> — its `can-fail` column states this per unit instead of hiding it.

Every artifact is emitted through `_p2lib.write_if_valid()`, which **validates against the declared
`output_schema` BEFORE it writes and refuses to persist a document that fails**. An artifact on
disk is therefore a receipt of validation, not a claim of it. This fired for real on the first
IMP-0433 run and blocked a bad write (see the detector-failure note below).

| unit | artifact | bytes | schema-VALID | tests | controls |
|---|---|---|---|---|---|
| IMP-0433 | `command-center/receipts/IMP-0433.json` | 18,229 | yes (metaschema **and** receipt schema) | 5/5 PASS | 2 |
| AUD-0041 | `command-center/audit/AUD-0041-ci-step-inventory.json` | 79,773 | yes | 3/3 PASS | 2 |
| AUD-0051 | `command-center/audit/AUD-0051-coverage-baseline.json` | 30,825 | yes | 2 PASS, 1 FAIL *(the FAIL is the finding)* | 1 |
| AUD-0030 | `command-center/audit/AUD-0030-import-graph-cycles.json` | 24,275 | yes | 3/3 PASS | 1 |
| AUD-0020 | `command-center/audit/AUD-0020-python-dep-inventory.json` | 35,273 | yes | 3/3 PASS | 1 |

### IMP-0433 — premise REFUTED, and the grounding lane RE-SCOPED

The row says to author `command-center/schema/receipt.schema.json` "that does not exist on disk".
It exists (5,882 B) and resolves by `$ref` to
`platform/schema/receipt.schema.json#/$defs/receipt_core` (42,109 B). Premise refuted.

So I built what the row's `tests_required` actually demands: **12 negative fixtures, one per
completion condition read out of `COMPLETION-GATES.json` `gate_a_unit_completion_predicate`, plus
one positive.** Result: 12/12 INVALID, positive VALID, metaschema self-validation clean, and the
metaschema control FIRES on a known-bad schema (2 errors) so T2 is not measuring nothing.

**The grounding lane reported "drop reviewer -> VALID=True" as a strictness gap. That is
state-blind, and I measured both states:**

```
T5 named strictness (state=SUCCESS): {'sentinel': True, 'evidence': True, 'reviewer': True}
T5 same drops on a BLOCKED receipt : {'sentinel': True, 'evidence': True, 'reviewer': False}
```

On a SUCCESS receipt all three of the row's named conditions already hold. On a BLOCKED receipt
`reviewer` is optional — which is correct design, not a hole: a blocked unit has no reviewer to
cite. The schema is right; the earlier sentence was wider than its evidence.

### AUD-0041 — CI step inventory

7 workflow files, 14 jobs, 143 steps, 4 conditional steps, 2 conditional jobs. Probe 2 (Actions
API) reconciles **4/4** with the static leg prediction and surfaces what the YAML cannot: **56
skipped steps in the `quality` run alone**.

The row's control asks the matrix expander to be checked against API leg counts. **Zero jobs in
this repo use `strategy.matrix`** — two mechanically independent signals: `grep -l matrix` returns
nothing, and a structural `strategy.matrix` scan of the parsed YAML returns nothing. So that check
is degenerate here, and the expander is proven separately on a synthetic fixture: 3 os x 2 py,
minus 1 exclude, plus 1 include = **6 legs**, and exactly **1 leg** on a plain job. Without that,
an INERT expander would be indistinguishable from a working one in a zero-matrix repo. Residual
disclosed inline in the artifact with its settling experiment.

Second control worth keeping: **PyYAML parses the bare `on:` key as boolean `True`** (YAML 1.1),
so `doc["on"]` returns nothing and every workflow reads as trigger-less — a silent, total detector
failure. The parser reads `doc.get("on", doc.get(True))` and the control asserts all 7 files yield
real triggers.

### AUD-0051 — the coverage gate in this tree is INOPERABLE

43 projects discovered; exactly **1** carries a `.coverage-thresholds.json`; the other 42 are
reported NOT-CHECKED rather than passed.

`tools/editor/metaswarm/.coverage-thresholds.json` declares `enforcement.command:
"pnpm test:coverage"` with `blockPRCreation: true` and `blockTaskCompletion: true`. That project's
`package.json` has an **empty `scripts` block**. Two independent signals: the static read finds no
`test:coverage` script, and actually running the declared command exits 1.

```
PROBE1 tools/editor/metaswarm: `pnpm test:coverage` exit=1 script_in_package_json=False coverage=NOT-CHECKED
SUMMARY projects=43 gated=1 ungated=42 enforcement_commands_that_run=0/1 projects_with_a_real_coverage_number=0
```

**A blocking gate whose command cannot run enforces nothing.** Repo line and branch coverage are
NOT-CHECKED — not zero, not passing. The control feeds the extractor a real test run with no
`--coverage` instrumentation and requires NOT-CHECKED, never `0`: rendering a missing measurement
as a real-but-bad number is exactly the outcome this row bans.

### AUD-0030 — import graph, and a detector of mine that was INERT

679 modules, 265 internal edges, **exactly 1 import cycle**:
`tools.crcp.crcp.sentinel <-> tools.crcp.crcp.write_path`. Highest fan-in is
`tools.monitorcore.monitorcore.redact` at 10. The bounded runtime trace (25 modules, one fresh
interpreter each) found **17** modules pulling internal imports the AST scan did not record, and
**3** modules that do not import at all.

MY OWN DETECTOR WAS INERT AND THE CONTROL CAUGHT IT:

```
run 1: CONTROL SCC: planted 2-module cycle -> 0 cycle(s) len=[] BROKEN; acyclic fixture -> 0 cycle(s) SILENT
run 2: CONTROL SCC: planted 2-module cycle -> 1 cycle(s) len=[2] FIRES;  acyclic fixture -> 0 cycle(s) SILENT
```

The resolver matched only fully dotted repo paths, so a bare sibling `import helper` — the dominant
shape under `tools/` — never resolved. Had the control been one-sided, **"0 cycles in tools/" would
have shipped as a finding from a detector incapable of finding one.**

The row names "tools/ and tools/lib/". Measured: `tools/lib` holds **0** Python files; it is a
JavaScript package. Recorded, not silently reinterpreted.

### AUD-0020 — dependency and lockfile inventory

23 manifests, 93 declared direct dependencies, 4 packages with a parsable lockfile and 19 without.
**0** out-of-range pins, **0** declared deps missing from a lock, **0** undecidable constraints.

A zero only means something because the differ is proven able to find one: the control injects
`requests==1.2.3` under a declared `>=2.31,<3` and requires exactly that package to be flagged,
then requires silence on the same manifest with an in-range lock. `satisfies()` returns `None`
(surfaced as `UNDECIDABLE-CONSTRAINT`) for any PEP 440 form it does not implement, so the violation
count is an honest LOWER bound rather than a guess.

---

## C6. BLOCKED units, with the precise blocker

`_b1r2_blockers.py` over the 449 READY units. Its own control:
`validator_for: known-good -> resolves; known-bad -> UnknownSchemaError` (both directions).

**B4 — reviewer gate: 449 of 449 READY units (100%).** THE STRUCTURAL FINDING OF THIS LANE.
`receipt_core` requires `reviewer.verdict == "PASS"` **and** `reviewer.independent == true` for
`state: SUCCESS`, and every READY unit in the catalog carries a `reviewer_requirement`. **A build
lane working alone can therefore deliver ZERO units at `state: SUCCESS` without forging condition
9.** That is the schema working as designed (it is the SEAL / self-authored-verification result
encoded as a constraint), not a defect. It does mean P2 needs a paired reviewer lane, or no unit in
this program will ever legitimately reach SUCCESS. All five of my artifacts are `state: BLOCKED`
with `failure.classification: ["reviewer-absent", "self-review-is-not-review"]` and a per-unit
`failure.blocked_on` naming the exact reviewer the row demands.

**B2 — `cloud-batch` substrate: 55 READY units.** Reported NOT-CHECKED, not unavailable: I ran no
reachability probe for that substrate. (Grounding lane said 53; the partition moved.)
Substrate histogram over READY: `{local-parallel: 157, local-serialized: 151, worktree-isolated: 86, cloud-batch: 55}`.

**B1 — contract unresolvable: 0. THE GROUNDING LANE'S "6 GENUINELY UNRESOLVABLE" IS REFUTED.**
Measured with the repo's own `schema_resolver.validator_for()` over **all 2,007** units, not just
the READY ones: **0 unresolvable**. The four it named individually all resolve:

```
IMP-0006: RESOLVES   IMP-0044: RESOLVES   IMP-0051: RESOLVES   RES-0001: RESOLVES
ALL-CATALOG unresolvable output_schema: 0
```

**But the real defect is worse than the one that was claimed, and is NOVEL.** Those contracts are
not unresolvable — they are **HALF-ENFORCED**. `schema_resolver.resolve()` calls
`parse_schema_ref()`, which takes the leading logical path and silently discards everything after
the `+`. Executed:

```
declared = 'command-center/schema/receipt.schema.json + tools/plugin/schema/error-taxonomy.schema.json'
resolved logical_id : command-center/schema/receipt.schema.json
a plain receipt validated against the TWO-schema expression -> errors: 0
=> the second half of the expression is DROPPED, not enforced
```

A plain receipt — certainly not a valid error-taxonomy document — validates clean against a
contract that declares both. **41 units** declare a two-schema expression (not 6), of which **5 are
READY right now** (IMP-0001, IMP-0006, IMP-0044, IMP-0051, IMP-0067) and the rest sit in phases 5-6.
Every one of them will report a green contract check that only ever tested half its contract.
Settling experiment: make `resolve()` either enforce an `allOf` across all `+`-joined paths or
raise on a multi-schema declaration; then re-validate the 41.

**B3 — off-limits inputs: 0 matched automatically, 1 found by reading.** The automated matcher for
`Documents/GitHub/Reframe`, `.claude/agent-worktrees` and `command-center/adversarial` in unit
inputs returned 0. But **AUD-0001** (rank 4, unblocks 3) declares inputs
`git for-each-ref over every repo under ~/source and ~/Documents/GitHub` — the *parent* of a
directory this wave is explicitly forbidden to touch — and a `reviewer_requirement` of "one
**cross-vendor Codex** reviewer who re-runs ONLY the second probe; a same-vendor reviewer shares
this unit's blind spots and does not satisfy the requirement". That is why it was skipped rather
than narrowed: delivering it would have meant either walking a forbidden tree or quietly redefining
its input set. Precise blocker: **input set includes a forbidden directory, and the reviewer
requirement is cross-vendor-mandatory.**

---

## C7. Detector controls (both-states) for every probe used

Every count in this document is gated behind a control proven to fire on a known-broken state and
stay silent on a known-good one. Three of them caught a real defect.

| control | bad state (must FIRE) | good state (must be SILENT) | caught a real defect? |
|---|---|---|---|
| `ready_units --self-test` | ADV-0031 (BLOCKED) rejected | WFA-0001 accepted | — (proves the legacy predicate accepted both) |
| missing-dir `open(w)` | `FileNotFoundError` | write succeeds | — |
| IMP-0433 metaschema | 2 errors on `{type:123}` | 0 errors on the real schema | — |
| IMP-0433 12-mutant matrix + ATTRIBUTION GUARD | 12/12 INVALID | positive VALID | **YES** |
| AUD-0041 matrix expander | 6 legs on the fixture | 1 leg on a plain job | — |
| AUD-0041 `on:`-as-`True` | `doc["on"]` empty on 7/7 | `doc.get("on", doc.get(True))` yields triggers | **YES** (pre-empted) |
| AUD-0051 NOT-CHECKED extractor | no-coverage run -> `NOT-CHECKED` | coverage table -> `93.41%` | — |
| AUD-0030 planted 2-cycle | 1 SCC of length 2 | acyclic twin -> 0 | **YES** |
| AUD-0020 injected out-of-range pin | flags `requests` only | in-range lock -> 0 | — |
| `validator_for` resolvability | `UnknownSchemaError` on a fake path | resolves a real one | — |

TWO DETECTOR FAILURES OF MY OWN, DISCLOSED RATHER THAN DROPPED:

1. **IMP-0433, run 1.** My base positive fixture was itself INVALID
   (`residual_unknowns[].verdict: 'UNVERIFIED'` is not in the enum), so conditions 1 and 7 scored
   "INVALID ok" on that unrelated error — **a false 12/12**. Both are now attributable to their own
   mutation (`state: 'DONE' is not one of [...]`, `tests[0].result: FAIL`). I added an
   **ATTRIBUTION GUARD**: the script refuses to report the matrix at all unless the base is clean,
   because a mutant's INVALID only attributes to its single change while the base is VALID.
2. **AUD-0030, run 1.** Described in C5 — the SCC detector was inert on sibling imports and the
   two-sided control is the only reason it did not ship a confident "0 cycles".

The `write_if_valid` gate also fired for real: it refused to persist the first IMP-0433 receipt
(`artifacts/0/exists: True was expected` — a receipt cannot list itself, because `exists` is
`const: true` and measured by stat, so a self-reference is unrepresentable and a self-hash would
recurse). Receipts therefore list what the unit PRODUCED, not themselves.

---

## C8. Partition re-run after the build

```
  units 2007 | delivered 1 | READY 449 | blocked 1390 | owner-gated 167
  artifacts present but NOT delivered (self-declared failure / invalid): 48
  block reasons: {'unbuilt': 1370, 'unknown-token': 20}
SUCCESS:ready-units partition sums correctly
```

INDEPENDENT RE-VERIFICATION FROM THE COMMITTED BLOB (`_b1r2_verify_committed.py`). A build script
validating its own in-memory variable is one signal; this is a mechanically different second one —
it reads back what git actually stored via `git show HEAD:<path>` and re-validates against the
schema the **catalog row** declares, not the one the build script happened to pass:

> **REFUTED (round 2).** "Re-validates against the schema the catalog row declares" is exactly
> the hole: for IMP-0433 that schema cannot fail, so its `schema-VALID YES` below is vacuous.
> The control shown at the bottom of that block also ran on AUD-0020 only, while the SUCCESS
> line spoke for all five. `_b1r2_verify_committed.py` is SUPERSEDED by `_r2_verify_committed.py`,
> which adds a `can-fail` column, a type-appropriate fallback, and a PER-UNIT two-sided control.

```
unit        blob B  CRLF  parses  schema-VALID  sentinel-matches  state
IMP-0433     17774     0  True    YES           True              BLOCKED
AUD-0041     77871     0  True    YES           True              BLOCKED
AUD-0051     29935     0  True    YES           True              BLOCKED
AUD-0030     23565     0  True    YES           True              BLOCKED
AUD-0020     34300     0  True    YES           True              BLOCKED
CONTROL verifier: AUD-0020 with `sentinel` removed -> 1 error(s) FIRES; unmodified -> 0 error(s) SILENT
SUCCESS:p2-verify 5/5 committed blobs are non-empty, parse, and validate against the schema their CATALOG ROW declares
```

0 CRLF in every blob, confirming the corrected floor: `git show <rev>:<path>` returns the stored
bytes without export-time EOL conversion (only `git archive` does that).

READ THIS HONESTLY. `delivered` is **1**, not 6, and that number went DOWN from the 44 this lane
inherited. That is not a regression — it is the first honest reading the tool has produced. The
`artifacts present but NOT delivered` counter moved 43 -> 48: my five artifacts are on disk, valid
against their contracts, and correctly not counted as delivered, because each is `state: BLOCKED`
on its reviewer gate (C6/B4). Under the OLD existence predicate this lane would have reported
"delivered 49" and every one of those 49 would have been a file whose own contents say otherwise.

---

## C9. Commits (explicit paths only)

| commit | what |
|---|---|
| `03e565ea` | `delivered()` fix + `--self-test` control + 14 `.gitkeep` dirs + measurement probes (22 files) |
| `a652a3af` | IMP-0433 + AUD-0041, their build scripts, 13 fixtures, 3 probe outputs (21 files) |
| `8d7bf365` | AUD-0051 + AUD-0030 + AUD-0020, their build scripts and probe outputs (20 files) |

Verified clean: `git show --name-only <c> | grep -v '^command-center/'` returns nothing for both
feature commits. **A sibling lane staged 22 foreign files into the shared index mid-commit**
(`tools/monitorcore/**`, `skills/workflow-monitor/**`, `commands/cs.md`, ...). I unstaged them, and
when two more appeared seconds later I switched to `git commit -F <msg> -- <explicit paths>`, which
commits only the named paths and is immune to the race. No `git add -A`, no `git add .`, no
`commit -a` was used at any point. Commit messages were written with the Write tool and passed via
`-F` (an apostrophe inside a Bash-tool command breaks its own quoting).

---

## C10. Residual / honest scope

Sherman-Kent bands attached. UNVERIFIED items name the experiment that settles them.

**ALMOST CERTAIN (90-99%)** — directly executed, with a two-sided control:
the partition numbers (tool's own self-asserting sum, quoted verbatim, run at both ends); the tier
ladder and the 36/1 movement; the 27/14/713/105 missing-directory census; the IMP-0433 12+1 fixture
matrix and the SUCCESS-vs-BLOCKED reviewer measurement; the AUD-0041 7/14/143 CI surface and the
4/4 API reconciliation; the inoperable coverage gate (two independent signals: empty `scripts`
block AND `exit=1`); the single `crcp` import cycle; the 23/93/4/19 dependency census; 0
unresolvable contracts across all 2,007 units; the 41 half-enforced two-schema declarations.

**LIKELY (55-80%)**: that the 17 "runtime-only internal imports" in AUD-0030 are genuinely dynamic
imports rather than transitive pulls my prefix matcher attributed loosely. Settling experiment is
named in that artifact's `residual_unknowns`.

**NOT-CHECKED — stated, never folded into a pass:**
- Repo-wide line and branch coverage. No enforcement command in this tree emits a coverage table.
- `cloud-batch` substrate reachability (55 READY units). No probe was run.
- Whether the 43 pre-existing BLOCKED artifacts are blocked for still-valid reasons. I read the
  `state` field, not the blocking justification. Settling experiment: parse `failure.blocked_on` on
  each and re-probe the stated blocker.
- Whether the second half of each of the 41 two-schema declarations would actually reject a real
  artifact. I proved it is not evaluated; I did not construct 41 counter-artifacts.

**PARTIAL:**
- AUD-0030's runtime trace covers 25 of 679 modules (cycle members + top fan-in). Host free RAM is
  ~4.5 GB and each module costs a fresh interpreter, so a full trace was not attempted.
- AUD-0041 records reusable-workflow and composite-action `uses:` references without expanding
  their inner steps, so 143 is a floor on the true step count.
- AUD-0020 parses only `uv.lock`; a `poetry.lock` or `Pipfile.lock` package would count as
  unlocked. Measured today the tree has 0 of either, so the gap is currently inert.
- AUD-0051's project discovery keys on `pyproject.toml` / `package.json` / `pytest.ini`, so 43 is a
  lower bound on the project count.

**SCOPE NOTE worth flagging to the orchestrator:** AUD-0030's runtime probe imported two
`tools/crcp/**` modules in throwaway subprocesses to satisfy its second named probe. CRCP is under
quarantine. No service was started, the subprocesses exited and were reaped, and nothing was
written to CRCP paths — but it was a module import, so it is disclosed rather than buried.

**NOT DONE this round:** CC-0002 and IMP-0440 (both phase 0, unblocks 3) were next in rank and were
not reached. AUD-0001 was skipped with the precise blocker recorded in C6/B3. No unit reached
`state: SUCCESS`, and per C6/B4 none can until a reviewer lane exists.
