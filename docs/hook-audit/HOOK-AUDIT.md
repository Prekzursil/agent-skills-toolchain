# Hook fleet audit — BUILD lane (HOOKRESEARCH), round 1

STATUS: SUPERSEDED IN PART. Read **`ROUND2-CORRECTIONS.md`** alongside this file: an
independent verifier confirmed five defects here, all of them a SENTENCE standing wider than
its evidence rather than broken code. The claim immediately below -- that every number was
produced by a committed, re-runnable probe -- is itself one of them: three tables cited
evidence that was untracked, absent, or two-thirds missing. Corrections are marked inline
next to the original wording; nothing is deleted.

STATUS (as written, round 1): COMPLETE for round 1. Code shipped, every number below produced
by a committed, re-runnable probe in `command-center/hook-audit/`.

COVERAGE — MEASURED here: per-check timing of all 25 live dispatcher checks and 35 of 42
live `settings.json` entries against their declared budgets; the wire-check decode defect
reproduced, fixed, and re-measured A/B against the HEAD blob; the two noise mechanisms
fixed with paired fire/silent tests; 5 dark hooks proven inert BY FIRING; the /rollback
deploy cost measured.
NOT MEASURED, stated inline where load-bearing: 7 of 42 settings entries (launchers, named
with reasons); the `~/.agents/harness` plane's internal per-module split; git-hygiene's
UNTHROTTLED full scan; whether the 5 inert hooks are *correct*, only that they run.

If a section reads "UNKNOWN - not yet measured", the unit died before measuring anything and
no verdict there may be cited.

---

## DoD 1 — every wired hook timed against its budget

**Inventory first, fail-closed.** `_b5_settings_inventory.py`:
<!-- cite: id=R3-h-entries file=B5-SETTINGS-INVENTORY.json path=total_entries value=42 -->
**42 entries** /
<!-- cite: id=R3-h-events file=B5-SETTINGS-INVENTORY.json path=event_count value=20 -->
**20 events**, across four planes — P2-direct 20, P3-agent-self 16, P1-dispatcher 4,
P4-other 2. All
<!-- cite: id=R3-h-declared file=B5-SETTINGS-INVENTORY.json path=declared_budget_count value=42 -->
**42/42 carry a DECLARED timeout**, so nothing silently inherits the vendor default (600 s;
30 s for `UserPromptSubmit`).
<!-- cite: id=R3-h-if file=B5-SETTINGS-INVENTORY.json path=uses_if_field_count value=0 -->
**0 of 42** use the `if` field,
<!-- cite: id=R3-h-exec file=B5-SETTINGS-INVENTORY.json path=uses_exec_form_count value=0 -->
**0 of 42** use exec form — confirming the grounding lane independently.

> **ROUND 3 — this document carried ZERO citations until now.** Round 2 built
> `check_citations.py` to stop a published number drifting from its evidence, and then
> checked only `ROUND2-CORRECTIONS.md`: the floor was global, so one annotated file
> satisfied it for the whole directory and the round-1 tables the verifier had just faulted
> stayed unchecked. The floor is per-document as of round 3, which is why the numbers above
> and the fleet counts below now carry markers. Numbers in this file that are still bare are
> superseded ones kept deliberately as refuted wording — they are labelled as such inline.

### P1 — the 25 live dispatcher checks (in-process, mirrors `dispatch.py`)

> **CORRECTED IN ROUND 2, AND THE WHOLE TABLE WITHDRAWN IN ROUND 4.** Round 2 withdrew one
> row: the wire-check reading is a point sample of a moving input (the same tool gave
> 11,590 ms to the verifier and a 4,406 ms median to round 2; run time tracks the session
> diff), so "135.8% - OVER" survives only as "true of one moment with a ~250-file diff".
> **Round 4 withdrew the other six.** An independent verifier resolved every number in the
> original table against `H4-TIMING-live.json` -- the only committed evidence for this
> measurement -- and found NONE of them present: they diverge **1.7x to 10.9x**. I confirmed
> that independently by reading the committed blob myself (`git show
> HEAD:command-center/hook-audit/H4-TIMING-live.json`); the corrected table below is that
> blob. The gate built to catch exactly this drift printed SUCCESS, because the table carried
> **zero** markers and the per-document floor was satisfied 30 lines higher up — that is
> `check_citations.py` hole **H4**, closed in round 4 and proven red-first against this very
> table. The refuted wording is kept below the corrected table, not deleted, because it is
> the finding.

**Resolved against committed evidence** — one in-process run mirroring `dispatch.py`, live
tree. `%` is of the check's own declared budget, which is NOT the enforceable ceiling; see
the budget-ceiling correction two paragraphs down.

