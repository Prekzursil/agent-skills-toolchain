# HOOKRESEARCH — BUILD round 5 (re-entry after a CONFIRMED refutation)

The round-4 adversarial verifier CONFIRMED, deterministically, that a probe in this lane
**destroys its own committed evidence on its failure path**. That defect was still live. This
round fixes it, finds two siblings sharing the shape that nobody had looked for, and closes a
second-order consequence the defect had been hiding.

COVERAGE — MEASURED here: the fail-path write shape across all 67 python files in
`command-center/hook-audit/`, with a pinned pre-fix baseline; the executed damage of the
confirmed instance and the executed preservation after the fix; pytest collection for every
`test_*.py` under `hooks/`; the citation gate before, during and after.
NOT MEASURED, stated inline where load-bearing: the success-path drift of
`_r4_githygiene_range.py` (read from source, not executed to completion — its arms did not
separate on this box); whether any of this changes live harness behaviour (nothing live was
touched); per-hook wall time (rounds 1-4 own that axis and I did not re-run it).

If a section below still reads "UNKNOWN - not yet measured", the unit died before measuring it
and no verdict there may be cited.

---

## 0. A self-correction made before any measurement, recorded not deleted

My first action was to write a skeleton artifact — and I wrote it to
`docs/hook-audit/BUILD-R3.md` **without checking whether the path existed**. It did. It was
tracked, and the write destroyed 242 committed lines. `git status` caught it on the next
command and `git checkout --` restored it; `git diff` is empty for that path in this round's
commits.

I am opening with it because it is the same defect class as the one I was spawned to fix — an
irreversible-looking write performed without reading the other side first — committed by the
agent fixing it, within sixty seconds of starting. The ground rule that would have prevented it
(*"Deleting, merging, moving or consolidating anything requires reading BOTH sides first"*) was
in my instructions and I applied it to other people's probes and not to my own file handle.

## 1. V3 — the CONFIRMED defect, and two siblings

`_r4_githygiene_range.py` writes its partial `out` dict over `R4-GITHYGIENE-RANGE.json` in the
INCONCLUSIVE branch and then returns 1. Scanning every python file in the directory for that
shape — a write to a **git-tracked** JSON followed by a non-zero exit in the same statement
list — finds it is not alone. Against the pinned pre-fix blobs:

| | count |
|---|---|
| probes overwriting committed evidence on a fail path | <!-- cite: id=R5-fp-probes file=B13-FAILPATH-WRITES.json path=prefix_baseline.n_offender_probes value=3 --> **3** |
| distinct write sites | <!-- cite: id=R5-fp-sites file=B13-FAILPATH-WRITES.json path=prefix_baseline.n_offending_sites value=4 --> **4** |
| after this round's fix | <!-- cite: id=R5-fp-now file=B13-FAILPATH-WRITES.json path=n_offenders value=0 --> **0** |

The three are `_r4_githygiene_range.py` (1 site), `_r4_budget_ceiling.py` (2 sites) and
`_r4_wire_exit.py` (1 site). The verifier found the first; the other two had never been asked
about, which is the blast-radius failure AGENTS.md §9b names — remediating the first symptom
of a confirmed defect instead of the whole set.

**Two damage modes, not one.** `githygiene` and `budget_ceiling` write a strict SUBSET of the
successful payload, so keys vanish. `wire_exit` keeps every cited key but its fail branch is
reached precisely when `repo_finding_rc == repo_clean_rc`, so it replaces a real measurement
with values that are equal by construction — a non-measurement that still parses as one. The
second is worse to read and would not have been caught by a key-count check.

### Executed, not inferred

Forcing the confirmed instance down its fail path with `GIT_HYGIENE=off`
(`hooks/git-hygiene/check.py:1184` makes both arms early-return, so the failure is
deterministic rather than lucky):

- top-level keys lost from the committed file:
  <!-- cite: id=R5-dr-keys file=B13-DESTRUCTION-REPRO.json path=historical_prefix_damage.n_top_level_keys_lost value=6 --> **6**
- citation gate, before:
  <!-- cite: id=R5-dr-b file=B13-DESTRUCTION-REPRO.json path=historical_prefix_damage.gate_unbacked_before value=0 --> **0** unbacked
