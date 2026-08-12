# WFSOTA — INTEGRATE lane log

Lane: WFSOTA INTEGRATE (final stage). Predecessor: build round 1 commit `1f05e805`
(H6 per-agent timeout + settled barrier), audited CONFIRMED, refutation says build SOUND / audit HOLDS.

COVERAGE at this rewrite: I1, I2 and I3 all MEASURED against executed commands. The one item that is
**not** done, and deliberately so, is the live-curated-tree deploy — quantified in §Residual with the
exact safe/unsafe split, not hand-waved.

## Mandate

| # | Item | State |
|---|---|---|
| I1 | Wire the work into the estate so it is REACHABLE | **DONE** — CI step + a non-circular pin |
| I2 | One executable check that FAILS if the integration is missing, shown going RED | **DONE** — 3-state proof |
| I3 | Residual written down honestly and inline | **DONE** — §Residual |

## What round 1 left, in its own words

> "NOT WIRED INTO `.github/workflows/quality.yml`. … Until someone adds the step, the H6 red-proof and
> `wf_gate` run only when invoked by hand — which is the same no-op-gate defect this lane fixed for
> `workflow_lint`, now one layer up."  — builder residual #1

> "tools/wf-timeout is named NOWHERE."  — auditor, and: "That is round 2's single highest-value action."

## C1 — the gap was real, re-measured here with a controlled detector

`python docs/workflow-sota/_int_c1_prestate.py`, over every text file under `.github/` and `ci/`:

```
files scanned: 88
CONTROL present-needle 'pytest': 40 file(s)      <-- the scanner can find things
CONTROL absent-needle:            0 file(s)      <-- and does not hallucinate them
  wf-timeout / wf_gate / h6_extract / h6_harness / test_h6_timeout  ->  0 file(s) each
SUCCESS:c1-probe detector_control_ok=True wf_timeout_refs_in_ci=0
```

Absence is a claim, so it ships with its control: a scan reading 0 for the present-needle would prove
nothing. Both controls held. Re-running the same probe after this lane reads
`wf_timeout_refs_in_ci=9` — the same instrument, opposite verdict, which is the cheapest both-states
evidence available for "the estate changed".

## I1 — what is now wired

**1. The executing step.** `.github/workflows/quality.yml`, job `test-python`, immediately after
`gate-tests-coverage workflow-authoring lint`:

| line | what it closes |
|---|---|
| `pytest --cov=wf_gate --cov=h6_extract --cov-branch --cov-report=term-missing --cov-fail-under=100` | **this run IS the H6 red-proof.** Its control feeds a bare `parallel()` a thunk that never resolves and requires the barrier to hang before the wrapped path may be green. `B3-migration-verification.md:156` demands verbatim *"H6 proven to break a synthetic barrier hang"* — this is where that is executed. |
| `python wf_gate.py --self-test` | the both-states control: red on a bad block, green on a clean one, **closed** on an empty walk (`rules/common/ci-hygiene.md` §1). |
| `python wf_gate.py` | the actual invocation of `workflow_lint` over real template source. Until now that linter had 110 tests and a 100% CI lane and had **never been run over a line of workflow code**. |
| `- uses: actions/setup-node@8207627…` (SHA-pinned, same pin as the node-workspaces job) | load-bearing, not hygiene: `test_h6_timeout.py:45,64` resolves `node` with `shutil.which` and **fails** the suite when absent rather than skipping. |

Charter slug reused (`gate-tests-coverage`) so no `charter.yml` edit is needed —
`bash .quality/charter_check.sh` → `OK -- 6 gates consistent`.

**2. The non-circular pin.** `ci/tests/test_wf_timeout_ci_wiring.py`, 9 tests.

A wiring assertion living *inside* the step it pins cannot fail when that step is deleted — it just
stops running. This file sits in `ci/tests/`, which `.github/workflows/skill-dual-write.yml:60`
collects as a whole **directory** (`run: python -m pytest ci/tests tools/d001-dual-write/tests -q`) on
every `pull_request`. Deleting the `quality.yml` step therefore turns a **different workflow** red.
`test_this_file_is_swept_by_the_independent_dual_write_workflow` asserts that sweep rather than
assuming it.

**Use-vs-mention:** the new step carries a long comment that names `wf_gate.py` in prose, so a naive
`in text` assertion would pass on the comment alone. Every assertion matches a set of
comment-stripped, whitespace-stripped lines, and `test_the_comment_stripper_actually_strips` is the
control for that stripper. Two of my own constants were initially wrong (`- uses:` prefix, `run:`
prefix) and the tests caught them — recorded because a test that never rejected anything is suspect.

