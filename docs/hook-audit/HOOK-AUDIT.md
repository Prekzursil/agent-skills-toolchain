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

> **CORRECTED IN ROUND 2 -- read `ROUND2-CORRECTIONS.md` C1-C2 before citing this table.**
> Two defects, both confirmed by an independent verifier. (a) It cited
> `H4-TIMING-live.json`, which was **never committed**; that file is now tracked. (b) The
> wire-check row is a **point reading of a moving input** and does not reproduce -- the same
> tool gave 11,590 ms (46.4%) to the verifier and a 4,406 ms median to round 2. A controlled
> dose arm shows run time tracks the session diff (5.86x the ripgrep walks -> 4.42x the
> time), so **the "135.8% - OVER" verdict is withdrawn as a standing property of the hook**
> and survives only as "true of one moment with a ~250-file diff". Kept verbatim below
> rather than deleted, because the refuted wording is the finding.

| check | budget | measured | % |
|---|---|---|---|
| **wire-check** (live copy) | 25 s | **33,938 ms** (REFUTED, see above) | **135.8% - OVER** |
| open-loops/resurface | 8 s | 981 ms | 12.3% |
| monitor-autolaunch | 6 s | 73 ms | 1.2% |
| **all other 22 checks** | 5–90 s | **≤ 23 ms** | **≤ 0.3%** |

Whole-event, as a real subprocess: SessionStart 3,798 ms / 20 s = 19.0% · **Stop 24,976 ms /
35 s = 71.4%** · PostToolUse 1,115 ms / 15 s = 7.4% · PreToolUse 1,416 ms / 15 s = 9.4%.

**Answer to "are other checks near their budgets?": no.** *(Round-2 rescope. The original
sentence continued "- one is, and it is over", naming the live wire-check; that half is
REFUTED, see C2. What survives is the mechanism, which is independent of the timing: when a
check DOES exceed its budget, `dispatch.py:368-372` **drops its output entirely**
(`_receipt(event, label, "timeout"); continue`), so an over-budget check is not slow, it is
silenced. That remains true, and remains why the deadline shipped in DoD 4 matters -- but the
live wire-check is not observed reaching it on a normal diff.)*

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

**5 dirs INERT-CONFIRMED** — they run cleanly standalone (exit 0) and are reachable from no
wiring surface, i.e. the probe fires and the wiring does not: `compute-confidence-gate`,
`figma-mirror`, `mvt-patch-leaving`, `recall-gate`, `skill-router`. All 5 also appear in the
grounding lane's independently-derived dark list, so two mechanically different methods
agree.

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
> Reported, NOT fixed (this lane reports before editing `hooks/**`): **`wire.py --check`
> prints `FAILED:` and still exits 0** — measured. A check that cannot return non-zero cannot
> be used as a gate, which is the same "a guard that cannot go red" class this audit is about.
> One-line fix, needs its own red-first test.

Detector controls, both directions, all passed: wired-control (`wire-check`) found = True;
synthetic absent-control found = False; and — the control the synthetic one cannot supply —
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

Controlled A/B, HEAD blob vs worktree, interleaved over the same tree (`B3-AB-BUDGET.json`):

> **CORRECTED IN ROUND 2 -- C5.** `B3-AB-BUDGET.json` held only TWO arms; the middle row
> came from an uncommitted one-off and was never reproducible. The probe now runs all three
> (the middle reconstructed from the shipped file with `WIRE_CHECK_DEADLINE_S=0
> WIRE_CHECK_NO_SKIP=1`) and pins its unfixed control at `95761504~1` -- which the original
> did not do: it read HEAD, so once the fix merged the control would have silently voided
> itself. Re-measured: 3,834 / 16,305 / 8,026 ms with 6 / 1 / 0 findings. The absolute
> numbers below are ~7x high for the C2 reason (a much larger diff that day); the ORDERING
> and the finding counts reproduce exactly, and that is all this A/B ever supported.

| arm | wall | % of 25 s budget | findings emitted |
|---|---|---|---|
| HEAD (unfixed) | 26,366 / 26,687 ms | **105.5% / 106.7%** (REFUTED) | **6** |
| encoding fix only | 64,996 / 69,625 ms (NO COMMITTED EVIDENCE) | 260.0% / 278.5% | 0 |
| fix + deadline (shipped) | **15,492 / 17,485 ms** (REFUTED) | **62.0% / 69.9%** | 0 |

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