- citation gate, after:
  <!-- cite: id=R5-dr-a file=B13-DESTRUCTION-REPRO.json path=historical_prefix_damage.gate_unbacked_after_destruction value=18 --> **18** unbacked

The evidence was backed up outside the repo first and restored byte-exact, verified by sha256
and by the gate returning to its prior state on both axes.

**18, not the verifier's 15.** The blast radius GREW by three between rounds, because BUILD-R4
added three more citations against that same file. A defect of this shape gets worse the longer
it is left, since every later round pins more claims to a file that any failing run can empty.

### Why this one mattered more than its key count

Re-running a probe is how anyone CHECKS a published claim. A probe that empties its evidence
when it cannot measure **punishes verification** — and this is not a theoretical fail path.
Running `_r4_githygiene_range.py` normally, with no forcing at all, it went INCONCLUSIVE: its
arms measured 211.7 ms and 19,108.5 ms, a ratio of **90.3** against its own ≥100× discrimination
threshold. The numerator barely moved from the recorded run (15,901 → 19,108 ms); the
denominator nearly doubled (115.7 → 211.7 ms), because arm A is an early return whose cost is
dominated by interpreter startup and therefore by machine load. So the destructive branch fires
on an ordinary run on a busy box. I hit it twice in one session — once forced, once not.

<!-- uncited-table: reason=none; the four wall-clock values in this paragraph are deliberately NOT pinned -- they are exactly the run-dependent numbers section 4 argues must never be cited, and pinning them here would reintroduce the defect being described -->

## 2. The fix

One helper, `_evidence_io.write_evidence(target, payload, *, ok)`, decides whether a run may
replace a committed evidence file. `ok=True` replaces it; `ok=False` writes a sibling
`<name>.INCONCLUSIVE.json` and leaves the committed file untouched. All four sites now route
through it.

It is a shared module rather than the same guard pasted into three probes, following the
convention this directory already adopted for exactly this reason — round 4's `_r4_table_scan.py`
was made to import the gate's classifier after two copies disagreed on the same corpus in the
same minute.

**Post-fix, executed:** the same forced failure now leaves the committed file byte-identical
<!-- cite: id=R5-pf-untouched file=B13-DESTRUCTION-REPRO.json path=committed_evidence_untouched value=True -->
and the partial output lands in the sibling, with the gate unmoved on both axes
<!-- cite: id=R5-pf-d5 file=B13-DESTRUCTION-REPRO.json path=controls.D5_gate_rc_unchanged value=True -->.
Eleven regressions cover it, written red-first: **4 failed** against the pre-fix probes and 7
passed (the 7 are the helper-contract and scanner-discrimination arms, present so a later green
is not trivially green). All 11 pass now.

They are pytest functions, not another standalone `main()` script — see §3 for why that was a
live hazard rather than a style preference.

## 3. A second-order consequence the defect had been hiding

Re-running `_r4_budget_ceiling.py` — safe for the first time — immediately showed its committed
evidence was **stale**: `repo_violation_count` read 2 on disk against 1 in reality. Commit
`6c6d9a69` (BUILD-R4 §5.1) had lowered `Stop/git-hygiene` 90 s → 30 s in the repo manifest,
removing that violation, and nobody regenerated the evidence measuring it. Two documents went on
citing a tree that no longer existed for a full round.

The gate caught it on the first attempt, and its message is the useful part —
`repo_violation_count is 1 on disk but 2 in the staged blob — a clone reads the second one` —
so the fix is to commit the regenerated evidence WITH the corrected sentences, which this round
does. Both citations are corrected in place with the superseded value and its cause recorded
rather than swapped out (`HOOK-AUDIT.md`, `ROUND4-CORRECTIONS.md`).

**The causal chain is the finding, not the number.** The fail-path defect made re-running these
probes hazardous; so nobody re-ran them; so a fix landed without its evidence being refreshed
and no gate could see it. Fixing the destructive branch is what made the staleness detectable.

### Measured while here: `pytest hooks/` does not run at all

<!-- uncited-table: reason=counts come from a pytest collection sweep run in this round; the artifact is the command and its exit codes, reproduced in the evidence section, not a JSON blob -->

| | |
|---|---|
| `test_*.py` files under `hooks/` | 105 |
| that pytest collects **zero** tests from | 32 |
| `python -m pytest hooks/ --collect-only` | `INTERNALERROR> SystemExit: 0`, **rc=3** |