| check | budget | measured | % of check budget |
|---|---|---|---|
| wire-check (live copy) | 25 s | <!-- cite: id=R4-t-wc file=H4-TIMING-live.json path=checks.8.run_ms value=6541.6 --> 6,541.6 ms | <!-- cite: id=R4-t-wcp file=H4-TIMING-live.json path=checks.8.pct_of_budget value=26.2 --> 26.2% |
| open-loops/resurface | 8 s | <!-- cite: id=R4-t-ol file=H4-TIMING-live.json path=checks.4.run_ms value=351.6 --> 351.6 ms | <!-- cite: id=R4-t-olp file=H4-TIMING-live.json path=checks.4.pct_of_budget value=4.4 --> 4.4% |
| monitor-autolaunch | 6 s | <!-- cite: id=R4-t-ma file=H4-TIMING-live.json path=checks.23.run_ms value=7.8 --> 7.8 ms | <!-- cite: id=R4-t-map file=H4-TIMING-live.json path=checks.23.pct_of_budget value=0.1 --> 0.1% |
| **git-hygiene** | 90 s | <!-- cite: id=R4-t-gh file=H4-TIMING-live.json path=checks.9.run_ms value=0.3 --> 0.3 ms — **NOT A MEASUREMENT**, see below | — |
| the other 21 checks | 5–25 s | max <!-- cite: id=R4-t-hb file=H4-TIMING-live.json path=checks.3.run_ms value=12.7 --> 12.7 ms (`heartbeat`) | <!-- cite: id=R4-t-hbp file=H4-TIMING-live.json path=checks.3.pct_of_budget value=0.2 --> ≤ 0.2% |

| event (whole dispatcher, real subprocess) | budget | measured | % |
|---|---|---|---|
| SessionStart | 20 s | <!-- cite: id=R4-e-ss file=H4-TIMING-live.json path=events.0.wall_ms value=349.1 --> 349.1 ms | <!-- cite: id=R4-e-ssp file=H4-TIMING-live.json path=events.0.pct_of_budget value=1.7 --> 1.7% |
| Stop | 35 s | <!-- cite: id=R4-e-st file=H4-TIMING-live.json path=events.1.wall_ms value=14895.7 --> 14,895.7 ms | <!-- cite: id=R4-e-stp file=H4-TIMING-live.json path=events.1.pct_of_budget value=42.6 --> 42.6% |
| PostToolUse | 15 s | <!-- cite: id=R4-e-po file=H4-TIMING-live.json path=events.2.wall_ms value=137.9 --> 137.9 ms | <!-- cite: id=R4-e-pop file=H4-TIMING-live.json path=events.2.pct_of_budget value=0.9 --> 0.9% |
| PreToolUse | 15 s | <!-- cite: id=R4-e-pr file=H4-TIMING-live.json path=events.3.wall_ms value=236.3 --> 236.3 ms | <!-- cite: id=R4-e-prp file=H4-TIMING-live.json path=events.3.pct_of_budget value=1.6 --> 1.6% |

<!-- uncited-table: reason=verbatim round-1 wording, REFUTED in round 4 and preserved as the finding; every number in it is unbacked and the corrected values are the cited tables above -->

| REFUTED round-1 table | budget | measured | % |
|---|---|---|---|
| **wire-check** (live copy) | 25 s | **33,938 ms** | **135.8% - OVER** |
| open-loops/resurface | 8 s | 981 ms | 12.3% |
| monitor-autolaunch | 6 s | 73 ms | 1.2% |
| **all other 22 checks** | 5–90 s | **≤ 23 ms** | **≤ 0.3%** |

*(and, in prose, the four whole-event numbers: SessionStart 3,798 ms / 19.0% · Stop 24,976 ms
/ 71.4% · PostToolUse 1,115 ms / 7.4% · PreToolUse 1,416 ms / 9.4% — all four unbacked.)*

**The `git-hygiene` row is the throttle, not the check.** `hooks/git-hygiene/check.py`
returns 0 before doing any work when its `.last-run` stamp is younger than
`GIT_HYGIENE_THROTTLE_SEC` (default 900 s), so `0.3 ms` is the cost of the early return —
understated by a factor of
<!-- cite: id=R4-gh-fac file=R4-GITHYGIENE-RANGE.json path=understatement_factor_vs_h4 value=53003 -->
**53,003**. That row is why "all other checks are ≤ 0.3% of budget" was able to absorb the
single most expensive check in the fleet. Measured on the guarded path
(`_r4_githygiene_range.py`, throttle defeated with the env knob rather than by deleting a
stamp, so the live 15-minute clock is untouched; arms separated by
<!-- cite: id=R4-gh-ratio file=R4-GITHYGIENE-RANGE.json path=ratio_defeated_over_effective value=137.4 -->
137.4x, stamp restored byte- and mtime-exact):
<!-- cite: id=R4-gh-mine file=R4-GITHYGIENE-RANGE.json path=B_throttle_defeated.ms value=15901.0 -->
**15,901 ms** on the repo copy. Across five samples from four different probes the range is
<!-- cite: id=R4-gh-lo file=R4-GITHYGIENE-RANGE.json path=range_ms.0 value=11800.0 -->
**11.8 s** to
<!-- cite: id=R4-gh-hi file=R4-GITHYGIENE-RANGE.json path=range_ms.1 value=32700.0 -->
**32.7 s** — load-dependent, so quote the range, never a point.

