---
name: lightning-studio-driver
description: "Use when driving Lightning.ai Studios via the lightning_sdk (auth, account switching, org-aware teamspace/studio discovery, create/start/stop/ switch-machine, upload, run commands) or when installing a big licensed suite (e.g. Schrödinger) on a Studio and running GPU jobs (FEP/MD) on it. Encodes."
---

# lightning-studio-driver

Drive Lightning.ai Studios programmatically via `lightning_sdk` (installed at
`C:\Python314`). The `lightning` CLI is BROKEN on Windows (imports
`simple_term_menu`→`termios`) — always use the SDK, never the CLI.

## Credentials — the hard boundary

- Auth = two env vars: `LIGHTNING_USER_ID` (non-secret UUID) + `LIGHTNING_API_KEY` (secret).
- **The assistant NEVER types/writes the API KEY** into any field, env var, or
  config. Only READ it from the registry:
  `[Environment]::GetEnvironmentVariable('LIGHTNING_API_KEY','User')`. The USER
  sets the key. The assistant MAY set the non-secret `LIGHTNING_USER_ID` itself.
- **setx pitfall (bites every time):** `setx VAR=value` (with `=`) SILENTLY
  FAILS to update on Windows. Must be `setx VAR value` (SPACE). Verify after:
  `[Environment]::GetEnvironmentVariable('VAR','User')`.
- Keys pasted in chat are compromised → tell the user to ROTATE, then re-set.
- In-process for a run: `$env:LIGHTNING_USER_ID = [Environment]::GetEnvironmentVariable('LIGHTNING_USER_ID','User')` (same for key), then run python.

## Auth + WHO AM I

```python
from lightning_sdk.lightning_cloud.login import Auth
from lightning_sdk.api.user_api import UserApi
a = Auth(); a.authenticate()
uid = a.user_id
uname = getattr(UserApi()._get_user_by_id(user_id=uid), "username", None)
```
`Auth()` resolves the account from `LIGHTNING_USER_ID` (it overrides — mismatched
user_id + key lands on the user_id's account). Confirm `uid`/`uname` match the

### ★ Org-owned teamspaces — the discovery gap that wastes hours
### Studio lifecycle
### Free-tier reality (same failure modes as the Boltz free tier)
### cloud-hub rotation (like Modal's md_account_*)
### Installing Schrödinger + running FEP (the heavy path)
### Worked context (2026-07-04)
