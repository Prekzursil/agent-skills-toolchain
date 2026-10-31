# SKILLS lane — INTEGRATE (last stage; the loop is over)

STATUS: **MEASURED AND LANDED** as commit `e9b65d60` (9 files, +937/-3, zero deletions, zero
foreign paths). Every claim below carries the command that produced it.

COVERAGE: D1 (CI gate), D2 (agent-facing surface), D3 (deployed to the read tree), the
end-to-end check and its RED proof, the P4 mutation table, the full `ci/tests` + `d001` run, and
the D-001 gate's own both-states control are all MEASURED. Nothing here is PENDING.
Residuals R1-R7 are open and scoped at the bottom; none of them is silent.

---

## The gap this lane exists to close

The BUILD lane shipped `scripts/deploy-skills-daily.py` — the missing last hop into
`~/.claude/skills.daily`, the only tree Claude Code reads. It was **unreachable and unproven**.

`git grep -l deploy-skills-daily` before / `grep -rl` after:

| area | before | after |
|---|---|---|
| `.github/` (does CI run it?) | **0** | **1** |
| `ci/` (is it tested?) | **0** | **1** |
| `.agents/skills/` (can an agent find it?) | **0** | **1** |
| `skills/` (projection twin) | **0** | **1** |
| `hooks/` | 0 | 0 |
| `scripts/` (the file itself) | 1 | 1 |

Before this lane the only other hits were the BUILD lane's own scratch notes under
`command-center/build/`. That is the exact defect class the prior six-lens audit named twice:
`tools/measure-guard/` (CI-enforced, 0 agent-facing surface) and `tools/detector-self-test/`
(wired NOWHERE, runs green). A 256-line script that writes into the loaded skill tree had joined
them.

---

## D1 — a gate wired into CI

**New:** `ci/tests/test_deploy_skills_daily.py` — 16 tests, hermetic (`tmp_path` only), so it
runs on a CI box with no `~/.claude` tree.

**Wired two independent ways**, which is the repo's own idiom (this repository has no test
autodiscovery, so a directory glob is one refactor away from silently un-gating a tool):

1. explicit named step — `.github/workflows/skill-dual-write.yml:82-83`
   `- name: gate-skill-deploy-hop self-test` / `run: python -m pytest ci/tests/test_deploy_skills_daily.py -q`
2. the pre-existing directory glob at `:60`, `python -m pytest ci/tests tools/d001-dual-write/tests -q`

Both routes are asserted *by the suite itself* (`test_the_workflow_runs_this_suite_by_explicit_path`,
`test_the_workflow_glob_still_covers_this_directory`), so removing either one fails loudly.

### What the suite proves that nothing did before: P4

The tool's docstring claimed "FOUR SAFETY PROPERTIES, each enforced AND self-tested". The
independent audit found that false for P4 and the adversarial verify confirmed it with its own
mutants. The cause is structural: `--self-test` returns before `main()` ever reaches the
`--apply` branch, so **no fixture inside `self_test()` can reach P4**. That sentence is now
corrected in the file rather than left standing (`scripts/deploy-skills-daily.py:17-26`).

`python command-center/integrate/_i1_p4_mutation.py`

```
 probe A --self-test |  probe B new pytest | mutant
------------------------------------------------------------------------------------------
               GREEN |               GREEN | CONTROL unmutated copy (must be GREEN on both)
               GREEN |                 RED | M5 --apply no longer runs the self-test first
               GREEN |                 RED | M6 dry-run default flipped (apply forced True)
                 RED |                 RED | M2 P2 skill-existence guard removed

probe A (tool --self-test) survivors: 2/3  [M5, M6]
probe B (new ci/tests suite) survivors: 0/3 []
SUCCESS:i1-p4-mutation new suite killed every mutant; the pre-existing self-test left 2 alive
```

Two mechanically different probes against the same mutant, plus an unmutated CONTROL that must
be green on **both** — without that row the harness could be measuring its own sandbox rather
than the mutation, and no row could be read. M2 is included to show the new suite is a superset,
not a replacement.

---

## D2 — an agent-facing surface (a skill in the curated set)

**Landing place:** `.agents/skills/writing-skills/SKILL.md` (+ its `skills/` twin). Chosen
because its own description already fires on *"verifying skills work before deployment"*, and
because that skill contained the instruction that **causes** the drift: line 12 told an agent
personal skills "live in" `~/.claude/skills`, i.e. author straight into a live tree, which is
precisely how work becomes orphaned from git.

Three additive edits, `+2,823` chars of BODY:

- line 12 now carries **"Those are DEPLOY TARGETS, not where you author."**
- a new section **"Where to author, and the last hop"** — the four-tree table with which one is
  canonical, the three runnable commands, what the tool returns, and an explicit *when NOT to
  use it* (it refuses a two-directionally diverged file, and it is not a prune because
  `microsoft-foundry` / `qdx-rush` would be the casualties)
