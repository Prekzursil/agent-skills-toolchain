# P2 BUILD — ROUND 3 (re-entry after a confirmed refutation)

STATUS: IN PROGRESS. Sections marked `UNKNOWN - not yet measured` are exactly that.
If a section still reads `UNKNOWN - not yet measured`, the unit died before measuring it and no
verdict there may be cited.

COVERAGE:
- C1 live partition re-run + quoted .................. MEASURED
- C2 round-2 confirmed defects enumerated ............ MEASURED
- C3 D1 (one-key `$schema` bypass) fixed + controlled  MEASURED
- C4 D2 (non-.json suffix bypass) fixed + controlled . MEASURED
- C5 overclaim sentences corrected, refutation recorded MEASURED (code docstrings) / IN PROGRESS (reports)
- C6 new units delivered this round .................. UNKNOWN - not yet measured
- C7 blocked units with precise blockers ............. UNKNOWN - not yet measured
- C8 independent blob re-verification ................ UNKNOWN - not yet measured
- C9 commits (explicit paths, no foreign paths) ...... UNKNOWN - not yet measured
- C10 residual / NOT-CHECKED ......................... UNKNOWN - not yet measured

---

## C1 LIVE PARTITION — first action of the lane, quoted verbatim

```
$ python command-center/ready_units.py
  units 2007 | delivered 1 | READY 449 | blocked 1390 | owner-gated 167
  artifacts present but NOT delivered (self-declared failure / invalid): 50
  block reasons: {'unbuilt': 1370, 'unknown-token': 20}
  contract-vacuity: 3 declarations cannot fail, declared by 23 units (checker=live)
  first ready: ['ADV-0001', 'ADV-0003', 'ADV-0004', 'ADV-0005', 'ADV-0006', 'ADV-0007', 'ADV-0008', 'ADV-0009']

SUCCESS:ready-units partition sums correctly
```

Movement since round 2 ended: `artifacts present but NOT delivered` 48 -> 50 and the READY head is
now all `ADV-*`, which was not true an hour ago. The partition moves under this lane continuously;
any unit list older than minutes is stale.

**The whole READY head is out of scope for this wave.** `ADV-*` writes into
`command-center/adversarial/`, which the wave floor forbids this lane from touching. That is a
scope blocker, not a delivery: recorded in C7, not silently skipped.

## C2 THE ROUND-2 DEFECTS, CONFIRMED BY EXECUTION (the verifier's, re-run by me)

The adversarial verifier left six re-runnable probes in `command-center/p2-wave/_av2_tmp/`. I ran
them rather than reading its summary. Two confirmed defects, both in code I shipped in round 2.

**D1 — the vacuous-contract fallback was a ONE-KEY bypass.** `looks_like_schema_doc` gated on the
presence of a `$schema`/`$id` key plus `check_schema`. `check_schema` accepts unknown keywords, so
adding one key to arbitrary garbage produced a "usable schema":

```
$ python command-center/p2-wave/_av2_tmp/probe_bypass.py        # BEFORE my fix
  CONTROL garbage, NO $schema     bytes=  69  delivered=False (contract-vacuous:no-type-appropriate-fallback)
  garbage + ONE key ($schema)     bytes= 128  delivered=True  (delivered(schema-document fallback...))
  2000-x blob + ONE key           bytes=2091  delivered=True  (delivered(schema-document fallback...))
  bare {$schema} only, 42 bytes   bytes=  59  delivered=True  (delivered(schema-document fallback...))
  BYPASS_PROVEN = True
```

23 units declare a contract that cannot fail, so 23 units were one key away from a false green.

**D1b — the control I shipped with D1 was silent in both states.** Its docstring claimed
two-sidedness against `{"type": 123, "required": "not-an-array"}`. That document carries neither
key, so the KEY check rejected it and `check_schema` was never exercised by the control at all.
This is the same defect shape the program keeps hitting: a control that never reaches the stage it
claims to test.

**D2 — every non-`.json` artifact skipped the gate entirely.** `artifact_delivered` returned
`(True, "non-json-present")` on suffix alone:

```
$ python command-center/p2-wave/_av2_tmp/probe_nonjson.py        # BEFORE my fix
  NON-.json units (predicate degenerates to exists+size): 120
  2000-x .md file -> delivered=True (non-json-present)
  CONTROL same 2000 bytes named .json -> delivered=False (unparseable:JSONDecodeError)
  SUFFIX_BYPASS_PROVEN = True
```

Scope of the hole, measured not estimated: 120 units, all `.md`, **0 of whose artifacts exist
today** — so D2 was latent, never exploited. Correctly scoped: no delivered count was ever wrong
because of D2; 120 future units would have been.

## C3 FIX FOR D1 — the artifact-as-contract must itself discriminate

`schema_doc_verdict(doc, resolver)` replaces the boolean `looks_like_schema_doc` (the old name is
kept as a thin wrapper so the verifier's probes still run unchanged). Three stages, and the
returned STAGE is asserted by the controls so a document rejected by the wrong stage still fails:

1. `$schema`/`$id` present (`not-a-schema-document`),
2. `check_schema` (`schema-document-invalid:*`),
3. **new**: the document, used AS a contract, must reject all three garbage probes
   (`schema-document-vacuous`).

**Stronger than the verifier's own candidate remedy, and here is the difference.** Its
`probe_fixviable.py` treated a raise as a refusal, which keeps WFA-0001 delivered — but WFA-0001
raises `_WrappedReferencingError` on every probe because its `$ref` is unresolvable in a bare
validator, so it would have passed *for the wrong reason*. `platform/lib/schema_resolver`
exposes `build_registry()`; attaching it makes the same pack discriminate on merit
(`command-center/p2-wave/_r3_probe_registry.py`):

```
  WFA-0001 real pack     registry=False  errors-per-garbage-probe = ['RAISE','RAISE','RAISE']
  WFA-0001 real pack     registry=True   errors-per-garbage-probe = ['12', '12', '11']
  garbage + $schema      registry=True   errors-per-garbage-probe = ['0', '0', '0']
  bare {$schema}         registry=True   errors-per-garbage-probe = ['0', '0', '0']
  2000-x blob + $schema  registry=True   errors-per-garbage-probe = ['0', '0', '0']
```

Refusal-by-raise is still accepted (the module's existing convention) but is now **disclosed in
the reason string** — `schema-document-discriminates(refused-by-raise:<Error>)` — because an
unresolvable `$ref` refuses a good instance too. WFA-0001 no longer needs that branch.

## C4 FIX FOR D2 — a text artifact is gated on what a text artifact can bear

`text_artifact_verdict(unit, text)`. What it can and cannot do, stated where it is used:

- it **cannot** contract-prove the artifact. All 6 contracts the 120 `.md` rows declare reject a
  markdown string outright (1 error each — they are object schemas). The declared contract is
  unenforceable against the declared `output_path`. That is a catalog-internal inconsistency,
  reported here, NOT repaired by me: re-scoping a unit's contract is out of this lane's authority;
- it **can** require the row's own `completion_sentinel` (declared by 2007/2007 rows, measured) to
  appear, and the body — the text with the sentinel removed — to carry ≥200 non-space characters,
  ≥12 distinct characters, and no ≥200-character single-character run.

The 200/12/200 numbers are a heuristic floor and are labelled as such in the source. They are not
a contract; the settling experiment is the first genuine `.md` artifact this program produces.

## C5 CONTROLS — one per STAGE, each with the OLD instrument's column beside it

`python command-center/ready_units.py --self-test` -> EXIT 0, 16 controls. The
`pre-r3-instrument` / `pre-r3-predicate` column is the proof each control bites: where it reads
`True` the shipped predicate accepted that exact document.

```
  CONTROL schema-doc unkeyed garbage         : want=False got=False stage=not-a-schema-document        | pre-r3-instrument=False -> OK
  CONTROL schema-doc KEYED garbage (bypass)  : want=False got=False stage=schema-document-vacuous      | pre-r3-instrument=True  -> OK
  CONTROL schema-doc bare {$schema}          : want=False got=False stage=schema-document-vacuous      | pre-r3-instrument=True  -> OK
  CONTROL schema-doc $id-only garbage        : want=False got=False stage=schema-document-vacuous      | pre-r3-instrument=True  -> OK
  CONTROL schema-doc KEYED broken schema     : want=False got=False stage=schema-document-invalid:SchemaError | pre-r3-instrument=False -> OK
  CONTROL schema-doc REAL WFA-0001 pack      : want=True  got=True  stage=schema-document-discriminates | pre-r3-instrument=True  -> OK
  CONTROL text good note                 : want=True  got=True  reason=delivered(text artifact...        | pre-r3-predicate=True -> OK
  CONTROL text sentinel absent           : want=False got=False reason=completion-sentinel-absent        | pre-r3-predicate=True -> OK
  CONTROL text body is only the sentinel : want=False got=False reason=body-too-thin(non-space-chars=2)  | pre-r3-predicate=True -> OK
  CONTROL text 2,000-x blob body         : want=False got=False reason=degenerate(longest-run=300)       | pre-r3-predicate=True -> OK
  CONTROL text two-character body        : want=False got=False reason=degenerate(distinct-chars=2)      | pre-r3-predicate=True -> OK
```

The `KEYED broken schema` control reads `pre-r3-instrument=False` honestly: `check_schema` did fire
on that document. It is not a control for D1 — it is the control D1b said was missing, proving the
merit stage runs *with the key present*.

Re-running the verifier's OWN instruments after the fix (the both-states test at program level):

```
$ python command-center/p2-wave/_av2_tmp/probe_bypass.py    ->  BYPASS_PROVEN = False
$ python command-center/p2-wave/_av2_tmp/probe_nonjson.py   ->  SUFFIX_BYPASS_PROVEN = False
```

Scoped honestly: `probe_nonjson` now stops at `no-completion-sentinel-declared` because its
synthetic unit declares no sentinel. That is a fail-closed rejection, not a demonstration of the
degeneracy stages — those are covered by the five per-stage fixtures above.

**Blast radius** (`command-center/p2-wave/_r3_blast.py`, old predicate executed from the HEAD blob
read via `git ls-files -s` + `git cat-file -p`):

```
  HEAD blob 624dad831688  19667 B  CR-bytes=0
  artifacts present and non-empty: 51
  verdict CHANGES under the round-3 fix: 0
  CONTROL, same run, on the bypass document itself:
    old instrument accepts it : True
    new instrument accepts it : False
  SUCCESS:r3-blast the fix closes the bypass and moves 0 verdicts on present artifacts
```

Zero movement is the point: no sibling's work is re-classified, and the same run proves the fix is
not inert.

### REFUTED WORDING FROM ROUND 2, recorded rather than deleted

| Where | The sentence that was too wide | Correctly scoped |
|---|---|---|
| `ready_units.looks_like_schema_doc` docstring | "Two-sided by construction: it accepts the real WFA-0001 schema pack, and rejects all three garbage probes AND a structurally-broken schema" | REFUTED by execution. All three garbage probes were rejected by the one-line KEY check, not on merit; adding one key flipped them to DELIVERED. The broken-schema example carried no key, so `check_schema` was never exercised. The docstring now carries this refutation inline. |
| round-2 report, "a declared contract that cannot fail is not a gate" | implied the fallback restored a real gate for the 23 meta-declaring units | Correctly scoped: it restored a real gate for artifacts that are NOT schema documents; for those that claim to be, it restored only a key check. The merit stage shipped this round. |
| round-1/2 reports, "each delivered unit executable-proven against its declared contract" | read as contract-PROOF for all five | Correctly scoped: IMP-0433's declared contract (`command-center/schema/meta/json-schema-draft.json`) is VACUOUS — the audit measured 0/12 garbage documents rejected. Its receipt is proven against `receipt.schema.json` (discriminating, 12 negative fixtures) but NOT against the contract its catalog row names, because that contract cannot fail. The other four declare discriminating contracts (12/12 garbage rejected each). |

## C6 UNITS DELIVERED THIS ROUND
UNKNOWN - not yet measured

## C7 BLOCKED, WITH PRECISE BLOCKERS
UNKNOWN - not yet measured

## C8 INDEPENDENT BLOB RE-VERIFICATION
UNKNOWN - not yet measured

## C9 COMMITS
UNKNOWN - not yet measured

## C10 RESIDUAL / NOT-CHECKED
UNKNOWN - not yet measured
