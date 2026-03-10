# Repository Guidelines

## Project Structure & Module Organization

This repo has three live surfaces and two supporting docs areas:

- `skills/` contains installable, validated skills. Each skill lives in its own folder with `SKILL.md`, `agents/openai.yaml`, and optional `references/`, `scripts/`, or `assets/`.
- `tools/mcp/` and `tools/web/` are reserved for runnable MCP-native or browser-mediated tools.
- `docs/plans/` holds design and rollout notes.
- `docs/incubating/skills/` and `docs/incubating/tools/` hold concepts that are not ready for promotion.
- `scripts/` contains repo-level validation and smoke-test helpers.

## Build, Test, and Development Commands

This repo does not have a single build step. Validate the parts you touch:

- `pwsh -File .\scripts\validate-all-skills.ps1`: validate every live skill under `skills/`.
- `python .\scripts\test-ops-skill-helpers.py`: run smoke tests for the helper scripts shipped with the ops skills.
- `git status --short --branch`: verify branch state before and after changes.

## Coding Style & Naming Conventions

- Keep Markdown concise, imperative, and ASCII unless a file already requires something else.
- Skill folder names must be lower-case hyphen-case, for example `codex-runtime-recovery`.
- `SKILL.md` frontmatter must contain only `name` and `description`.
- `agents/openai.yaml` should keep quoted string values and short UI-facing text.
- Helper scripts should default to read-only discovery where possible and must document stop rules before any risky workflow.

## Testing Guidelines

- Live skills must pass `validate-all-skills.ps1` before commit.
- If a skill ships code in `scripts/`, add or update a lightweight smoke test and run it locally.
- Incubating docs are not installable; keep them short and use the four-section format already established in `docs/incubating/skills/`.

## Commit & Pull Request Guidelines

- Follow the repo’s existing history style: short imperative subjects such as `Add ops skill helper smoke tests`.
- Keep related doc, script, and skill changes in the same commit only when they support one workflow.
- PRs should summarize promoted skills, incubation additions, validation commands run, and any new helper scripts or repo docs.