- the **Deployment checklist** no longer stops at "commit to git" — it now names the last hop,
  the dual-write twin, and a re-run confirmation

**The description was deliberately NOT touched.** A description is always-loaded context and the
entire lexical recall surface; the trigger this skill needs already exists in it. Measured
delta: **+0 chars** (see D3).

---

## D3 — deployed where the client reads it

Deployed *with the tool itself* — the deploy hop deploys its own documentation:

`python scripts/deploy-skills-daily.py --only writing-skills --apply`
→ `SUCCESS:deploy-skills-daily copied=1 needs_merge=434`

`python command-center/integrate/_i2_verify_live.py`

```
TREE PARITY (LF-normalised sha256, first 16)
  6fac2e844f21d9d7   25998 B  repo/.agents/skills
  6fac2e844f21d9d7   25998 B  repo/skills
  6fac2e844f21d9d7   25998 B  live/skills.daily
  6fac2e844f21d9d7   25998 B  live/.claude/skills      <- the symlink Claude Code loads
  OK all four routes byte-identical after LF-normalisation

DESCRIPTION DELTA (always-loaded context -- must be ZERO)
  before 97 / after 97 / delta +0 chars   OK the whole delta is body
BODY DELTA  +2823 chars
CONTROL: a mangled description is detected as changed: True
SUCCESS:i2-verify-live problems=0
```

The description control matters: round 1 measured a near-miss where deploying a pure body edit
would have silently shortened two skills' always-loaded descriptions by 282 and 307 chars. A
body-only diff review does not show that. This probe asserts the delta is zero and proves its
own detector can see a change.

### The P1 guard fired on my own edit — real content, not a fixture

My first version of the line-12 edit **rewrote** that line instead of adding to it. Because the
differ classifies by line-set membership, that gave the live tree a line the repo no longer had:

```
first (rewriting) edit :  DIVERGED 102, RIGHT-AHEAD 1, safe to deploy 0     <- REFUSED
additive edit          :  DIVERGED 101, RIGHT-AHEAD 2, safe to deploy 1     <- WOULD-COPY
```

This is the strongest single piece of evidence in the lane that the guard is not a no-op: it
blocked a real edit by the person who wrote its test, and reshaping the edit to be purely
additive is what unblocked it. It also demonstrates the tool's intended discipline — additive
edits deploy, rewrites go to the human-merge pile.

---

## The one executable end-to-end check

```
python -m pytest ci/tests/test_deploy_skills_daily.py -q
```

That is byte-for-byte the CI step. It spans all three deliverables: the tool's behaviour (P1-P4),
the CI wiring (both routes), and the agent-facing reachability (a curated skill must carry the
runnable command, in **both** roots).

### It goes RED without the integration — measured, not asserted

Run against the tree *before* the workflow step and the skill edit existed:

```
FAILED ci/tests/test_deploy_skills_daily.py::test_the_workflow_runs_this_suite_by_explicit_path
FAILED ci/tests/test_deploy_skills_daily.py::test_the_deploy_hop_has_an_agent_facing_surface
E  AssertionError: no curated skill tells an agent to run `python scripts/deploy-skills-daily.py`;
   the last deploy hop is unreachable and skills authored in the live tree stay orphaned from git
E  assert set()
2 failed, 14 passed in 14.40s
```

After the integration: `16 passed in 2.00s`.

The 14/2 split is the useful part — the behaviour tests passed in both states, so the two that
flipped are measuring the *integration* specifically and nothing else.

Third route, the glob: `python -m pytest ci/tests tools/d001-dual-write/tests -q --collect-only`
→ `627 tests collected`, of which `16` are `test_deploy_skills_daily.py::`.

Pre-existing wiring suite unaffected: `python -m pytest ci/tests/test_ci_wiring.py -q` → `15 passed`.

**The whole CI self-test command:** `4 failed, 622 passed, 1 skipped in 177.96s`. All four
failures are in files this lane never touched, and I did not attribute them by reasoning — I
re-ran exactly those four node-ids alone, with my file not collected, and all four reproduce
(`4 failed in 6.71s`). They are Windows-platform artifacts (invalid-UTF-8 filename bytes ×2, an
executable mode-bit regression check, and a git `update-ref` race injector) that would not fire
on the Linux runner:

```
FAILED ci/tests/test_check_skill_dual_write.py::test_strict_parity_keeps_distinct_invalid_utf8_path_bytes_distinct
FAILED tools/d001-dual-write/tests/test_d001_apply.py::test_project_keeps_distinct_invalid_utf8_path_bytes
FAILED tools/d001-dual-write/tests/test_d001_apply.py::test_verifier_refuses_an_executable_mode_regression
FAILED tools/d001-dual-write/tests/test_d001_apply.py::test_atomic_ref_create_refuses_a_branch_created_after_precheck
```

