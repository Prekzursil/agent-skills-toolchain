# P2NEXT — INTEGRATE lane, round 2: the sweep that closed round 4's residual was reachable by nobody

STATUS: COMPLETE. Every claim below was executed; the commands and their real output are in §3
and §5.

COVERAGE: §1-§5 measured. §6 is what is NOT done, inline, each with its settling experiment. Two
things stay unmeasured and say so there: full CI (a Windows-local green is not CI green, and this
workflow has still never executed on a GitHub runner), and whether the 39 owed units would PASS a
Codex review.

## 0. What this lane inherited

The prior INTEGRATE round wired `rail_count_gate.py`, `vendor_satisfiability.py` and
`split_review_gate.py` into `.github/workflows/p2next-rail-count.yml`. Round 4 then added C6 — the
citing-page consistency check — and closed its own residual 3 by writing `_k4_tree_survey.py`, a
whole-tree sweep for pages still asserting the retracted "the rail is DOWN" verdict. It ran the
sweep once, committed the receipt, and disclosed what remained:

> a NEW owner-facing page could assert it tomorrow and C6 would not scan it

That residual cannot be closed by a survey run once by hand, because **the next page is written
after the survey ran**. And the survey itself had gone the way of every other fixed-but-unwired
script in this program: `git grep` finds `_k4_tree_survey.py` referenced **only inside its own
docstring** — not by a workflow, not by a test, not by a doc's run line. It was tracked,
fail-closed, correct, and reachable by nobody.

## 1. Reachability inventory — measured, not assumed

| P2NEXT deliverable | reachable? | by what |
|---|---|---|
| `rail_count_gate.py` (C1–C6) | YES | `.github/workflows/p2next-rail-count.yml` |
| `vendor_satisfiability.py` | YES | same workflow |
| `split_review_gate.py` | YES | same workflow |
| `claim_gate.py` anchor fixes (rounds 1–2) | YES | `quality.yml:1046-1050` — self-test + suite + mutations |
| **`_k4_tree_survey.py`** | **NO** | nothing but its own docstring |

I expected the claim-gate work to be the unreachable one and it was not — it has been in
`quality.yml` all along. Reading the instrument beat the inference, which is the whole lesson of
this program.

## 2. Where the work is now reachable from

| surface | what changed |
|---|---|
| `.github/workflows/p2next-rail-count.yml` | two new steps: `gate-p2next-tree-survey self-test`, then `gate-p2next-tree-survey`. 8 steps total, parsed and ordered. |
| `command-center/p2-next/_k4_tree_survey.py` | gains `--check` (derive + assert, never write) and `--self-test` (6 cases, 2 expecting a hit). Classification split out of `main()` into `classify()` so it is testable without git. |
| `ci/tests/test_p2next_tree_survey_wiring.py` | **new.** 6 tests that fail if the wiring is removed. Runs in `skill-dual-write.yml:65`'s `python -m pytest ci/tests …` directory sweep. |

**Why `ci/tests/` is where a wiring test actually runs.** `quality.yml:685` states outright that
`ci/tests/` has **no tree-wide step**, so a suite dropped there is invisible to quality.yml unless
a step names it. `skill-dual-write.yml:65` *does* sweep the directory. That step is also **first**
in its job, ahead of the `--strict-parity` step at line 181 that carries this repo's known
pre-existing dual-write violation — so the wiring test executes even while that blocker is
unresolved. Both facts were read from the workflows, not assumed.

**Why `--check` exists.** Round 2 of this lane had to fix `vendor_satisfiability.py` because
re-running it REWROTE the artifact it verified. `_k4_tree_survey.py` had the identical shape:
`main()` wrote `K4-TREE-SURVEY.json` on every run, including a verifying one. CI now runs
`--check`. A test pins that CI uses the non-writing form, so the gate cannot launder its own
receipt.

**Why the self-test runs first, and why two of its cases expect a HIT.** A gate that has never
failed is indistinguishable from a no-op (`ci-hygiene.md` §1), and a suite whose cases all expect
SILENCE proves only that the instrument runs.

## 3. The end-to-end proof — `_l1_redproof.py`, receipt `L1-REDPROOF.json`

The claim under test is not "the survey passes today". It is the two-part integration claim:
**without this wiring the defect ships GREEN, and the check that proves the wiring exists goes RED
the moment the wiring is removed.** The probe clones the repo, commits this lane's files into the
clone, and measures four states.

