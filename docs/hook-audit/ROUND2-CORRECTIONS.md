---
title: ROUND2-CORRECTIONS
type: note
permalink: dqverify-repo-20261013/docs/hook-audit/round2-corrections
---

# HOOKRESEARCH round 2 — corrections to round 1, and one new false-positive fix

STATUS: COMPLETE for round 2. Every number below carries a machine-checkable citation to a
**committed** evidence file. `python command-center/hook-audit/check_citations.py` opens
each cited file, walks the cited JSON path and compares the resolved value to the number
printed here; `--self-test` mutates every expected value and requires the gate to go red.

COVERAGE — MEASURED here: the reproducibility of round 1's two timing headlines (controlled
dose-response, 3 arms × 4 iterations); the fleet timing re-measured with repeat=3 so the
worst entry is a median with a spread; the missing third A/B arm reconstructed and run; the
one live git-hygiene false positive fixed and proven in both states end to end.
NOT MEASURED, stated inline where load-bearing: the stub-ledger phantom mechanism (§N3);
git-hygiene's unthrottled scan against the FULL default root set (§N1 measured a scoped
subset); the 7 launcher entries (unchanged from round 1).

If a section reads "UNKNOWN - not yet measured", the unit died before measuring anything and
no verdict here may be cited.

---

## What the verifier confirmed, and what each correction turned out to be

Five findings were confirmed against round 1. **None of them was broken code.** All five were
a document standing wider than its evidence — the estate's dominant defect shape. Round 1's
`hooks/wire-check/check.py` change re-verified clean; what follows repairs the sentences and
the evidence trail, and records the refuted wordings rather than deleting them.

<!-- uncited-table: reason=an index of REFUTED round-1 wordings; the quoted numbers are the refuted ones and every corrected value is cited in its own section below (C2 gives the range, C4 gives 17.8 percent) -->

| # | Round-1 wording (now REFUTED) | What is true |
|---|---|---|
| C1 | per-check table cited `H4-TIMING-live.json` | that file was never committed — a citation to nothing |
| C2 | "live wire-check **33,938 ms = 135.8% — OVER**" | a point reading of a moving input; range 3.7 s–20.7 s measured |
| C3 | "Full table: `B6-FLEET.json`" (timing) | the file held only `inertness`; the probe clobbered its own evidence |
| C4 | "Worst offender is **50.6%** of budget" | jitter on a 2 s budget; worst by median is 17.8%, stable |
| C5 | a **three**-row A/B table | `B3-AB-BUDGET.json` held two arms; the middle row was an uncommitted one-off |

---

## C1 — a published table cited a file that was never committed

CONFIRMED. `_h4_timing.py` and `H4-TIMING-live.json` were both untracked, so round 1's
entire per-check table pointed at bytes that exist only on this disk. A reader in a fresh
clone had no way to see it, and no gate noticed.

Both files are committed by this round, and the general case is now gated: `check_citations.py`
treats an UNTRACKED evidence file as a failure distinct from a missing one, precisely because
an uncommitted file reads as present to its author and absent to everyone else.

## C2 — the 135.8% headline was a point reading of a moving input

CONFIRMED, and the refuted sentence is worth keeping: round 1 wrote *"the live wire-check
exceeds its 25 s budget … today's live wire-check is not slow, it is silenced."* An
independent verifier re-ran round 1's own tool and got 11,590 ms (46.4%). I now measure the
same check at a median of
<!-- cite: id=C2-live-median file=C2-TIMING-VARIANCE.json path=summary.live-unfixed.median_ms value=4406.4 tol=0.001 -->
**4,406 ms**. Three readings, three answers, one hook.

`_c2_timing_variance.py` states the two hypotheses first and then discriminates:

* **H1** the number is noise, so no timing claim about this hook is possible;
* **H2** the number tracks a moving input — wire-check resolves symbols out of the session's
  uncommitted diff, nine sibling lanes write to that tree continuously, and the cost is
  roughly (symbols to resolve) × (per-ripgrep-walk cost).

