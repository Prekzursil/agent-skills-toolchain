# HOOKRESEARCH — round 4 corrections (BUILD lane)

Round 3's independent verifier returned `build_is_sound: false` with two CONFIRMED defects
and one defect the round-3 auditor had missed. This file closes all three. Two of them were a
SENTENCE standing wider than its evidence; one was a hole in the gate that exists to catch
exactly that, and it is the one that mattered.

COVERAGE — MEASURED here: `wire.py`'s process exit code in both verdict states on both trees;
`git-hygiene`'s cost on the guarded path with the throttle defeated and the stamp restored
byte-exact; the check-vs-event budget ceiling computed over both manifests with discriminating
controls; the citation gate's new measurement-table rule proven red-first against the shipped
documents and against a pinned pre-round-4 gate.
NOT MEASURED, stated inline where load-bearing: whether a live Stop event has ever actually
hit the 35 s harness ceiling (arithmetic and a 32.7 s sample say it is reachable, not that it
happened); the LIVE copy of `git-hygiene` on the guarded path (I measured the repo copy on
purpose, to leave the live 15-minute throttle clock untouched).

If a section below still reads "UNKNOWN - not yet measured", the unit died before measuring it
and no verdict there may be cited.

---

## R4-1 — CONFIRMED: `wire.py --check` does NOT exit 0. The claim was false in two documents.

Round 3 wrote, in `HOOK-AUDIT.md` and again in `ROUND3-CORRECTIONS.md`, that
`hooks/checkpoint/wire.py --check` *"prints `FAILED:` and still exits 0 — measured"*, and
handed round 4 a one-line fix inside `hooks/**`. **There is no defect. The code fails closed.**

Three mechanically different signals now agree, and the third is mine:

1. the source — `wire.py:228` is `return 0 if verdict == "CLEAN" else 1`, reached through
   `:232` `sys.exit(main())`;
2. the verifier's shell redirect and PowerShell `$LASTEXITCODE` reads, on both trees;
3. `_r4_wire_exit.py`, which **spawns** the script and reads the real process exit status.

The control the original claim lacked, and the reason this probe is not just a fourth
assertion: observing ONE verdict cannot distinguish "always 0" from "tracks the verdict", and
observing exit 1 once cannot distinguish "always 1" from it either. So the probe drives both
verdicts through the same binary using the script's own `--settings`/`--manifest` overrides —
the real surfaces (neither half wired), and synthetic fixtures with both halves wired:

| arm | verdict | exit code |
|---|---|---|
| real surfaces | `FAILED:checkpoint-wiring` | <!-- cite: id=R4c-w-f file=R4-WIRE-EXIT.json path=repo_finding_rc value=1 --> **1** |
| synthetic wired fixtures | `SUCCESS:checkpoint-wiring` | <!-- cite: id=R4c-w-c file=R4-WIRE-EXIT.json path=repo_clean_rc value=0 --> **0** |
| live tree, same two arms | identical | <!-- cite: id=R4c-w-lf file=R4-WIRE-EXIT.json path=live_finding_rc value=1 --> 1 / <!-- cite: id=R4c-w-lc file=R4-WIRE-EXIT.json path=live_clean_rc value=0 --> 0 |

<!-- cite: id=R4c-w-d file=R4-WIRE-EXIT.json path=arms_discriminate value=True -->
`arms_discriminate=True`. If the two arms ever return the same code the probe publishes
`INCONCLUSIVE` and refuses a verdict, because at that point it has not measured the exit code
at all.

**The class, which is worth more than the instance.** The refuted sentence carried the word
*"measured"* and named no instrument. Whatever was read — a printed `FAILED:` marker, most
likely — it was not a process exit status, and no instrument that reads one can return 0 here.
An audit whose subject is "guards that cannot go red" shipped a self-reported measurement with
no named instrument, twice, and it cost round 4 a work item. Nothing was edited under
`hooks/**` as a result: the sentences were fixed, struck through rather than deleted.

## R4-2 — CONFIRMED (and missed by the round-3 auditor): the flagship table published 7 numbers no evidence file contains

`HOOK-AUDIT.md`'s DoD-1 deliverable table is the headline of this whole audit. The verifier
resolved all 7 of its numbers against `H4-TIMING-live.json`, the only committed evidence for
that measurement, and found **none** of them present — divergence 1.7x to 10.9x. I did not
take that on trust: I read the committed blob myself
(`git show HEAD:command-center/hook-audit/H4-TIMING-live.json`) and it is the verifier's
number every time. Corrected values, now cited in the document:

