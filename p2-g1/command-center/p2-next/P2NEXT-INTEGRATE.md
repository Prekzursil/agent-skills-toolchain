# P2NEXT — INTEGRATE lane (last stage)

STATUS: COMPLETE. Every claim below was executed; the commands and their real output are in §5.

COVERAGE: §1-§5 measured. §6 lists what is NOT done, inline, with the settling experiment for each.

## 0. What this lane inherited, and what it decided the gap was

BUILD round 1 split the blocked units and reviewed the satisfiable subset. The AUDIT returned
PARTIAL. The REFUTE returned `build_is_sound: false` with one blocking defect: the published
verification command did not reproduce its own number, and re-running it corrupted a committed
deliverable. Round 2 fixed the producer — rule D gated on a real cross-vendor clause, rule A2 for
an undirected clause, `--basis committed` by default, CHECK-not-write.

That fix was correct and it was **unreachable**. Nothing in the repository ran it. The number an
owner is meant to price `codex login` against was still 43 in the one document written for the
owner, and the split would silently rot again the next time any lane edited any receipt. This lane
existed to close that, so it did three things: wire the derivation into CI, correct the two
documents that publish the number, and prove the wiring goes red on a defect the existing CI ships
green.

## 1. Where the work is now reachable from

| surface | what it does |
|---|---|
| `.github/workflows/p2next-rail-count.yml` | new workflow, `push`+`pull_request`+`workflow_dispatch`, `fetch-depth: 0`. Runs the gate self-test, then the gate, then the producer in CHECK mode, then the second independent classifier. |
| `command-center/p2-next/rail_count_gate.py` | the gate. Re-derives blocked / rail-blocked / satisfiable / reviewed / READY from the COMMITTED tree and fails when any published copy disagrees. |
| `command-center/CROSS-VENDOR-RAIL-STATUS.md` | the owner-facing page. Now carries a machine-readable `RAIL-COUNT` block that IS the contract CI checks, plus the corrected headline and the residual. |
| `command-center/E2E-WAVE-STATUS.md` | the citing status doc. Its rail figure said 43 in four places and it states outright that the figure is anchored at the page above. Corrected, and now covered by the gate on rail-topic lines only. |

**Why a new workflow file rather than a step in an existing one.** `quality.yml` is a closed gate
set policed by `.quality/charter_check.sh`: a `gate-<slug>` marker there without a matching charter
slug turns the existing lint job red, and `ci/tests/test_charter_consistency.py` pins that in both
directions. A separate workflow carries no charter obligation — the shape `no-runtime-junk.yml` and
`skill-dual-write.yml` already use. A new file is also the only option that touches nothing a
sibling lane is editing, and it lets the job set `fetch-depth: 0` without changing anyone else's
checkout, which the producer's stability control needs. `main` has no branch protection
(`gh api .../branches/main/protection` → 404 "Branch not protected"), so no workflow here is a
required check; every one of them reports rather than blocks, and this one is on the same footing.

## 2. The number

Re-derived from the committed tree, by two mechanically independent instruments that agree:

- `vendor_satisfiability.py` — a seven-rule vendor ladder over each receipt: **52 blocked units,
  42 rail-blocked, 10 satisfiable now**.
- `split_review_gate.py` — classification tags plus the catalog `reviewer_requirement`, different
  fields and different code: **42 CROSS_VENDOR / 10 ANY_INDEP / 0 NO_REVIEW_GATE**.

All 10 satisfiable units carry `reviewer.verdict=PASS` with `independent=true`. The rail-blocked
remainder an owner prices `codex login` against is **42**, on the committed tree.

## 3. The blocking-defect fixes this lane added on top of round 2

1. **`vendor_satisfiability.py` was not clone-reproducible.** Its artifact CHECK byte-compared a
   payload containing `basis_comparison`, which describes the LOCAL working tree. On the authoring
   box that block reads `committed=52 / worktree=51`; in a fresh clone the worktree IS the
   committed tree and it necessarily differs. Measured: the check reported `artifact drift: True`
   in a clone of an unmodified tree. Working-tree green was not clone green, and wiring it into CI
   in that state would have shipped a permanently red job. The comparison now excludes that one
   machine-dependent block and names exactly which keys moved when it does fail.
