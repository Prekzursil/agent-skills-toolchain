---
title: RULE-AUDIT-INTEGRATE-R3
type: note
permalink: dqverify-repo-20261013/docs/rule-audit/rule-audit-integrate-r3
---

# RULE-AUDIT — INTEGRATE lane, round 3

STATUS: complete and measured. Every claim below was executed, not read.

COVERAGE: sections 1-4 are measured first-hand this round. Section 5 (residual) carries
items I did NOT close, each with the reason and the experiment that settles it. Section 6
lists what I did not check at all, declared rather than folded into a pass.

---

## 1. The hole this round closed

The lane's whole output — ten gates over four audit rounds, three adversarial rounds and
three build rounds — was reachable through **exactly one file**,
`.github/workflows/rule-audit.yml`, and **nothing pinned that file**.

Measured, with the detector controlled in both directions before the absence was believed:

| probe | result |
|---|---|
| `grep -rn "rule-audit\.yml\|rule-audit/ci_gate\|docs/rule-audit" ci/ .github/` | ONE hit outside the workflow itself: `hook-audit.yml:20`, a prose comment listing sibling workflows |
| POSITIVE CONTROL — same search shape for `wf-timeout` | finds `ci/tests/test_wf_timeout_ci_wiring.py` + `quality.yml`, so the shape CAN find a guard |
| NEGATIVE CONTROL — same search for a bogus token | no output |

A mention is not a guard. Deleting, renaming or quietly weakening that one workflow removed
every rule-audit gate from CI and **nothing went red** — the lane's founding defect
(`ci_gate.py`: *"A gate nobody invokes is indistinguishable from one that does not exist"*)
recurring silently.

## 2. What is now wired, and where the client actually reads it

| surface | wired | evidence |
|---|---|---|
| `ci/tests/test_rule_audit_ci_wiring.py` — the guard | NEW | 16 passed |
| Named in `quality.yml` (the workflow with `push: branches:[main]`) | NEW step | `gate-tests-coverage rule-audit gate reachability` |
| Reached on PRs by `skill-dual-write.yml`'s directory sweep | pre-existing | pinned by `test_this_file_is_itself_reachable` |
| `docs/rule-audit/r6_wiring_redproof.py` — proves the guard fires | NEW | 5/5 arms |
| Ninth entry in `ci_gate.py`'s `CI_PLAN` | NEW | `9 planned runs over 9 gates` |
| `rule-audit.yml` installs the `pytest` the red-proof needs | NEW | `pip install tiktoken==0.13.0 pytest==8.4.2` |

Two independent paths to running, so the guard is **not circular**: a wiring assertion that
lived only inside the workflow it pins would simply stop running when that workflow was
deleted. This one turns a *different* workflow red.

## 3. The end-to-end proof — the check FAILS if the integration is missing

This was measured twice, in two different ways, and the second one caught a real defect in
my own harness.

**(a) Genuine fail-first on the live tree.** The guard was written and run BEFORE the
`quality.yml` step existed:

```
2 failed, 13 passed        <- wiring-suite-not-named
...add the quality.yml step...
16 passed
```

The second failure was the mutation helper refusing to run its control because the line it
mutates did not yet exist — a control that cannot find its target says so instead of
silently passing.

**(b) Process-level red-proof** (`r6_wiring_redproof.py`) — builds five throwaway trees,
copies the real suite into each, and runs `pytest` as a subprocess:

```
  [ok] A control: unmutated copy                      GREEN rc=0
  [ok] B rule-audit.yml DELETED                       RED   rc=1
  [ok] C gate step removed, workflow kept             RED   rc=1
  [ok] D quality.yml stops naming the suite           RED   rc=1
  [ok] E push trigger removed                         RED   rc=1
SUCCESS:r6_wiring_redproof 5/5 arms behaved
```

Every red arm asserts on a NAMED violation string as well as the exit code, so an arm cannot
pass because pytest failed for an unrelated reason.