The observational arms cannot separate these, because they differ in code as well as input.
So the probe carries a **DOSE arm**: the same file, the same tree, the same per-walk cost,
with only the amount of input the hook admits changed (`WIRE_CHECK_NO_SKIP=1`). Result —
ripgrep walks rise
<!-- cite: id=C2-cov file=C2-TIMING-VARIANCE.json path=dose_response_verdict.covariate_swing_x value=5.86 tol=0.001 -->
**5.86×** (from 7 to
<!-- cite: id=C2-dose-rg file=C2-TIMING-VARIANCE.json path=summary.repo-fixed-DOSE-noskip.rg_calls_max value=41 -->
41) and median wall time rises
<!-- cite: id=C2-time file=C2-TIMING-VARIANCE.json path=dose_response_verdict.median_time_swing_x value=4.42 tol=0.001 -->
**4.42×** (4,187 ms →
<!-- cite: id=C2-dose-med file=C2-TIMING-VARIANCE.json path=summary.repo-fixed-DOSE-noskip.median_ms value=18517.2 tol=0.001 -->
18,517 ms).
<!-- cite: id=C2-h2 file=C2-TIMING-VARIANCE.json path=dose_response_verdict.H2_supported value=True -->
**H2 holds.** The 33,938 / 11,590 / 4,406 spread is not instrument failure and not lying —
it is three different diffs.

**The correctly-scoped claim.** wire-check's cost is a function of the session diff, not a
constant. On the tree as it stood on 2026-08-13 the live copy runs at 15–25% of its 25 s
budget; driven to a ~123-file diff the fixed copy reaches
<!-- cite: id=C2-dose-pct file=C2-TIMING-VARIANCE.json path=summary.repo-fixed-DOSE-noskip.max_pct value=82.6 tol=0.001 -->
**82.6%** and is held there by the 20 s deadline shipped in round 1 — which is therefore
load-bearing, not belt-and-braces. **The claim "the live hook is over budget and its output
is discarded every Stop" is withdrawn as a standing property**; it was true of one moment
with a ~250-file diff. Settling experiment for the worst case: re-run
`_c2_timing_variance.py` with `WIRE_CHECK_DEADLINE_S=0` on a comparable diff and read
`repo-fixed-DOSE-noskip.max_ms` — §C5's middle arm does exactly this and lands at 16.3 s.

A second, unlooked-for result from the same run: at an identical covariate (122–123 changed
files) the unfixed copy issues
<!-- cite: id=C2-unfixed-rg file=C2-TIMING-VARIANCE.json path=summary.live-unfixed.rg_calls_max value=10 -->
**10** ripgrep walks where the fixed copy issues up to 41. **The unfixed hook is fast because
it is blind** — the cp1252 decode blanks the diff before symbols can be extracted. Speed was
a symptom of the defect, which is why "it got slower after the fix" was never a regression.

## C3 — the probe destroyed its own evidence, and the doc cited the hole

CONFIRMED, with a root cause worth more than the instance. `probe_hook_fleet.py` built a
fresh `res = {}` each run and wrote it whole, so a later `--inertness`-only run replaced
`{"timing": …, "inertness": …}` with `{"inertness": …}`. The timing key the document cited
was deleted by a subsequent run of the tool that produced it — silently, because a partial
result is indistinguishable from a complete one once written.

Fixed by merging instead of clobbering, plus a `_coverage` block stamping each section with
when and how it was produced, and a printed `CARRIED FORWARD` line naming any section this
run did not measure. The file now holds
<!-- cite: id=C3-measured file=B6-FLEET.json path=timing.entries_measured value=35 -->
35 of
<!-- cite: id=C3-total file=B6-FLEET.json path=timing.entries_total value=42 -->
42 timed entries alongside
<!-- cite: id=C3-dark file=B6-FLEET.json path=inertness.dirs_dark value=10 -->
10 dark of
<!-- cite: id=C3-dirs file=B6-FLEET.json path=inertness.dirs_total value=73 -->
73 dirs.

## C4 — "worst offender 50.6%" was measuring the box, not the hook

CONFIRMED. Round 1 said 50.6% (`PreToolUse` → harness); the verifier's re-run of the same
probe said 62.3% (`PostToolUse` → harness); a third run said 18.4% (`UserPromptSubmit` →
semantic-router). Three runs, three numbers, three different entries named as worst.

The mechanism is arithmetic, not mystery: these entries have 2–3 s budgets and 200–300 ms
wall times, so a few hundred milliseconds of Windows process-spawn jitter moves the
*percentage* by tens of points and reorders the table. A single-shot percentage of a tiny
budget is a property of machine load.

`run_timing` now takes `--repeat` and reports the worst **median** with its observed spread.
At
<!-- cite: id=C4-repeat file=B6-FLEET.json path=timing.repeat value=3 -->
repeat=3 the worst entry is `semantic-router` at
<!-- cite: id=C4-worst file=B6-FLEET.json path=timing.worst_pct value=17.8 tol=0.001 -->
**17.8%** of its 10 s budget, and it is *stable* —
<!-- cite: id=C4-min file=B6-FLEET.json path=timing.worst_entry.pct_min value=17.4 tol=0.001 -->
17.4% to
<!-- cite: id=C4-max file=B6-FLEET.json path=timing.worst_entry.pct_max value=18.1 tol=0.001 -->
18.1% — because its wall time is large relative to its budget. The harness entries that
previously took the crown swing 12.6–29.2% between samples on identical work.