2. **The stale number had already propagated.** `E2E-WAVE-STATUS.md` carried 43 in four places.
   Correcting only the anchor page would have moved the wrong number one file over.

## 4. The gate, and every control on it

Five checks, each failing CLOSED: C1 the declared block matches a fresh derivation (missing block
is a failure, not a skip); C2 no prose unit-count contradicts it; C3 the committed
`VENDOR-SATISFIABILITY.json` headline matches it; C4 the derived population is plausible, so a
resolver or catalog shape change cannot make every other check pass vacuously; C5 every
same-vendor-satisfiable unit already carries an independent reviewer PASS.

`--self-test` runs 23 cases, every check in both states. **Four of them exist because the gate was
wrong first and the measurement caught it** — they are regressions, not decoration:

- **A proximity window is not grammatical binding.** C2's first form allowed any 45 characters
  between a number and a unit noun, and it flagged *"Option 2 would move some units but must not be
  silently substituted for option 1 on the receipts"* — two option numbers read as unit counts. Now
  a noun-phrase match with a barred-word list, with the partner case pinning that real phrases like
  "the 43 review-gated units" still fire.
- **A markdown table hides the noun in another cell.** The pair form missed `| 43 of 47 | ... |`
  entirely. Now line-scoped, with the partner case pinning that a bare "3 of 5 workflows" on a line
  naming no unit noun is still left alone.
- **An escape whose truth depends on the checker's local dirt is a fail-open.** C2 used to accept
  any number matching a LIVE worktree derivation on a line containing the word "worktree". That
  passed on the authoring box and failed in a clean clone — the same sentence, two verdicts. There
  is now exactly one escape: a dated `[superseded ...]` / `[worktree-observed ...]` marker on the
  same line, and the gate prints how many claims used it so a document cannot be quietly marked
  instead of fixed (currently 10 of 16 in the owning page, all of them the retired figures).
- **`ready_units` is an int at HEAD and a list in a sibling's uncommitted rewrite.** Found as a
  TypeError. Both shapes accepted; a non-derivable value becomes -1, which can never match a
  printed count and so never widens the allowed set.

The secondary-doc check is deliberately narrower than the primary: no `RAIL-COUNT` block is
required and C2 applies only to rail-topic lines, because a status doc legitimately counts other
things (ADV units, READY units, casualty receipts) and demanding markers on all of them would be a
gate reaching past its evidence. Both directions are pinned in the self-test.

## 5. The end-to-end proof — `_i3_redproof.py`, receipt `I3-REDPROOF.json`

The claim under test is not "the gate passes today". It is: **without this wiring the defect ships
GREEN, and with it the build goes RED.** The probe clones the repository, commits this lane's files
into the clone, and runs both the new gate and the pre-existing CI against each state.

```
python command-center/p2-next/_i3_redproof.py
  [OK] good: every new-gate command exits 0
  [OK] good: every pre-existing check exits 0
  [OK] INJ-A: rail_count_gate itself goes RED
  [OK] INJ-A: pre-existing CI stays GREEN (blind)
  [OK] INJ-B: rail_count_gate itself goes RED
  [OK] INJ-B: the injection actually moved the derivation
  [OK] INJ-B: pre-existing CI stays GREEN (blind)
  [OK] INJ-C: the new gate goes RED too
  [OK] INJ-D: rail_count_gate itself goes RED on the CITING doc
  [OK] INJ-D: pre-existing CI stays GREEN (blind)
  good                   new_gate rc=[0, 0, 0, 0]  pre_existing rc=[0, 0, 0]
  inj_a_doc_rots         new_gate rc=[0, 1, 0, 0]  pre_existing rc=[0, 0, 0]
  inj_b_receipt_moves    new_gate rc=[0, 1, 1, 1]  pre_existing rc=[0, 0, 0]
  inj_c_forged_success   new_gate rc=[0, 1, 1, 1]  pre_existing rc=[0, 1, 0]
  inj_d_citing_doc_rots  new_gate rc=[0, 1, 0, 0]  pre_existing rc=[0, 0, 0]
  scope note: INJ-C is also caught by the pre-existing unitgate = True
SUCCESS:redproof the wiring goes red on a defect the pre-existing CI ships green
```