## I2 — the red-proof, three states, live tree never mutated

`python docs/workflow-sota/_int_redproof.py` mirrors the 10 files the check reads into a temp tree
(the test derives its root from `__file__.parents[2]`, so a mirror suffices) and runs the SAME test
file against three states:

```
I2 both-states red-proof for the wf-timeout CI wiring
  S0 WIRED   rc=0 -> PASS (want PASS) [9 passed in 0.48s]
  S1 UNWIRED rc=1 -> FAIL (want FAIL) [5 failed, 4 passed in 0.64s]
  S2 WEAKENED rc=1 -> FAIL (want FAIL) [1 failed, 8 passed in 0.88s]
SUCCESS:redproof control fires -- green when wired, red when not
```

- **S1 UNWIRED** excises the added block by anchor — the genuine "step was never added" state.
- **S2 WEAKENED** keeps the step but downgrades `--cov-fail-under=100` to `80`. Caught by exactly one
  test, which is the granularity claimed rather than a blanket red.
- **S0 WIRED** is the control on the control. Without it, a mirror broken for an unrelated reason
  would read red in every state and prove nothing.

## Coverage side-effect (deliberate)

`wf_gate.py` was 99% — branch partial `36->39`, the import-time `sys.path` guard's already-present arm,
unreachable in a single import. Round 1's README therefore proposed shipping the CI step at
`--cov-fail-under=95`. A permanent coverage exception nobody re-examines is worse than a test, so
`test_import_is_idempotent_when_the_lint_dir_is_already_on_the_path` reloads the module with the path
present and asserts the guard does not duplicate the entry. Now 100%, and the step is a clean
`--cov-fail-under=100` matching repo doctrine. 39 tests → 40.

## Verification (every command executed here, with its real output)

```
bash .quality/charter_check.sh              -> OK -- 6 gates consistent: lint-format types
                                               tests-coverage sast secrets deps
python ci/check_skill_dual_write.py         -> OK: no skills/ change lacks a .agents/ counterpart (rc=0)
python ci/check_skill_context_budget.py     -> DAILY: 21 | catalog: 379   (rc=0)
python -m pytest ci/tests -q                -> 566 passed, 1 skipped, 1 failed *
tools/wf-timeout$ pytest --cov=wf_gate --cov=h6_extract --cov-branch --cov-fail-under=100
                                            -> 40 passed; 148 stmts / 38 branch / 0 miss / 100%
skills/workflow-authoring/scripts$ pytest --cov=workflow_lint --cov-branch --cov-fail-under=100
                                            -> 110 passed; 452 stmts / 216 branch / 0 miss / 100%
tools/wf-timeout$ python wf_gate.py --self-test
                                            -> SUCCESS:wf-gate-self-test red on bad, green on clean,
                                               closed on empty
tools/wf-timeout$ python wf_gate.py         -> SUCCESS:wf-gate 0 error(s), 1 warning(s), 15 block(s)
ruff 0.15.17 check / format --check <my .py>    -> All checks passed / already formatted
python docs/workflow-sota/_int_blobcheck.py -> blobs extracted (git cat-file -p, NOT git archive): 6
                                               CRLF byte pairs inside those blobs: 0
                                               ruff check rc=0 "All checks passed!"
                                               ruff format rc=1 "1 file would be reformatted,
                                                                 6 files already formatted"
                                               CONTROL FIRED: True   REAL BLOBS FLAGGED: []
                                               SUCCESS:blobcheck stored blobs are LF and CI-clean
```

The blob check is not a formality. A Windows working-tree green does not imply CI green
(`rules/common/windows-shell.md` 8b): the tree is CRLF, git stores LF, CI checks out LF, and ruff can
decide differently on the two. It extracts the **index blobs** with `git cat-file -p :<path>` —
never `git archive`, which re-applies EOL conversion on Windows and hands back the wrong bytes — copies
`ruff.toml` alongside so a bare temp dir cannot manufacture a false red, and adds a deliberately
mangled control file whose appearance in the reformat list is asserted before any green is accepted.

\* **The one `ci/tests` failure is pre-existing and Windows-only**, not mine, established with two
mechanically independent signals rather than an assumption:
1. Re-running the suite with `--ignore=ci/tests/test_wf_timeout_ci_wiring.py` fails **identically**
   (`557 passed` vs `566 passed`; the delta is exactly my 9 tests).