The load-bearing statistic is the one that does not depend on the denominator: **no
settings.json entry has ever been measured above
<!-- cite: id=C4-abs file=B6-FLEET.json path=timing.max_wall_ms_any_entry value=1807.9 tol=0.001 -->
1,808 ms** on any sample, against budgets of 2–10 s, and the over-budget list is
<!-- cite: id=C4-over file=B6-FLEET.json path=timing.over_budget value=[] -->
empty. Residual, disclosed: repeat=3 bounds jitter, it does not eliminate it; a contended
box will still widen these. The 7 launcher entries remain unmeasured for the reason given in
round 1.

## C5 — the three-row A/B table had two rows of evidence

CONFIRMED. `B3-AB-BUDGET.json` contained `HEAD-unfixed` and `worktree-fixed` only; the
middle row ("encoding fix only", 64,996 / 69,625 ms) came from an uncommitted one-off and
was never reproducible.

Two repairs. First, the probe's own control had rotted: it read the unfixed arm from
`HEAD:hooks/wire-check/check.py`, and once the fix merged that path began returning the
*fixed* file, so the `had_encoding` guard would have voided every future run. The unfixed
revision is now pinned at
<!-- cite: id=C5-rev file=B3-AB-BUDGET.json path=unfixed_rev value=95761504~1 -->
`95761504~1`, and
<!-- cite: id=C5-guard file=B3-AB-BUDGET.json path=head_blob_already_had_encoding_kwarg value=False -->
the guard confirms that blob is genuinely unfixed. Second, the middle arm is reconstructed
from the shipped file with both mitigations off through their documented env knobs
(`WIRE_CHECK_DEADLINE_S=0 WIRE_CHECK_NO_SKIP=1`) — an honest reconstruction, labelled as one
in the artifact, and re-runnable, which the original was not.

| arm | wall (r1) | findings | reading |
|---|---|---|---|
| HEAD-unfixed | <!-- cite: id=C5-a-ms file=B3-AB-BUDGET.json path=runs.0.wall_ms value=3834.2 tol=0.001 -->3,834 ms | <!-- cite: id=C5-a-f file=B3-AB-BUDGET.json path=runs.0.finding_count value=6 -->6 | fast because blind; all 6 false |
| fix, no mitigations | <!-- cite: id=C5-b-ms file=B3-AB-BUDGET.json path=runs.1.wall_ms value=16304.9 tol=0.001 -->16,305 ms | <!-- cite: id=C5-b-f file=B3-AB-BUDGET.json path=runs.1.finding_count value=1 -->1 | the real cost of seeing the work |
| shipped | <!-- cite: id=C5-c-ms file=B3-AB-BUDGET.json path=runs.2.wall_ms value=8025.6 tol=0.001 -->8,026 ms | <!-- cite: id=C5-c-f file=B3-AB-BUDGET.json path=runs.2.finding_count value=0 -->0 | deadline + scratch skip |

The absolute numbers differ from round 1's by ~7× in every arm — same cause as §C2, a
smaller diff — while the ORDERING and the finding counts reproduce exactly. That ordering,
not the milliseconds, is what the A/B was ever able to support.

Disclosed inline: the middle arm emits **1** finding the shipped arm suppresses. It is a
version-suffix finding on `_audit7_adv0041.py`, an untracked sibling-lane scratch file —
i.e. exactly the class F3's scratch skip exists to drop, and visible with
`WIRE_CHECK_NO_SKIP=1`. The skip is doing what it says, on one file, today.

---

## N1 — git-hygiene's permanent false positive, fixed (NEW)

Every Stop firing reported `[YOURS] agent-skills-toolchain: 2 uncommitted file(s) at a
detached HEAD, no upstream`. Measured directly, the two entries are
`tools/mcp/cloud-hub/accounts.json` and `tools/mcp/search-hub/accounts.json` — the live
credential-rotation pool. A standing owner constraint forbids staging it, so **uncommitted is
the correct state and always will be**, and the hook's printed remedy ("commit, then
`git push -u origin HEAD`") is an action that must never be taken. This repo was going to be
flagged on every turn forever.

Fixed with a live-state path filter in `_parse_status_v2`, defaulting to `accounts.json`,
tunable via `GIT_HYGIENE_LIVE_STATE`, and **auditable** — the excluded count rides on
`RepoState.dirty_excluded`, is printed in the verdict detail, and `GIT_HYGIENE_NO_SKIP=1`
turns the whole filter off.