| number | doc said | committed evidence says |
|---|---|---|
| wire-check | 33,938 ms / 135.8% | <!-- cite: id=R4c-t-wc file=H4-TIMING-live.json path=checks.8.run_ms value=6541.6 --> 6,541.6 ms / <!-- cite: id=R4c-t-wcp file=H4-TIMING-live.json path=checks.8.pct_of_budget value=26.2 --> 26.2% |
| open-loops/resurface | 981 ms / 12.3% | <!-- cite: id=R4c-t-ol file=H4-TIMING-live.json path=checks.4.run_ms value=351.6 --> 351.6 ms / <!-- cite: id=R4c-t-olp file=H4-TIMING-live.json path=checks.4.pct_of_budget value=4.4 --> 4.4% |
| monitor-autolaunch | 73 ms / 1.2% | <!-- cite: id=R4c-t-ma file=H4-TIMING-live.json path=checks.23.run_ms value=7.8 --> 7.8 ms |
| event SessionStart | 3,798 ms / 19.0% | <!-- cite: id=R4c-e-ss file=H4-TIMING-live.json path=events.0.wall_ms value=349.1 --> 349.1 ms / <!-- cite: id=R4c-e-ssp file=H4-TIMING-live.json path=events.0.pct_of_budget value=1.7 --> 1.7% |
| event Stop | 24,976 ms / 71.4% | <!-- cite: id=R4c-e-st file=H4-TIMING-live.json path=events.1.wall_ms value=14895.7 --> 14,895.7 ms / <!-- cite: id=R4c-e-stp file=H4-TIMING-live.json path=events.1.pct_of_budget value=42.6 --> 42.6% |
| event PostToolUse | 1,115 ms / 7.4% | <!-- cite: id=R4c-e-po file=H4-TIMING-live.json path=events.2.wall_ms value=137.9 --> 137.9 ms |
| event PreToolUse | 1,416 ms / 9.4% | <!-- cite: id=R4c-e-pr file=H4-TIMING-live.json path=events.3.wall_ms value=236.3 --> 236.3 ms |

### The gate was GREEN the whole time. That is the actual defect.

`check_citations.py` was built in round 2 to stop a published number drifting from its
evidence, and hardened in round 3 with three fixes. It reported `SUCCESS` over this table for
two rounds. Not because it resolved the numbers and agreed — **because the table carried zero
`cite:` markers, and every rule in the gate operates on a marker.** An unmarked number was not
"unbacked" to this gate; it was invisible. The per-document floor added in round 3 was
satisfied by twelve markers elsewhere in the same file, thirty lines higher up.

That is hole **H4**, closed here: a markdown table that publishes a MEASUREMENT (a number
carrying ms / s / % / x / B) must carry a `cite:` marker **inside the table block**, or be
preceded by `<!-- uncited-table: reason=... -->` naming why not — a waiver with no `reason=`
is itself a violation, for the same reason `NO_CITE_EXEMPT` demands one.

**Sized against the corpus before the rule was chosen, not after.** `_r4_table_scan.py` counted
**6** measurement tables in `docs/hook-audit/`, **3** already carrying inline markers — so the
rule would flag 3, a floor the corpus can actually meet. (Those are the pre-round-4 counts; this
round's own corrections added tables, and the live count the gate now prints is 11 scanned / 0
uncited.) That sizing mattered: a gate that fires on everything trains the reader to ignore it,
and "hooks that fire so noisily they are ignored" is one of this audit's own axes. Scoping the
rule to tables is deliberate — prose numbers remain uncovered, disclosed here rather than
silently claimed.

*A detector failure of mine, caught and recorded rather than deleted:* the first
`_r4_table_scan.py` carried its own copy of the classifier, and once the waiver mechanism
existed it reported "WOULD FLAG: 3" while the gate reported "0 uncited" **on the same corpus in
the same minute**. Two detectors disagreeing is a detector failure, not a finding. It now
imports `measurement_tables` from the gate, so there is one classifier and it cannot drift.

**Both-states proof, six controls.** `test_citation_gate.py` grew from 14 to 24 cases:

* the **pre-round-4 gate**, pinned as blob `b7262302f035`, **PASSES** the uncited table —
  without that control, "the new gate fails it" would not be evidence that anything changed.
  The helper refuses to run if the pinned blob already contains the fix, so the control cannot
  quietly become the new gate comparing itself;
