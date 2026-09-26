---
title: Cursor TUI stored-auth-invalid was revoked CURSOR_AUTH_TOKEN 2026-09-02
type: note
permalink: main/research/cursor-tui-stored-auth-invalid-was-revoked-cursor-auth-token-2026-09-02
status: active
valid_as_of: '2026-09-02'
---

- [fact] Cursor Agent TUI `v2026.09.02-b17caae` banner "Your stored authentication is invalid. Please log in again. Press any key to log in..." is `InvalidTokenError` after a 401, then the welcome screen. Pressing a key starts browser `loginDeepControl` / Okta and `agent login` **clears** a stored API key.
- [fact] User-env `CURSOR_AUTH_TOKEN` was a `type:session` JWT (local TTL ~60d) that GetMe returned 401 `ERROR_NOT_LOGGED_IN`. CLI `api-key-auth` function D() treats any `CURSOR_AUTH_TOKEN` as authenticated **without** GetMe, persists it as both access+refresh, and **skips** `CURSOR_API_KEY`.
- [fact] `auth.json` `type:api_key_token` GetMe 200 as `costin.ionescu@bolt.eu`. Presenting `crsr_` to `POST api2.cursor.sh/auth/exchange_user_api_key` returns a 1-hour `api_key_token` (not a 60-day session). Designed refresh is re-present the same key, not `/oauth/token` (that returns `shouldLogout:true` on api_key_token).
- [decision] Removed HKCU `CURSOR_AUTH_TOKEN` only (revoked poison JWT). Kept `CURSOR_API_KEY` / `CURSOR_API_TOKEN`. Backed up the JWT to `Cowork/private/session-keys/cursor-user-env-auth-jwt-revoked_2026-09-02.json`. This is not credential rotation.
- [decision] Do not press a key on the waiting TUI. Ctrl+C, open a **new** terminal (old processes still have the env var), run `cursor-agent` or `cursor-agent --api-key $env:CURSOR_API_KEY`. Do not drive glass Continue / Okta.
- relates_to [[Cursor logout forensics + CLI reauth via API key 2026-09-02]]
- relates_to [[Cursor lockout deeper research 2026-09-02]]
See also [[research CURSOR_API_TOKEN full options tree 2026-08-28]].