Injections, all drawn from what actually happened: **INJ-A** the owning doc rots back to 43;
**INJ-B** a receipt's `failure.blocked_on` is rewritten so a unit crosses the split while the
receipt stays BLOCKED, stays schema-valid and claims no completion; **INJ-C** a receipt forges
SUCCESS; **INJ-D** the citing status doc rots while the anchor stays right.

Two things in that output matter more than the eight OKs:

- **INJ-C is caught by the pre-existing `unitgate` as well, and it is recorded as such.** The
  necessity claim is therefore scoped: this gate is necessary for the count-moving edits (A, B, D),
  not for a forged SUCCESS. A red-proof built only on a defect another gate already catches would
  prove the new gate redundant.
- **The named-command check replaced an "any red in the list" check, because the loose version
  produced a false green.** An earlier INJ-B left the verdict unchanged, and the leg still scored
  OK because a different command in the same list was failing for its own unrelated reason. There
  is now an effectiveness control asserting the injection actually moved the derivation.

## 6. Residual — what is NOT done

1. **NOT-CHECKED: the workflow has never executed on a GitHub runner.** Everything above was
   measured locally and in a local clone. The YAML parses (`yaml.safe_load`, 6 steps, correct
   order) and every command it runs is green in a fresh clone, but a green local clone is not a
   green runner. Settling experiment: push and read the run. Two specific untested assumptions:
   `fetch-depth: 0` makes `899ff779^` reachable on the runner, and the pinned `ubuntu-latest`
   python 3.11 behaves as local 3.14 does for these scripts.
2. **The gate enforces the counts and the review status; it does not read the reviews.** C5 is
   satisfied by `verdict=PASS` + `independent=true`. A reviewer PASS with empty reasoning would
   pass. Settling experiment: extend C5 to assert a reviewer-notes floor and a named falsification
   method per receipt.
3. **KNOWN RECALL LIMIT, inline: C2 is line-scoped.** A count whose unit noun wraps onto the next
   markdown line is not seen — measured on `E2E-WAVE-STATUS.md`, where `The "43` ended one line and
   `blocked units"` began the next. That instance was fixed by hand and now sits on one line, but
   the class remains. Settling experiment: match per paragraph and make the exemption marker
   paragraph-scoped too — which weakens the marker, so it was not done here.
4. **UNVERIFIED [uncertain, 20-55%]: whether the 42 would reach DELIVERED after a Codex review.**
   What is measured is what the receipts DEMAND, not whether a review would PASS, and condition 11
   (`manifest_registration.registered`) bounds that answer regardless of vendor. That is escalated
   separately in `OWNER-DECISION-condition-11.md`. It changes the price of `codex login` and the
   owner should read both before deciding.
5. **NOT-CHECKED: `codex login` itself.** Owner-only credential write. Not attempted;
   `~/.codex/auth.json` not read for value.
6. **NOT-CHECKED: full CI.** Run here, all green after the commit: the gate self-test, the gate,
   `vendor_satisfiability.py`, `split_review_gate.py`, `check_published_commands.py`,
   `unitgate.py`, `charter_check.sh`, and `_i4_blobcheck.py` — which format-checks the COMMITTED
   BLOBS rather than the working tree, carrying `ruff.toml` into the temp tree so the check is not
   run against a default line length, and mangling one extracted file to prove the detector fires
   (5 blobs, 0 CRLF bytes, clean; control rc=1). The suite has roughly 25 steps and they were not
   all run.
7. **Two files in `command-center/p2-next/` are ruff-format-dirty and are NOT this lane's**
   (`_a3_idem_and_137.py`, `_a3_preedit.py`, both untracked, authored by the audit lane). They were
   deliberately left alone. If that lane commits them unformatted, the lint job goes red for a
   reason that has nothing to do with this change.
8. **SHARED FILE, declared: `command-center/E2E-WAVE-STATUS.md`.** It was clean immediately before
   the edit; the change is +7/-5 lines on a 680-line LF file, four number corrections and one
   superseded marker, with the line endings preserved. If a sibling lane is holding an edit to it,
   this is the collision to check first.
