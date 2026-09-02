# P2 BUILD — ROUND 3 (re-entry after a confirmed refutation)

STATUS: COMPLETE for this round. Every section carries a measurement, a control, or an
explicit NOT-CHECKED. (While it was in progress each unmeasured section read `UNKNOWN - not yet
measured`; if any such line survives below, the unit died before measuring it and no verdict there
may be cited.)

COVERAGE:
- C1 live partition re-run + quoted .................. MEASURED
- C2 round-2 confirmed defects enumerated ............ MEASURED
- C3 D1 (one-key `$schema` bypass) fixed + controlled  MEASURED
- C4 D2 (non-.json suffix bypass) fixed + controlled . MEASURED
- C5 overclaim sentences corrected, refutation recorded MEASURED (docstrings + banners in ROUND1/ROUND2)
- C6 new units delivered this round .................. MEASURED (2 delivered)
- C7 blocked units with precise blockers ............. MEASURED
- C8 independent blob re-verification ................ MEASURED (9/9)
- C9 commits (explicit paths, no foreign paths) ...... MEASURED (0 foreign)
- C10 residual / NOT-CHECKED ......................... MEASURED

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

## C6 UNITS DELIVERED THIS ROUND — two, chosen up front, in the recorded owner order

`command-center/p2-wave/_r3_rank.py` (OQ-2: ascending INTEGER phase, then unblocking power; the
phase comparator carries its own control, `['10','2','0','2A'] -> ['0','2','2A','10']`):

```
  READY 449 | excluded, adversarial/ (wave scope): 108 | excluded, artifact already exists: 9
  candidates: 332   substrate {local-serialized 119, local-parallel 113, cloud-batch 51, worktree-isolated 49}
  rank 1  AUD-0001  phase 0  power 3   -> BLOCKED (off-limits inputs, see C7)
  rank 2  AUD-0006  phase 0  power 2   -> BUILT
  rank 3  AUD-0015  phase 0  power 2   -> DEFERRED with reason (see C7)
  rank 4  AUD-0021  phase 0  power 2   -> BUILT
```

**AUD-0021 — node dependency inventory and lockfile integrity** (blob 31,991 B).
26 `package.json`; 42 prod + 32 dev + 0 peer + 0 optional dependencies; 5 `package-lock.json`;
**0 failing integrity, 0 out of sync with their manifest, 21 manifests with no lock at all**.
Probe 1 parses the dependency classes; probe 2 is the static integrity scan PLUS npm's own resolver
(`npm ls --all --json` exit status per locked directory); a third cross-check counts the same
population from the git INDEX and agrees (26 = 26).

> TWO DETECTOR FAILURES OF MY OWN, both caught before any count was published.
> (a) the lock-format decision keyed on the FILE NAME, so both control fixtures — copies of a real
> lock saved under fixture names — came back `unsupported-lock-format` and the control scored
> `ok=False` in BOTH states. The builder refused to emit; fixed by taking format from an explicit
> `kind`. (b) the first plausible run reported **"2 locks failing integrity"**. All 5 offending
> entries are `link: true` workspace links whose `resolved` is a LOCAL PATH — npm attaches no hash
> to those by design. **The true count is 0.** Both are recorded in the source and in the artifact's
> observations, not quietly patched.

**AUD-0006 — uncommitted and untracked work census** (blob 81,812 B).
174 uncommitted or untracked paths; body classifier: 152 real work, 10 scratch, 12 undecided. The
row's real question is whether a path-only sweep suffices, and the answer is measured: it disagrees
on 37 paths — it would **LOSE 17 files the body says are real authored work**, and KEEP 8 the body
says are scratch plus 11 it cannot decide. Those three numbers are deliberately separate; folding
UNDECIDED into "junk" would claim a verdict the classifier explicitly refuses to make.
The row's planted-mutant control is implemented in BOTH directions (authored module under a
scratch path: content rescues, path-only loses; 4,000-z blob under `src/core`: content rejects,
path-only keeps).