---

## The gate that guards my own commit — and the two controls that were themselves broken

`python ci/check_skill_dual_write.py --base e9b65d60^ --head e9b65d60 --strict-parity`
→ `OK: changed skill paths match their final-tree counterparts.` (exit 0)

That OK is worthless until the gate is shown capable of saying something else. Two controls were
tried and **both were broken detectors**, which is worth recording:

| attempt | idea | result | why it measures nothing |
|---|---|---|---|
| 1 | re-run over a historical range that once had a violation (`3bf14581^..6c742fd3`) | exit 0 | `--strict-parity` resolves the counterpart in the FINAL tree; that violation was repaired before HEAD |
| 2 | break the projection twin in the WORKING TREE, re-run the same command | exit 0 / 0 / 0 | "final tree" means the tree of the `--head` COMMIT, not the worktree — a worktree edit is invisible |
| 3 | build a throwaway repo, COMMIT a canonical-only change, run the real gate with `--repo` | **exit 1 / exit 0** | the violation exists in a commit, which is the only thing the gate reads |

```
  exit=1   BROKEN state  canonical-only change   D-001 DUAL-WRITE VIOLATION
  exit=0   FIXED  state  twin repaired           OK: changed skill paths match their final-tree counterparts.
SUCCESS:i3-gate-control red_on_violation=True green_on_repair=True
```

Attempt 2 is the one that would have done real damage: it returned green in all three states, so
reporting the STATE-1 green off the back of it would have been evidence-tag theatre — a probe
silent in the known-broken state. Nothing in the real worktree was touched by any attempt
(`_i3_gate_control.py` verifies its own restore by sha256, and attempt 3 never leaves `tempdir`).

---

## Two round-1 residuals re-checked with my own probe, not inherited

- **CLOSED — the wrong blob recipe.** Round 1 reverted its own fix to
  `workflow-authoring/templates/governed-run-orchestrator.md:1145` to avoid a live collision. A
  sibling landed it as `faedd97e`. My read: `:1145` now says
  `git show <final-sha>:<path>   # NOT git archive: it applies export-time EOL`, and the
  legitimate packaging `git archive` at `:2177` was correctly left alone.
- **STILL OPEN — the Codex vault carries the pre-fix ui-audit guard.** My own marker count
  (`realpathSync.native`, 6 entry points, 3 trees):

  | tree | fixed / present |
  |---|---|
  | `~/.agents/skills` | **0 / 6** |
  | `~/.claude/skills.daily` | 6 / 6 |
  | repo `.agents/skills` | 6 / 6 |

  The adversarial verify was right to scope the audit's version of this down: the vault copy
  *runs* at its real path and there is no reparse-point route into `~/.agents/skills`, so it is
  not vacuous today. But it is one deploy away from being reached, and the tool I wired targets
  `skills.daily` only — see residual R1.

---

## Residual — honestly scoped

**R1. The deploy hop covers ONE of the two live trees.** `scripts/deploy-skills-daily.py`
targets `~/.claude/skills.daily`. `~/.agents/skills` (the Codex vault) still has no repo-side
writer with these guards — `scripts/sync-skills.ps1` writes there but from `skills/` and with a
`-Prune` mode that would delete `qdx-rush`. So the vault keeps its pre-fix ui-audit guard (0/6
above). Settling experiment: point the same tool at `--target ~/.agents/skills` and read the
plan; it is a one-flag run, deliberately not performed here because deploying into a second live
tree during an active multi-agent session is an owner call, not a subagent's.

**R2. The gate only runs on `pull_request` to main.** `skill-dual-write.yml:34-36`. A direct push
to main does not run it. That is inherited from the workflow I attached to, not introduced here;
moving it would need the charter-slug coordination the workflow's own header documents at `:9-19`.

**R3. 434 files still need a read-both-sides human merge — and that number is smaller than it
looks.** Correctly scoped from the audit's per-file census: **189** are genuinely two-directional;
the other **245** are LEFT-ONLY-FILE and fully accounted (199 vendored `RsaCtfTool`, 31 `.bak-`,
12 `cv-studio` self-nested, 3 binaries), none of which needs a merge at all. My run measured
`needs_merge 434` before the deploy and `434` after, with `DIVERGED 101 -> 101` and
`IDENTICAL 225 -> 226` once `writing-skills` landed.

**R4. `is_noise()` in the shared differ still leaks `.bak-` DIRECTORIES** (it tests the infix on
the leaf only), inflating `needs_merge` by 31. One-line fix, deliberately not applied: other
lanes are quoting these numbers this session and moving the shared differ mid-wave would
invalidate their evidence more than it helps mine.