**Arm A is the load-bearing one, and it earned its place.** On the first run it went RED:
the temp tree held only `ci_gate.py`, so the suite's "every script `CI_PLAN` names exists"
assertion failed for a reason that had nothing to do with wiring. Arms B-E were "firing"
against a broken harness. The control is the only thing that distinguished *the guard
fires* from *my harness is broken* — and without it this round would have reported four
green-looking reds that proved nothing.

## 4. Full gate, post-integration

```
  ok  inventory: 9 planned runs over 9 gates, 35 excluded with reasons
  ok  rc=0 (want 0)   12.3s  r6_wiring_redproof (proves the reachability guard fires)
  ok  always-on set is exactly the expected 8 rules
  ok  load-semantics divergence is exactly the 3 allowlisted rules
SUCCESS:rule-audit-ci-gate 9/9 gates behaved, always-on=8, divergence=3
```

`ci_gate.py --self-test` 12/12. `pytest ci/tests/ -k "rules or wiring"` → **293 passed**.
`test_charter_consistency.py` + `test_workflow_action_contracts.py` → 13 passed, so the
`quality.yml` edit did not break the bidirectional charter check (the new step reuses the
existing `gate-tests-coverage` slug on purpose, so no `charter.yml` edit was needed).

The lane's own no-silent-shrink invariant worked on me: adding `r6_wiring_redproof.py`
made `ci_gate.py` fail closed with *"new file(s) in neither CI_PLAN nor EXCLUDED"* until I
classified it.

## 5. Residual — what is NOT done

**5.1 The deploy drift is still UNPAID. This is the headline residual.** 7 always-on + 22
lazy rules remain undeployed to `~/.claude`. The deployed copy of
`common/harness-vcs-hygiene.md` still tells every agent on this box that
`sync-from-live.ps1 -Report json` *inspects*, when the script writes
(`:133` makes `$Report` a `[ValidateSet('text','json')]` FORMAT selector, `:477`
`$writeAllowed = (-not $WhatIf -and -not $Drift)` omits it, `:499` selects mode `sync`,
`:601`/`:670` `Copy-Item -Force`). **Owner action** — deploying mutates what every
concurrently-running agent reads mid-flight, at roughly +1,966 tok/turn. Settling
experiment: `pwsh scripts/sync-rules.ps1 -WhatIf`, read the list, then the real run, after
which `r5_deploy_drift_gate.py` MUST go red with 29 `SHRANK` lines and the baseline must be
emptied in the same change. Gated and non-growing is the achievable half; paying it is not
an agent's call.

**5.2 On a runner, the drift is permanently NOT-CHECKED.** No runner has the owner's home
directory. A green CI run means "the ratchet works", never "the deployed tree matches".
Stated in the gate marker, the `ci_gate.py` docstring and the workflow comment.

**5.3 The credential inversion is unfixed and deliberately pinned RED.**
`r4_credential_rule_gate` is the one `CI_PLAN` entry expected at `rc=1`
(`agent-self/config/AGENTS.md` would deploy an inverted §9 over `~/.claude`). AGENTS.md §9
puts credential policy outside an agent's authority. The pin keeps it TRACKED rather than
tolerated: the day it is repaired the entry goes red and the repairer promotes it to a
blocking `rc=0` in the same change.

**5.4 The two gates still disagree about a third load bucket — carried forward, not
closed.** The adversarial round found it and I did not overturn it: `ci_gate.py:330` counts
`frontmatter_without_paths` as ALWAYS-ON, while `r5_deploy_drift_gate.py:196` does
`(lazy if repo_fm else always_on)`, so ANY frontmatter reads as lazy. Why it does not
block, measured rather than argued: files in that bucket today are **repo 0 / live 0**, so
no current output is wrong; drift in such a file is still DETECTED, only filed at lower
severity; and `ci_gate` invariant 3 pins `ALWAYS_ON` to exactly 8 names, so the file's
appearance turns the gate red before the mislabel could matter. Latent, double-guarded,
unexercised. **Settling experiment (unchanged from the refutation): add a
frontmatter-without-paths rule and require both gates to classify it identically.** I did
not fix it because choosing which semantics is correct is an audit judgment, not an
integration one, and it is unfalsifiable in the current tree.

