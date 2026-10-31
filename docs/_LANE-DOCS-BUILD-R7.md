---
title: _LANE-DOCS-BUILD-R7
type: note
permalink: dqverify-repo-20261013/docs/lane-docs-build-r7
---

# LANE DOCS — BUILD round 7 (re-entry after a CONFIRMED refutation of round 6)

COVERAGE: every row in §2 is backed by a command I executed this round. NOT measured here, and
said so rather than folded into a pass: a real CI run, a fresh-clone run of the whole suite, the
full `ci/tests` sweep, and `validate-all-skills.ps1` over 337 skills. See §6.

> If this document still reads `UNKNOWN - not yet measured`, the unit died before measuring
> anything and no verdict here may be cited.

---

## 0. What round 7 is for

Round 6 (`65af5451`, `a946b643`, `5423de0f`) corrected five evidence-hygiene defects in round 5
and pinned two counts to immutable commits. **Every one of those corrections stands.** I
re-measured all fifteen numbers round 6 asserted, by executing them rather than reading them:
`SUCCESS:docs-r7-remeasure all round-6 numbers reproduce`, 15 rows, 0 differ. Nothing round 6
*measured* is being undone.

What round 7 fixes is a **decision resting on a refuted reason**, plus the gap that let the
original defect recur in the first place:

1. **R6-7 concluded the pinned probe was "structurally unrunnable" in CI.** The premise (the
   hosting job's checkout is shallow) is true. The conclusion drawn from it is false, and the
   repo itself is the counter-example. The DECISION not to wire it survives; both REASONS given
   for it do not.
2. **Nothing protected the anchors round 6 had just added.** The defect was "a count presented as
   current"; the fix was "pin it to a commit"; but a later tidy-up could strip the anchor back off
   and no gate would notice. Round 7 ships the gate — the cheap one that can actually run where
   this suite runs.

---

## 1. Starting state (executed, not assumed)

```
HEAD at entry     9cc80f55 2026-08-14      HEAD at exit  f25b429f (siblings committed 4x during
branch            main                                   the round; 293 -> 310 dirty paths)
3 docs suites     42 passed, exit 0        py -3.11, the interpreter CI uses
gate suite        17 passed, exit 0        ci/tests/test_command_doc_promises.py
```

---

## 2. The doc-vs-reality table for round 7

Verdict = what I measured. Resolution = fix-doc / fix-code / no-action, with the reason.

| # | claim under test | probe (executed by me this round) | verdict | resolution + reason |
|---|---|---|---|---|
| **R7-1** | R6-7: the pinned probe is **"structurally unrunnable"** in CI, so it must not be wired | `docs/_lane_docs_r7_shallow_control.py` — ONE clone, ONE variable changed. Arm 1, depth-1 (what `actions/checkout` gives that job today): **rc=1**, `fatal: not a tree object`, and both pinned commits absent. Arm 2, the SAME clone after `fetch --unshallow` (== `fetch-depth: 0`): **rc=0**, `pre_fix=20/16 post_fix=19/15`. Preconditions asserted before arm 1 is believed: `.git/shallow` exists, `rev-list --count HEAD` is 1, and `cat-file -t` fails on both SHAs — without those, arm 1 failing would prove nothing | **PREMISE CONFIRMED, CONCLUSION REFUTED.** A shallow checkout does fail closed. "Structurally unrunnable" does not follow: `fetch-depth: 0` is the remedy, and **6 workflows in this repo already set it as a live YAML field — including `quality.yml` itself**, whose `secrets` job checks out with it at line 1630-1631, three lines from the setting R6 cited as proof it could not be done | **FIX DOC.** The decision (do not wire) survives on a reason round 6 did not give: the probe's inputs are **two immutable commits**, so its answer is frozen — a gate on it can never go red because reality changed, only because the probe or the checkout broke. Both refuted reasons are kept verbatim in `_LANE-DOCS-BUILD-R6.md` §4 and marked REFUTED, not deleted. |
| **R7-2** | all fifteen numbers round 6 asserted | `docs/_lane_docs_r7_remeasure.py`, with 3 kill-switch controls (census must find HEAD's own prefix; the blob reader must not return a constant; a known-absent token must score 0) | **ALL REPRODUCE** — 15 rows, 0 differ, incl. `20/16` -> `19/15`, the 22 siblings, 1 author identity, and the fetch-depth line set `[1631]` | **no action.** Round 6's measurements are sound; re-reporting them as new findings would be false. |
| **R7-3** | the anchors round 6 added are protected by something | `git grep` for any gate naming either SHA -> **none**. The 17-test suite passed identically before and after I stripped `67137879` by hand | **CONFIRMED GAP — the fix was unenforced.** The recurrence path was open | **FIX CODE.** New arm in `ci/tests/test_command_doc_promises.py` (+6 tests, 17 -> 23): the region of each carrier that states the counts must still contain its commit anchors. Two file reads, **no git history walk**, so it runs in the fetch-depth-1 job that hosts it — which is the whole point of R7-1. No workflow edit: that file is already wired at `quality.yml:1503`. |
| **R7-4** | *my own first version of that arm worked* | `docs/_lane_docs_r7_bothstates.py` — mutate the REAL file on disk, run the SHIPPED test. Result: **`FAILED: gate stayed GREEN with 67137879 stripped`** | **REFUTED — my arm was INERT.** Its expected SHAs lived in a constant *inside one of the files it checks*, so stripping the anchor from the file stripped it from the expectation too; the gate agreed with itself | **FIX CODE.** Expectation moved to `ci/tests/docs_count_anchors.py`, which is not a carrier, and a control (`test_control_the_expectation_does_not_live_in_a_carrier`) pins that. Re-run: `SUCCESS:docs-r7-bothstates fixed=0 broken=1 carriers=2 ... restored=True`. General rule this cost: **a gate whose expected value lives inside the artifact under test cannot detect that value's removal.** |
| **R7-5** | G1, the lane's charter exemplar: `/context-budget` is a published command delegating 100% to a skill that exists nowhere | `git ls-files` -> 3 command docs, still **no** skill dir; 3 repo roots and 2 live roots all ABSENT. But `commands/context-budget.md:22` now reads *"This command is self-contained — run the four phases below directly"*, and `test_context_budget_command_is_self_contained` pins it, including a clause forbidding the retirement sentence from being silently deleted | **CLOSED — and closed correctly** (fix-doc, because the doc's promise was the false part; the retired path is still named so the history is not lost) | **no action, and explicitly not re-reported.** The grounding pack listed G1 as open; it is not. Re-reporting a closed finding to pad a round is the same overclaim in a different direction. |
| **R7-6** | R6 §5: "Shipped as `65af5451` and `a946b643`" | `git log -- docs/_LANE-DOCS-BUILD-R6.md` -> **2** commits touch it: `65af5451` and `5423de0f`. `5423de0f` is a 4-line insert into §5 itself | **NOT A DEFECT.** `5423de0f` is the commit that *added* those anchors and cannot cite itself | **no action.** Recorded because "the shipped list is incomplete" is a plausible-looking finding that measurement dissolves. |
| **R7-7** | R6-7's parenthetical: line 1631 belongs to the "gitleaks" job | job-key parse -> the job key is **`secrets`**; line 1635 runs `gitleaks/gitleaks-action` | **SUBSTANTIVELY ACCURATE** (tool named instead of job key) | **no action.** |

---

## 3. What changed

### 3.1 `docs/_LANE-DOCS-BUILD-R6.md` — four sentences, refuted wording kept

Row **R6-7**'s verdict cell, its resolution cell (now carrying the *Correction (round 7)* with the
two-arm control), **§4**'s "Why it is not wired into CI" paragraph, and **§6** residual 6. The
round-6 wording is quoted verbatim and labelled REFUTED in each place rather than replaced, so a
later reader can see what the reasoning was and why it did not hold.

### 3.2 `ci/tests/test_command_doc_promises.py` — +6 tests (17 -> 23)

One gate and five controls. The gate asserts that the region of each carrier stating the round-5
surface counts still contains its commit anchors. Scope is stated inline: it proves an anchor
*survives*, not that it names the right commit — the on-demand probe settles that.

### 3.3 `ci/tests/docs_count_anchors.py` — new, 1 constant

The expectation, deliberately outside both carriers, with the reason it had to move.

### 3.4 Scope, stated up front

This round edits `ci/tests/**`, outside the lane's declared scope of `docs/**`, `README.md`,
`AGENTS.md`, `CLAUDE.md`. Stated rather than left implicit, because an undisclosed scope widening
is exactly what an audit faulted in round 5:

- both carriers of the defect are that file and `docs/_LANE-DOCS-BUILD-R5.md`; gating only the
  second would leave the recurrence path open;
- precedent: round 5 §8.5 and round 3 §7.6 record this lane owning `ci/tests/` for its own gate;
- **no workflow file was touched.** `.github/workflows/quality.yml` is the named shared hazard and
  it already runs this suite at line 1503, so the new tests reach CI with no edit to it.

