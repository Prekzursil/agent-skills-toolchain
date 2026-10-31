---
title: AGENTS
type: note
permalink: dqverify-repo-20261013/agents
---

# Repository Guidelines

## Project Structure & Module Organization

This repo has four live surfaces and two supporting docs areas:

- `.agents/skills/` is the canonical repo-published skill root. Each skill lives in its own folder with `SKILL.md`, `agents/openai.yaml`, and optional `references/`, `scripts/`, or `assets/`.
- `skills/` remains a temporary compatibility copy during migration; do not add new canonical content there unless the same change lands in `.agents/skills/`.
- `tools/mcp/`, `tools/editor/`, and `tools/web/` are reserved for runnable MCP-native, editor-local, or browser-mediated tools.
- `docs/plans/` holds design and rollout notes.
- `docs/incubating/skills/` and `docs/incubating/tools/` hold concepts that are not ready for promotion.
- `scripts/` contains repo-level validation and smoke-test helpers.

## Build, Test, and Development Commands

This repo does not have a single build step. Validate the parts you touch:

- `pwsh -File .\scripts\validate-all-skills.ps1`: validate every live skill under `.agents/skills/` and fall back to `skills/` if the migration layer is all that exists.
- `python .\scripts\test-live-skill-helpers.py`: run smoke tests for the current live scripted skills.
- `git status --short --branch`: verify branch state before and after changes.

## Coding Style & Naming Conventions

- Keep Markdown concise, imperative, and ASCII unless a file already requires something else.
- Skill folder names must be lower-case hyphen-case, for example `codex-runtime-recovery`.
- Tool folders should be lower-case hyphen-case, for example `workstation-codex-bundle`.
- `SKILL.md` frontmatter must contain only `name` and `description`.
- `agents/openai.yaml` should keep quoted string values and short UI-facing text.
- Helper scripts should default to read-only discovery where possible and must document stop rules before any risky workflow.
- Treat consumer-owned manifests as closed schemas. Never add a manifest key merely to carry provenance; store provenance in `.provenance/<repo-relative-manifest-path>.md` instead.

## Testing Guidelines

- Live skills must pass `validate-all-skills.ps1` before commit.
- If a live skill ships code in `scripts/`, add or update a lightweight smoke test or fixture-backed regression case and run it locally.
- Live tool projects should include at least one explicit local validation note or script when they introduce runnable behavior.
- Incubating docs are not installable; keep them short and use the four-section format already established in `docs/incubating/skills/`.

## Commit & Pull Request Guidelines

- Follow the repo's existing history style: short imperative subjects such as `Add ops skill helper smoke tests`.
- Keep related doc, script, and skill changes in the same commit only when they support one workflow.
- PRs should summarize promoted skills or tools, validation commands run, and any new helper scripts or repo docs.

## Cursor Cloud specific instructions

The startup update script runs `npm install` and installs the pinned Python lint/test
tooling. Notes below cover only non-obvious caveats; standard commands live in
`package.json`, `.github/workflows/quality.yml`, and each package's `pyproject.toml`.

- **Runtimes:** Node 22 + npm 10, Python 3.12. `pwsh` and `uv` are NOT installed (so the
  `validate:skills` npm script cannot run — see below). There is no `.cursor/environment.json`;
  the environment is snapshot-managed.
- **Runnable surfaces.** Retired 2026-08-09: this bullet used to name two Node MCP servers,
  `codex-orchestrator` and `promptbridge-talk-lane`. Both trees were deleted with the rest of
  the ChatGPT-web lane, and the repo root no longer ships an MCP server entrypoint. The Node
  surfaces that remain are libraries and linters, not long-running servers —
  `tools/fanout-schema`, `tools/agentspec-js`, `tools/lib`, and the vendored
  `tools/mcp/hacktricks-mcp-server` (which has its own `npm ci && npm test`).