`test_live_state_exclusion.py` was run against the unfixed file first and went red on 4
cases. Every suppression case is paired with a fire case, so a "fix" that merely stops
finding things fails the file: accounts.json alone is silent, but accounts.json *plus* a real
file still reports — and reports **1**, not 3. The filter also covers porcelain-v2 record
types `2` (rename) and `?` (untracked), because a renamed or untracked copy of the same file
would otherwise walk straight back in.

Unit-level proof is not message-level proof, so `_n1_live_state_e2e.py` runs the whole hook
against the real disk in both states:
<!-- cite: id=N1-on file=N1-LIVE-STATE-E2E.json path=filter_on.target_named value=False -->
absent with the filter on,
<!-- cite: id=N1-off file=N1-LIVE-STATE-E2E.json path=filter_off_CONTROL.target_named value=True -->
present with it off. The control is the load-bearing half: without it, "absent" could equally
mean the scanner never reached the repo, the budget expired, or the 15-minute throttle
suppressed the run — three ways to get a silent pass that proves nothing. Every other repo
(`ast-integrate`, `csie-foundation-wt`, `databricks-fanout-harness`, `ast-patch167`, the
no-remote `scratch`) is still reported in both states.

**Partial settlement of a round-1 UNVERIFIED.** Round 1 could not exercise git-hygiene's
unthrottled path, so its 90 s budget was untested. This run was unthrottled
(`GIT_HYGIENE_THROTTLE_SEC=0`) and took
<!-- cite: id=N1-ms file=N1-LIVE-STATE-E2E.json path=filter_on.wall_ms value=28314.7 tol=0.001 -->
**28,315 ms** — 31.5% of 90 s, and a close match to the 28,275 ms recorded when the budget
was raised. UNVERIFIED still, narrowed: this scan was scoped to `~/source` with the sync,
docs and coverage halves off, so it is a floor, not the full-root cost. Settling experiment:
re-run `_n1_live_state_e2e.py` with `GIT_HYGIENE_ROOTS` unset and the three halves on.

## N2 — the squash-merge `ahead_by` claim does NOT reproduce (REFUTED)

The hand-off attributed `[YOURS] ast-patch167: 1 uncommitted file(s)` to the documented
squash-merge trap, on the grounds that its commit `69ec33a` is already merged as PR #260 and
a squash rewrite leaves the branch reporting 1 ahead forever.

Measured: that repo reports `# branch.ab +0 -0` — git already knows it is not ahead — and its
single dirty entry is `? e2e/`, an untracked directory. **The hook never made the ahead claim
attributed to it.** The trap is real as a class (it is in `ci-hygiene.md`), but it is not
firing here, so no `git cherry` guard was added: building a fix for a defect that does not
reproduce is the same overclaim shape this round exists to correct. The measurement is pinned
as a re-runnable case (`test_squash_merge_claim_does_not_reproduce`) rather than asserted, and
it SKIPS rather than passes if that repo disappears.

Not a defect either, examined and dismissed: counting `? e2e/` as uncommitted work is correct
behaviour — an untracked directory can hold real work, and the hook cannot know it does not.

## N3 — the stub-ledger phantom count: UNVERIFIED, not fixed

The hand-off reports 31 placeholders cited across five files that exist in none of the nine
clones, with a sound detector control (the same `find` fires on a known-present file). The
proposed mechanism — the ledger records at write time and never re-validates at report time —
is **UNVERIFIED here; I did not read the ledger's storage or report path**, and it is
out of the budget this round spent on the five confirmed defects. Settling experiment,
unchanged from the hand-off: write a file containing `# PLACEHOLDER`, delete it, and check
whether the next Stop firing still cites it. Fix shape, if confirmed: a `Path.exists()` filter
at report time, and phantom entries counted separately rather than summed into the headline.

## D1 — the wire-check fix is committed and still NOT deployed

Unchanged and re-confirmed this round by direct hash comparison (`arm_control` in
`C2-TIMING-VARIANCE.json`: `live_has_encoding_fix: false`, `repo_has_encoding_fix: true`),
and by a live `UnicodeDecodeError: 'charmap' … byte 0x9d` raised from
`subprocess._readerthread` during this round's own probe runs. The running hook is the
unpatched copy.

Not deployed by this lane, deliberately: the live tree is outside this lane's file scope,
nine lanes are mid-flight, and hand-copying a deployed hook is the anti-pattern
`harness-vcs-hygiene` names. The deploy plan and its verification recipe are in
`ROLLBACK-DEPLOY-PLAN.md`; the recipe's key clause is that silence is not proof — after
deploying, feed the hook a single-file script whose function is called only at module level
and require it to stay SILENT, **and** feed it a genuinely unreferenced function and require
it to FIRE.