> SCOPE, STATED LOUDLY RATHER THAN NARROWED QUIETLY: the row says "every owner-controlled repo".
> This lane may touch exactly one. `~/Documents/GitHub/**` and `~/.claude/agent-worktrees/**` belong
> to concurrent sessions and are forbidden by the wave floor, and walking `~` to find the rest would
> read credential-bearing files. **1 repo of N, N NOT-CHECKED**, recorded in `residual_unknowns`.

Both artifacts come from a writer that validates BEFORE writing and refuses to persist a failing
document — it fired for real four times across these two units.

## C7 BLOCKED, WITH PRECISE BLOCKERS

`command-center/p2-wave/P2-BLOCKED-UNITS-R3.json` (`_r3_blockers.py`, with a census control
asserting every filter is a PROPER subset: `adv=108, outside-all=279, of 449`).

| blocker | count | precise reason |
|---|---|---|
| `B-SCOPE-ADVERSARIAL` | 108 | `output_path` under `command-center/adversarial/`, which this wave forbids this lane from touching. **These occupy the entire current READY head** — the exclusion decides what this lane could build at all. |
| `B-REVIEWER-GATE` | 449/449 | the row names an independent reviewer and `receipt_core` forbids `state=SUCCESS` without `reviewer.verdict=PASS` + `independent=true`. Structural: a build lane can deliver an artifact but cannot close a unit. |
| `B-CLOUD-BATCH-UNVERIFIED` | 55 | declares `execution_substrate=cloud-batch`, whose reachability this lane did NOT probe. NOT-CHECKED, not "unavailable". |
| `B-TEXT-CONTRACT-UNENFORCEABLE` | 0 READY / 120 catalog-wide | `.md` output_path against an object JSON-Schema contract that rejects a markdown string. Both numbers are stated because they differ: the hole is latent, not absent. |
| `B-AUD-0001-OFF-LIMITS-INPUTS` | 1 | rank 1 by unblocking power; its declared inputs walk `~/Documents/GitHub`. Re-affirmed from round 1, not re-litigated. This blocker costs real throughput and needs an owner decision. |
| `B-AUD-0015-CREDENTIAL-ADJACENT` | 1 | rank 3, DEFERRED by me, not skipped: its inputs include `~/.claude/settings.json`, which the floor forbids reading wholesale (live credentials in its env block). It needs a field-scoped redaction-safe reader whose non-leakage is itself proven, which I could not also do in the remaining budget. |

## C8 INDEPENDENT BLOB RE-VERIFICATION — all nine artifacts this lane has ever delivered

`python command-center/p2-wave/_r3_verify_committed.py` -> EXIT 0. Blobs read with
`git ls-files -s` + `git cat-file -p` (never `git archive`), validated by a reader that shares no
code with the builders. The DISCRIM column is the one the audit said was missing.

```
unit          blobB  CR parse VALID DISCRIM sent exact state
IMP-0433      17774   0  True   YES      NO True  True BLOCKED
AUD-0041      77871   0  True   YES     yes True False BLOCKED
AUD-0051      29935   0  True   YES     yes True False BLOCKED
AUD-0030      23565   0  True   YES     yes True False BLOCKED
AUD-0020      34300   0  True   YES     yes True False BLOCKED
CC-0002       13399   0  True   YES     yes True  True BLOCKED
IMP-0440      15418   0  True   YES     yes True  True BLOCKED
AUD-0021      31991   0  True   YES     yes True  True BLOCKED
AUD-0006      81812   0  True   YES     yes True  True BLOCKED

CONTROL verifier: AUD-0021 with `sentinel` removed -> 1 error(s) FIRES; unmodified -> 0 SILENT
units whose DECLARED contract cannot fail (so schema-VALID is not evidence): ['IMP-0433']
```

Two findings from running it, both mine to own:

- **a detector failure in the verifier itself**, disclosed: its first version asserted the sentinel
  `startswith("SUCCESS:<uid>")` and scored IMP-0433 and IMP-0440 False. Both are correct — they
  declare a `SENTINEL:<uid>:...` form. A verifier that invents the expected value measures its own
  assumption; it now reads the value the ROW declares;
- **a real drift in four round-1 receipts**: AUD-0041/0051/0030/0020 carry a PARAPHRASED sentinel,
  not the row's `completion_sentinel` verbatim. Correctly scoped: this is NOT a contract failure
  (the schema requires a sentinel string, not that string) and the gate is the prefix. Not re-run
  here because re-running those builders re-measures live inputs (one calls the Actions API). The
  `exact` column publishes it rather than letting the prefix check hide it.

## C9 COMMITS — explicit paths only, every one verified foreign-path-free

| sha | what |
|---|---|
| `11c53a1b` | fix(command-center): one added key was enough to be counted DELIVERED — D1 + D1b + D2, 16 controls, blast-radius probe, 5 text fixtures, the verifier's 6 probes preserved |
| `9d914028` | feat(command-center): deliver AUD-0021 and AUD-0006, both controls two-directional |

`git show --name-only --pretty=format: <sha> | grep -v '^command-center/'` returns **0 lines** for
both. No `git add -A`, no `git add .`, no `git commit -a` at any point; every commit used
`git commit -F <file> -- <explicit paths>`, which is immune to a sibling staging into the shared
index mid-commit (a hazard that actually fired in round 1).

## C10 RESIDUAL / NOT-CHECKED

**No unit reached `state=SUCCESS`, and none can from a build lane alone.** 449/449 READY units carry
a `reviewer_requirement`; `receipt_core` forbids SUCCESS without an independent reviewer PASS. All
nine artifacts are `BLOCKED` with `failure.classification = ["reviewer-absent",
"self-review-is-not-review"]` and are one reviewer block away from SUCCESS. **The program needs a
paired reviewer lane or it will never legitimately close a unit.**

NOT-CHECKED, stated rather than folded into a pass:
- cloud-batch substrate reachability (55 READY units) — no probe run;
- every owner-controlled repo except this one, for AUD-0006;
- npm's resolved TREE (no `node_modules` exists anywhere here), and whether integrity hashes are
  *correct* rather than present and well-formed — so AUD-0021's "0 failing" is a lower bound;
- whether the 43 pre-existing BLOCKED artifacts are blocked for still-valid reasons.

Honest limits of the two fixes shipped this round:
- the text gate's 200/12/200 thresholds are a heuristic floor, labelled as such in the source. The
  settling experiment is the first genuine `.md` artifact the program produces;
- `schema_doc_verdict` still accepts refusal-by-raise (the module's existing convention), now
  DISCLOSED in the reason string. WFA-0001 no longer needs that branch — with the registry attached
  it discriminates on merit — but a future artifact with an unresolvable `$ref` would pass on the
  weaker evidence;
- the 6 contracts the 120 `.md` units declare remain unenforceable against a markdown path. That is
  a catalog inconsistency I reported and deliberately did NOT repair: re-scoping a unit's declared
  contract is outside this lane's authority.

CONFIDENCE. Almost-certain (90-99%) on everything executed with a two-sided control and re-read
from the committed blob: the partition at both ends, the two bypass refutations and their closure
(the verifier's own probes flipped `True -> False` on the same scripts), the 0-verdict blast radius
over 51 artifacts, the 16 self-test controls, AUD-0021's 26/42/32/5/0/21 census, AUD-0006's
174/152/10/12 census and the 17-file path-only loss. Likely (55-80%): that AUD-0006's REAL-WORK
label is correct on every one of the 152 — the classifier is a signal heuristic, its UNDECIDED
class is reported rather than assigned, and no human adjudication was done. Deliberately not
claimed: that any of these nine artifacts is CORRECT. No independent reviewer has run.
