# quality-gate-autofix-planner

## Purpose

Potential future skill for converting a specific repo's current checks, workflow files, and branch rules into a decision-complete autofix implementation plan.

## Why this is not a live skill yet

- The current architecture skill already covers this use case at the planning layer.
- A dedicated repo-specific planner should only exist after repeated use proves a narrower trigger.

## Likely scope

- inspect workflows, rulesets, and failing checks
- map required contexts to their producers
- choose `workflow_run`, PR comments, or scheduled workflows
- write lane-specific prompts and stop rules

## Planned resources

- reference on producer-mapping patterns
- template prompts for PR rescue, coverage ratchet, and backlog jobs
- example workflow skeletons once repeated structure is proven
