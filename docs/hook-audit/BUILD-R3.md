# HOOKRESEARCH — BUILD round 3 (re-entry after a CONFIRMED refutation)

A verifier CONFIRMED one real defect and four overclaims against BUILD round 2, and surfaced one
open residual the lane had never claimed. This round fixes the defect, fixes the SENTENCES — the
refuted wording is recorded here, not deleted — and closes the residual with an executed sweep.

Every number below was produced by a probe in `command-center/hook-audit/` that re-runs, and every
verdict carries a control that was checked in BOTH states. Where a control could not separate the
two hypotheses, the result is published as INCONCLUSIVE rather than as a number.

## 1. D1 — a measurably false statement was committed to the repo (CONFIRMED, fixed)

`.github/workflows/hook-audit.yml` documented why the citation-gate suite is wired as `python` and
not `pytest`. Its stated reason was:

> "`pytest … test_citation_gate.py -q` collects ZERO tests and **exits 0** … Wiring it the obvious
> way would have been a **permanently green no-op** (ci-hygiene section 1)."

**REFUTED.** Measured in this round, with a control before the claim was believed:

| arm | command | result |
|---|---|---|
| subject | `python -m pytest command-center/hook-audit/test_citation_gate.py -q` | `no tests ran`, **exit 5** |
| control | `python -m pytest command-center/hook-audit/test_hook_predeploy_gate.py -q` | **exit 0**, 53 passed |

<!-- uncited-table: reason=exit codes and pass counts from a live shell, reproduced three times across two invocation forms; the artifact is the command itself, not a JSON blob -->

The control matters: it proves the instrument *can* return 0 in the same shell, so exit 5 is a
property of the subject and not of the environment. No pytest configuration governs this path —
there is no root `pytest.ini`, `pyproject.toml`, `tox.ini`, `setup.cfg` or `conftest.py`.

**The consequence inverts, and that is the part worth keeping.** Exit 5 is non-zero, so a GitHub
`run:` step fails on it. The naive wiring would have turned the workflow **RED without ever
executing the 24 cases** — loud and wrong, not silently green. `python` remains the correct wiring,
but for the opposite reason to the one recorded. The `ci-hygiene §1` citation was also misapplied:
that rule is about a `python -m` gate whose module has no `main()`, which is not this file's
failure mode.

Fixed in the workflow header, with the false version quoted in place rather than swapped out.

## 2. O1–O4 — four sentences wider than their evidence

Round 2's own commit `01febbed` adopted the rule "stop citing a number that changes every time a
sibling commits" and then left three of these in place. Each is corrected below with the scope that
was actually measured.

### O1 — the exit-0 claim, repeated in the report

Same refutation as D1. It appeared in the round-2 evidence block *and* in a confidence line rated
ALMOST CERTAIN. **Correctly scoped:** pytest collects zero tests and exits 5
(`EXIT_NOTESTSCOLLECTED`) because the file is a standalone script with `main()`; the naive wiring
fails CI loudly instead of passing silently.

### O2 — "188 citations checked" (three numbers for one quantity)

The report said 188, the workflow header said 181, and the gate printed 189. None was wrong when
written: the count moves whenever **any** lane commits a document or an evidence file.

**Correctly scoped:** the count is not a stable fact and must not be pinned anywhere. The pinned
number is now removed from the workflow header, which prints its own count at run time. The gate's
value is that *every* citation is mutated and required to go red — not that the total is any
particular integer.

### O3 — "before the fix `2 failed, 15 passed`" (understated; direction favours the builder)

Re-measured by materialising both files from their stored blobs and running each arm
(`_b11_redfirst.py`, evidence `B11-REDFIRST.json`):

- pre-fix arm: **3** failed <!-- cite: id=R3-rf-f file=B11-REDFIRST.json path=arm_old.failed value=3 -->,
  **14** passed <!-- cite: id=R3-rf-p file=B11-REDFIRST.json path=arm_old.passed value=14 -->
- post-fix arm: **0** failed <!-- cite: id=R3-rf-nf file=B11-REDFIRST.json path=arm_new.failed value=0 -->,
  **17** passed <!-- cite: id=R3-rf-np file=B11-REDFIRST.json path=arm_new.passed value=17 -->
- the published claim does **not** reproduce <!-- cite: id=R3-rf-repro file=B11-REDFIRST.json path=published_claim_reproduces value=False -->

The third red test is `test_main_blocks_secret_write`, whose assertion was re-pointed in the same
commit. **Correctly scoped:** 3 of 17 go red against the pre-fix hook. Red-first was *stronger*
than claimed, which is why this is an overclaim about direction and not a broken fix.

Controls: the post-fix arm must be green <!-- cite: id=R3-rf-c1 file=B11-REDFIRST.json path=controls.C1_new_arm_green value=True -->
(without it, a red pre-fix arm cannot be told from a test file that cannot pass in this layout);
the arms must discriminate <!-- cite: id=R3-rf-c2 file=B11-REDFIRST.json path=controls.C2_arms_discriminate value=True -->;
and both arms must collect the same suite <!-- cite: id=R3-rf-c3 file=B11-REDFIRST.json path=controls.C3_same_test_count value=True -->,
which is the "comparing two DIFFERENT files" trap.