**The denominator was also wrong, and this is the round-4 finding.** Round 2 raised
git-hygiene 30 s → 90 s, and round 3 called 18.7 s "20.7% of the CURRENT 90 s budget, NOT
over budget". **90 s is not reachable.** The dispatcher is ONE command the harness runs under
the *event* timeout, and Stop's is 35 s; when that expires the harness kills the dispatcher
process, so `dispatch.py`'s own `_receipt(..., "timeout")` never runs and **every check on
that event loses its output, not just the slow one**. `_r4_budget_ceiling.py` (controls
discriminate: a synthetic 90 s-in-35 s is flagged, a synthetic 5 s-in-35 s is not; fails
closed below 20 checks compared) finds
<!-- cite: id=R4-bc-live file=R4-BUDGET-CEILING.json path=live_violation_count value=1 -->
**1** such pair live and
<!-- cite: id=R4-bc-repo file=R4-BUDGET-CEILING.json path=repo_violation_count value=1 -->
**1** in the repo.

> **This cell read 2 until round 5, and 2 was correct when it was written.** Commit
> `6c6d9a69` then lowered `Stop/git-hygiene` 90 s → 30 s in the repo manifest, which removed
> that row — but nobody regenerated `R4-BUDGET-CEILING.json`, so the committed evidence went
> on describing a tree that no longer existed. Round 5 re-ran the probe and the gate caught
> the drift immediately (`repo_violation_count is 1 on disk but 2 in the staged blob`). The
> reason it went unnoticed for a round is the round-5 defect itself: re-running any of these
> three probes could destroy their evidence, so re-running them was the one thing nobody did.
> The remaining repo row is `PreToolUse/edit-checkpoints`; BUILD-R4 §4 REFUTED it as a defect
> by measuring the **enforced** 20 s ceiling instead of the manifest's stale 15 s mirror, and
> this probe still counts it only because it reads that mirror.

<!-- cite: id=R4-bc-un file=R4-BUDGET-CEILING.json path=live.violations.0.unreachable_s value=55.0 -->
**55 s of git-hygiene's 90 s is unreachable live**, which is the row still awaiting a deploy.
So the honest pair of numbers for
the guarded path is
<!-- cite: id=R4-gh-p90 file=R4-GITHYGIENE-RANGE.json path=range_pct_of_declared_90s_check_budget.1 value=36.3 -->
**≤ 36.3% of the declared 90 s** but
<!-- cite: id=R4-gh-p35 file=R4-GITHYGIENE-RANGE.json path=range_pct_of_enforced_35s_event_budget.1 value=93.4 -->
**up to 93.4% of the enforced 35 s event ceiling it shares with eight other checks**.

**Answer to "are other checks near their budgets?": no — with one exception that the
throttled row hid.** *(Round-2 rescope, round-4 requalification. The 21 unremarkable checks
are ≤ 12.7 ms and that is unchanged by the correction. `wire-check` at 26.2% is not near its
budget on a normal diff. `git-hygiene` IS near a budget — not its own 90 s, but the 35 s
event ceiling, at up to 93.4% of it. What survives from round 2 unchanged is the mechanism:
when a check exceeds its budget `dispatch.py:368-372` **drops its output entirely**
(`_receipt(event, label, "timeout"); continue`), so an over-budget check is not slow, it is
silenced — and when the EVENT budget goes first, all nine are.)*

UNVERIFIED, inline: I did not observe a live Stop event actually hitting the 35 s ceiling —
the arithmetic and the 32.7 s sample say it is reachable, not that it has happened. Settling
experiment: let the 15-minute throttle expire, then time the whole Stop dispatcher as a
subprocess (`_h4_timing.py` measures it) on a session with a large diff, and record whether
the harness kills it.

### P2/P3 — 35 of 42 settings entries timed as real subprocesses

~~Worst offender is **50.6%** of budget (`PreToolUse` -> agent-self harness, 1,012 ms / 2 s).
Nothing else exceeds 42%.~~ **REFUTED -- see `ROUND2-CORRECTIONS.md` C3-C4.** Two defects:
`B6-FLEET.json` did not contain a `timing` key at all (a later `--inertness`-only run of the
producing probe had overwritten it), and the percentage was jitter on a 2 s budget -- three
runs named three different entries as worst (50.6% / 62.3% / 18.4%). Re-measured at repeat=3
the worst is `semantic-router` at **17.8%** (stable 17.4-18.1%), and the denominator-free
statistic is that **no entry has ever been measured above 1,808 ms**. Full table, now actually
present: `command-center/hook-audit/B6-FLEET.json` -> `timing`.

