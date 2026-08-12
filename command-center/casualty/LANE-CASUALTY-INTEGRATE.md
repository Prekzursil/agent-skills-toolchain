# LANE CASUALTY — INTEGRATE

**What this stage did:** made the lane's work *reachable*, and proved the wiring can fail.

Generated 2026-08-12. Commits `f087a6f6` (the wiring) and the follow-up recorded in §6.
Every command below was executed; its real output is pasted, not paraphrased.

---

## 1. The problem INTEGRATE was for

Rounds 1 and 2 shipped two recovered receipts and six instruments into
`command-center/casualty/`. The adversarial audit confirmed every one of them. None of them
was called by anything. Grepped at the start of this stage: `.github/` contained **zero**
references to the lane, so the only thing keeping it from rotting was somebody remembering it
existed. That is not a resting state — it is the same shape already recorded twice on this
estate (`tools/detector-self-test/`, the gate-fabrication instrument, is wired into no CI job,
no hook and no skill; `tools/measure-guard/` had no agent-facing surface at all).

Four of the instruments also hardcoded `C:/Users/Prekzursil/source/ast-integrate` as the repo
root, so **none of them could run on a runner or in a fresh clone** — lesson 1 of this program,
reproduced inside the lane that exists to catch it.

## 2. What is now wired (three surfaces)

| # | Surface | Concretely | Verified by |
|---|---|---|---|
| I1 | **CI gate** | `.github/workflows/quality.yml:437-439` runs the lane's pytest suite, `casualty_guard.py`, and `integration_redproof.py` inside the existing `gate-tests-coverage command-center` step | `probe_wiring` reads the COMMITTED blob: worktree line 439 == blob line 439 |
| I2 | **Register enrolment** | `tools/measure-guard/suitefloor.py` registers a `casualty` suite (path `command-center/casualty/tests`, 32 collected, floor 28); `quality.yml` enforces it with `--suite casualty` | `SUCCESS:suite-floor 1 suite(s) at or above floor` |
| I3 | **Reachable instruments** | `casualty_guard.py` — six probes, and a disposition table that gates every shipped instrument in both directions | `SUCCESS:casualty-guard 6 probe(s) green` |

Deliberately **not** a new `gate-<slug>` step: `.quality/charter.yml` is a closed set and
`charter_check.sh` enforces it, so the lane rides inside an existing gate instead of widening
the contract. Re-run after the edit: `charter_check: OK -- 6 gates consistent`.

### What `casualty_guard.py` actually checks

- **P1 wiring** — quality.yml must *invoke* the guard. Comment lines are stripped first, so a
  path named in prose does not count. (use-vs-mention produced four false findings in one wave
  here.) Second, mechanically independent signal: the same check against
  `git cat-file -p HEAD:...`, and by default a worktree/blob disagreement **fails** — an
  uncommitted wire is one a fresh clone would not run.
- **P2 inventory** — every shipped instrument carries a disposition (`EXECUTED` /
  `CI-EXECUTED` / `TESTED` / `EXEMPT` + a written reason); every disposition names a file that
  exists; every file parses. Fail-closed both ways, and on an empty walk.
- **P3 receipts** — both recovered receipts still reproduce their published elided sha256 and
  declared byte count, cross-checked against `verify_elided_digest.py` executed as a
  subprocess. A disagreement between the two **fails** rather than picking a winner.
- **P4 no-lost-work** — a substantive artifact for each unit must exist *somewhere*.
  Location-agnostic on purpose: promoting the receipts to `command-center/adversarial/` is the
  intended end state, and a guard pinned to the location would go red on the act of finishing.
- **P5 banners** — the two superseded round-1 outputs keep `_DO_NOT_CITE`. They carry eight
  CASUALTY verdicts of which **six were false**; the banner is what stops them being cited.
- **P6 executed** — actually *runs* `liveness_v2.py --selftest` and `verify_blob_parity.py` and
  requires their markers. Checking bytes is not running a program (the `launchpath` lesson; the
  silent-no-op shape that once made `ui-audit` a vacuous pass).

## 3. The red-proof — one check that fails when the integration is missing

The strongest version of this was free, because the guard existed before the wiring did.

**Measured RED, before any CI line existed** (`integration-proof/RED-before-wiring.txt`):