---

## The class fix: `check_citations.py`

Every defect in the C-table is one shape — *a published number drifted away from its evidence
and nothing was watching*. Three instances in one document, found by a human reader.

`check_citations.py` resolves each inline `cite:` marker — an HTML comment carrying
`id`, `file`, `path`, `value` and an optional `tol`, so it renders invisibly — by opening the
named file, walking the named JSON path and comparing to the number printed here. It does not
read prose and it does not trust a claim. Its own controls:

* **fail-closed on zero citations** — an unannotated document silently passing is the exact
  failure it exists to prevent. Verified: exit 1 with the message, before any citation existed.
* **`--self-test` mutates every expected value and requires a red for each.** A citation the
  checker cannot fail is not being checked.
* **untracked ≠ missing.** An uncommitted evidence file is its own failure mode, because that
  is precisely how C1 shipped: present to its author, absent in a clone.
* **the OTHER side of the comparison.** `--self-test` mutates the expected value, which
  simulates the *document* drifting. The defect that actually happened (C3) was the
  *evidence* drifting under a document that never moved. Those are opposite sides of one
  comparison and exercising one does not demonstrate the other, so
  `_c6_gate_evidence_side.py` tampers with a committed evidence file in both real shapes —
  key deleted and value changed — and requires a NEW failure for each, measured against
  that same run's own baseline rather than against an assumed-green one (this probe cannot
  assume green: the document cites the probe's own output, so its first run is legitimately
  red, and a baseline red for any unrelated reason would otherwise mask the thing under
  test):
  <!-- cite: id=C6-del file=C6-GATE-EVIDENCE-SIDE.json path=tamper_detected_key_deleted value=True -->
  a NEW unbacked citation appears when the key is deleted,
  <!-- cite: id=C6-chg file=C6-GATE-EVIDENCE-SIDE.json path=tamper_detected_value_changed value=True -->
  and again when the value is changed, and the file
  <!-- cite: id=C6-restore file=C6-GATE-EVIDENCE-SIDE.json path=restored_byte_exact value=True -->
  restored byte-exact (sha256 compared before and after).

Its strongest evidence is not synthetic, though: run against this very document before the
JSONs were committed, the gate returned **13 unbacked of 30** and named two untracked
evidence files and one path that does not resolve — the C1 and C3 shapes, caught on the
author's own work before publication rather than by a reader afterwards.

Residual, inline: the gate proves the number in the prose matches the number in the JSON. It
cannot prove the JSON describes what the prose says it describes — a citation pointed at an
unrelated-but-equal value would pass. Narrowing that needs a second reader, not a stricter
regex.

---

## Two defects this round committed in its own instruments, recorded not deleted

Both were caught by a control, not by review, and both are the same shape as C1–C5.

**1. The blob gate read the wrong commits and still said SUCCESS.** `_r2_blobgate.py`
defaulted to `HEAD~1 HEAD`. Nine lanes commit to this branch, so by the time it ran, `HEAD~1`
had drifted onto a sibling lane's commit: it staged **1** `.py` blob instead of 9, found it
clean, saw its mangled control correctly flagged, and printed `SUCCESS`. The control was
sound and proved the wrong thing — it demonstrates the checker READS files, never that it
read the RIGHT ones. What caught it was the self-contradiction between "1 .py blob" and two
commits known to hold nine. Fixed by pinning the revisions to `63ff313d 03365d08` and adding
a `MIN_PY = 9` coverage floor that fails closed. Final run: 9 blobs, 0 CRLF, `ruff check`
clean, `format --check` clean with only the control flagged.

**2. A commit message overstates a count.** `03365d08` says "33 citations"; the real number
is **32**. It was written before the `C6-base` citation was removed to break a self-reference
(the artifact would otherwise have cited its own baseline and needed three runs to converge).
History is not rewritten to hide it. The live count is whatever `check_citations.py` prints,
which is the point of having the gate.

## Deployment status of everything shipped this round

Both hook fixes are **repo-only**. Verified by direct read: the live
`~/.claude/hooks/git-hygiene/check.py` has 0 occurrences of `LIVE_STATE_GLOBS` and an mtime of
2026-08-07, and the live `wire-check/check.py` still has 0 occurrences of `encoding="utf-8"`.
So **the accounts.json false positive will keep firing every turn, and the cp1252 defect stays
live, until the repo→live deploy step runs** — the same architectural hole as D1, now holding
two fixes instead of one. Nothing here should be read as "the running harness is fixed".