**7 entries NOT fired, named with reasons** (a launcher fired during an audit spawns GUI
apps on a shared machine): `re-autolaunch` (IDA/Ghidra), `workflow-monitor-autolaunch`,
`codex-monitor-autolaunch`, `loop-recovery`, `stopfailure-notify` (desktop notifications),
and 2 `WorktreeCreate`/`WorktreeRemove` entries whose command is not a resolvable `.py`
path. UNVERIFIED: their wall time. Settling experiment: run
`probe_hook_fleet.py --timing --include-launchers` on an idle box and accept the spawns.

### Budget drift found while doing this (new)

The repo manifest's `settings_timeout` **disagrees with the live settings.json** for two
events: PostToolUse manifest 15 s vs live 25 s, PreToolUse manifest 15 s vs live 20 s.
SessionStart (20) and Stop (35) agree. So the manifest documents a budget that is not the
one enforced, and no gate compares them. Consequence for readers: any "% of budget" quoted
from the manifest for those two events is computed against the wrong denominator.

## DoD 2 — inert hooks proven inert by a fired probe, not asserted

`probe_hook_fleet.py --inertness` searches four wiring surfaces, then **fires** every hook
it finds dark with an event-appropriate payload. Firing is what separates "named nowhere"
from "inert" — a directory listing cannot tell a dark hook from a broken one.

<!-- cite: id=I1-inert file=B6-FLEET.json path=inertness.verdicts.INERT-CONFIRMED value=6 -->
**6 dirs INERT-CONFIRMED** — they run cleanly standalone (exit 0) and are reachable from no
PATH-shaped wiring surface, i.e. the probe fires and the wiring does not: `checkpoint`,
`compute-confidence-gate`, `figma-mirror`, `mvt-patch-leaving`, `recall-gate`,
`skill-router`. Five of the six also appear in the grounding lane's independently-derived
dark list, so two mechanically different methods agree. The sixth is `checkpoint`, held out
of the count in round 1 pending a settling experiment and SETTLED as dark in round 3 on four
mechanically different signals — see the round-3 block below, which already says in so many
words that "the inert set can include it".

> **REFUTED 2026-08-14 (integrate round), kept rather than silently corrected.** From round 1
> until now this paragraph opened with the wording fenced below — fenced at top level, not
> inside this blockquote, because `_strip_fenced` anchors its fence match at the start of the
> line and does not see a fence carrying a `>` prefix, so a quoted refuted number inside a
> blockquote is still audited as a live claim (measured while writing this correction).

```
**5 dirs INERT-CONFIRMED** — ... `compute-confidence-gate`, `figma-mirror`,
`mvt-patch-leaving`, `recall-gate`, `skill-router`. All 5 also appear in the grounding
lane's independently-derived dark list ...
```

> The probe was right and the sentence was stale. Round 3 settled `checkpoint` 54 lines below
> and nobody carried the settlement back up to the headline, so the flagship deliverable
> disagreed with its own evidence file, with its own addendum, and with `BUILD-R3.md`, which
> cites 6. Three review rounds read past it because **no gate could see it**: the number is
> in prose, carries no unit and sits in no table, so the H4 uncited-measurement-table rule
> did not reach it. Editing the published 5 to a 7 kept the gate green — measured, with the
> gate proven alive in the same run by mutating a CITED number and watching it go red. That
> hole is closed by the H5 rule in `check_citations.py`, and this correction is the first
> thing it caught.

**1 dir is NOT merely dark — it does not terminate.** `harness-bench` was fired once and
**did not return inside 45 s** (`exit=TIMEOUT`). Wiring it would hang its event, so
"fix the darkness by wiring it" is the wrong move here. It is now on the probe's
do-not-fire list with that reason recorded, so re-runs do not keep re-triggering it.

**3 dirs have no script at all**: `_fleet-backups`, `_golden`, `sonar-secrets`.

**Scope of my search, stated because it disagrees with the grounding lane.** I count only
PATH-shaped wiring references (`.../hooks/<dir>/<file>.py` plus manifest `script` fields),
so I find
<!-- cite: id=R3-h-dark file=B6-FLEET.json path=inertness.dirs_dark value=10 -->
**10 dark** of
<!-- cite: id=R3-h-dirs file=B6-FLEET.json path=inertness.dirs_total value=73 -->
**73** against the grounding's **24**. Mine is **not a correction** —
a hook wired by MODULE NAME rather than path is invisible to my regex, so I under-report
wiring and could produce a false "dark". That is exactly what happened for **`checkpoint`**:
my probe calls it dark, the grounding lane records it as P3-wired. I **excluded `checkpoint`
from the inert set** rather than pick a side, and named the settling experiment: read the
`~/.agents/harness/dispatcher.py` module registry.