```
$ python command-center/casualty/casualty_guard.py
  FAIL P1-wiring: .github/workflows/quality.yml does not INVOKE
       command-center/casualty/casualty_guard.py (mentioned 0x anywhere, invoked 0x).
       The lane is not wired into CI.
  OK   P2-inventory ... OK P3-receipts ... OK P4-no-lost-work ... OK P5-banners ... OK P6-executed
FAILED:casualty-guard P1-wiring
REAL_EXIT=1
```

**Measured GREEN, after the wiring was committed:**

```
$ python command-center/casualty/casualty_guard.py
  OK   P1-wiring: invoked at worktree line(s) [439], blob line(s) [439]
  OK   P2-inventory: 8 instrument(s), all dispositioned and parseable
  OK   P3-receipts: 2 receipt(s) reproduce their published digest and byte count
  OK   P4-no-lost-work: ADV-0021 substantive at lane (6/6); ADV-0022 substantive at lane (6/6)
  OK   P5-banners: 2 superseded output(s) banner-stamped
  OK   P6-executed: 2 instrument(s) executed and emitted their marker
SUCCESS:casualty-guard 6 probe(s) green
STRICT_EXIT=0
```

That one-off is now **repeatable and in CI** as `integration_redproof.py`, which runs the same
command against two trees differing only in the wiring:

```
$ python command-center/casualty/integration_redproof.py
  PASS  C1-green: rc 0 and SUCCESS:casualty-guard on the real tree
           returncode: 0   marker: SUCCESS:casualty-guard
  PASS  C2-red-no-ci-line: rc 1 and FAILED:casualty-guard P1-wiring when the CI line is deleted
           returncode: 1   marker: FAILED:casualty-guard P1-wiring
  PASS  C3-floor-raised: green at the declared floor, RED when the floor is raised above observed
           green : {'ok': True,  'reason': 'collected 32 >= floor 28'}
           broken: {'ok': False, 'reason': 'collected 32, below the declared floor 82 ...'}
  PASS  C4-empty-suite: a tests directory with no tests FAILS closed
           observed: 0     reason: collected NOTHING (floor 28)
SUCCESS:integration-redproof 4 control(s) discriminate
```

C2 deliberately leaves the guard's path behind **in a comment**. A mutation that deleted the
string outright would not test the thing the matcher exists to resist.

Per-probe both-states control (`--selftest`, `integration-proof/selftest.txt`): all five
structural probes fire on a deliberately broken copy, plus a positive control requiring the
unmutated copy to pass.

## 4. Defects found in my own work — recorded, not quietly patched

1. **Four instruments could not run anywhere but this box.** `census_v2.py`, `liveness_v2.py`,
   `recover_failed_agents_v2.py`, `verify_blob_parity.py` hardcoded the repo root. Now derived
   from `__file__`, with `CASUALTY_REPO` to aim them at a mutated copy. Behaviour-preserving
   here: both selftests re-ran identical to their pre-edit baseline, and `verify_blob_parity`
   still reports `MATCH=True` on both receipts.
2. **The wiring probe printed a fake locator.** It reported the index within its
   comment-stripped list as if it were a file line — "line 176" for an invocation at line 439.
   Now carries the original line number, with a regression test.
3. **My anti-rot check was VACUOUS.** "Every `EXECUTED` instrument has a real call site"
   returned True for all eight names — because every name is also a *key of the registry dict*.
   Counting the document instead of the field, reproduced inside the check written to prevent
   it. Fixed by excluding the registry from the matcher, and
   `test_the_call_site_matcher_discriminates` is now the control that keeps it honest
   (`liveness_v2.py` in, `census_v2.py` out).
4. **P4 crashed instead of failing.** It imported the scorer from a `_`-prefixed file outside
   the inventory P2 gates, so deleting that file produced a traceback — which in a CI log reads
   as an infrastructure hiccup, not a finding. Now a named `REQUIRED_DEPS` failure.

The inventory gate also fired on real work mid-build, twice: `integration_redproof.py` and then
`verify_ci_parity.py` each arrived undispositioned and P2 refused them until a reason was
written.

## 5. Residual — what is NOT done

Honestly scoped. Nothing below is hidden in a trailing section it is not also flagged at.

