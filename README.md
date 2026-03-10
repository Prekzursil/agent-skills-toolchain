# codex-skills-lab

Private working lab for developing, validating, and publishing Codex skills.

## Purpose

This repo keeps real installable skills under `skills/` and everything else needed to evolve them safely around that core:

- design notes
- incubation docs for future skills
- validation helpers
- reference packs that grow from repeated real-world use

The first shipped skill is [`quality-gate-automation-architect`](skills/quality-gate-automation-architect/SKILL.md), which designs safe automation systems for PR repair, coverage ratchets, analyzer debt burn-down, and merge governance.

## Layout

- `skills/`
  - installable, validated skills only
- `docs/plans/`
  - repo-level design documents and implementation notes
- `docs/incubating/`
  - future-skill concepts and stubs that are not installable yet
- `scripts/`
  - repo-level helpers such as validation

## Current skill

### `quality-gate-automation-architect`

Use this skill when the task is to design or compare:

- PR autofix loops until required checks are green
- coverage ratchets that avoid broad refactors
- SonarQube Cloud or Codacy debt burn-down systems
- zero-touch versus human-approved merge governance
- GitHub-native versus Codex-first versus local-hybrid automation backbones

## Validation

Validate all live skills from the repo root:

```powershell
pwsh -File .\scripts\validate-all-skills.ps1
```

The helper resolves the installed Codex system validator from `CODEX_HOME` or the default user profile path.

## Installability

Only `skills/` is intended for installation. `docs/` and `scripts/` exist to support development and maintenance of the skills.

For a GitHub-based install flow, the intended skill path is:

```text
skills/quality-gate-automation-architect
```

## Working rules

- `skills/` only contains tested, installable skills.
- Future ideas live under `docs/incubating/` until they are proven enough to become real skills.
- Derived summaries are allowed in references; raw session or chat exports are not.