> **ROUND 3 — SETTLED, and the dark verdict stands.** The experiment was run
> (`_r3_checkpoint_wiring.py`). `HarnessDispatcher.__init__` builds `self.modules` from
> `build_default_modules(...)`, and those are **classes inside `~/.agents/harness/modules.py`
> carrying a `name = "<snake_case>"` attribute** — in-process objects, not
> `hooks/<dir>/<script>.py` subprocesses. Counting the two shapes separately across six
> wiring surfaces (325,602 B of P3 alone), `hooks/checkpoint/` scores
> <!-- cite: id=R3-ck-path file=R3-CHECKPOINT-WIRING.json path=targets.checkpoint.path_total value=0 -->
> **0 path-shaped** references and
> <!-- cite: id=R3-ck-name file=R3-CHECKPOINT-WIRING.json path=targets.checkpoint.name_total value=5 -->
> **5 name-shaped** ones — and every one of the five is a collision: `edit-checkpoints/`**`checkpoint.py`**
> (a different directory), a manifest comment about `/rollback`, and `# Sanitized compaction
> checkpoint` in P3. Verdict
> <!-- cite: id=R3-ck-verdict file=R3-CHECKPOINT-WIRING.json path=targets.checkpoint.verdict exists=true -->
> **NAME-ONLY** (the citation syntax is whitespace-delimited, so this string value is pinned
> with `exists=true` and the two counts above carry the number — the gate caught the
> whitespace mismatch itself rather than resolving half a value), with a positive control
> (`wire-check`
> <!-- cite: id=R3-ck-ctl file=R3-CHECKPOINT-WIRING.json path=control_positive_is_path_wired value=True -->
> path-wired) and a negative control (a synthetic name
> <!-- cite: id=R3-ck-neg file=R3-CHECKPOINT-WIRING.json path=control_negative_is_absent value=True -->
> ABSENT) both holding.
>
> Two further signals, both of which were sitting in the repo unread the whole time:
> `hooks/checkpoint/README.md:76` says *"currently: FINDING, neither half wired"*, and the
> directory ships its own purpose-built detector. Running it now:
> `python hooks/checkpoint/wire.py --check` → `NOT-WIRED PreCompact` / `NOT-WIRED
> SessionStart(settings)` / `NOT-WIRED SessionStart(dispatch)` /
> `FAILED:checkpoint-wiring FINDING — NEITHER half is wired: the hook is on disk and live
> nowhere`. **Four mechanically different signals agree**, so `checkpoint` is dark and the
> inert set can include it — the disagreement was a use-vs-mention error on the other side,
> not a scope difference on mine.
>
> ~~Reported, NOT fixed (this lane reports before editing `hooks/**`): **`wire.py --check`
> prints `FAILED:` and still exits 0** — measured. A check that cannot return non-zero cannot
> be used as a gate, which is the same "a guard that cannot go red" class this audit is about.
> One-line fix, needs its own red-first test.~~
>
> **REFUTED IN ROUND 4. `wire.py` fails closed; there was never a defect here.** The word
> "measured" in the struck sentence was doing work no measurement supported — whatever was
> read, it was not the process exit status. Three mechanically different signals now agree:
> the source (`hooks/checkpoint/wire.py:228` `return 0 if verdict == "CLEAN" else 1`, invoked
> at `:232` through `sys.exit(main())`), the verifier's shell and PowerShell
> `$LASTEXITCODE` reads, and `_r4_wire_exit.py`, which SPAWNS the script and reads the real
> exit code on **both** trees. That probe carries the control the original claim lacked —
> observing one verdict cannot distinguish "always 0" from "tracks the verdict", so it drives
> both through the same binary using `--settings`/`--manifest` overrides:
> <!-- cite: id=R4-w-find file=R4-WIRE-EXIT.json path=repo_finding_rc value=1 -->
> FINDING → **rc 1**,
> <!-- cite: id=R4-w-clean file=R4-WIRE-EXIT.json path=repo_clean_rc value=0 -->
> synthetic CLEAN → **rc 0**, live tree identical, and
> <!-- cite: id=R4-w-disc file=R4-WIRE-EXIT.json path=arms_discriminate value=True -->
> `arms_discriminate=True` (it publishes INCONCLUSIVE if they ever agree).
> **Cost of the error:** round 3 handed round 4 a one-line fix inside `hooks/**` for working
> code. The class is worth more than the instance — a *self-reported* "measured" with no
> named instrument is not evidence, and this audit shipped one while auditing for exactly
> that.

