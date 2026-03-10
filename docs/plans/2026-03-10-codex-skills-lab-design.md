# codex-skills-lab Design

## Summary

This repo is a private working lab with an installable `skills/` tree. The first live skill is `quality-gate-automation-architect`, a planning and architecture skill for safe repo-quality automation.

## Key decisions

- Keep the repo private under the personal `Prekzursil` account.
- Keep `skills/` reserved for real, validated, installable skills.
- Store future ideas as incubation docs, not fake live skills.
- Keep the first skill tool-neutral, but ship tool-specific references for GitHub, Codex, analyzers, and local consultation lanes.
- Store only derived summaries from prior work, not raw conversation exports.

## Why the first skill exists

The recurring problem is not "how do I write one workflow file." The recurring problem is choosing the right automation backbone and guardrails for:

- PR autofix until green
- coverage ratchets
- SonarQube Cloud and Codacy debt burn-down
- zero-touch versus human-approved merge policy

Without a reusable architecture skill, answers tend to be competent but inconsistent. They frequently skip at least one of:

- comparing GitHub-native, Codex-first, and local-hybrid backbones
- separating PR rescue from historical debt reduction
- forcing explicit retry and stop rules
- clarifying whether human-approved merge is mandatory
- returning a full playbook instead of isolated tips

## Baseline pressure-test gaps

Before writing the skill, three baseline scenarios were run without it:

1. `PR autofix until green`
2. `coverage ratchet without broad refactors`
3. `Sonar/Codacy debt burn-down with safe governance`

The baseline outputs were useful, but they still left reusable gaps:

- no mandatory comparison of backbone options
- no required discovery step for current control plane, gates, and merge policy
- no unified output contract
- no reusable discipline separating PR repair from debt burn-down

The new skill is designed to close those gaps.

## Repo structure

- `skills/quality-gate-automation-architect/`
  - live installable skill
  - lean `SKILL.md`
  - modular `references/`
- `docs/plans/`
  - design and implementation notes
- `docs/incubating/`
  - future-skill concept docs
- `scripts/`
  - repo-level validation helpers

## Future direction

This repo should grow by promoting repeated, pressure-tested workflows into real skills. Incubation docs are the holding area; live skills remain the clean install surface.