- **R-I1 — CI has not actually run yet. `almost-certain (90-99%)` it passes; NOT `measured`.**
  Everything above was executed locally on Windows plus a CI-parity pass over the *committed
  blobs* with the repo's `ruff.toml` and a firing control (`SUCCESS:ci-parity 9 committed
  blob(s) clean`). What is unverified is the ubuntu runner itself. Settling experiment: open a
  PR and read the `gate-tests-coverage command-center` step. Two residual risks I can name:
  the runner's Python is 3.11 against 3.14 here, and `probe_receipts` needs the two receipts
  tracked at HEAD (they are — `verify_blob_parity` confirms).
- **R-I2 — nothing prevents a human deleting the CI line.** The red-proof proves the guard
  *detects* a missing wire; it cannot *enforce* one, because if the line goes, the guard stops
  running in CI. That is a branch-protection / CODEOWNERS question, not a script question. The
  partial mitigation is that `suitefloor --suite casualty` is a second, independent line in a
  different step, so a single deletion leaves a survivor. **Do not read this integration as
  tamper-proof.**
- **R-I3 — inherited and still open: no reviewer on either receipt.** ADV-0021 needs one
  cross-vendor refuter, ADV-0022 needs two different-vendor reviewers each independently
  reproducing. Zero have run; both receipts carry `reviewer.verdict = NOT-REVIEWED`. INTEGRATE
  does not close this and does not claim to.
- **R-I4 — inherited: the receipts are parked outside their canonical `output_path`.** They sit
  in `command-center/casualty/` because this lane was forbidden from writing into
  `command-center/adversarial/` while a sibling wave was live. P4 is written to accept the
  promotion whenever an orchestrator makes it. Until then, a tool reading only the canonical
  path sees two 2 KB skeletons and will report two false casualties.
- **R-I5 — inherited: `recover_failed_agents_v2.py` is not installed over v1.**
  `command-center/recover_failed_agents.py` is outside this lane's scope, so the next casualty
  triage still runs the tool that over-matches 62/92 transcripts.
- **R-I6 — three instruments are EXEMPT from CI, by design and with reasons.**
  `r2_verify_all.py` (Git Bash + a real clone + machine-local transcripts),
  `recover_failed_agents_v2.py --selftest` (same transcripts), `verify_ci_parity.py` (fetches
  pinned ruff over the network). `census_v2.py` is `TESTED` rather than executed because it
  reads `command-center/adversarial/`, which a live sibling wave is still writing — pinning its
  control pairs in CI would make an unrelated sibling commit a red build. The separation
  property it depends on is measured against fixtures instead. **A CI green therefore does not
  mean every lane instrument ran.** The exemption table is itself gated by P2 in both
  directions, so this cannot silently widen.
- **R-I7 — the suite floor is tuned, not derived.** 28 against 32 observed. It catches a
  collapse, not the loss of two cases.
- **R-I8 — five lane JSON outputs are dirty in the working tree and are NOT mine.**
  `ADV-COMPLETENESS-CENSUS-V2.json`, `ADV-LIVENESS-V2.json`, `R2-ADV0002-RECHECK.json`,
  `R2-DEFECT-CONTROLS.json`, `R2-FINAL-VERIFICATION.json` were rewritten during this session by
  a sibling's run of `r2_verify_all.py` (one now cites a `wf_e58dfd3f-7b1` transcript from this
  session). Deliberately left unstaged. Verified with a control rather than assumed: running my
  own P6 instruments leaves all three sampled files byte-identical.

## 6. Commands and commits

Reproduce the whole thing from the repo root:

```
python -m pytest command-center/casualty/tests -q          # 32 passed
python command-center/casualty/casualty_guard.py           # SUCCESS:casualty-guard 6 probe(s) green
python command-center/casualty/casualty_guard.py --selftest  # per-probe both-states control
python command-center/casualty/integration_redproof.py     # SUCCESS:integration-redproof 4 controls
python tools/measure-guard/suitefloor.py --suite casualty  # SUCCESS:suite-floor
python command-center/casualty/verify_ci_parity.py         # SUCCESS:ci-parity (blobs, not worktree)
bash .quality/charter_check.sh                             # OK -- 6 gates consistent
```

- `f087a6f6` — the wiring: guard, red-proof, 32-test suite, the four portability fixes,
  quality.yml, suitefloor enrolment. 15 files, all mine, verified with an explicit foreign-path
  check before committing (`git diff --cached --name-only` filtered to the three allowed
  prefixes returned nothing).
- The follow-up commit adds `verify_ci_parity.py` + its disposition + this dossier.

Git discipline held throughout: no `git add -A`, no `git add .`, no `git commit -a`, explicit
pathspecs only, nothing written into `command-center/adversarial/`, no force-push, no
`--no-verify`, no history rewritten.
