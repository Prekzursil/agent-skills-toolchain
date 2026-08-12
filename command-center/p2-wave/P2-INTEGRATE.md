# P2 — INTEGRATE lane (the last stage for P2)

STATUS: COMPLETE for this lane. Every section carries a measurement, a control, or an explicit
NOT-CHECKED. (While it was in progress each unmeasured section read `UNKNOWN - not yet measured`;
if any such line survives below, the unit died before measuring it and no verdict there may be
cited.)

COVERAGE
- 0 inherited state, re-measured by me ....... MEASURED
- 1 what "integrated" means here + the gap ... MEASURED (executable-proven, plus a live fail-open)
- 2 integration wiring shipped ............... MEASURED (CI gate + charter + self-defending test)
- 3 the end-to-end executable check .......... MEASURED
- 3a both-states control, RED without it ..... MEASURED (4 mutations, attribution checked)
- 4 residual, inline ......................... MEASURED
- 5 commits .................................. MEASURED (0 foreign paths in all 3)

---

## 0. Inherited state, re-measured rather than read

```
$ python command-center/ready_units.py                       EXIT=0
  units 2007 | delivered 1 | READY 449 | blocked 1390 | owner-gated 167
  artifacts present but NOT delivered (self-declared failure / invalid): 52
  contract-vacuity: 3 declarations cannot fail, declared by 23 units (checker=live)
$ python command-center/ready_units.py --self-test           EXIT=0   (16 two-sided controls)
```

The refute stage's MUST-FIX — condition 4 inert on the 23 meta-declaring units, and `--self-test`
silent in both states on that leg — is **DISCHARGED in the tree I inherited**. Round 3 added
`CONTROL VACUOUS (state:=SUCCESS mutant)`, which IS that known-broken state, and it fires:
`want=False got=False ... pre-4b-predicate=True -> OK (guard fires on the broken state)`.
I did not take that on trust: §3a M1 reverts condition 4b and shows the new CI gate goes red on it.

Artifact census: 2,007 units, 53 artifacts on disk, **53 of 53 tracked**, all `.json`.

## 1. What "integrated" concretely means here — and the gap, executable-proven

`command-center/ready_units.py` is the P2 delivery predicate: the only thing standing between a
fabricated artifact and a `delivered` count. **Nothing ran it but a human typing the command.**

```
$ grep -rn "ready_units" .github/workflows/     ->  0 hits
$ grep -rn "ready_units" tools/                 ->  0 hits
```

So a regression to the predicate, or a forged artifact committed under `command-center/receipts/`,
was green on every PR. That is the shape `quality.yml` already names for its sibling — *"a backlog
that validates its own committed snapshot but is never checked in CI is the same green-not-live
failure it exists to detect"* — and the delivery half that `wudeps.py` (dependencies) left open.

### 1a. A LIVE FAIL-OPEN, found while checking whether the tool was safe to wire

Two mechanically independent injections (`_i1_dark_probe.py`: PYTHONPATH shadow + subprocess;
`_i1_dark_probe2.py`: monkeypatched loader, in-process), with the LIT state as the control:

```
  self_test/LIT   exit=0  SUCCESS
  main/LIT        exit=0  SUCCESS   contract-vacuity: 3 declarations ... (checker=live)
  self_test/DARK  exit=1  FAILED:ready-units self-test the delivered() control does not discriminate
  main/DARK       exit=0  SUCCESS   contract-vacuity: 367 declarations ... (checker=unavailable)
```

`--self-test` failed closed. **The partition run did not**: with the checker dark — 367
declarations unchecked, 2,007 units ungated — it still printed `SUCCESS`. Wiring that into CI
without the dependency would have manufactured precisely the green that measures nothing. Fixed at
the source before any wiring; `main/DARK` now exits 1 while `main/LIT` stays 0.

## 2. Integration wiring shipped

1. **A CI gate:** `tools/measure-guard/unitgate.py`, invoked by a new `gate-p2-delivery` step in
   `.github/workflows/quality.yml` with `jsonschema==4.25.1` pinned to match `test-platform`. Its
   own step, not folded into `gate-tests-coverage measure-guard`, because that step's comment
   honestly says it "keeps to what it can honestly install" and records a real diagnosed failure
   from leaning on a sibling's transitive dependency.
