---
title: BUILD-ROUND4-2026-08-13
type: note
permalink: dqverify-repo-20261013/command-center/ssot/build-round4-2026-08-13
---

# LANE SSOT — BUILD round 4 (final round)

STATUS: **all three CONFIRMED defects fixed and measured.** Every claim below names the
command that produced it.

If any row still reads `UNKNOWN - not yet measured`, the unit died before measuring it and
no verdict there may be cited. (None does.)

COVERAGE: §1–§6 measured. Disclosed and NOT measured: the destructive cache-side
`worktree remove` arm (R4, unchanged), the uncommitted content of `_advver_M14/scratch`
(R9, unchanged), and `classify_population.py`'s full sweep, which was deliberately not
re-run — see §3.

---

## 0. What this round fixed

Source: the round-3 adversarial verifier (`ADVVERIFY-SSOT-R3.md`), which returned
`build_is_sound=TRUE · audit_holds=TRUE · must_fix=EMPTY` and **three non-blocking
corrections**. All three are OVERCLAIMS — in each, the code is right and the sentence is
wider than its evidence. That is the estate's measured 7:5 ratio for the third round
running.

| # | verifier's correction | landed as |
|---|---|---|
| 1 | DoD-1 sentence → the scoped version (177/178, not 178/178) | `BUILD-ROUND3-2026-08-14.md` §5 REFUTED note + inventory §5a + this file |
| 2 | `CLAUDE.md:34-35` → the arithmetic must close at 178 | `CLAUDE.md` now reads 9 + 168 + **1 severed** = 178, with the old wording kept as REFUTED |
| 3 | `population-classified.json` → carry a `resolved_by` on the disagree row | `apply_severed_resolution.py`, red-proofed 5/5 |

## 1. The defects, located by measurement

`python command-center/ssot/_r4_defect_survey.py`

| # | claim as written | measured |
|---|---|---|
| 1 | `178/178, two agreeing signals` | `signals_agree True = 177`, not-True = 1 |
| 2 | `9 linked worktrees` + `168 independent clones`, population 178 | 9 + 168 = **177** |
| 3 | "the row is now resolved by a third signal" | `kind` histogram `{own-store: 168, worktree: 9, kind-signals-disagree: 1}` — **no resolution field existed anywhere in the artifact** |

Reader control: the survey must see **both** kinds before "177 agree" means anything —
`kinds>=2 and agree>0 -> discriminates=True`. A reader pointed at the wrong collection
returns one kind or zero rows, which is exactly how this lane's `manifest["events"][ev]`
mistake produced four agreeing wrong probes earlier in the program.

## 2. The third signal, validated in BOTH states before it was used

`python command-center/ssot/_r4_probe_pointers.py`

    severed-cache-copy                       dotgit=FILE     target_exists=False
    live-linked-worktree(ast-integrate)      dotgit=FILE     target_exists=True
    live-linked-worktree(wt-salvage-probe)   dotgit=FILE     target_exists=True
    main-checkout(canonical)                 dotgit=DIR      target_exists=-
    fabricated                               dotgit=MISSING  target_exists=-

