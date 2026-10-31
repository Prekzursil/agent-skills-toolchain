---
title: README
type: note
permalink: dqverify-repo-20261013/tools/mcp/codex-fleet-github/readme
---

# codex-fleet-github MCP

A small **FastMCP (stdio)** server that lets a LOCAL Claude Code / Codex agent
drive the **Codex runner fleet** — trigger autonomous Codex runs across the
repos enabled in `codex-targets.yml`, sweep a task fleet-wide, check status, and
decompose a big plan into per-repo tasks.

It is the local counterpart to the Wave-1 **private runner**
(`.github/workflows/codex-runner.yml` in `Prekzursil/agent-skills-toolchain`),
which holds the ChatGPT-subscription `auth.json`, runs Codex with the vendored
harness + MCPs + skills + AGENTS.md, and opens a **propose-only DRAFT PR** on the
target repo.

## Security model (the split — never violated)

- **This MCP NEVER handles `auth.json`.** It only *triggers* runs. `auth.json`
  lives exclusively as a secret inside the private runner repo.
- Auth here is a **scoped dispatch token** read from the environment/keyring —
  `CODEX_DISPATCH_PAT` → `GH_TOKEN` → `GITHUB_TOKEN` → keyring
  (`service=codex-fleet-github`, `user=dispatch`). The recommended token is a
  fine-grained PAT with **Actions: read+write on `agent-skills-toolchain` only**
  (it can start runs; it cannot read `auth.json` or repo contents). If no token
  is found, `gh`'s own ambient auth (`gh auth login`) is used.
- The token is injected into the child `gh` process **environment**, never onto
  argv and never logged.
- **Propose-only.** The runner opens DRAFT PRs; nothing here merges. All runs
  serialize through the runner's `concurrency: codex-runner` group.
- Inputs are validated at the boundary (repo shape, effort allowlist, integer
  ranges, no control chars) and passed to `gh` as a list — never spliced into a
  shell line.

## Tools

| tool | what it does |
|---|---|
| `fleet_dispatch(repo, task, model?, effort?, max_changed_files?)` | Trigger ONE run of the private runner against `repo`. Returns the run URL (best-effort) + Actions URL. |
| `fleet_sweep(task, repos?, model?, effort?, max_changed_files?)` | Dispatch the same `task` to many repos (default: every enabled repo in `codex-targets.yml`). **Fail-closed:** if `codex-targets.yml` can't load or has zero enabled targets, it raises instead of fanning out — pass explicit `repos` or fix the config. Serialized by the runner. |
| `fleet_status(limit?)` | List recent codex-runner runs + open codex-runner DRAFT PRs across the fleet (via `gh run list` / `gh search prs`). Read-only. |
| `fleet_orchestrate(plan, repos?, dispatch?, ...)` | Decompose a natural-language `plan` into one concrete task per repo and RETURN it **without dispatching** (safe default). `dispatch=true` then fires `fleet_dispatch` per item. |

`fleet_orchestrate`'s decomposition is a deterministic template (`plan + repo →
task`); a smarter per-repo-aware decomposition is a documented follow-up.

## The fleet source of truth: `codex-targets.yml`

`fleet_sweep` / `fleet_orchestrate` read the shared **`codex-targets.yml`** (in
the public QZT control-plane repo). Resolution order:

1. `CODEX_TARGETS_FILE` — a local path (a QZT checkout), if set.
2. else fetch `codex-targets.yml` (repo root, then `.github/`) from the QZT repo
   via `gh api`.
3. else **fail-closed** — raise `FleetError` (fix the config or pass explicit
   `repos`). The tool will **not** silently fan out to a built-in fleet.

> **Fail-closed by default.** A misconfigured or unreachable `codex-targets.yml`
> must never fan changes out to unintended repos. Only when the operator sets
> `CODEX_FLEET_ALLOW_FALLBACK=1` does the tool consult the built-in catalogue —
> and even then only the **4 curated public repos** (`Reframe`, `env-inspector`,
> `omniaudit-mcp`, `WebCoder`) are enabled; every private repo, `momentstudio`
> (payment/auth), and all non-curated public repos stay **off**.

```yaml
defaults: { model: gpt-5.6-sol, effort: max, max_changed_files: 40 }
targets:
  - repo: Prekzursil/Reframe
    enabled: true
    tasks: ["Documentation only: ..."]
    max_changed_files: 25      # optional per-repo override
  - repo: Prekzursil/momentstudio
    enabled: false             # payment/auth — off by default
    tasks: []
```

## Install & run

```bash
cd tools/mcp/codex-fleet-github
uv sync                    # or: python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python server.py   # stdio MCP server
```

## Environment

| var | purpose |
|---|---|
| `CODEX_DISPATCH_PAT` / `GH_TOKEN` / `GITHUB_TOKEN` | dispatch token (first non-empty wins; else keyring, else `gh auth`) |
| `CODEX_RUNNER_REPO` | private runner repo (default `Prekzursil/agent-skills-toolchain`) |
| `CODEX_RUNNER_REF` | ref the workflow dispatches on (default `main`; set to the runner's branch until PR #68 merges) |
| `CODEX_QZT_REPO` | control-plane repo holding `codex-targets.yml` (default `Prekzursil/quality-zero-platform`) |
| `CODEX_TARGETS_FILE` | local path to `codex-targets.yml` (skips the `gh api` fetch) |
| `CODEX_FLEET_ALLOW_FALLBACK` | set `1`/`true` to opt into the built-in curated fallback (4 public repos) when `codex-targets.yml` is missing/empty; unset = fail-closed (raise) |
| `CODEX_GH_BIN` | path to the `gh` binary (default `gh` on PATH) |

## MCP client registration

### Codex — `~/.codex/config.toml`

Codex forwards named env vars (it does **not** expand `${VAR}`), so list the
token var(s) under `env_vars` and make sure they're set in Codex's launching
environment.

```toml
[mcp_servers.codex-fleet-github]
command = "C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/codex-fleet-github/.venv/Scripts/python.exe"
args = ["C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/codex-fleet-github/server.py"]
env_vars = ["CODEX_DISPATCH_PAT", "GH_TOKEN"]
enabled = true
```

### Claude — `~/.mcp.json`

Claude sets literal `env` values. Either put the PAT here (this file is
user-scoped and gitignored), **or** leave it empty and rely on `gh auth login`.

```json
"codex-fleet-github": {
  "command": "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\codex-fleet-github\\.venv\\Scripts\\python.exe",
  "args": ["C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\codex-fleet-github\\server.py"],
  "env": {
    "CODEX_DISPATCH_PAT": ""
  }
}
```

> Never commit a real token. Leave `""` to fall back to `gh` ambient auth, or set
> `CODEX_DISPATCH_PAT` in the OS environment instead of inlining it here.

## Tests

```bash
cd tools/mcp/codex-fleet-github
python -m pytest -q          # unit tests, no live gh / no network (injected fake runner)
ruff check . && ruff format --check .
```