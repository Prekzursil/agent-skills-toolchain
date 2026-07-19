---
name: codex-fleet-github
description: Use when dispatching, sweeping, monitoring, or planning autonomous Codex-on-GitHub runs across the private fleet via the codex-fleet-github MCP server. Drives the Wave-1 workflow_dispatch runner (codex-runner.yml) with propose-only draft PRs and a fail-closed auth model. Covers the four tools (fleet_dispatch, fleet_sweep, fleet_status, fleet_orchestrate), token setup, and the pre-PR-68 runner-branch caveat. Do NOT use for local Codex CLI consultation (use codex-consult) or for editing the runner workflow itself.
---

# codex-fleet-github — Autonomous Codex-on-GitHub Fleet Connector

A local FastMCP (stdio) server that lets a Claude Code or Codex agent drive the
private Wave-1 Codex runner (`codex-runner.yml`) on `Prekzursil/agent-skills-toolchain`.
It fans out coding tasks to any repo in the curated fleet, each run producing a
**draft PR** — nothing is ever merged autonomously.

Server subtree: `tools/mcp/codex-fleet-github/` · FastMCP name: `codex-fleet-github`.

## When to use

- "Dispatch Codex to fix X in repo Y" → `fleet_dispatch`.
- "Run this task across the whole fleet" → `fleet_sweep`.
- "What Codex runs / draft PRs are open?" → `fleet_status`.
- "Break this plan into per-repo work" → `fleet_orchestrate`.

Do NOT use for local Codex CLI consult/curate/review (that is the `codex-consult`
skill), nor for editing `codex-runner.yml` (edit the workflow directly).

## The four tools

| Tool | What it does | Writes? |
|------|--------------|---------|
| `fleet_dispatch(repo, task, model?, effort?, max_changed_files?)` | Fires ONE `gh workflow run codex-runner.yml` against `target_repo=repo`. Returns the run URL (best-effort) plus the Actions URL. | Yes — one dispatch, one draft PR |
| `fleet_sweep(task, repos?, model?, effort?, max_changed_files?)` | Dispatches the same task to many repos (default: enabled repos in `codex-targets.yml`; built-in fallback fleet). Serialized by the runner's concurrency group. | Yes — many dispatches |
| `fleet_status(limit?)` | Lists recent codex-runner runs and open codex-runner **draft** PRs across the fleet (`gh run list` / `gh search prs`). | No — read-only |
| `fleet_orchestrate(plan, repos?, dispatch?, ...)` | Structured per-repo decomposition of a plan. By default does NOT dispatch; `dispatch=true` fires `fleet_dispatch` per item. | Only if `dispatch=true` |

The dispatch contract matches the runner exactly:
`gh workflow run codex-runner.yml --repo Prekzursil/agent-skills-toolchain --ref <CODEX_RUNNER_REF> -f target_repo=… -f task=… -f model=… -f effort=… -f max_changed_files=…`.
The workflow filename `codex-runner.yml` and the `codex-runner` PR label are the
runner's own identifiers and are UNCHANGED by the connector rename.

## Safety model (propose-only + fail-closed)

- **Propose-only.** Every run opens a draft PR on the target repo. The connector
  has no merge path — a human reviews and merges.
- **Fail-closed auth.** No usable token ⇒ the tool refuses and returns an error;
  it never falls through to an unauthenticated or wrong-identity `gh` call.
- **Token never leaks.** The PAT is read from the environment and injected into
  the child `gh` process env only — never placed on argv, never logged, never
  echoed in tool output or errors.
- **No `auth.json` contact.** The connector never reads or writes the runner's
  `auth.json`; it only triggers `workflow_dispatch`.
- **Boundary-validated inputs.** repo/task/model/effort/max_changed_files are
  validated at the tool boundary and passed to `gh` as an argv list (no shell),
  so no injection through task text.

## Auth & setup

1. **Token.** Create a fine-grained PAT with `actions:write` on
   `Prekzursil/agent-skills-toolchain` (dispatch) and `pull-requests:read` across
   the fleet (status). Export it as `CODEX_DISPATCH_PAT`. Resolution order:
   `CODEX_DISPATCH_PAT` → `GH_TOKEN` → `GITHUB_TOKEN` → OS keyring
   (`codex-fleet-github`/`dispatch`). Reference the env var NAME only — never
   paste the secret value into any config file.
2. **Runner ref (important pre-merge).** `CODEX_RUNNER_REF` selects which ref
   `gh workflow run` targets. The server defaults to `main`, BUT until **PR #68**
   merges the workflow only exists on the runner branch — set
   `CODEX_RUNNER_REF=feat/codex-parity-runner` until then, then switch back to
   `main` (or unset).
3. **Register the MCP server** (see the splice files in this folder):
   - Canonical manifest: `canonical-mcp-servers.entry.json`
   - Claude `~/.mcp.json`: `mcp.json.entry.json`
   - Codex `~/.codex/config.toml`: `config.toml.entry.toml`
4. **Reconnect.** In Claude: `/mcp reconnect codex-fleet-github`. In Codex: restart
   the session (it forwards `env_vars` on launch).

## Env overrides (advanced)

`CODEX_RUNNER_REPO` / `CODEX_RUNNER_REF` / `CODEX_RUNNER_WORKFLOW`,
`CODEX_QZT_REPO`, `CODEX_TARGETS_FILE` / `CODEX_TARGETS_PATH`,
`CODEX_FLEET_OWNER`, `CODEX_GH_BIN`. `codex-targets.yml` is resolved local-file →
QZT `gh api` (root then `.github/`) → built-in fallback fleet.

## Verify

- `python -c "import server"` constructs `FastMCP("codex-fleet-github")`.
- `fleet_status()` with a valid token returns recent runs without dispatching —
  the safe smoke test. If it errors with an auth message and no `gh` call fired,
  fail-closed is working.
