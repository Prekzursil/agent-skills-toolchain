# VERIFY-SLOP-R2 — adversarial verification of BUILD round 2 and the CLEAN audit

VERDICT: **build_is_sound = true · audit_holds = true · must_fix = EMPTY.**

COVERAGE: every DoD item re-executed by me at the live HEAD, not read. Four non-blocking
findings below (F1–F4), none of them a defect in the builder's code. NOT measured: the other
~84 `quality.yml` steps (I measured `gate-lint-format` only); whether the 29 carried files are
byte-unchanged (the pre-commit disk state is gone — the auditor's "likely 55-80%" is the
correct band and I confirm the settling artifact does not exist, see V8).

If this file still reads as a skeleton with `UNKNOWN - not yet measured`, the unit died before
measuring anything and no verdict here may be cited.

HEAD moved under me three times while I ran (`1461850c → dc0d30b7 → c2c293a5`). Siblings are
live in this tree. I verified `git diff --name-only 1461850c..HEAD -- command-center/slop-report`
is EMPTY before restoring anything, so no sibling byte was at risk.

---

## What I executed

| # | claim under test | my method (different from theirs where it mattered) | result |
|---|---|---|---|
| V1 | D2 fix works, both states | ran `_b1_control.py` and `--sentinel legacy` directly | default rc 0 / PASS / quiet 0 · legacy rc 1 / FAIL / **quiet 7** — distinguished by exit code |
| V2 | the lane did not turn main red | `_r2_gate_now.py` at the live HEAD (`1461850c`), fresh LF clone, CI pin 0.15.17 | `check rc=0`, `format --check rc=0`, **0 would-reformat**, 6/6 controls, 2402 tracked `.py`, **0 CRLF** |
| V3 | commit integrity, all 8 lane commits | my own `git show --name-status` loop, not their probe | anc=True on all 8 · files 6/8/29/10/4/2/15/6 — **exact** · del=0 · foreign=0 |
| V4 | frozen evidence untouched | **wider range than either lane used** — `fa87d1a2~1..HEAD` (both rounds), not `61e69cf2..HEAD` | 0 commits touching · 0 diff · 0 dirty, for `casualty/probes` (7) and `p2-wave/probes` (25) |
| V5 | the committed suite reproduces | ran **all 20** committed lane probes from the committed state (`_v2_suite.py`) | 20/20 rc 0 · runner control: known-pass rc 0 / known-fail rc 1 |
| V6 | O2 decomposition is a property, not a coincidence at one rev | re-derived at a rev **neither lane measured** | 305 − 45 + 6 = **266** = measured `n_files_leaving_the_gate`. Residual 0. Holds |
| V7 | `.gitignore` ↔ `ruff.toml` ↔ tree are consistent | `git ls-files` vs negation-line count vs disk | 45 tracked `command-center/_*.py` · 45 `!command-center/_` lines · 0 missing on disk · **0 tracked deletions anywhere in the worktree** |
| V8 | residual #4 (digest manifest) is genuinely unverified | opened `_VERIFY-SLOP-R1.json` and searched it | contains **no `sha256` at all** — the settling artifact does not exist. The band is right |
| V9 | two inherited round-1 classifications | re-executed with a controlled matcher | R12: **0** `advver`/`M14` paths tracked or on disk (control: same matcher finds 117 `slop-report`) · R9: **13** empty dirs incl. `platform/~/` — both as published |

`_r2_gate_now.py` banner at HEAD:

```
gate @ 1461850c (2026-08-13T04:30:33+00:00): ruff check rc=0, format --check rc=0 with
0 would-reformat. THIS TREE MOVES -- re-run
`python command-center/slop-report/_r2_gate_now.py` before citing this line.
```

## The D2 fix is the strongest artifact in the set, and I tried to break it

`--sentinel legacy` cannot rot green: `citations()` greps HEAD blobs, `_b1_control.py` is
tracked, and `LEGACY_SENTINEL` is a literal in it forever. If the fix were REVERTED the flag
would not parse and argparse would exit rc 2 — still not rc 1, so `_r2_fix_verify` still fails.
Both directions are covered. This is a control with a failing state, which is what this program
usually lacks.

---

## Findings (4). None blocking. None is a defect in the builder's code.

### F1 — the audit CONFIRMED a builder residual that is not in the repo. LOW.

`_AUDIT-SLOP-R2.json` / the audit narrative say *"Residual #6 (receipt drift benign) …
Confirmed"* and list *"6 receipts drift, benign"* among claims tested. Measured:
`SLOP-BUILD-R2.md` has exactly **five** numbered residuals (1–5) and the strings `receipt
drift` / `6 receipts` appear in **zero** lane `.md` files.
`git grep -n -i "residual #6" HEAD -- command-center` returns hits ONLY inside the auditor's own
artifacts — `_aud2_rot.py:1`, `_aud2_rot.py:3`, `_aud2_msg.txt:27`. The verbatim quote almost
certainly came from the builder's ephemeral orchestration handoff, not from anything committed.

