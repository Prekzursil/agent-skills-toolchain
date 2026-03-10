# Roadmap

## Now

- Ship `quality-gate-automation-architect` as the first validated skill.
- Keep the core skill tool-neutral and push vendor detail into references.
- Use derived summaries to keep the references current without storing raw session artifacts.

## Next candidates

### `quality-gate-autofix-planner`

Specialize in turning an existing repo's current checks, failures, and workflow files into a concrete PR-repair implementation plan.

### `coverage-ratchet-playbook`

Specialize in coverage-only uplift strategies, target sizing, and stop rules.

### `debt-burndown-orchestrator`

Specialize in analyzer backlog batching, allowlists, reviewer-only zones, and safe recurring schedules.

### `skill-knowledge-refresh`

Specialize in mining recurring lessons from accepted work and updating skill references with derived summaries only.

## Promotion criteria

Promote an incubation note into a live skill only when:

- the workflow has been used repeatedly
- the failure modes are understood
- the trigger is clear enough that Codex can load the right skill reliably
- the skill can be validated with pressure scenarios, not just described

## Non-goals

- stuffing multiple overlapping workflows into one giant skill
- storing raw transcript or session exports in the repo
- adding scripts before a repeated deterministic task is proven