```
python command-center/p2-next/_l1_redproof.py
  ok  0 GOOD state: survey rc=0 gate rc=0 wiring-test rc=0 (want 0/0/0)
  ok  A new live page asserts DOWN: survey rc=1 (want 1 = RED), rail_count_gate rc=0
        (want 0 = BLIND, which is why the sweep was needed)
  ok  B same sentence in a round artifact: survey rc=0 (want 0 -- use-vs-mention, not
        'the word DOWN is bad')
  ok  C wiring steps deleted: wiring test rc=1 (want non-zero -- the check must FAIL when
        the integration is missing)
SUCCESS:l1-redproof the sweep goes red on a page the pre-existing p2next CI ships green,
        and its wiring test goes red when the wiring is removed
```

Three things in that output carry the weight, not the four OKs:

- **Leg A measures the pre-existing gate BLIND on the same injection.** A red-proof that only
  showed the new gate going red would prove the sweep works, not that it was needed. `rail_count_gate.py`
  returns 0 on a page asserting the retracted verdict because C6 reads a DECLARED list.
- **The injected sentence carries NO digits, deliberately.** C2 checks unit COUNTS; a number in
  the injection would confound "blind to the state assertion" with "saw a wrong count".
- **Leg B is the use-vs-mention control.** The same sentence under `command-center/p2-next/` leaves
  the sweep green. Without it, leg A is indistinguishable from "the word DOWN is bad".

Leg C is the answer to *"prove it end to end with one executable check that would FAIL if the
integration were missing"*: the workflow steps are stripped in the clone and
`ci/tests/test_p2next_tree_survey_wiring.py` goes from `6 passed` to `rc=1`.

## 4. A failure of mine, and the control that caught it

The `ci/tests` sweep returned **4 failed, 912 passed**. Two hypotheses — my change broke them, or
they are pre-existing on this box — and the failing names (invalid-UTF-8 path bytes, an executable
mode bit, a git race injector) *looked* obviously Windows-local. Looking obvious is not a
measurement. `_l2_pre_existing_control.py` clones HEAD, which carries none of this lane's
uncommitted files, and runs the same four node ids there:

```
clone HEAD=095973eb  my wiring test present in clone: False (want False)
pytest at HEAD rc=1
  4 failed in 4.23s
SUCCESS:l2-control H2 CONFIRMED -- these 4 fail at HEAD, which carries none of this lane's
        files, so they are pre-existing and not introduced here
```

The `want False` line is the part that makes it a control: a clone that somehow carried my files
would make "pre-existing" unfalsifiable. My 6 new tests added 0 failures.

Earlier in the round I also reported `_k4_tree_survey.py` as untracked, on the strength of one
commit's `--stat` not listing it. `git ls-files` says it is tracked — it was committed a commit
earlier. A commit's file list is not a tracked/untracked test.

## 5. Gate sweep — measured on the working tree, after the reformat

`ruff format` rewrote all three files after they first went green, so every check below was
**re-run against the reformatted bytes**; the pre-format greens were measured on different files
and are not cited.