`AGENTS.md`, `CLAUDE.md` and `README.md` are **not touched** — verified against the commit surface
in §5. (`CLAUDE.md` changed under me during the round; that is the SSOT lane's commit, not mine.)

---

## 4. Detector controls (each distinguishes two hypotheses)

| control | H1 | H2 | result |
|---|---|---|---|
| **shallow-arm preconditions** — is arm 1 really shallow? | `.git/shallow` present, depth 1, both SHAs absent | arm 1 failed for an unrelated reason | **PASS** — all three asserted before the arm is read |
| **two-arm difference** | remedy exists -> arms differ | structurally unrunnable -> both fail | **PASS** rc1 vs rc0 |
| **real-file mutation** (`_lane_docs_r7_bothstates.py`) | the arm reads the artifact | it agrees with itself | **FAILED first, then PASS** — see R7-4 |
| **expectation-not-in-carrier** | expectation independent | expectation moves with the artifact | **PASS** (was the failure) |
| **region ≠ whole file** | region is the count block | region is the file | **PASS** — module docstring marker absent from the region |
| **EOL agnosticism** | verdict independent of line endings | CRLF vs LF disagree | **PASS** |
| **remeasure kill-switches** ×3 | instrument can find a known-present object | zero is a dead matcher | **PASS** |
| **use-vs-mention on `fetch-depth: 0`** | count the YAML field | count the document | **PASS** — 7 files mention it, **6** set it; `rule-audit.yml` mentions it and does not set it |

---

## 5. Evidence (executed; commands and their real output)

```
remeasure      SUCCESS:docs-r7-remeasure all round-6 numbers reproduce   rows=15 differs=0
shallow ctrl   SUCCESS:docs-r7-shallow arm1_shallow=rc1 arm2_unshallowed=rc0 arms_differ=True
               verdict=NOT-structurally-unrunnable-remedy-is-fetch-depth-0        (41 s)
  arm 1        FAILED:docs-r6-pinned git ls-tree -r --name-only 67137879... rc=128
               fatal: not a tree object   ; cat-file -t on both SHAs -> Not a valid object name
  arm 2        SUCCESS:docs-r6-pinned controls=C1,C2,C3-ok pre_fix=20/16 post_fix=19/15
both-states    FIRST RUN  FAILED:docs-r7-bothstates gate stayed GREEN with 67137879 stripped
               AFTER FIX  SUCCESS:docs-r7-bothstates fixed=0 broken=1 carriers=2
                          test_command_doc_promises.py:fires _LANE-DOCS-BUILD-R5.md:fires
                          restored=True
fetch-depth    setting=1 in autofix-models, hook-audit, mcp-audit, p2next-rail-count,
               quality, skill-dual-write  (6 files) ; rule-audit mentions, sets 0
               quality.yml:1629-1631 = job `secrets`, checkout with fetch-depth: 0
probe timing   27,757 ms here vs round 6's 33,535 ms  (same order; Windows both times)
gate suite     py -3.11 -m pytest ci/tests/test_command_doc_promises.py -q -> 23 passed, exit 0
3 docs suites  48 passed, exit 0            (42 before this round's +6)
3 siblings     49 passed, exit 0            test_deploy_doc_consistency, test_rules_doc_coherence,
                                            test_rules_doc_contracts
collection     812 tests collected across ci/tests, exit 0 -- the new non-test helper module
                                            does not break collection
ruff 0.15.17   check "All checks passed!" exit 0 ; format --check "6 files already formatted"
               exit 0.  Exit codes captured BEFORE any pipe.
               CI runs `ruff format --check .` repo-wide at quality.yml:93, so this is blocking:
               my appended arm FAILED it, HEAD's version passed -> the regression was MINE,
               proven by stashing my change and re-running (HEAD_FORMAT_EXIT=0). Fixed.
EOL            byte census (CR/LF counts, not grep): all three carriers CR=0 before the round;
               CRLF after `git checkout --` restored them (autocrlf). The apply script MEASURES
               per file and re-emits unchanged.
blob gate      SUCCESS:docs-r7-blobcheck rev=HEAD files=7 blob_format=clean control_fires=True
               `ruff format --check` re-run on bytes from `git cat-file -p` in BYTE mode -- a
               PowerShell `>` redirect re-encodes and joins with the OS newline, so a
               redirect-based census of the same blob is not trustworthy. ruff.toml is carried
               into the temp root and the repo-relative path mirrored, because a bare temp dir
               makes ruff fall back to its own line-length and answer a different question.
               All 7 blobs CR=0. CONTROL: a mangled file in the SAME harness exits non-zero,
               so the green is not an inert invocation.
clone green    fresh depth-1 clone of the commit -> 23 passed, exit 0, and the new non-test
               helper module imports correctly there. That clone checked out CRLF on this box;
               the LF form CI sees is covered by the blob gate above and by the in-suite EOL
               control -- NOT by a Linux run.
diff surface   ci/tests/test_command_doc_promises.py +153/-0 (append + 1 import)
               docs/_LANE-DOCS-BUILD-R6.md +14/-6      -- no whole-file EOL rewrite
```

---

## 6. Residual, disclosed inline rather than in a footnote

1. **No real CI run, and this lane does not push.** Everything is local, on the CI interpreter
   (3.11.9). Settling experiment: push and read `gate-lint-format (ruff)` and the
   `gate-tests-coverage docs executable claims` step.
2. **Fresh-clone run: DONE for this lane's gate, not for the repo.** A depth-1 clone of the
   commit runs the 23-test suite green, and R7-1 is itself a clone experiment. What is still
   NOT-CHECKED is the *rest* of `ci/tests` from a clone, and any run on Linux — the clone
   checked out CRLF here, so the LF arm rests on `_lane_docs_r7_blobcheck.py` and the in-suite
   EOL control rather than on a real runner.
3. **Full `ci/tests` sweep NOT-CHECKED.** 812 tests collect cleanly; prior rounds measured 4
   Windows-only failures at parent `96362031` that are not this lane's. I ran the 6 suites that
   touch what I changed.
4. **TWO self-inflicted detector failures this round**, both caught by a second probe rather than
   by inspection, both disclosed:
   - `grep -c $'\r'` reported **586/586, 209/209, 254/254 CRLF** on the three carriers; a raw byte
     census returned **CR=0** on all three. The tell was the count being *exactly* the line total
     for every file. My apply script's fail-closed EOL guard refused to write on the strength of
     the correct reading, which is the only reason three files were not rewritten LF -> CRLF.
   - `(Get-Content f | Measure-Object -Line).Lines` reported **486** lines against `wc -l`'s
     **586** — it counts 0 for a blank line, and the file has 100 of them.
5. **The gate proves an anchor is PRESENT, and also that it is the EXPECTED string.**
   *REFUTED wording (round 7, kept rather than deleted): "The gate proves an anchor is PRESENT,
   not CORRECT. A future edit could replace `67137879` with a different valid-looking SHA and the
   arm would stay green."* That was inferred, never measured — round 7's own control only ever
   **stripped** an anchor (`source.replace(sha, "")`), and stripping is not replacing.
   Round 8 ran the named mutation: `docs/_lane_docs_r8_anchor_mutation.py` replaces each anchor
   with `0badc0de` in each carrier and runs the SHIPPED test — **4 mutations, 4 fired**
   (`SUCCESS:docs-r8-anchor fixed_state_rc=0 mutations=4 fired=4 verdict=H1-exact-sha
   restored=True`). The arm compares against exact SHAs held in a non-carrier module, so any
   change to the anchor string is detected, not just its removal.
   **The residual that IS real, correctly scoped:** the arm cannot check that the anchored commit
   *produces* the counts (that `67137879` really measured 20/16). That needs history. Round 8
   settled the cheap half locally — `git rev-parse 5d573583^` → `67137879`, confirming the
   "parent of the fix" claim in `docs_count_anchors.py` — and re-derived the counts themselves
   with the on-demand `_lane_docs_r6_pinned_counts.py`: `pre_fix=20/16 post_fix=19/15`, controls
   C1/C2/C3 ok. Neither can be a CI gate here, for the fetch-depth reason R7-1 measured.
6. **`docs/_lane_docs_r7_apply.py` is one-shot and now slightly stale.** `ruff format` rewrote the
   arm *after* it was applied, so re-running the script from a clean HEAD reproduces the arm in
   pre-format shape and needs `ruff format` after. It refuses to re-apply over itself.
7. **R5-1 half 2 remains UNVERIFIED [likely 55-80%]** — a fresh `claude plugin install` wiring 3
   dead plugin-root targets. Unchanged since round 5, still routed to hook-audit, still not gated
   red.
8. **`skill-dual-write.yml` still has no `push:` trigger** — carried from INTEGRATE §6.1, not mine.
9. **G3 (rollback edit-checkpoints) is still open by design**, awaiting the owner's decision with a
   round-3-reviewed plan at `docs/hook-audit/ROLLBACK-DEPLOY-PLAN.md`. Not this lane's to close.