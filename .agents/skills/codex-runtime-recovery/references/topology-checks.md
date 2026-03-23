# Topology Checks

Confirm topology before recovery work.

## Baseline facts

- Which host launched Codex: Windows shell, WSL shell, VS Code, or remote.
- Effective `CODEX_HOME` and whether it is inherited, overridden, or symlinked.
- Candidate stores such as `.codex`, `.codex-vscode`, and archived mirrors.
- Presence of `auth.json`, `config.toml`, `state_5.sqlite*`, `sessions/`, and `migration_conflicts/`.

## Read-only checks

- Read environment variables from the active shell.
- Inspect Codex config files and user settings without editing them.
- Count `rollout-*.jsonl` files in candidate stores.
- Record mtimes and sizes for `state_5.sqlite*` rather than inferring health from existence alone.

## Escalation threshold

Move from inspection to mutation only after you can name one canonical store and one concrete reason the current launch path is wrong.
