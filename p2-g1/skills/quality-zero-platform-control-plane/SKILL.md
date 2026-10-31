---
name: quality-zero-platform-control-plane
description: Use when working with `Prekzursil/quality-zero-platform`, enrolling or auditing governed repos, checking strict-zero wrapper workflows, ruleset drift, trusted-runner Codex remediation, or provider/bootstrap state for the personal-account control plane.
---

# Quality Zero Platform Control Plane

## Overview

Audit and operate the `Prekzursil/quality-zero-platform` strict-zero control plane without assuming rollout is complete. Read controller truth first, compare it with live GitHub state second, then classify the target repo as `success`, `partial`, or `blocked`.

## Reference Map

- Run [scripts/audit_quality_zero_platform.py](scripts/audit_quality_zero_platform.py) for a repeatable enrollment or drift audit.
- Read [references/control-plane-map.md](references/control-plane-map.md) to see which controller files own inventory, profiles, wrappers, prompts, rulesets, and provider bootstrap.
- Read [references/operator-flow.md](references/operator-flow.md) for the required audit order and stop rules.
- Read [references/live-truth-caveats.md](references/live-truth-caveats.md) whenever the user wants current rollout status or asks whether the platform is already configured everywhere.

## Required Discovery

1. Confirm the task is about `Prekzursil/quality-zero-platform` or a repo meant to be governed by it.
2. Resolve controller truth from:
   - `inventory/repos.yml`
   - `profiles/stacks/*.yml`
   - `profiles/repos/*.yml`
   - `templates/repo/.github/workflows/*`
   - `templates/repo/AGENTS.md`
   - `scripts/quality/*`
   - `scripts/provider_ui/*`
3. Compare live GitHub truth for the target repo:
   - wrapper workflow presence
   - wrapper `uses:` refs
   - ruleset presence and required-context parity
   - latest `Quality Zero Platform`, `Quality Zero Gate`, `Codecov Analytics`, backlog, and remediation runs
4. Treat missing provider secrets, missing provider URLs, or missing trusted-runner auth as rollout blockers, not code defects.

## Workflow

1. Run the audit helper with the target repo slug. Prefer `--controller-path` when a local checkout or worktree of `quality-zero-platform` exists. Use `--fixture-dir` only for tests.
2. Read the helper result before proposing changes.
3. Separate findings into:
   - enrollment gap
   - wrapper drift
   - ruleset drift
   - provider/bootstrap blocker
   - actual code or scanner debt
4. Recommend or apply only the smallest next step that matches the highest-signal drift category.
5. If the repo is not enrolled, stop at the minimum onboarding contract:
   - repo profile and inventory entry in the controller
   - thin wrapper workflows
   - repo-local `AGENTS.md`
   - repo-local `bash scripts/verify`
6. If the repo is enrolled but drifted, fix drift before touching product code.

## Output Contract

Always report:

- controller repo/ref used
- enrolled or not enrolled
- expected profile id
- expected ruleset name
- wrapper workflow state
- live ruleset state
- latest relevant workflow conclusions
- final status: `success`, `partial`, or `blocked`
- smallest next action

## Stop Rules

- Do not claim fleet-wide success from local controller verification alone.
- Do not treat missing rulesets, stale wrapper refs, or missing provider secrets as "code fixed".
- Do not recommend pushing directly to a governed repo default branch from automation.
- Stop at `blocked` when GitHub auth, trusted-runner auth, or provider inputs are missing.

## Common Mistakes

- Assuming the controller template equals live rollout truth
- Ignoring stale pinned controller SHAs in repo wrapper workflows
- Looking only at provider dashboards without comparing wrapper files and rulesets
- Calling a repo "configured" when wrappers exist but rulesets or required contexts do not
- Mixing remediation-lane failures with backlog-lane cleanup
