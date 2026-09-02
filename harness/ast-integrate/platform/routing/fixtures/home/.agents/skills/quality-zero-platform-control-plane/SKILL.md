---
name: quality-zero-platform-control-plane
description: Use when working with `agentuser/quality-zero-platform`, enrolling or auditing governed repos, checking strict-zero wrapper workflows, ruleset drift, trusted-runner Codex remediation, or provider/bootstrap state for the personal-account control plane.
---

# Quality Zero Platform Control Plane

## Overview

Audit and operate the `agentuser/quality-zero-platform` strict-zero control plane without assuming rollout is complete. Read controller truth first, compare it with live GitHub state second, then classify the target repo as `success`, `partial`, or `blocked`.

## Reference Map

- Run [scripts/audit_quality_zero_platform.py](scripts/audit_quality_zero_platform.py) for a repeatable enrollment or drift audit.
- Read [references/control-plane-map.md](references/control-plane-map.md) to see which controller files own inventory, profiles, wrappers, prompts, rulesets, and provider bootstrap.
- Read [references/operator-flow.md](references/operator-flow.md) for the required audit order and stop rules.
- Read [references/live-truth-caveats.md](references/live-truth-caveats.md) whenever the user wants current rollout status or asks whether the platform is already configured everywhere.

## Required Discovery

1. Confirm the task is about `agentuser/quality-zero-platform` or a repo meant to be governed by it.
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

### Workflow
### Output Contract
### Stop Rules
### Common Mistakes