**I expected a silent coverage hole and the measurement REFUTED it.** My hypothesis was that a
directory-level run would quietly skip 32 files and report green over the other 73. It does not:
the standalone scripts call `sys.exit()` at import time, so collection dies with an
INTERNALERROR and the whole invocation fails loudly. The honest statement is narrower and still
worth having — **the hooks fleet has no working directory-level pytest entry point**; its 73
collectable suites can only be run file-by-file, and the 32 standalone ones only via `python`.
Not fixed here: reshaping 32 files is its own round with its own red-first proof.

## 3a. Wired, so it does not depend on anyone remembering

The 11 regressions are now a step in `.github/workflows/hook-audit.yml`, and
`_b10_ci_proof.py` executes all five wired commands from a **fresh clone of HEAD** with `HOME`
and `USERPROFILE` redirected to a nonexistent directory: **5/5 green**, with the redirection
proven to bite, the gate proven still able to go RED inside the clone, and the clone proven to
contain the wired files. Working-tree green is not clone green; this lane has shipped that
mistake before.

That probe kept its own hand-written copy of the workflow's command list — the same hardcoded-list
shape that let a CI-red file stay invisible for two commits in `_r4_blobgate.py`. It now carries
**C4**, which compares its list against the workflow's actual `run:` steps in both directions and
fails closed if the workflow cannot be read.

## 4. What is still hazardous, stated rather than implied

**`_r4_githygiene_range.py` remains unsafe to re-run on its SUCCESS path.** Four of its cited
values are wall-clock-derived — `A_throttle_effective.ms`, `B_throttle_defeated.ms`,
`ratio_defeated_over_effective` and `understatement_factor_vs_h4` (`round(b / 0.3)`) — so a
successful re-run necessarily moves them and breaks their citations. This round fixed the
branch that DESTROYS data; it did not un-pin the numbers that legitimately move, which is the
discipline round 3 recorded as O2 and BUILD-R4 §7.4 applied to its own wall times.

Scope of my claim, precisely: **the fail path no longer destroys committed evidence.** Re-running
these probes is not yet fully safe. UNVERIFIED inline: I did not observe the success-path
breakage, because the probe's arms did not separate on this box — the four values above are read
from source, not executed. **Settling experiment:** run it on an idle box until
`arms_discriminate` is true, then run `check_citations.py` and count the broken ids; the fix is
to replace those four citations with the stable ones already in the file
(`arms_discriminate`, `stamp_restored_exact`, `range_ms`) and waive the wall-time table.

**And the scan's "0 offenders" is narrower than it sounds.** It measures TRUNCATE-AND-BAIL — a
partial payload written over committed evidence with a non-zero exit in the *same statement
list*. A probe that writes a **complete** record and only then decides to exit non-zero is
deliberately out of scope, pinned by control **C6**
<!-- cite: id=R5-c6 file=B13-FAILPATH-WRITES.json path=controls.C6_complete_record_write_is_out_of_scope value=True -->,
because widening the rule would flag the honest record-the-failure-completely pattern and turn
the scan into the noise this audit's own axes complain about.

The residual that leaves is real and smaller: `_b10_ci_proof.py` and both of my own `_b13_*`
probes write their evidence before the exit decision, so a failing run still REPLACES the
committed file — with a full record, but one whose booleans have flipped. `B10-CI-PROOF.json`'s
`controls.C2_gate_can_fail_in_clone` is cited by BUILD-R2, so a failing CI-proof run would
break that citation. Key loss cannot happen there; value flipping can. **Settling experiment:**
force `_b10_ci_proof.py` to fail (point `WORKFLOW` at a missing file so C4 goes false), then run
the citation gate and count the broken ids — if it is non-zero, route those writes through
`write_evidence` too. I did not run it, so I do not claim the count.

## 5. Detector controls