Detector controls, both directions, all passed: wired-control (`wire-check`) found = True;
synthetic absent-control found = False; and — the control the synthetic one cannot supply —
<!-- cite: id=I1-mentioned file=B6-FLEET.json path=inertness.control_mentioned_only_count value=2 -->
**2 dirs came back MENTIONED-BUT-NOT-PATH-WIRED** (`checkpoint`, `sonar-secrets`), which is
direct evidence that the loose document-level search over-reports. My first version used
that loose search and reported **8 dark of 73** while calling 65 dirs wired; its synthetic
absent-control passed anyway, because a name that appears nowhere was never the hypothesis
under test.

## DoD 3 — the /rollback producer gap

Deploy plan written: **`docs/hook-audit/ROLLBACK-DEPLOY-PLAN.md`**, with the load-bearing
cost measured rather than assumed (`_b8_rollback_cost.py`, isolated throwaway repo asserted
empty first): arming the producer costs **cold 5,486 ms / warm mean 2,545 ms / warm max
3,706 ms per Edit·Write·MultiEdit** — 17.0% of its 15 s check budget and 12.7% of the live
20 s PreToolUse event budget. It fits, but it charges ~2.5 s to the most frequent tool call
in a session, which is the decision the owner has to make and is why this lane wrote a plan
instead of deploying unilaterally.

That probe initially reported "producer wrote no index" and **failed closed instead of
publishing a cost with no evidence the producer worked** — the index lands in
`CKPT_ROOT/<session_id>/index.ndjson`, a per-session subdir, and my check looked at the
root. Corrected: index written, 1 record, 1 real snapshot ref created.

**The gap itself, re-anchored to evidence that is now IN GIT (integrate round).** Until
2026-08-14 this section's anchor, `H8-ROLLBACK-GAP.json`, was UNTRACKED — present on one
disk, absent from every clone, and named by no `cite:` marker, so nothing could check it and
its absence was invisible. It is tracked now and the two load-bearing facts are pinned:
the producer is
<!-- cite: id=I1-r-manifest file=H8-ROLLBACK-GAP.json path=deployment.in_live_manifest value=False -->
**absent from the live manifest** while it
<!-- cite: id=I1-r-writes file=H8-ROLLBACK-GAP.json path=producer.index_written value=True -->
**does write the index when fired** — verdict
<!-- cite: id=I1-r-verdict file=H8-ROLLBACK-GAP.json path=verdict value=PRODUCING -->
`PRODUCING`. That pairing is the whole finding: the hook works and is wired nowhere, so
`/rollback` reads an index no live hook writes. If the producer is ever deployed and the
probe re-run, `in_live_manifest` flips and this citation goes RED, which is the point — the
document can no longer describe a gap that has been closed.

## DoD 4 — false-positive sources named with a fix

Three mechanisms, all fixed in `hooks/wire-check/check.py`, each with a red-first
regression test that was run against the unfixed file first.

**F1 — cp1252 silent-empty (the big one).** Both subprocess sites used `text=True` with no
`encoding=`, decoding the child under the ANSI codepage with STRICT errors. `subprocess.run`
does **not** raise: the decode dies in `subprocess._readerthread`, `communicate()` returns
`""`, and `returncode` stays 0 — so `_rg_lines` took its *success* branch and returned `[]`,
and the os.walk fallback was never reached. Zero references is this hook's dead-code
trigger, and since the odds of a non-cp1252 byte rise with output size, the failure is
**inverted: most wrong about the most-referenced symbols.**

Re-anchored in the integrate round for the same reason as DoD-3: `H7-WIRECHECK-FP.json` was
UNTRACKED and uncited, so the mechanism above rested on a file no clone has. Tracked and
pinned now —
<!-- cite: id=I1-f1-empty file=H7-WIRECHECK-FP.json path=silently_emptied_count value=3 -->
**3 of the 6 probed patterns came back silently emptied**, with a bogus-token row in the same
table returning 0 lines on both arms so "emptied" stays distinguishable from "genuinely
absent".

Controlled A/B, HEAD blob vs worktree, interleaved over the same tree (`B3-AB-BUDGET.json`):

> **CORRECTED IN ROUND 2 -- C5.** `B3-AB-BUDGET.json` held only TWO arms; the middle row
> came from an uncommitted one-off and was never reproducible. The probe now runs all three
> (the middle reconstructed from the shipped file with `WIRE_CHECK_DEADLINE_S=0
> WIRE_CHECK_NO_SKIP=1`) and pins its unfixed control at `95761504~1` -- which the original
> did not do: it read HEAD, so once the fix merged the control would have silently voided
> itself. Re-measured: 3,834 / 16,305 / 8,026 ms with 6 / 1 / 0 findings. The absolute
> numbers below are ~7x high for the C2 reason (a much larger diff that day); the ORDERING
> and the finding counts reproduce exactly, and that is all this A/B ever supported.