### O4 — "prior art fired 5 hooks to prove inertness" (understated)

`B6-FLEET.json` records **6** rows with verdict `INERT-CONFIRMED`
<!-- cite: id=R3-inert file=B6-FLEET.json path=inertness.verdicts.INERT-CONFIRMED value=6 -->,
and all six carry `ran=true`. The sixth is `checkpoint`; the round-5 prose enumerated five by name
and handled `checkpoint` separately because it had been settled dark by four other signals, so the
list and the field disagreed. **Correctly scoped:** six hooks were fired and proven inert —
`checkpoint`, `compute-confidence-gate`, `figma-mirror`, `mvt-patch-leaving`, `recall-gate`,
`skill-router`.

The counting probe (`_b11_inert_count.py`) carries a control that a non-fired row may never carry
the `INERT-CONFIRMED` label, which is the whole distinction between *proven* inert and *asserted*
inert.

## 3. R1 — the open residual: what did the 25 timing rows actually measure?

The verifier's residual was that `Stop/git-hygiene`'s `run_ms=0.3` is a throttle early return, and
that the diagnosis was never swept across the other 24 rows — so DoD-1 ("every wired hook timed
against its budget") was wider than its evidence. `_b11_earlyreturn_sweep.py` closes it.

**First, what `run_ms` is.** `_h4_timing.py:160-184` imports each check (`load_ms`) and then calls
`main()` **in-process** (`run_ms`). It is the body of `main()` on one synthetic payload per event —
not a subprocess, not the dispatcher, not a live turn.

**Three hypotheses explain a sub-millisecond row,** and they need different fixes: the hook is
genuinely cheap (REAL); a throttle/cache guard returned early (FASTPATH); or `main()` exited
because the synthetic payload is not the state it reacts to (DECLINED). The third is separable
without firing anything, because `_h4_timing.py:143` records whether each check's own matcher
accepted the payload's `tool_name` — and then calls `main()` **anyway**.

Measured across all 25 rows, and the three classes partition them exactly
<!-- cite: id=R3-sw-part file=B11-EARLYRETURN-SWEEP.json path=partition_exact value=True -->:

| class | rows | what the number is |
|---|---|---|
| DECLINED-BY-MATCHER | 7 <!-- cite: id=R3-sw-dec file=B11-EARLYRETURN-SWEEP.json path=n_declined_by_matcher value=7 --> | a timing of a call the dispatcher would never have made |
| RAN-SILENT | 15 <!-- cite: id=R3-sw-sil file=B11-EARLYRETURN-SWEEP.json path=n_ran_silent value=15 --> | matcher accepted, `main()` produced nothing |
| WORKED | 3 <!-- cite: id=R3-sw-wrk file=B11-EARLYRETURN-SWEEP.json path=n_worked value=3 --> | the only rows that timed a hook doing something |
| total | 25 <!-- cite: id=R3-sw-tot file=B11-EARLYRETURN-SWEEP.json path=rows_total value=25 --> | |

The seven DECLINED rows are the checks whose matcher rejects the probe payload's `Edit`:
`memory-spool/flush_check`, `claim-guard/ledger-write` (`Bash`), `bg-registry/register` (`Task`),
`memory-spool/spool`, `dup-guard` (`Write`), `monitor-autolaunch`, `codex-monitor-autolaunch`. The
three WORKED rows are `SessionStart/heartbeat`, `SessionStart/open-loops/resurface` and
`Stop/wire-check`.

**So DoD-1, correctly scoped:** *every wired check's `main()` was invoked once, in-process, on one
synthetic payload per event, and its wall time compared to its declared budget. Seven of those
invocations were made with a payload the check's own matcher rejects, and twenty-two produced no
output at all. Three rows time a hook that did work.* The original sentence — "every wired hook
timed against its budget" — implies a cost model the artifact does not support, and the strongest
counter-example is the one already known: `git-hygiene` records `0.3 ms` while its real cost is
seconds.

### The detector was validated against the known-broken state

A sweep that cannot re-find the one row already proven broken is measuring nothing. `git-hygiene`
is therefore run as a POSITIVE CONTROL, with its throttle defeated via `GIT_HYGIENE_THROTTLE_SEC=0`
on the repo copy (its stamp is gitignored), and the stamp's bytes and mtime restored and re-read
afterwards <!-- cite: id=R3-sw-stamp file=B11-EARLYRETURN-SWEEP.json path=executed_arms.positive_control_git_hygiene.stamp_restored_exact value=True -->.
The control fires <!-- cite: id=R3-sw-c3 file=B11-EARLYRETURN-SWEEP.json path=controls.C3_positive_control_detects_known_early_return value=True -->.

The defeated/effective ratio is deliberately **not** published as a pinned value. Across five runs
of the same arm it measured 29.1x, 83.4x, 104.3x, 109.8x and 165.6x — the direction is unambiguous
and the magnitude is not stable, so the citable claim is the boolean, and the honest statement is a
range. (The ratio is damped relative to `R4-GITHYGIENE-RANGE.json`'s 137.4x because both of my arms
are subprocesses and each pays interpreter start; that is a difference in method, not a
disagreement.)

### The one open case I tried to settle by execution came back INCONCLUSIVE

`Stop/heartbeat` looked like a second FASTPATH candidate. It is **not** confirmed as one
<!-- cite: id=R3-sw-hb file=B11-EARLYRETURN-SWEEP.json path=executed_arms.open_case_heartbeat_stop.status value=INCONCLUSIVE -->,
and my arms never separated the two states
<!-- cite: id=R3-sw-hbsep file=B11-EARLYRETURN-SWEEP.json path=executed_arms.open_case_heartbeat_stop.states_separated_by_emitted_bytes value=False -->.

What the attempt did establish: with the manifest's argv, both calls emit nothing and write no
state, so the silence is the **"healthy → silent"** branch at `heartbeat.py:210` ("only when
noteworthy AND past the throttle window") — the throttle was never on the path. The early-return
hypothesis is **unsupported** here, not confirmed. UNVERIFIED inline: no cost number for
`Stop/heartbeat` may be cited from this round. **Settling experiment:** redirect `BG_REGISTRY_DIR`
and `MEMORY_SPOOL_DIR` to scratch dirs seeded with an open background job and an unflushed spool
entry so the noteworthy branch is taken, then compare first call against immediate second call.

### A finding that came out of my own failures: five checks take argv, and a probe that omits it runs a different program

The manifest hands `args` to 5 of the 25 checks — `Stop/heartbeat` gets `["stop"]`. Three
successive heartbeat arms passed no argv, so `heartbeat.py` fell through to its `sessionstart`
branch and returned a `hookEventName: "SessionStart"` envelope while I was feeding it a Stop
payload. Three arms agreed with each other and all three were void. Any future probe that fires a
check must pass the manifest's argv or it is not testing the wired program.

## 4. Detector controls, and the do-not-fire list

| probe | control that had to hold |
|---|---|
| `_b11_redfirst.py` | post-fix arm green; arms discriminate; both arms collect the same suite |
| `_b11_inert_count.py` | reads `inertness.rows`, fails closed on the wrong collection; a non-fired row may never carry `INERT-CONFIRMED` |
| `_b11_earlyreturn_sweep.py` | reader not blind; classes partition exactly; positive control re-detects the known early return |
| `_b11_matchers.py`, `_b11_args.py` | read `events[ev]["checks"]`, fail closed below 20 checks |

<!-- uncited-table: reason=index of which control guards which probe; every value is asserted and cited at its point of use above, not re-cited here -->

Hooks that write to owner state stores or spawn processes were **not** fired, and the reason for
each is recorded in the evidence blob: the two autolaunch checks launch external monitors, and
`claim-guard/ledger-write`, `stub-ledger/record`, `edit-validate/record`, `bg-registry/*` and
`memory-spool/*` write the event ledger, background registry and memory spool. For those rows the
classification rests on the recorded matcher field, which is evidence; no cost number was invented
for them.

## 5. Self-corrections made before publishing (recorded, not deleted)

1. **Read the wrong collection, and it failed closed.** `_b11_inert_count.py` first read
   `data["inertness"]` as the row list. It is a dict — the same one-level-too-high error that
   produced four false parity readings earlier in this program. It exited 2 rather than counting
   three key names.
2. **Read the wrong field.** My first H4 dump printed `check` and got `None` for all 25 rows; the
   field is `name`. A blind reader that prints `None` is more honest than one that prints a
   plausible wrong number, but it was still the recurring failure of this audit.
3. **Published a ratio that measured nothing, twice, then a third time.** The heartbeat arm went
   through three revisions — live-vs-scratch state dir, then first-vs-second call, then a pinned
   throttle window — each returning a ratio near 1.0 that I could have published as "the throttle
   is not what makes this row fast". Reading the arms' own output refuted it each time: both arms
   emitted identical bytes, so both were in the same state. The root cause was the missing argv.
   The probe now reports INCONCLUSIVE by construction when the states do not separate.
4. **The citation gate caught me.** Committing this document's skeleton took the gate red with
   `BUILD-R3.md — ZERO citations`. That is the gate doing exactly what it was wired for, on its
   author, within minutes of being wired into CI.

## 6. What this round did NOT do

- The `commands/rollback.md` edit remains handed off — it is outside this lane's file scope.
- The `agent-self/config/settings.json` SessionEnd hazard is unstarted; it stays contained by a
  failing gate axis, which is containment, not a fix.
- Behavioural equivalence for the 12 DIVERGED wired hook bodies is still unmeasured, so
  "do not bulk-copy the trees" still stands.
- Per-hook wall time was **not** re-timed fleet-wide. This round re-scoped what the existing
  timing artifact means; it did not replace it.