* the new gate FAILS it, and the failure names `UNCITED-MEASUREMENT-TABLE`;
* a marker **inside a cell** passes — stops the rule passing H4 by failing every table;
* a waiver **with** a reason passes; a waiver **without** one fails;
* a table with **no measurement** in it passes — the rule is scoped to measurements, not to
  tables;
* the classifier's own both-states self-check runs on **every** gate invocation and refuses to
  issue a verdict if it cannot both fire on a measurement table and stay silent on a prose
  table. A regex that quietly stops matching would otherwise make this rule a permanently
  green no-op, which is precisely the shape it was added to catch.

Red-first against the real documents, not only fixtures: the extended gate goes red on the
shipped corpus naming `HOOK-AUDIT.md:63` — the faulted table — while all 71 pre-existing
citations still resolve, so the only new signal is the new rule.

## R4-3 — CONFIRMED: the `git-hygiene` timing row is the throttle, and the denominator was wrong too

`H4-TIMING-live.json` records `Stop/git-hygiene`
<!-- cite: id=R4c-gh-h4 file=R4-GITHYGIENE-RANGE.json path=h4_recorded_run_ms value=0.3 -->
`run_ms=0.3`, `emitted_bytes=0`, `pct_of_budget=0.0`. That is not a measurement of the check.
`hooks/git-hygiene/check.py:1196-1207` returns 0 before doing any work while the `.last-run`
stamp is younger than `GIT_HYGIENE_THROTTLE_SEC` (default 900 s); the stamp is written only
after a completed scan. The row is the early return, understated by
<!-- cite: id=R4c-gh-fac file=R4-GITHYGIENE-RANGE.json path=understatement_factor_vs_h4 value=53003 -->
**53,003x** — and it is what let "all other 22 checks are ≤ 0.3% of budget" quietly absorb the
most expensive check in the fleet.

`_r4_githygiene_range.py` measures the guarded path **without touching the live throttle
clock**: `throttle > 0 and stamp.exists()` guards the early return, so exporting
`GIT_HYGIENE_THROTTLE_SEC=0` defeats it with no stamp deletion and no back-dating, and it runs
the repo copy, whose `.last-run` is gitignored.

| arm | wall | emitted |
|---|---|---|
| throttle effective | <!-- cite: id=R4c-gh-a file=R4-GITHYGIENE-RANGE.json path=A_throttle_effective.ms value=115.7 --> 115.7 ms | 0 B |
| throttle defeated | <!-- cite: id=R4c-gh-b file=R4-GITHYGIENE-RANGE.json path=B_throttle_defeated.ms value=15901.0 --> 15,901.0 ms | 1,364 B |

<!-- cite: id=R4c-gh-r file=R4-GITHYGIENE-RANGE.json path=ratio_defeated_over_effective value=137.4 -->
The arms separate by **137.4x** (the probe requires ≥ 100x or it publishes `INCONCLUSIVE` —
without that, "I defeated the throttle" would be an assumption), and
<!-- cite: id=R4c-gh-s file=R4-GITHYGIENE-RANGE.json path=stamp_restored_exact value=True -->
the stamp was restored byte- and mtime-exact, verified by re-reading it. Across five samples
from four different probes the guarded path spans
<!-- cite: id=R4c-gh-lo file=R4-GITHYGIENE-RANGE.json path=range_ms.0 value=11800.0 -->
11.8 s to
<!-- cite: id=R4c-gh-hi file=R4-GITHYGIENE-RANGE.json path=range_ms.1 value=32700.0 -->
32.7 s. It is load-dependent: quote the range, never a point. **The verifier's own framing
that the auditor's "109% of the original 30 s budget" was wider than its evidence is correct,
and this correction inherits that discipline — no single sample here is the number either.**

### The denominator: 90 s is not a budget, it is a number in a file

Round 2 raised git-hygiene 30 s → 90 s after it was disarmed twice, and round 3 concluded
18.7 s was "20.7% of the CURRENT 90 s budget, i.e. NOT over budget". **That denominator is
unreachable.** The dispatcher is ONE command the harness runs under the *event* timeout —
35 s for Stop. When the event timeout expires the harness kills the dispatcher process, so
`dispatch.py`'s own `_receipt(..., "timeout")` never executes and **every check on that event
loses its output, not just the slow one.**

I checked the obvious alternative explanation first and it is not a defect: `dispatch.py`
joins its threads sequentially with `remaining = budget - (now - start)`, and since all
threads share one `start`, that arithmetic is correct per check. The problem is one level up,
between the check budget and the event budget.

