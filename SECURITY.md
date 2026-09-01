# SECURITY — PRIVATE ONLY

**This repository must never be made public.**

It is the owner's personal-harness SSOT (`Prekzursil/agent-skills-toolchain`).
It contains:

- the live agent control plane (skills, MCP inventory pointers, scripts)
- `browser-profiles/` — **live browser login cookies / profile data** (owner decision 28.08.2026)
- other machine-local harness state that is useless and harmful off this box

## Do not flip visibility

```text
gh repo edit Prekzursil/agent-skills-toolchain --visibility public
```

is a **data-leak command** for this repo. GitHub does **not** warn that `browser-profiles/` holds session cookies. Making the repo public would publish live logins.

If visibility must change: delete `browser-profiles/` from git history first (filter-repo / BFG), rotate every session in those profiles, and get an explicit owner sign-off. A visibility flip without that is a security incident.

## What stays gitignored (real secrets)

Even in a private repo, these must not be committed:

- `local.json`
- `secrets/`, `secure-evidence/`
- `*.token`, `*.pem`, `*.key`
- `.env`, `.env.*`
- `__pycache__/`, `node_modules/`
- hook capture queues and other PII dumps listed in `.gitignore`

`browser-profiles/` is the exception (cookies allowed). Chrome Privacy Sandbox `TrustTokenKeyCommitments/` is ignored because the path looks like a token store and is not login data.

## MCP / browser-bridge

`browser-bridge/` **code** is committed. Registering `chrome-bridge` as a callable MCP in `agents.json` is **deferred** until the hub on `127.0.0.1:8770` is hardened (hub token, extension-id pin, CDP allowlist). An unauthenticated local CDP socket must not be advertised to agents.

## Pre-push guard (optional local hook)

`scripts/git-hooks/pre-push-private-guard.ps1` refuses a push if `gh` reports the repo is public. Install:

```powershell
Copy-Item .\scripts\git-hooks\pre-push-private-guard.ps1 .git\hooks\pre-push
```

The documentation in this file is the mandatory safeguard; the hook is defense in depth.