**5.5 A residual inside my own guard, disclosed rather than hidden.** A single direct push
to `main` that deletes `rule-audit.yml` AND the `quality.yml` step AND the guard file is
caught by nothing, because `skill-dual-write.yml` has no `push:` trigger. That is one
strictly smaller hole than the one this round closed. Settling experiment (owner action,
shared blast radius): add `push: branches: [main]` to `skill-dual-write.yml` and confirm
its D-001 diff gate still behaves when `--base origin/main --head HEAD` spans an empty
range on a push event.

**5.6 SHARED-FILE EDIT, DECLARED.** I edited `.github/workflows/quality.yml` — the file the
ground rules name as the single hazard that red-blocked every PR. The edit is **one step,
self-contained**, inserted in the existing rules cluster (after the doc-coherence step,
well before the py3.12 pivot), reusing the `gate-tests-coverage` charter slug so
`.quality/charter_check.sh` needed no `charter.yml` change. It adds no job, no trigger and
no new slug. There was no way to put this guard on the push path without it:
`quality.yml:685` records that `ci/tests/` has no tree-wide step, and this program's
commits land by direct push.

## 6. NOT-CHECKED — declared, never folded into a pass

* **The new gate on an Ubuntu runner.** `r6_wiring_redproof.py` is pure
  `pathlib`/`shutil`/`subprocess`/`tempfile` with no shell and no `~` dependency, so it
  *should* be platform-neutral — that is a reading of the code, **not a measurement on
  Linux**, and this lane has had exactly that class of claim refuted before. Settling
  experiment: the first run of `.github/workflows/rule-audit.yml`, which has still never
  executed on a runner. The tiktoken-on-Linux repair remains UNVERIFIED for the same reason.
* **The ~25-step `quality.yml` CI.** I make NO claim that CI is green. I claim only that my
  changed files pass the pinned `ruff==0.15.17` check and format, that the charter gate
  passes, and that the suites I named above pass locally.
* **The other contradictions.** I re-verified 4.2 first-hand from the real script; the
  remaining ones are inherited from prior rounds and were not re-measured here.
* **Whether `cl100k_base` tracks Anthropic's real tokenizer.** The 17,107 / 15,141 / 1,966
  token figures are an OpenAI-tokenizer proxy, a ±10-20% estimate, not a receipt. The
  first-party `/context` path needs an owner action and is still untaken after four rounds.

## 7. Confidence

**ALMOST CERTAIN (90-99%)** that the integration is real and the proof is sound: the guard
was measured red before the wiring existed and green after, on the live tree; the
process-level red-proof forces four distinct regressions red with a control arm that must
stay green and which *did* catch a broken harness on its first run; the full gate reports
9/9 with the always-on and divergence invariants intact; 293 rules+wiring tests pass; ruff
passes at the CI pin.

**LIKELY (55-80%)** that `r6_wiring_redproof.py` passes on an Ubuntu runner — mechanism is
strong, execution on Linux is UNVERIFIED. Same band both prior lanes assigned to their own
new gates; I found no reason to move it.

Calibration note on my own strongest sentence. "The lane's gates are now guarded" is scoped
precisely: guarded **against deletion, weakening, un-naming and de-triggering of
`rule-audit.yml`**, on both the push and pull-request paths, provably so. It is NOT a claim
that CI is green, NOT a claim that the deployed rule tree matches the repo (5.1/5.2), and
NOT a claim that no combined-deletion hole remains (5.5). Writing it wider than that is the
overclaim shape this lane has been refuted on repeatedly — where the code is right and the
sentence is wider than its evidence.