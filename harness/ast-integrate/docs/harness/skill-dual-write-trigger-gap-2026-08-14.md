# Six gates never run on push — and the obvious fix is already refuted

`skill-dual-write.yml` is `pull_request`-only. 242 commits landed on `main` in 36 hours,
essentially all pushed directly, so every gate in that workflow sat out the entire delivery.

**The gap is real. The one-line fix is wrong.** Both halves are recorded here because the
second half is what stops the next agent repeating the attempt.

## What does not run on a push to main

| step | what it guards |
|---|---|
| `test_cs_wiring.py` | Claude Science wiring — stale-checkout routing, undeployed probes |
| `test_ssot_wiring.py` | the SSOT rule + drift gate are actually *reachable* |
| `check_skill_description_ratchet.py` | description budget (descriptions are always-loaded context) |
| `check_skill_render_traps.py` | skill frontmatter strict-parse |
| `gen_skill_index.py --check --fail-on-drift` | generated index vs source |
| `gen_skills_manifest.py --check` | manifest drift |

Two *different* lanes' gates ride this one workflow, so a single missing trigger silenced
both. PR #281 exists precisely because `gate-cs-wiring` "has never run" — it makes them run
**on that PR**, and they would still not run on the push that follows.

## Why adding `push:` is refuted

I added `push: branches: [main]`, having first measured that the diff-based last step is
harmless in that state: with `--base origin/main --head HEAD` after a push, both revisions
are the same commit, and it exits 0 with *"OK: changed skill paths match their final-tree
counterparts."*

That measurement was correct and the conclusion drawn from it was wrong. `ci/tests/test_ci_wiring.py:163`:

```python
def test_workflow_does_not_advertise_null_range_events() -> None:
    """KNOWN-BROKEN: push/dispatch fetched main then diffed main against itself."""
    assert "\n  push:\n" not in text
    assert "\n  workflow_dispatch:\n" not in text
```

The trigger was **deliberately removed** and the decision encoded as a test. Exiting 0 on an
empty diff is not the safety property — **it is the defect**: the parity gate becomes a
permanently-green no-op, the exact shape `rules/common/ci-hygiene.md` §1 forbids. I read
"degenerates to pass" as reassurance when the author had already classified it as breakage.

## The repo uses its own unfixed defect as a test fixture

Adding the trigger broke three tests. Two are named
`test_control_fires_on_a_workflow_with_no_push_trigger`, and they are well-built two-hypothesis
controls (`ci/tests/test_rule_audit_ci_wiring.py:435`) that need a **real** push-triggerless
workflow as their known-bad arm. `skill-dual-write.yml` is that arm. Its own assertion message
anticipates this exactly:

> `"precondition: skill-dual-write.yml gained a push: trigger, so it is no longer a known-broken example. Re-point this control."`

So the repo's wiring checker already flags this workflow `not-push-triggered`, and that
violation is load-bearing test scaffolding. Fixing the defect breaks the tests that depend on
it existing. That is worth naming as a design smell: **a known-broken example used as a
fixture makes the defect expensive to fix**, and nothing warns you until you try.

## The fix that would actually work

Split by what each step needs, rather than moving the whole workflow:

* **State checks on `push` + `pull_request`** — the six above read the committed tree and are
  meaningful on any event. All six pass against current `main` (measured locally).
* **The diff-based parity check stays `pull_request`-only** — it is inherently a two-revision
  comparison and has no meaning when base == head.
* **Re-point the two controls** at another genuinely push-triggerless workflow
  (`codex-runner.yml`, `workflow_dispatch`-only) — but first check the wiring checker does not
  then report *it* as a violation, since that one is manually dispatched by design and
  flagging it would be a false positive.

**Not done here.** It is a coordinated multi-file CI-wiring change, and CI has been unable to
start a job since 04:33:59Z — so it could not be verified end to end. Shipping unverifiable
CI-wiring changes while the runner is dead is how main ends up red with no way to see it.

## Separately: four tests fail on Windows and would pass in CI

`python -m pytest ci/tests tools/d001-dual-write/tests -q` reports **7 failed, 909 passed**
locally. Three were mine (above). The other **four fail at clean HEAD** and are platform
artifacts, confirmed by reading the failures rather than inferring from their names:

| test | failure | cause |
|---|---|---|
| `test_verifier_refuses_an_executable_mode_regression` | `fixture lost executable mode` — got `100644`, wanted `100755` | NTFS has no exec bit |
| `test_project_keeps_distinct_invalid_utf8_path_bytes` | `UnicodeDecodeError: byte 0xff` from `<frozen os>` | Windows paths cannot hold non-UTF-8 bytes |
| `test_strict_parity_keeps_distinct_invalid_utf8_path_bytes_distinct` | same | same |
| `test_atomic_ref_create_refuses_a_branch_created_after_precheck` | ref-race assertion | **UNVERIFIED** — not diagnosed |

This is the **inverse** of the local-green/CI-red family this repo has burned five times:
local-RED, CI-green. It matters for the local CI substitutes — a runner that included
`ci/tests` wholesale would report four permanent failures that do not exist on the runner, and
a standing false red trains you to ignore the output. `_ci_quality_nopip.py` names test files
individually and does not include these; that is deliberate and should stay that way.