Why it is not blocking: the underlying property was really executed and really holds (I re-ran
`_aud2_rot.py` on a clean tree → rc 0, `DRIFT-BENIGN-AND-DETECTOR-PROVEN`, 0 verdict-bearing
leaves moved across 6 receipts, synthetic-flip control fires). The builder's committed report
makes no false claim, so BUILD has nothing to fix. Fix is one sentence in the audit: cite the
handoff explicitly, or land the residual in the `.md`. Same class as the lane's own round-1
finding (a citation that dangles on a clone), recursed one more level.
Adjacent: the audit cites *"residual #5"* for the byte-unchanged uncertainty; in the committed
report that is **#4** (#5 is "nothing pushed").

### F2 — "exactly 6 receipts dirty" is scoped to a six-probe list; the real number is 14. LOW.

`_aud2_rot.py:36-43` defines `SUITE` as six probes, so "6" is correct *within that scope*.
Running the lane's **full** committed probe set (20) dirties **14** tracked receipts —
including **8 of the auditor's own** (`_aud1_census`, `_aud2_commits`, `_aud2_files`,
`_aud2_dod34`, `_aud2_eol`, `_aud4_files_and_buckets`, `_aud6_residuals`, `_aud7_blastradius`)
plus `_ver3_dod`. Measured in `_v2_suite.out.json` → `probes_that_dirty_tracked_files`.
Not blocking: same benign class (rev/count/status leaves), and the D2 fix already de-fanged the
one that mattered — the *published* regenerator is now read-only by default.

### F3 — a vacuous-control shape in the AUDITOR's DoD-4, latent not live. LOW.

`_aud2_dod34.py:89-93` computes `untouched` as `not changed_in_range and not commits_touching
and not dirty` — with **no `len(files) > 0` guard**. A frozen path that did not exist would
therefore report `untouched: true`: silence from three git queries about a nonexistent pathspec
is indistinguishable from silence about an untouched one. The builder's `_r2_frozen.py:81` has
exactly that guard (`… and len(files) > 0`). Not live — I confirmed both dirs exist (7 and 25
files) — and `control_hasher_nonconstant` incidentally covers `FROZEN[0]` only, never `FROZEN[1]`.
One line fixes it.

### F4 — A-O1 is real and the number has moved again. CONFIRMS the audit.

`SLOP-BUILD-R2.md` Residual #1: *"cost 208 files of lint coverage"*, no rev anchor.
Measured: 208 @`f009c680` (builder) → 233 @`2caafe53` (auditor) → **266 @`1461850c`** (mine).
§O2 at line ~197 anchors it correctly and warns it grows, so this is a stale restatement, not a
wrong measurement. The recommendation (**do not widen the exclusion**) is unaffected and gets
stronger as the number grows.

---

## My own detector failures (2), recorded rather than dropped

1. **I mis-measured a file length with an instrument that drops empty lines.**
   `Get-Content … | Measure-Object -Line` reported **275** for `SLOP-BUILD-R2.md` while
   `Select-String` was returning a heading at line **326**. A self-contradicting output is a
   detector failure, not a finding. `@(Get-Content …).Count` → **339**. Had I trusted the first
   reading I would have "found" a truncated report.
2. **My own runner reproduced the ambient-state rot this lane audits — third recursion.**
   `_v2_suite.py` ran 14 receipt-writing probes *before* `_aud2_rot.py`, whose documented
   precondition is a clean tree. It correctly returned `PRECONDITION-FAILED-TREE-ALREADY-DIRTY`,
   rc 1, and my first reading of that was "the suite does not reproduce". It does: restored the
   15 paths (all clean at start, and no sibling commit had touched them) and re-ran on a clean
   tree → rc 0, `DRIFT-BENIGN-AND-DETECTOR-PROVEN`. The probe failing closed is the *correct*
   behaviour; my ordering was the bug.

## What I did NOT establish

- **Whether all ~86 `quality.yml` steps pass.** I measured `gate-lint-format` (ruff check +
  ruff format --check) at the CI pin only. Everything I say about "the gate" is scoped to ruff.
- **Whether the 29 carried files are byte-unchanged.** Not verifiable post-hoc: the pre-commit
  on-disk state is gone, `+3057/-0` looks identical whether or not they were reformatted (a
  pure-addition diff is not a distinguishing signal), and V8 shows no digest manifest exists.
  The auditor's *likely (55-80%)* is the right band; I did not narrow it.
- **Whether `origin/main` is current.** Nothing in this lane is pushed.
- **Whether the 78 uncited root probe scripts have value.** Still untracked, still destroyed by
  `git clean -Xdf`, still correctly not proposed for deletion.

*Artifacts: `_v2_suite.py` / `_v2_suite.out.json` (20-probe re-execution with a both-states
runner control), `_v2_gate_head.json` (`_r2_gate_now.py` at the live HEAD).*
