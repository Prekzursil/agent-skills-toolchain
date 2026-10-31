---
title: 2026-03-10-agent-skills-toolchain-design
type: note
permalink: dqverify-repo-20261013/docs/plans/2026-03-10-agent-skills-toolchain-design
---

# agent-skills-toolchain Design

## Summary

This repo is a private Windows-first platform for three live surfaces that work together without collapsing into one ambiguous tool bucket:

- installable skills under `skills/`
- raw Codex orchestration under `tools/mcp/`
- PromptBridge/Agentify talk-only tooling under `tools/web/`

The operator model is intentionally dual-path:

- beginner path: use the wrapper skills
- advanced path: call the raw tools directly
- post-plan execution stays choice-based: subagent-driven is recommended, but inline execution remains available

## Key decisions

- Keep the repo private under the personal `Prekzursil` account.
- Use the active Windows `CODEX_HOME`, default `%USERPROFILE%\.codex`, as the canonical environment root.
- Treat `.codex-vscode` as migration input only, not a second active home.
- Keep Codex orchestration and PromptBridge talk-only participation as separate lanes.
- Keep the root install graph warning-free by isolating release packaging from the runtime dependency path.

## Live surfaces

### Skills

The skill layer teaches and wraps the system:

- `multi-agent-quickstart`
- `promptbridge-codex-consult`
- core orchestration wrappers (`codex-brainstorm`, `codex-review`, `codex-discuss`, `codex-coordinate`, `codex-curate`)
- workflow wrappers (`codex-audit`, `codex-triage`, `codex-fix`, `codex-governance`)

### MCP

`tools/mcp/codex-orchestrator/` owns the structured multi-agent Codex lane and exposes:

- `codex_consult`
- `codex_brainstorm`
- `codex_review`
- `codex_discuss`
- `codex_coordinate`
- `codex_curate`

### Web

`tools/web/promptbridge-talk-lane/` owns the talk-only PromptBridge lane and exposes:

- `promptbridge_discuss`
- `promptbridge_curate`
- status/session tools
- `agentify_*` compatibility aliases during `0.1.x`

## Why the lanes stay separate

The Codex lane is for structured work: planning, review, coordination, and final selection. The PromptBridge lane is for conversation and curation only. Mixing them would blur authority, make failures harder to classify, and increase operator confusion.

## Environment model

Canonical Codex setup is Windows-first:

- canonical root: active Windows `CODEX_HOME`
- default root: `%USERPROFILE%\.codex`
- orchestration config: `promptbridge-orchestration.toml`
- MCP registration and Codex defaults stay in `config.toml`

The system must also support custom `CODEX_HOME` values without hardcoded user or path assumptions.

## Validation contract

The repo is not considered healthy unless all of these hold:

- root `npm ci --ignore-scripts` completes without deprecated warnings
- `npm test` passes for both live tool projects
- skills validate from the repo root
- orchestration status/probe/self-test work from the active Windows root
- PromptBridge remains talk-only and fail-closed when session/model/search/reasoning confirmation is uncertain

## Future direction

Grow the repo by adding more proven skill wrappers and orchestration profiles, not by piling more ad-hoc prompt instructions into one giant system prompt. The backend should stay explicit, testable, and operator-readable.