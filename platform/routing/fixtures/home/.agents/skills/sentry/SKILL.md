---
name: "sentry"
description: "Use when the user asks to inspect Sentry issues or events, summarize recent production errors, or pull basic Sentry health data via the Sentry API; perform read-only queries with the bundled script and require `SENTRY_AUTH_TOKEN`."
---


# Sentry (Read-only Observability)

## Quick start

- If not already authenticated, ask the user to provide a valid `SENTRY_AUTH_TOKEN` (read-only scopes such as `project:read`, `event:read`) or to log in and create one before running commands.
- Set `SENTRY_AUTH_TOKEN` as an env var.
- Optional defaults: `SENTRY_ORG`, `SENTRY_PROJECT`, `SENTRY_BASE_URL`.
- Defaults: org/project `{your-org}`/`{your-project}`, time range `24h`, environment `prod`, limit 20 (max 50).
- Always call the Sentry API (no heuristics, no caching).

If the token is missing, give the user these steps:
1. Create a Sentry auth token: https://sentry.io/settings/account/api/auth-tokens/
2. Create a token with read-only scopes such as `project:read`, `event:read`, and `org:read`.
3. Set `SENTRY_AUTH_TOKEN` as an environment variable in their system.
4. Offer to guide them through setting the environment variable for their OS/shell if needed.
- Never ask the user to paste the full token in chat. Ask them to set it locally and confirm when ready.

## Core tasks (use bundled script)

Use `scripts/sentry_api.py` for deterministic API calls. It handles pagination and retries once on transient errors.

## Skill path (set once)

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export SENTRY_API="$CODEX_HOME/skills/sentry/scripts/sentry_api.py"
```

User-scoped skills install under `$CODEX_HOME/skills` (default: `~/.codex/skills`).

### 1) List issues (ordered by most recent)

```bash
python3 "$SENTRY_API" \

### 2) Resolve an issue short ID to issue ID
### 3) Issue detail
### 4) Issue events
### 5) Event detail (no stack traces by default)
### API requirements
### Inputs and defaults
### Output formatting rules
### Golden test inputs