**R5. The description-budget lever is still unpulled** — de-curating the 23 `source-command-*`
wrappers and deploying the committed 75-skill description cap. Unchanged from round 1 and for
the same reason: the 26-dark set is usage-dependent, the startup truncation warning is not
readable from inside a subagent, so a before/after would measure noise. This is the item the
sixth (overlap) lens should have cleared and the one place where "default hard to KEEP" is doing
real work rather than just being cautious.

**R6. Nothing merged, nothing retired — and that is still only backed by TOKEN-LEVEL evidence.**
Two independent overlap measurements (57 candidate pairs, max Jaccard 0.185 against a 0.30 floor)
refute *textual* duplication decisively. Neither can see two skills doing the same job in
different words. The settling experiment is a pairwise body read of the 57 candidates, which no
lane has done. Confidence that no pair is functionally redundant: **LIKELY (55-80%)**, not higher.

**R7. This lane added a gate; it did not add a gate for its own probes.** `_i1_p4_mutation.py`,
`_i2_verify_live.py` and `_i3_gate_control.py` are lane instruments under `command-center/`, not
CI. All three carry their own CONTROL and all three fail closed, but nothing re-runs them. That
is the right scope for a one-shot measurement and the wrong scope for a standing gate; the
standing gate is `ci/tests/test_deploy_skills_daily.py`, which *is* wired, twice.

**R8. The reachability assertion is satisfied by exactly ONE skill.** If `writing-skills` is ever
re-vendored from upstream `superpowers`, my +2,823-char body edit is overwritten and the deploy
hop goes dark again. That is not silent — `test_the_deploy_hop_has_an_agent_facing_surface` turns
RED the moment it happens, which is the behaviour I want — but a second carrier would make the
route survive a re-vendor rather than merely report its loss. Not added here: a second body edit
is a second place to drift, and the gate already converts the failure mode from silent to loud.

---

## Evidence appendix — exact commands

| # | command | result |
|---|---|---|
| 1 | `git grep -l deploy-skills-daily` (pre) | 4 hits, all the tool + lane scratch; 0 in CI/skills/hooks |
| 2 | `python -m pytest ci/tests/test_deploy_skills_daily.py -q` (pre-integration) | `2 failed, 14 passed` |
| 3 | `python command-center/integrate/_i1_p4_mutation.py` | `SUCCESS:i1-p4-mutation`, probe A survivors 2/3, probe B 0/3 |
| 4 | `python -m pytest ci/tests/test_deploy_skills_daily.py -q` (post) | `16 passed in 2.00s` |
| 5 | `python -m pytest ci/tests tools/d001-dual-write/tests -q --collect-only` | `627 collected`, 16 mine |
| 6 | `python -m pytest ci/tests/test_ci_wiring.py -q` | `15 passed` |
| 7 | `python scripts/deploy-skills-daily.py --only writing-skills` (rewriting edit) | `safe to deploy 0` — REFUSED |
| 8 | `python scripts/deploy-skills-daily.py --only writing-skills` (additive edit) | `safe to deploy 1` — WOULD-COPY |
| 9 | `python scripts/deploy-skills-daily.py --only writing-skills --apply` | `SUCCESS:deploy-skills-daily copied=1` |
| 10 | `python command-center/integrate/_i2_verify_live.py` | `SUCCESS:i2-verify-live problems=0` |
| 11 | `python -m pytest ci/tests tools/d001-dual-write/tests -q` | `4 failed, 622 passed, 1 skipped in 177.96s` |
| 12 | the same 4 node-ids alone, my file not collected | `4 failed in 6.71s` — pre-existing, none mine |
| 13 | `python ci/check_skill_dual_write.py --base e9b65d60^ --head e9b65d60 --strict-parity` | `OK`, exit 0 |
| 14 | `python command-center/integrate/_i3_gate_control.py` | `SUCCESS:i3-gate-control` — exit 1 broken / exit 0 fixed |
| 15 | `git show --name-only e9b65d60` filtered against my declared scope | `NONE - every path is mine`; deletions 0 |
| 16 | ui-audit guard marker count across 3 trees | vault `0/6`, skills.daily `6/6`, repo `6/6` |
| 17 | `grep -n` on `workflow-authoring/templates/governed-run-orchestrator.md:1145` | now `git show <final-sha>:<path>` — round-1 residual CLOSED by `faedd97e` |

## Commit

`e9b65d60  feat(skills): wire the last deploy hop into CI and into a skill an agent can find`
— 9 files, +937/-3. Staged by explicit path with a foreign-path check between the `git add` and
the `git commit`; the commit itself uses the pathspec form so a sibling's staged work cannot be
swept in. This is the failure that produced round 1's commit `772159ce`, where a concurrent
blanket `git add` put this lane's work under another lane's message. Zero deletions, no
force-push, no history rewrite, no `--no-verify`.
