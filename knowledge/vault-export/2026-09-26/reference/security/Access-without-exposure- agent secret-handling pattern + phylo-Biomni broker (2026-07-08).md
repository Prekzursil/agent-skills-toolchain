---
title: 'Access-without-exposure: agent secret-handling pattern + phylo/Biomni broker
  (2026-07-08)'
type: reference
permalink: main/reference/security/access-without-exposure-agent-secret-handling-pattern-phylo-biomni-broker-2026-07-08
tags:
- secrets
- workos
- authkit
- mcp
- claude-code
- broker
- 1password
- keyring
- guardrail
---

# Access-without-exposure — how an AI agent uses secrets without handling the literal

**Research verdict (5-agent fan-out, 2026-07-08, all cited/graded).** The sanctioned pattern that RESPECTS (not circumvents) a no-raw-credentials rule: a **deterministic non-model component** resolves a POINTER and injects the literal; the agent only ever handles the pointer.

## The ranking (Windows, one rotating WorkOS Bearer/refresh token)
1. **Claude Code `headersHelper`** — per-connection command emits header JSON, **auto-reruns on 401/403**. Native, ideal for expiring tokens. `.mcp.json` field alongside `url`; `${VAR}`/`${VAR:-default}` expand only in command/args/env/url/headers.
2. **Local loopback reverse-proxy broker** — holds rotating RT in Windows Credential Manager (keyring/DPAPI), refreshes + **writes back the rotated single-use RT** under a single-flight lock, injects `Authorization: Bearer` on the wire → agent hits `127.0.0.1` only. Strongest isolation.
3. mitmproxy reverse-mode + addon (proven proxy, you write refresh). 4. `op run`/`op://` (static inject of the SEED; SDK enables broker write-back; NOT a rotation engine). 5. keyring→Windows Credential Manager (store; ⚠️ ~2560-byte blob cap vs big JWT). 6. `${ENV}` in `.mcp.json` (static tokens, fail-closed). 7. PreToolUse deny-`.env` hook (guardrail, not injection). 8. pizauth (refresh engine, **WSL-only** on Win). 9. Vault+Agent/Doppler/SOPS = overkill/wrong-fit (Vault auto-renew ≠ WorkOS rotation; SOPS static-only; Doppler exports to cloud).

⭐ **Load-bearing (all 5 lenses converged):** NO store/CLI (op, keyring, Vault, Doppler, SOPS) rotates a WorkOS token for you — the broker must own refresh + write-back. The **process boundary** (non-model launcher/hook), not the store choice, is what protects the literal.

## WorkOS AuthKit facts (HIGH, primary docs)
Access token = JWT ~5 min. Refresh token = **single-use + rotated every exchange** (persist the new one or the session dies). Refresh: `POST api.workos.com/user_management/authenticate` grant_type=refresh_token. Rotation-reuse = revoke → re-seed via one-time human login. No API-key/M2M path here → one interactive login must seed the first token.

## NordPass (migration angle) — HIGH
NordPass has **NO** CLI / secret-refs / SDK / CI injection (only admin/reporting APIs). Its "Secrets Manager" = marketed vault storage, zero dev surface. **Rule:** NordPass = interactive human logins; keep a minimal **op / Windows Credential Manager / Bitwarden `bws`** path for the automation SEED only. Never duplicate a secret across both stores.

## Built this session (deployed, verified)
- ⭐ **Guardrail hook** `~/.claude/hooks/deny-credential-reads/deny.py` → wired into `settings.json` PreToolUse (matcher Read|Edit|MultiEdit|Grep|Bash|PowerShell). Denies `.env`/`*.key`/`*credentials*`/`id_rsa` reads incl. `Bash: cat .env` (the gap `permissions.deny` left). Fail-open. **Now active for ALL sessions (applies to me too).**
- **Broker scaffold** `C:\Users\Prekzursil\bin\phylo-broker\` (smoke-tested: /healthz 200, /token clean 502): phylo_broker.py (loopback proxy + /token + single-flight + keyring, `workos_direct`+`phylo_session` modes), seed.py (getpass→keyring, USER-run), phylo.env (op:// pointers only), phylo-headers.ps1 (headersHelper), README.
- **phylo.bio finding:** app.phylo.bio → biomni.phylo.bio = **Next.js SSR, no client-side AuthKit SDK → confidential/BFF** (not public SPA); api.phylo.bio = uvicorn/FastAPI. Broker default = `phylo_session`. OPEN: the DevTools check (what api.phylo.bio consumes: Bearer JWT vs cookie + the token endpoint) needs the user's login — README §1.

Sources: workos.com/docs/authkit/sessions · code.claude.com/docs/en/mcp + /hooks · 1password.dev/cli · nordpass.com support. Relates to [[project_claude_science_hardening_2026-07-07]] (same user/Biomni context).