| gate | result |
|---|---|
| `_k4_tree_survey.py --self-test` | PASS — 6 cases, 2 expecting a hit, both states |
| `_k4_tree_survey.py --check` | SUCCESS — 66 candidate lines, 0 LIVE, 4 historical, control True |
| `pytest ci/tests/test_p2next_tree_survey_wiring.py` | 6 passed |
| `pytest ci/tests tools/d001-dual-write/tests` (the exact CI command) | 912 passed, 4 failed — all 4 pre-existing at HEAD (§4) |
| `_l1_redproof.py` | SUCCESS, 4/4 legs |
| `_l2_pre_existing_control.py` | SUCCESS, H2 confirmed |
| `rail_count_gate.py --self-test` | PASS — 50 cases, 27 expecting a FIRE |
| `rail_count_gate.py` | SUCCESS — 52 / 42 (39 owed, 3 served) / 10 / 10; C6 declares UP probed 2026-08-14 |
| `vendor_satisfiability.py --basis committed` | SUCCESS |
| `split_review_gate.py --basis committed` | SUCCESS |
| `_k2_redproof.py` (round 4's, must survive) | SUCCESS |
| `_j3_redproof.py` (round 3's, must survive) | SUCCESS |
| `ruff@0.15.17 check` / `format --check` (4 files) | All checks passed / already formatted |
| workflow YAML | parses; 8 steps; self-test at 6, gate at 7, in that order |
| line endings | 0 CRLF across all 5 touched files |

## 6. Residual — inline, not blocking

1. **NOT-CHECKED: this workflow has still never executed on a GitHub runner.** Everything above is
   local plus a local clone. Untested runner assumptions: `git grep HEAD -- *.md` behaves on the
   `fetch-depth: 0` checkout as it does here, and `ubuntu-latest` python 3.11 matches local 3.14
   for these scripts. Settling experiment: push and read the run.
2. **THE LANE'S LAST TWO ROUNDS HAVE NO VERIFIER ARTIFACT, AND NEITHER DOES THIS ONE.** Round 4's
   own artifact records that two mechanically different searches found nothing newer than
   `P2NEXT-VERIFY-R4.md`, which verifies round *2* — so rounds 3 and 4 are self-verified, and this
   round is a third. Every "SUCCESS" here is my own instrument reporting on my own work.
   Settling experiment: a fresh-context reviewer runs `_l1_redproof.py` and
   `pytest ci/tests/test_p2next_tree_survey_wiring.py` from a clone and confirms leg C fails when
   the steps are stripped. **This is the honest ending, not a clean one.**
3. **MY OWN SPAWN BRIEF IS STALE AND ITS HEADLINE PREMISE IS REFUTED IN-TREE.** It states the
   cross-vendor rail is DOWN, that `codex login` is the fix, and gives 48 blocked / 43-of-47
   cross-vendor. The committed page declares `rail_state: up`, `rail_probed: 2026-08-14`, and
   52 blocked / 42 rail-blocked / **39 owed, 3 already served** / 10 satisfiable, all 10 reviewed.
   I did not re-probe the rail — round 3 did, on two transports with a control — so this is a
   pointer to their measurement, not a fresh one of mine.
4. **The sweep is phrasing-blind, and I measured exactly how far.** Executed against `classify()`:
   `'The rail is DOWN and cannot be used.'` → CAUGHT; `'The rail is down.'` → CAUGHT;
   `'The rail does not answer.'` → **missed**; `'The review rail remains unavailable.'` →
   **missed**; `'Codex cannot be reached; the rail is unusable.'` → **missed** (it contains
   "rail is" and still misses, because the gate's predicate keys on a small state vocabulary, not
   on the grep pattern). This is the same negation/synonym blindness round 4 disclosed for C6,
   now with concrete strings. It also scans `*.md` only. Settling experiment: add a negation
   window and a synonym set to `STATE_ASSERT` in `rail_count_gate.py`, then re-run
   `_k1_premise_scan.py`, which must still find exactly 3 assertions in the owning doc and 0 in
   the citing one.
5. **`--check` means the committed `K4-TREE-SURVEY.json` can go stale without CI noticing.**
   Deliberate: the historical bucket legitimately grows every round, so byte-comparing the receipt
   would red CI on normal work. What is gated is the LIVE bucket being empty, which is the claim
   that matters. The receipt is a record, not the contract.
6. **The dual-write blocker is unchanged and NOT implicated here** — this round touches no
   `.agents/skills/**` file. It remains a pre-existing, systemic, escalated owner/orchestrator
   decision (mirroring the ~12 canonical-only skills is a skill-surface policy call; editing the
   checker so a commit goes green is the anti-pattern the gate exists to prevent).
7. **Condition 11 is still the delivery ceiling and still bounds the price of `codex login`.**
   `receipt_schema_gate.py:520-521` rejects while nothing in production sets
   `manifest_registration.registered`. `codex login` buys review capacity for the 39 owed units and
   delivers zero of them. The two owner decisions must be priced together.
8. **NOT-CHECKED: full CI.** ~14 of roughly 25 steps ran locally. Not run: the node/npm steps,
   CodeQL, gitleaks, and the hook/workflow gates owned by sibling lanes.
9. **NOT-CHECKED: `codex login`.** Owner-only credential write (AGENTS.md §9). Not attempted;
   `auth.json` never read.
10. **SHARED FILE, declared: `.github/workflows/p2next-rail-count.yml`.** Only ever touched by
    p2next commits (`0c64b983`, `00d0a311`), so the collision risk is low — but if a sibling lane
    is holding an edit to it, this is the first place to look. `quality.yml` was NOT touched.