- **Nothing in the repo spawns the external `codex` CLI any more.** The `codex_consult` tool
  and the `cli.mjs self-test` / `probe` commands that used to fail with `spawn codex ENOENT`
  in cloud went with `tools/mcp/codex-orchestrator/`. `tools/lib/codex-invocation.mjs` only
  *resolves* a Codex binary path; it does not spawn one, and its tests do not require the
  binary to exist.
- **Node tests:** `npm test` runs the root workspaces (`tools/fanout-schema`,
  `tools/agentspec-js`, `tools/lib`) via `npm run test --workspaces --if-present`.
  `tools/lib` was added to the workspace list on 2026-08-09: its 6 suites (72 tests) were
  extracted out of `tools/web/agentify-desktop`, whose CI step went away with the tree, so
  until then nothing ran them.
- **Python tooling lives in `~/.local/bin`** (ruff, pytest). Add it to `PATH`
  (`export PATH="$HOME/.local/bin:$PATH"`) before running `ruff`/`pytest`. Repo-wide lint is
  `ruff check .` + `ruff format --check .`, and the gate pins **ruff 0.15.17** (honors
  `ruff.toml`) — match it exactly (`pip install ruff==0.15.17`, or `uvx ruff@0.15.17`), because
  a different ruff reports different findings than CI. The fan-out schema linter is invoked
  with file args, as CI does: `cd tools/fanout-schema && npm run lint -- ../../workflows`.
- **Per-package Python tests** need an editable install from that package's own dir first,
  e.g. `pip install --break-system-packages -e ".[dev]"` in `tools/mcp-manager`,
  `tools/scholarly-access-mcp`, `tools/taskwatch_monitor`, `tools/monitorcore`. `tools/stdin-server`
  is stdlib-only (pytest only). There is no repo-wide pytest autodiscovery — the many standalone
  suites in `.github/workflows/quality.yml` (test-python job) are the source of truth for what to run.
  Two per-package specifics worth knowing: `tools/mcp-manager` enforces 100% branch coverage
  (`pytest --cov=. --cov-branch --cov-fail-under=100 -q`) and its PySide6/Textual GUI needs a
  display while its CLI runs headless (`app.py status|preset list|json`); `tools/scholarly-access-mcp`
  auto-ignores the network suite `tests/test_live.py` via `addopts` (run it manually only), and
  `list_tools.py` prints its 8-tool surface.
- **`scripts/validate-all-skills.ps1` (`npm run validate:skills`) needs PowerShell (`pwsh`) plus an
  external skill-creator validator under `CODEX_HOME`; neither is present in cloud, so skip skill
  validation here.**
- **Full quality gate details** (types via basedpyright, SAST, secrets, deps) are in `README.md`
  and `.github/workflows/quality.yml`.

<!-- AgentBridge retired 2026-07-27. The block that stood here told agents to coordinate
     via AgentBridge and call its MCP tools (reply / get_messages); those tools no longer
     exist, so following it made an agent call removed tools and wait on a silent peer. -->

## Multi-agent collaboration (AgentBridge is retired)

AgentBridge was Windows-broken and has been disabled (`claude plugin disable
agentbridge@agentbridge`); its daemon does not run and its MCP tools (`reply`,
`get_messages`, `get_budget`) are gone. Do not follow the old protocol.

Two rails replace it - setup, the verify-before-trust probe, and the honest limits of each
are in the `multi-ai-mingle` skill (`skills/multi-ai-mingle/SKILL.md`):

- **Fan-out (Claude to Codex).** The official `codex mcp-server` is mounted at user scope, so
  `mcp__codex__codex` / `mcp__codex__codex-reply` are native tools. Call them in parallel for
  independent Codex threads; results come back as ordinary tool results.
- **Live peer channel.** `mcp_agent_mail` on `127.0.0.1:8812` gives symmetric Claude/Codex
  messaging plus advisory file leases.

Retiring AgentBridge also removed `get_budget`, so budget pacing is advisory and manual now
rather than enforced; `agent-self/config/CLAUDE.md` records that consequence.