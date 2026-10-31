---
name: autofix-bot-api
description: Use when scanning a repository or code change for security vulnerabilities, leaked secrets, or dependency issues via the Autofix Bot API (api.autofix.bot) and auto-applying detected fixes; requires AUTOFIX_BOT_API_KEY ; do NOT use for general code review without an Autofix Bot account ; returns findings report and applied-fix summary.
---

# Autofix Bot API

Scan code for security vulnerabilities, secrets, and dependency issues via the Autofix Bot REST API, and auto-fix detected issues.

## Authentication

All API calls require a Bearer token. Read the key from the `AUTOFIX_BOT_API_KEY` environment variable:

```bash
curl https://api.autofix.bot/workspace \
  -H "Authorization: Bearer $AUTOFIX_BOT_API_KEY"
```

If the key is not set, ask the user to provide it. Never hardcode API keys or pass them as command-line arguments. All bundled scripts read from this environment variable automatically.

## Workflow

### Step 1: Create a repository

```bash
curl -X POST https://api.autofix.bot/repositories \
  -H "Authorization: Bearer $AUTOFIX_BOT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-repo",
    "external_id": "local:my-repo",
    "detection": ["security", "secrets"],
    "fix": ["security", "secrets"]
  }'
```

Save the returned `id` (e.g., `repo_...`). Use `external_id` to avoid duplicates — if a repo with the same `external_id` exists, retrieve it with `GET /repositories/external:local:my-repo` instead.

### Step 2: Sync code

Use the bundled `scripts/sync_repo.sh` script:

```bash
# Full sync (first time)
./scripts/sync_repo.sh /path/to/repo <repo_id>

# Incremental sync (subsequent updates)
./scripts/sync_repo.sh /path/to/repo <repo_id> <base_ref>
```

The script creates a git bundle, obtains a signed upload URL, uploads the bundle, and polls until sync completes. It outputs the sync ID on success.

### Step 3: Run analysis
### Step 4: Poll for results
### Step 5: Inspect results and apply fixes
### Detection Categories
### Key Patterns
### API Reference