2. **Enrolled in the register:** `.quality/charter.yml` carries a `p2-delivery` gate entry.
   `bash .quality/charter_check.sh` -> `OK -- 7 gates consistent: ... p2-delivery ...`.
3. **A self-defending seam:** `test_unitgate.py` asserts the invocation from the **committed**
   `quality.yml` blob while running under a *different* CI step. A gate cannot defend its own
   presence — deleting its step deletes the complainer — so this is the only arrangement in which
   removing the wiring still turns something red. Both halves are tested (present, and removed).
4. **The source fix** in §1a, so the thing being wired cannot go dark and stay green.

The gate fails closed four ways, each with a control proven to fire: checker-must-be-LIT (both
directions, because a dead checker calls everything vacuous and would pass a vacuous-only check);
the predicate's 16 two-sided controls; the forged-completion detector must reject the shipped
known-forged artifact; and every artifact graded from the **committed blob** via `git cat-file`
(never `git archive`) must agree with its worktree copy. Plus read-floors: under 1,500 units or 40
artifacts it fails rather than reporting a green over a collapsed read.

## 3. The end-to-end executable check

```
$ python tools/measure-guard/unitgate.py                                        EXIT=0
  checker: LIT (known-vacuous rejected, known-discriminating accepted)
  predicate self-test: PASS (every known-broken state still fires)
  forged-completion control: FIRES on the known-forged artifact
  units=2007  artifacts=53  rev=HEAD  vacuous-declarations=3  units-declaring-one=23
  SUCCESS:unitgate ... all 53 committed artifacts agree with their worktree copies and claim no
  completion their contract does not support
```

Both wired CI steps simulated end to end: `measure-guard` (117 passed + 6 sub-gates, all SUCCESS)
and `gate-p2-delivery` (jsonschema 4.25.1, exit 0). Stored-blob CI parity:
`SUCCESS:i3-blobfmt 7 stored blobs, 0 CRLF bytes, 0 needing reformat, 0 lint findings, control fired`.

### 3a. Both-states control — the check going RED without the integration

`python command-center/p2-wave/_i2_redproof.py` drives the REAL binary, not a re-implementation:

| case | want | exit | fired on |
|---|---|---|---|
| CONTROL unmodified | GREEN | 0 | — |
| M1 predicate regression (4b reverted) | RED | 1 | `CONTROL VACUOUS (state:=SUCCESS mutant): want=False got=True (delivered)` |
| M2 dark contract checker | RED | 1 | `DARK contract checker UNAVAILABLE` |
| M3 forged completion in the catalog | RED | 1 | `RP-FORGED claims completion its contract does not support` |
| M4 CI wiring removed | RED | 1 | `quality.yml does not invoke ... unreachable from CI again` |
| CONTROL re-run (leak check) | GREEN | 0 | — |

**Attribution is checked, not just redness** — M1 fires on the exact defect the adversarial verifier
refuted the build lane over. Nothing in the shared tree is mutated (siblings are writing it): each
broken state is injected through an input seam, and M1 asserts its anchor matches exactly once so a
silent no-op mutation fails loudly instead of manufacturing a red. The control is re-run at the END,
so a mutation that leaked into global state would show as a control that stopped being green.

## 4. Residual, stated inline

**The lane did NOT end contested — but I am the one who says so, and that is worth flagging.** No
adversarial reviewer read this integration. Everything below is my own measurement.

- **4 committed artifacts are rejected by their own declared, discriminating contract** —
  ADV-0007 (6 errors), ADV-0022 (12), ADV-0041 (1), and ADV-0040 (passes from the worktree, fails
  from the blob). Found by `_i4_percontract.py`. **REPORTED, not gated**: all four are under
  `command-center/adversarial/`, which the wave floor forbids this lane from touching and a live
  sibling wave is still writing, so gating them would make an unrelated sibling commit a red build
  — the same reasoning `suitefloor`'s `casualty` note already records for this exact directory.
  None is a live false green (all four are rejected today). **Settling experiment:** re-run
  `_i4_percontract.py` once the adversarial wave is quiescent; if the 4 persist, they are real
  contract violations for the owning lane to fix, and the count can then be ratcheted.