`_r4_budget_ceiling.py` computes this over both manifests. Controls first — a synthetic 90 s
check inside a 35 s event MUST be flagged
(<!-- cite: id=R4c-bc-hot file=R4-BUDGET-CEILING.json path=control_broken_state_flags value=1 -->
1 flag) and a synthetic 5 s check MUST NOT be
(<!-- cite: id=R4c-bc-cold file=R4-BUDGET-CEILING.json path=control_clean_state_flags value=0 -->
0 flags); it reads `events[ev]["checks"]` as a LIST and fails closed below 20 checks compared,
because `events[ev]` is a dict whose three key names have already produced a false parity
reading in this program. It compared
<!-- cite: id=R4c-bc-nlive file=R4-BUDGET-CEILING.json path=live.checks_compared value=25 -->
25 live and
<!-- cite: id=R4c-bc-nrepo file=R4-BUDGET-CEILING.json path=repo.checks_compared value=27 -->
27 repo checks, and found
<!-- cite: id=R4c-bc-live file=R4-BUDGET-CEILING.json path=live_violation_count value=1 -->
**1** violation live,
<!-- cite: id=R4c-bc-repo file=R4-BUDGET-CEILING.json path=repo_violation_count value=1 -->
**2** in the repo **at the time this round measured it**; the cell now reads **1**:

> **The cited value moved from 2 to 1, and neither number was ever wrong.** This round's own
> §5.1 fix (`6c6d9a69`, `Stop/git-hygiene` 90 s → 30 s in the repo manifest) removed the first
> bullet below from the repo side — but the evidence file was not regenerated, so it kept
> asserting the pre-fix count for a whole round. Round 5 re-ran the probe and the gate flagged
> the drift on the first attempt. Recorded rather than quietly reconciled, because the failure
> is not the number: a round that fixes a defect and does not re-run the probe measuring it
> publishes evidence for a tree that no longer exists.

* `Stop/git-hygiene` 90 s inside a 35 s event — **live only now**, repo fixed by §5.1 —
  <!-- cite: id=R4c-bc-un file=R4-BUDGET-CEILING.json path=live.violations.0.unreachable_s value=55.0 -->
  **55 s unreachable**. The 30 → 90 s raise bought at most ~5 s of real headroom over the old
  30 s, not 60.
* `PreToolUse/edit-checkpoints` 15 s inside a 15 s event, **repo only** — the `/rollback`
  producer the deploy plan proposes arming, declared a budget it can never spend. (Live's
  PreToolUse event budget is 20 s, which is why this pair is repo-only; that gap is the
  manifest-vs-settings budget drift already recorded in DoD 1.)

So the honest pair of numbers for the guarded path is **≤ 36.3% of the declared 90 s** but
<!-- cite: id=R4c-gh-p35 file=R4-GITHYGIENE-RANGE.json path=range_pct_of_enforced_35s_event_budget.1 value=93.4 -->
**up to 93.4% of the enforced 35 s ceiling it shares with eight other checks**. "Not over
budget" was true of the wrong budget.

UNVERIFIED, inline: I have not observed a live Stop event actually hitting the 35 s ceiling.
Settling experiment: let the 15-minute throttle expire, then time the whole Stop dispatcher as
a subprocess on a session with a large diff and record whether the harness kills it.

## What did NOT change, and must not be read as fixed

* **Both hook fixes are still repo-only.** The live `wire-check` cp1252 fix and the live
  `git-hygiene` `LIVE_STATE_GLOBS` fix are not deployed. Nothing in this round touched the
  live tree.
* **`edit-checkpoints` and `mcp-liveness/pretool` are still undeployed**, so `/rollback` still
  returns nothing. R4-3 adds one input to that decision (the producer's declared budget equals
  the repo's PreToolUse event budget); it does not make the decision.
* **The repo→live deploy step still has no gate.** Unchanged and still the largest hole.
* **`check_citations.py` is invoked by no workflow.** Measured this round:
  `grep -rn "check_citations" .github/workflows/` returns 0 hits. Every round has hardened a
  gate that only runs when an agent remembers to run it — a producer with no consumer, which
  is the same class as the `/rollback` gap this audit opened with. Wiring it means editing
  `.github/workflows/quality.yml`, which is shared with every sibling lane and is the file
  that red-blocked main; this lane did not edit it. **Recommended as the single highest-value
  follow-up**, as one line in the existing docs job.
* **The new table rule covers tables only.** A drifted number in PROSE is still invisible to
  the gate. Disclosed, not claimed. Settling experiment for a future round: extend the
  classifier to measurement-bearing prose lines and re-run `_r4_table_scan.py` to size the
  flood before adopting it.
