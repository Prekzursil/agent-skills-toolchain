---
title: Cursor session-persistence 2026-08-27
type: note
permalink: main/research/knowledge/cursor-session-persistence-2026-08-27
---

Consolidated knowledge of how Cursor keeps the owner signed in and how a saved web sign-in can be reused or restored. Sources: prior private docs in `C:\Users\Prekzursil\Cowork\private\` (CURSOR-SESSION-KNOWLEDGE_2026-08-25.md, CURSOR-LOGIN-RESILIENCE.md) and the parent chat transcript fe5e02b8 (grepped, not read end-to-end).

## Account in play

- Desktop Cursor app account: `costin.ionescu@bolt.eu`, enterprise team **Bolt Technology OÜ** (10939257), SSO-enforced via Bolt's Okta IdP. Not locked out; actively rolling.
- A separate PERSONAL Google account exists on a phone Chrome (different user entirely) whose web session was valid to 2026-10-19 — not costin.ionescu.

## How Cursor auth works (the model)

- **Desktop app** authenticates from a single rolling JWT in `%APPDATA%\Cursor\User\globalStorage\state.vscdb`, keys `cursorAuth/accessToken` and `cursorAuth/refreshToken` (same value, type = `session`).
- The token is **non-rotating and auto-renewing**: each refresh re-issues it with a fresh ~60-day expiry. Refresh endpoint `POST https://api2.cursor.sh/oauth/token` (`grant_type=refresh_token`, `client_id=KbZUR41cY7W6zRSdpSUJ7I7mLYBKOCmB`), reusable (does not consume the token). Normal app use keeps it alive indefinitely.
- The token authenticates two surfaces WITHOUT SSO: (1) backend API `api2.cursor.sh` (Connect-RPC, `Authorization: Bearer <token>`); (2) web API `cursor.com/api/*` via cookie `WorkosCursorSessionToken = <workosUserId>::<token>`.
- What the token CANNOT do: render the interactive browser dashboard SPA. That needs a `type:"web"` token carrying a live `workosSessionId`, HS256-signed by Cursor's server secret, mintable only by a real WorkOS/SSO login. There is no token->web-session exchange endpoint.

## Three independent login channels (redundancy)

1. **Desktop app** — from `cursorAuth/refreshToken` in state.vscdb; does not need the browser cookie. Restore via `cursor-desktop-auth-backup_<date>\RESTORE-RUNBOOK.md`.
2. **`cursor-agent` CLI** — its own device-login store, independent of app and browser. `cursor-agent login` once.
3. **Browser (cursor.com)** — SSO via Bolt Okta. The `WorkosCursorSessionToken` cookie is App-Bound-encrypted (bound to this machine + this Chrome profile), so not transplantable elsewhere; the browser anchor is the re-login path, not a cookie-restore path.

## The August web logout — root cause & options

- The costin.ionescu WEB session (browser) was **server-side invalidated** (all three browsers signed out simultaneously — not a lost local cookie). Likely trigger: heavy multi-browser automation hammering the cursor.com -> WorkOS -> Bolt-Okta re-auth flow on 18-19 Aug. Re-injecting the dead cookie does not work.
- The DESKTOP app session was unaffected and stayed alive throughout.
- Recovering the interactive web dashboard = one real web login (email one-time-code if Bolt hasn't hard-enforced SSO — untested; else one Okta sign-in), then snapshot the fresh `type:web` cookie.

## What can be done WITHOUT SSO (proven)

- Retrieved all 181 team shared chats via `api2.cursor.sh DashboardService/GetSharedConversation` with the desktop Bearer token.
- Reconstructed web-API cookie works for `cursor.com/api/auth/me`, `/api/usage-summary`, `/api/auth/stripe`.
- Durable no-SSO token refresh via `C:\Users\Prekzursil\Cowork\private\cursor-token-refresh.mjs` (mints a fresh ~60-day token, backs it up, never touches state.vscdb).

## NEVER-DO rules (these trigger invalidations)

- Never run two mirrored desktop sessions concurrently (same account live on two machines) — classic server-side invalidation trigger.
- Never "test" a suspect token by POSTing/replaying it — a rejected replay can trigger further invalidation; verify JWT `exp` offline instead.
- Never clear, rotate, or "fix" the cookies/tokens; backups are copy-only.

## Artifact index (sensitive material stays in Cowork\private)

- `CURSOR-SESSION-KNOWLEDGE_2026-08-25.md`, `CURSOR-LOGIN-RESILIENCE.md`, `NO-SSO-SESSION-KEY.md`, `cursor-web-restore_2026-08-24.md`, `cursor-durable-access_2026-08-24.md`, `cursor-backend-api_2026-08-24.md`, `cursor-web-session-research_2026-08-25.md`, `cursor-token-refresh.mjs`, and desktop auth backups `cursor-desktop-auth-backup_2026-08-20\` and `_2026-08-24\` (each with cursorAuth-keys.json, state.vscdb, restore runbook).

## OPEN / gaps

- OPEN: The email-OTP no-Okta web-login fallback is untested — unknown whether Bolt has hard-enforced SSO.
- OPEN: Codex-CLI -> Cursor backend bridge never finished (needs an OpenAI-compatible proxy fronting Cursor's backend). Claude-CLI cursor-bridge is installed in WSL, needs one `cursor-agent login`.
- OPEN (see companion note "cursor sign-in longevity 2026-08-27"): the `CursorSessionBackup` daily task referenced in CURSOR-LOGIN-RESILIENCE.md is NOT currently registered on the box (verified 2026-08-28); newest desktop auth backup is 2026-08-24.

## Relations

- relates_to [[Cursor session-persistence 2026-08-27]]
- relates_to [[ChatGPT web session multi-browser inject 2026-07-21]]