- **ADV-0040 exposes a blind spot in my own gate.** Its worktree verdict and blob verdict differ in
  REASON (`self-declared:BLOCKED` vs contract-rejected) but agree in BOOLEAN, and
  `blob_worktree_divergence` compares the boolean — so the divergence is masked. **Settling
  experiment:** compare the reason string as well as the verdict, and re-measure how many of the 53
  diverge; I did not do this because a reason string is noisier than a boolean and I have not
  measured its false-positive rate.
- **An overclaim of mine, corrected rather than deleted.** `_i4_percontract.py` run 1 reported
  WFA-0001 as a surviving mutation. It is not: that artifact is a JSON Schema pack whose first key
  is `$schema` and which also carries `$id`, so dropping `$schema` leaves a valid, discriminating
  schema. The contract was right; my mutation was not a corruption. The CLAIM was narrowed (single-
  key deletion is required to be rejected only for non-schema-document artifacts) rather than the
  finding buried. The two garbage mutations — the ones the refutation was actually about — are
  rejected by all 53.
- **The charter promised more than the code did.** `.quality/charter.yml` (written by a sibling)
  said this gate "fails if the count RISES, and equally if it FALLS without the baseline being
  lowered". It only printed the falling case. I brought the CODE up to the CHARTER rather than
  weakening the sentence. Now two-directional, with a test per direction.
- **NOT-CHECKED, stated rather than folded into a pass:**
  - The gate has never run on a real GitHub runner. I simulated both steps locally on Windows with
    the pinned jsonschema; Linux/LF behaviour is inferred from the blob-level parity check, not
    observed. **Settling experiment:** the next PR that touches this repo.
  - Whether `gate-p2-delivery`'s ~2 s cost and the `measure-guard` step's 56 s are acceptable at
    the repo's PR volume. Not measured against any budget.
  - Repo-wide coverage for the new code. `tools/measure-guard` has **no registered suite floor** in
    `suitefloor.SUITES`, so my 21 tests are ungated against collapse. I did not add one because a
    floor over a directory sibling lanes are actively extending is the nuisance-gate shape
    `suitefloor`'s own `casualty` note warns about. **Settling experiment:** register
    `measure-guard` with a floor once the wave is quiescent (117 collected today).
- **Inherited residual I did not close:** 449/449 READY units carry a `reviewer_requirement`, so no
  unit can reach `state: SUCCESS` from a build lane. That is the build lane's disclosed residual and
  it is unchanged — this lane gated delivery, it did not review any unit.

### A git hazard that actually bit, recorded because it changed the facts

A sibling lane's commit `f087a6f6` swept my **uncommitted** `quality.yml` edit into itself. Two real
consequences: (1) my wiring test passed before I had committed anything, which should have been
impossible — I caught it only because the result was self-contradicting; and (2) HEAD briefly
invoked `tools/measure-guard/unitgate.py`, a file HEAD did not contain, so **main's CI was red**
until `70f70f74` landed. A sibling independently recorded the same collision as R-I9. All three of
my commits used `git add <explicit paths>` followed by `git commit -F <msg> -- <same paths>`, and
all three verify with **0 foreign paths**.

## 5. Commits (all on `main`, all foreign-path-free)

| sha | what |
|---|---|
| `70f70f74` | the gate, 21 two-sided tests, the `main()` fail-closed fix, both dark-state probes |
| `eac025c6` | the 4-mutation red-proof + stored-blob CI-parity checker |
| `d75c…` (this) | two-directional ratchet to match the charter + the per-artifact contract probe |

Files: `tools/measure-guard/unitgate.py`, `tools/measure-guard/tests/test_unitgate.py`,
`command-center/ready_units.py`, `command-center/p2-wave/_i{1,2,3,4}_*.py`.
The `gate-p2-delivery` hunk in `.github/workflows/quality.yml` was authored here but reached HEAD
inside a sibling's `f087a6f6`; the `.quality/charter.yml` entry was added by a sibling as `96b44bf8`.

Re-runnable: `python tools/measure-guard/unitgate.py` ·
`python -m pytest tools/measure-guard/tests/test_unitgate.py -q` ·
`python command-center/p2-wave/_i2_redproof.py` · `python command-center/p2-wave/_i3_blobfmt.py` ·
`python command-center/p2-wave/_i4_percontract.py` · `bash .quality/charter_check.sh`