**Re-measured, and resolved against committed evidence** (`B3-AB-BUDGET.json`, two rounds
interleaved; the unfixed control is pinned at `95761504~1` and the file asserts
`head_blob_already_had_encoding_kwarg=false` or the comparison is void):

| arm | wall (r1 / r2) | % of 25 s budget (r1) | findings emitted |
|---|---|---|---|
| HEAD (unfixed) | <!-- cite: id=R4-ab-u1 file=B3-AB-BUDGET.json path=runs.0.wall_ms value=3834.2 --> 3,834.2 / <!-- cite: id=R4-ab-u2 file=B3-AB-BUDGET.json path=runs.3.wall_ms value=4147.6 --> 4,147.6 ms | <!-- cite: id=R4-ab-up file=B3-AB-BUDGET.json path=runs.0.pct_of_budget value=15.3 --> 15.3% | <!-- cite: id=R4-ab-uf file=B3-AB-BUDGET.json path=runs.0.finding_count value=6 --> **6** |
| encoding fix only (reconstructed) | <!-- cite: id=R4-ab-m1 file=B3-AB-BUDGET.json path=runs.1.wall_ms value=16304.9 --> 16,304.9 / <!-- cite: id=R4-ab-m2 file=B3-AB-BUDGET.json path=runs.4.wall_ms value=16470.9 --> 16,470.9 ms | <!-- cite: id=R4-ab-mp file=B3-AB-BUDGET.json path=runs.1.pct_of_budget value=65.2 --> 65.2% | <!-- cite: id=R4-ab-mf file=B3-AB-BUDGET.json path=runs.1.finding_count value=1 --> 1 |
| fix + deadline (shipped) | <!-- cite: id=R4-ab-s1 file=B3-AB-BUDGET.json path=runs.2.wall_ms value=8025.6 --> 8,025.6 / <!-- cite: id=R4-ab-s2 file=B3-AB-BUDGET.json path=runs.5.wall_ms value=7061.2 --> 7,061.2 ms | <!-- cite: id=R4-ab-sp file=B3-AB-BUDGET.json path=runs.2.pct_of_budget value=32.1 --> 32.1% | <!-- cite: id=R4-ab-sf file=B3-AB-BUDGET.json path=runs.2.finding_count value=0 --> 0 |

<!-- uncited-table: reason=verbatim round-1 wording, REFUTED; its middle arm never had committed evidence at all and the corrected values are the cited table above -->

| REFUTED round-1 arm | wall | % of 25 s budget | findings emitted |
|---|---|---|---|
| HEAD (unfixed) | 26,366 / 26,687 ms | **105.5% / 106.7%** | **6** |
| encoding fix only | 64,996 / 69,625 ms (NO COMMITTED EVIDENCE) | 260.0% / 278.5% | 0 |
| fix + deadline (shipped) | **15,492 / 17,485 ms** | **62.0% / 69.9%** | 0 |

**All 6 findings the unfixed hook emitted against this repo were false positives**, and the
fixed hook emits none. This defect is live in the DEPLOYED tree too, by a second
independent signal: one live dispatch run printed **7** `charmap codec can't decode`
tracebacks from `subprocess._readerthread`.

**F2 — a pathlib literal reported as an unlinked route.** `re.IGNORECASE` over the whole
`_ROUTE` pattern made the Django `path(` alternative match pathlib's `Path(`, so
`LIVE = Path("C:/Users/Prekzursil/.claude/hooks")` was emitted verbatim as
`route 'C:/…/hooks' is linked/navigated 0x`. Fixed by splitting `_ROUTE` into a
case-insensitive half (HTTP verbs/decorators) and a case-SENSITIVE half (`path(`,
`<Route path=`), plus a `_NOT_ROUTE` guard rejecting drive-absolute, UNC and
scheme-qualified literals. All six real dialects still extract (Express, Flask, FastAPI,
Django, React Router) — the pre-existing 19-case route suite still passes.

**F3 — it fires on untracked scratch.** It flagged `_h1_inventory.py`, `_h2_unwired.py` and
a sibling lane's `_s2_render_probe.py` minutes after they were written. Fixed with a
deliberately narrow rule: skip a file only when it is in a known scratch tree, **or** it is
UNTRACKED *and* named `_*` — extending to files the private-by-convention prefix the module
already honours for symbols. A TRACKED `_build_thing.py` and an untracked `feature.py` both
stay in scope, and `WIRE_CHECK_NO_SKIP=1` disables the whole skip so the suppression is
auditable.

### The regression my own fix introduced, and its fix

The encoding fix **tripled** wall time (24 s → 67 s), because blanked diffs used to mean
there was nothing to resolve. Profiling attributed it rather than guessing
(`B4-PROFILE.json`): **ripgrep is 67,476 ms of a 78,828 ms run (86%) across exactly 40
full-tree walks at 1,687 ms mean**; git is 2,537 ms. Worst single lookup was 12,256 ms,
because a ripgrep call that blows its own `timeout=8` raises, gets swallowed, and then falls
through to the *slow os.walk fallback* — so that path is not the rare "ripgrep missing" case
it reads as.