2. A direct OS probe: `os.fsdecode(b"\xff")` as a filename →
   `OS REFUSES invalid-utf8 filename: UnicodeDecodeError`. The test
   (`test_strict_parity_keeps_distinct_invalid_utf8_path_bytes_distinct`, `:497`) deliberately creates
   invalid-UTF-8 filenames, which NTFS/Windows will not do. CI runs `ubuntu-latest`.

## Residual — what is NOT done

**R1. The live curated tree is still stale, and I deliberately did not deploy to it.**
This is the biggest honest gap and it is quantified, not asserted.
`python docs/workflow-sota/_int_live_reachability.py` (control: self-vs-self → `IDENTICAL`;
if that control ever reports drift, no verdict below counts) compares every repo file of the two
workflow skills against both live trees, **in both directions**:

```
SUCCESS:reach files=44 identical=8 absent_live=32 unsafe_to_deploy=2
```

| file | verdict |
|---|---|
| `workflow-authoring/templates/h6-timeout-heartbeat.md` (+ the other 2 templates, `workflow_lint.py`, its tests) | **ABSENT-LIVE** in all trees — additive deploy would be lossless |
| `workflow-foundry/SKILL.md` | **REPO-SUPERSET** (+39 repo-only, **0** live-only) — deploy would be lossless |
| `workflow-authoring/SKILL.md` | **TWO-WAY DIVERGED** — 53 live-only vs 234 repo-only (`skills.daily`), 32 vs 234 (`~/.agents/skills`). **A deploy would destroy live-unique content.** |

Why I stopped rather than deployed the safe subset: (a) live trees are outside this lane's declared
file scope (`tools/**`, `.agents/skills/workflow-*/**`, `docs/workflow-sota/**` — note that is the
*repo's* `.agents`, not `~/.agents`); (b) sibling lanes are writing this estate concurrently;
(c) the repo's own `ci/check_skill_deploy_drift.py` exists precisely to report and **refuse to copy**,
for the same measured reason; and (d) deploying the H6 *template* alone buys nothing, because the live
`SKILL.md` — the diverged file — is what would have to reference it, so the only reachability-improving
deploy is the destructive one. Settling experiment: union-merge `workflow-authoring/SKILL.md`
(53 live-only lines are the input), then deploy the merged file plus the 32 absent-live files, then
re-run this probe and require `unsafe_to_deploy=0`.
Root cause is architectural and named in the fleet harvest: `~/.claude/skills.daily` has **no sync
path in the repo at all**. That is not fixable inside this lane.

**R2. Nothing has actually executed the new step on a GitHub runner yet.** Band: **likely** (55-80%)
that it passes first try. Evidence for: both suite commands were run verbatim locally and are green;
`setup-node` uses a pin already proven in this workflow; `wf_gate.py` derives its root from `__file__`
so `working-directory` is safe. Evidence against, disclosed inline: I have never seen this job run on
Linux, and `pip install pytest pytest-cov` inside a job that already installed several packages could
in principle resolve differently. Settling experiment: open a PR and read the `test-python` job log.
**UNVERIFIED until then** — no claim here covers runner behaviour.

**R3. Round 1's residuals 2-9 are untouched by this lane** and remain as written in `BUILD-LOG.md`:
R6 (migrating the 15 live barriers to `pipeline()`/`settle()`), R5 (two competing resume mechanisms),
`prefer-pipeline`'s zero real-corpus catches, the `setTimeout`-injection claim being binary-derived
rather than executed in a real Workflow, and the heartbeat being an observation rather than a stall
verdict. Only residual #1 is closed; `BUILD-LOG.md` now marks it superseded rather than deleting it,
so the round-1 record stays truthful.

**R4. One pre-existing `agent-schema` WARN survives** at
`governed-run-orchestrator.md#js[4]:9` — advisory, pre-existing, out of this lane's intent. The gate
is not `--strict`, so it does not fail on it. Left rather than silently edited.

**R5. The auditor's one real defect is NOT fixed here.** `workflow_lint._maps_nulls` (`:675-682`) is a
bare substring test, so a `.map()` whose body merely contains the letters `null` (`v.nullable`)
suppresses the `parallel-filter-boolean` warning. WARN-level, fires once on the whole live corpus,
nothing gates on it. It is in `skills/**`, outside this lane's scope, and touching it would have
pulled a dual-write pair into an integration commit. Settling experiment is already written by the
auditor: add the `r.map(v => v.nullable)` fixture and require it to warn.