| probe | control | why it exists |
|---|---|---|
| `_b13_failpath_writes.py` | C1 broken-shape FIXTURE is flagged | pinned the live file first; repointed before the fix could rot it |
| | C2 success-path write NOT flagged | else "everything is flagged" reads as a finding |
| | C3 untracked fail-path write NOT flagged | separates *destroys evidence* from *writes on a fail path* |
| | C4 walk non-empty (≥20 files, ≥5 tracked JSON) | a zero from a blind walker is not a clean bill |
| | C5 pinned pre-fix blobs still show the defect | else the "3 → 0" claim loses its *before* |
| | C6 complete-record write NOT flagged | pins the detector's SCOPE — see §4 |
| `_b10_ci_proof.py` | C4 WIRED list matches the workflow | a hand-copied command list drifts silently |
| `_b13_destruction_repro.py` | D1-D5 | baseline clean, fail path really taken, file untouched, axis unmoved, nothing else moved |

<!-- uncited-table: reason=index of which control guards which probe; each control's value is asserted and cited at its point of use above rather than re-cited here -->

C1 and C5 are the two that matter. **C1 pinned `_r4_githygiene_range.py` by name in the first
draft** — a control that would have started failing the moment the defect was fixed, i.e. one
that reports a problem because the tree got better. This lane has already paid for that shape
(`d2177dd3`, *"my both-states control pinned itself to HEAD and rotted on the next run"*). It was
repointed to a fixture **before** the fix landed. C5 is its mirror: the pre-fix baseline is read
from three blob SHAs, not from HEAD, so committing the fix cannot quietly turn the *before*
number into 0.

## 6. Self-corrections made before publishing

1. **I overwrote a tracked 242-line document with a skeleton** — §0. Restored byte-exact.
2. **My repro failed its own controls while the thing it measured worked.** D1 asserted the
   gate's exit code was 0; the gate was red because *my own* in-progress `BUILD-R5.md` had zero
   citations and tripped the per-document floor. The control was bound to a coarser signal than
   the claim, so it failed on my own unrelated work. Rebound to `unbacked`, with the exit-code
   check kept separately as D5.
3. **I predicted a silent coverage hole in `pytest hooks/` and the measurement refuted it** —
   §3. It fails loudly, rc=3. The narrower true statement shipped instead of the one I expected.
4. **I wrote "gitignored scratch" into `_evidence_io`'s docstring without checking.**
   `git check-ignore` exits 1 on the sibling: it is untracked, not ignored. Sentence corrected;
   the difference matters because nothing prevents someone committing one.
5. **My repro was a one-shot that would have rotted.** Its first version asserted the committed
   file now reads `INCONCLUSIVE` — true only of the broken code. Rewritten to assert
   PRESERVATION, with the pre-fix damage kept as a pinned historical block naming the blob it
   was measured against.

## 7. What this round did NOT do

- **Nothing live was touched.** No file under `~/.claude` was written. The three fixed probes,
  the helper and the regressions are all repo-side.
- **No hook behaviour changed.** `hooks/**` is in this lane's scope and I edited nothing in it;
  the only reads were `git-hygiene/check.py:1184` for the env knob and the collection sweep.
- **`/rollback` is still unresolved.** `edit-checkpoints` and `mcp-liveness/pretool` remain
  undeployed; the deploy plan still stands unexecuted. Unchanged by this round.
- **The repo→live deploy step still has no gate**, and the 12 DIVERGED wired bodies were not
  touched. Still the largest hole in this audit.
- **The 32 uncollectable hooks test files were not reshaped** — §3.
- **The fleet was not re-timed** and no inertness probe was fired.

## 8. Noise observed while working (DoD-4 corpus)

`SENSITIVE ARTIFACT REPORT` fired **three times** on my edits to `_r4_wire_exit.py`, every time
with the identical artifact id `sha256:47e638ec2abd` — a probe whose only "credential" is a
synthetic `settings.json` fixture it builds at runtime to drive `wire.py`. This is the **fourth**
independent corpus for the repeat-fire false positive already named in DoD-4 (round 2:
`test_secrets.py`; the round-3 auditor's own scratch file; BUILD-R4: `test_hook_predeploy_gate.py`),
and it strengthens the same proposed fix: dedupe by artifact id per session.

`per-edit-check` fired usefully in the same window — F401 on each of the three probes at the
moment I added the import and before I had rewired the call sites, and F841 on a control variable
I assigned before using. Correct every time, and it is the reason those three edits did not ship
with dead imports. The fleet is not uniformly noisy; the defect is specific and worth fixing
rather than silencing.