Shipped remedy: a wall-clock deadline (`DEADLINE_S = 20`, `WIRE_CHECK_DEADLINE_S` to tune,
`=0` for unbounded) propagated into `_rg_lines` so it bounds both the child timeout and the
fallback. Truncation is disclosed in the emitted message instead of passing as an all-clear.

**And the hazard that created:** once the deadline passes, `_rg_lines` returns `[]` — which
reads as zero references, i.e. it would manufacture the very false positive F1 removed, from
a new cause. Every zero verdict is therefore routed through a `_measured()` gate that
downgrades an unconfirmed zero to a truncation and never emits it. Regression-tested in both
directions.

Residual, disclosed: the deadline trades coverage for staying inside budget — on a large
diff fewer symbols are resolved than before. The structural fix is to batch the 40 per-symbol
ripgrep walks into one alternation pass (the profile says that is where 86% of the time is);
not done in round 1 because it changes reachability semantics under ripgrep's smart-case
rules, which needs its own both-states suite.

---

## Changes shipped by this lane

| file | change |
|---|---|
| `hooks/wire-check/check.py` | F1 encoding fix at both subprocess sites · F2 route case-split + `_NOT_ROUTE` · F3 scratch skip + `WIRE_CHECK_NO_SKIP` · budget deadline + `_measured()` zero-gate · truncation disclosure |
| `hooks/wire-check/test_wire_check_decode.py` | NEW — 7 cases, 6 locale-independent, fail-closed if all skipped |
| `hooks/wire-check/test_wire_check_noise.py` | NEW — 32 cases (18 must fire, 14 must stay silent) |
| `command-center/hook-audit/probe_hook_fleet.py` | NEW re-runnable tool — fleet timing + fire-to-prove-inertness, controls, fail-closed |
| `command-center/hook-audit/_b*.py` + `B*.json` | probes and evidence for every number above |
| `docs/hook-audit/ROLLBACK-DEPLOY-PLAN.md` | NEW — DoD 3 |

Test state after the change: decode 7/7 · noise 32/32 · pre-existing routes 19/19 · pre-existing
`test_wire_check.py` ALL PASS. No pre-existing test was modified.

## Self-corrections — recorded, not deleted

Four of my own detectors were wrong first and were fixed before their numbers were used.

1. **A one-shape findings parser** reported `finding_count: 0` beside `emitted: true` — a
   self-contradiction, i.e. a detector failure, not a finding. wire-check emits **four**
   shapes. The superseding probe `_b3_ab_budget.py` parses all four and says so in its
   docstring; the one-shape probe was dropped rather than committed.
2. **A loose document-level wiring search** called 65 of 73 dirs wired (8 dark) by matching a
   hook's name anywhere in 764 KB of `~/.agents/harness` text — counting the document, not
   the field. Replaced with a path-shaped/field-level search, whose remaining scope limit is
   stated in DoD 2.
3. **A scratch-skip test case that passed before the fix existed.** `git status --porcelain`
   collapses a wholly-untracked directory to `?? scratchpad/`, which has no source extension
   and is dropped — so the case measured git's output shape, not my skip. Rewritten to use a
   tracked-and-modified file, with the collapsing behaviour pinned as its own case.
4. **A cost probe that looked for the index in the wrong directory** and reported "producer
   wrote no index". Its fail-closed gate refused to publish a cost number, which is the only
   reason a wrong "producer is broken" claim did not reach this document.

Also corrected against the grounding lane, in its favour: it filed `wire-check/check.py:117`
(`_git`) among 10 "lower risk, they only call git" candidates. For wire-check specifically
that call carries `git diff` output — arbitrary **file content** — so it is not low risk, and
its failure mode is the opposite one (a blanked diff means a real dead symbol is silently
MISSED). Both directions are now regression-tested.

## Residual / not done

1. **My fix is repo-only; the live tree still has the defect** (7 live decode tracebacks
   measured). Deploying is the manifest/live-copy step covered by the deploy plan.
2. **10 sibling `text=True` sites** named by the grounding lane remain unfixed. The live
   decode tracebacks prove at least one is firing, but I did not attribute them per-file.
   Settling experiment: re-run `_h4_timing.py` with a per-module stderr capture.
3. **Batching the 40 ripgrep walks** — the 86%-of-runtime structural fix (above).
4. **`re-autolaunch` emits a real `permissionDecision: deny`** against AGENTS.md §6; arming
   predicate still unread.
5. **The repo→live deploy step has no gate at all** — the architectural hole behind both the
   /rollback regression and the budget drift in DoD 1.