**The negative rows are the load-bearing ones.** A `.git` FILE alone does not mean severed —
two LIVE linked worktrees have one too. A resolver keyed on "`.git` is a FILE" would call all
three severed, pass a positive-only control, and be inert. Keyed on *pointer-target
existence* it separates them. State the two hypotheses first (H1 "the resolver detects
severance" vs H2 "the resolver calls every `.git`-file severed") and ask what a PASS looks
like under each: only this form differs.

## 3. What landed, and what was deliberately not re-run

`resolve_severed()` and `kind_buckets()` live in `classify_population.py`, so a future fresh
sweep produces the same fields. `apply_severed_resolution.py` **imports** them rather than
re-implementing, so the applier and the sweep cannot drift apart.

**The full sweep was NOT re-run, on purpose.** It re-measures 178 live checkouts against a
tree that moved three times this evening; every row's head/dirty/unpushed would churn and
the one field under repair would be buried in an unreviewable diff. The applier instead
touches only rows whose two primary signals disagree, and refuses to write if anything else
about the file's shape moved. UNVERIFIED inline [likely 55–80%]: that a fresh full sweep
reproduces exactly 9/168/1 — the population is a moving target. **Settling experiment:**
run `classify_population.py` end-to-end when the box is quiescent and diff the three kind
counts, not the whole file.

`python command-center/ssot/apply_severed_resolution.py`

    CONTROL synthetic missing target -> 'severed-worktree'  expect severed
    CONTROL live linked worktree     -> 'worktree'          expect worktree
    CONTROL fabricated path          -> None                expect None
    discriminates: True

    rows=178 on_disk=178 primary-signal disagreements=1
      kind-signals-disagree -> severed-worktree  via third-signal:dotgit-file-pointer-target-missing
          pointer: C:/Users/Prekzursil/source/agent-skills-toolchain/.git/worktrees/agent-skills-toolchain
          target exists: False

    kind arithmetic: 9 worktrees + 168 clones + 1 severed + 0 unresolved = 178 vs on_disk 178 -> closes=True
    SUCCESS:apply-severed resolved=1 unresolved=0 rows_changed=1 arithmetic_closes=True

Idempotent: the second run reports `rows_changed=0` and the same verdict.

`signals_agree` **stays false** on that row. The two primary signals really did disagree;
deleting that record to make the row look clean would be the same overclaim pointing the
other way. The third signal adds a verdict *beside* the record, not over it — which is why
the JSON now carries `kind_signals_disagree` (1, the primary fact) **and**
`kind_signals_disagree_unresolved` (0, the resolved fact).

### The check the defect earned

`kind_buckets()` fails closed when the split stops adding up. Round 2 published "9 linked
worktrees + 168 independent clones" against a population of 178 and nobody added them up: a
number that does not close is a defect whether or not any individual row is wrong.

## 4. Red-proof — every new check fired on its broken state

`python command-center/ssot/redproof_severed.py` (mutations applied to TEMP COPIES;
`population-classified.json` is never mutated by that file)

      [OK ] healthy                      expect=0 got=0
      [OK ] floor-breached               expect=3 got=3
      [OK ] no-disagreeing-row           expect=1 got=1
      [OK ] invariant-moved              expect=3 got=3
      [OK ] arithmetic-does-not-close    expect=3 got=3
    SUCCESS:redproof-severed cases=5 all fired

`healthy` is the positive control: without it the four reds would prove only that the
applier *can* fail, not that it can distinguish. `arithmetic-does-not-close` reproduces
round 2's exact shape — a live row in no bucket, sum 178 vs on_disk 179.

**A sixth red-proof happened by accident and is the most convincing one.** Naming two new
`.py` receipts inside `CLAUDE.md` turned `test_the_scratch_copy_is_green_before_mutation`
RED with `W3-referenced-path-missing`, because the scratch copy did not carry them. That is
the W3 wire firing on a real, unplanned defect — observed red, then green after
`COPY_PATHS` was extended. The suite is not vacuous.

## 5. Gates, measured after the last edit

| gate | result |
|---|---|
| `python command-center/ssot/ssot_wiring_check.py` | `SUCCESS:ssot-wiring-check wires=6 all intact` |
| `python -m pytest ci/tests/test_ssot_wiring.py -q` | `16 passed` |
| `python -m pytest ci/tests -q` (the whole suite CI runs, under `longrun`) | **`1 failed, 842 passed, 1 skipped in 103.82s`** — see below |
| `ruff format` / `ruff check` (0.15.17, the CI pin) on every touched `.py` | reformatted, then `All checks passed!` |
| `python command-center/ssot/_blob_ci_check.py 874a66b5` | `SUCCESS:blob-ci-check files=6 lint=0 format=0` · **0 CRLF** across the extracted blobs · mangled-file control **FIRED** |

**The one failure is not mine, proven by two independent signals rather than asserted.**
`test_check_skill_dual_write.py::test_strict_parity_keeps_distinct_invalid_utf8_path_bytes_distinct`
dies on `os.fsdecode(b"\xff")` → `UnicodeDecodeError`, a Windows platform difference in
another lane's suite. (a) Neither of my commits touches that file —
`git show --name-only 874a66b5 c3cfefde | grep skill_dual_write` is empty. (b) The failing
expression is byte-identical in the PRE-fix blob `874a66b5^:ci/tests/test_check_skill_dual_write.py`.
Last touched by `f15cddbf`, a different lane. **NOT-CHECKED:** whether it also fails on the
Linux CI runner — I cannot run that from here, and it is plausible this is Windows-only.

**A first `longrun` invocation reported `exit code 0` while the suite never ran** (the bash
wrapper rejected `-Id` with `Unknown option`). Taking that green would have been a
completion claim resting on a wrapper's exit code rather than on any test result — the
single-signal failure this lane keeps measuring. The number above is from the re-run.

### The committed state verified in BOTH states

`python command-center/ssot/_r4_verify_committed.py <rev>` reads the STORED BLOBS
(`git show <rev>:<path>`, not the CRLF working tree, and not `git archive`, which converts).

    at HEAD          -> SUCCESS:r4-verify-committed checks=14 all pass (blob form)
    at 874a66b5^     -> FAILED:r4-verify-committed 9 of 11 checks failed

The pre-fix run is the control. Exactly two rows stay green there, and they are the right
two: *primary disagreement still recorded* and *round-3 original wording kept* — the facts
this round PRESERVED rather than created. A verifier green in both states would measure
nothing.

## 6. Definition of Done (lane), re-scored with this round's scope

| DoD item | status |
|---|---|
| every clone classified worktree-vs-clone by measurement | **PASS, correctly scoped** — **177 of 178** by two agreeing primary signals; the 178th by a third signal validated in both states. The artifact now records both facts. Round 3's `178/178` is REFUTED and kept |
| unique-content measured per clone | **PASS** — 173 by unpushed+dirty+staged, the 5 remote-less at blob level (0 unique committed bytes). Unchanged this round; the round-3 verifier CONFIRMED it by an independent hasher (7,645 raw-absent blobs, 7,645 CRLF, **0** absent both ways). Residual R9 (uncommitted content in a 0-commit tree) still disclosed, not folded in |
| inbound-reference measured per clone | **PASS** — config corpus at 178, plus Scheduled Tasks + PATH + env with both-states controls, plus the verifier's three extra surfaces (MSYS/UNC path shapes, registry Run/RunOnce, Startup folder). **Retire candidates affected by all of it: 0** |
| a one-sentence SSOT rule written | **PASS** — sentence unchanged; wire gate green and its 16 mutation red-proofs pass, measured after the last edit |
| nothing deleted | **PASS** — 6/6 source paths still present with a fabricated control reading False; canonical still registers 5 worktrees; every probe read-only; no `worktree` subcommand run anywhere |

## 7. Residuals

1. **R4 destructive arm still untested, by choice.** Whether a cache-side `worktree remove`
   reaches the 3 armed targets is UNVERIFIED. **Settle:** against a throwaway worktree,
   never a live one. Never run a `worktree` subcommand from the plugin cache — `repair`
   rewrites links bidirectionally and would repoint the real trees at the cache.
2. **R9 — `~/source/_advver_M14/scratch`** remains the sharpest exposure: 0 commits, no
   remote, thousands of untracked entries in no store anywhere. Unchanged this round.
3. **43 retire candidates identified; nothing retired, nothing deleted.** Prefer moving a
   directory aside over `git worktree remove`.
4. **A fresh full sweep has not been run** (§3). The three kind counts are inherited from
   round 2's sweep with one row's kind corrected.
5. **Two sibling-refreshed receipts left dirty and uncommitted:** `drift-gate.json`
   (`behind` 198 → 322) and `salvage-atrisk.json` (a re-run that reports the salvaged blobs
   as reachable — true *after* the salvage, but it overwrites the salvage receipt fields, so
   landing it would delete the evidence). Neither is mine to land. `population-classified.json`
   carried the same kind of refresh in 3 hunks and had to be committed with my fix; disclosed
   in the commit message.
6. **Every count is a snapshot.** `main` moved during this round. Re-run before acting.
7. **One pre-existing suite failure on this box, outside this lane** (§5). Reported, not
   touched, and NOT-CHECKED on Linux.
8. **The verifier's own residual, carried unchanged:** whether a reference to a checkout
   exists on a surface nobody has read — Windows services, WMI event subscriptions, IDE
   workspace files, shell rc files outside the corpus roots. **Settle:** extend
   `inbound_surfaces.py` with a services + `Get-CimInstance __EventFilter` surface, each
   with the same synthetic-row control.
9. **Not pushed.** Local `main` is ahead of `origin/main`.