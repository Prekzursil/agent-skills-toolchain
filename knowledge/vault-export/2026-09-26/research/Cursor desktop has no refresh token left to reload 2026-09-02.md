---
title: Cursor desktop has no refresh token left to reload 2026-09-02
type: note
permalink: main/research/cursor-desktop-has-no-refresh-token-left-to-reload-2026-09-02
status: active
valid_as_of: '2026-09-02'
---

- [fact] Live `%APPDATA%\Cursor\User\globalStorage\state.vscdb` (~2.6 GB) `cursorAuth/%` keys are only `stripeMembershipType=free`, empty `cachedEmail`, `cachedSignUpType=unknown`. **No** `cursorAuth/accessToken` or `refreshToken`. No `state.vscdb.backup`.
- [fact] Earlier this session those JWTs existed (`type:session`, ~60d local TTL) and GetMe was 401; `POST api2.cursor.sh/oauth/token` returned `shouldLogout:true`. Do not repeat that POST.
- [decision] Developer: Reload Window / HTTP2 toggle / MCP toggle cannot mint a new desktop session. There is nothing left on disk to refresh. The generic "14 days of inactivity" claim is false here (Cursor session JWT lifetime is 60 days; this one was server-revoked, then wiped).
- [decision] Do not toggle `http.electronFetch` (already true) or MCP servers. Do not press a key on the Agent TUI login banner. CLI remains on `CURSOR_API_KEY` / 1h `api_key_token`.
- relates_to [[Cursor TUI stored-auth-invalid was revoked CURSOR_AUTH_TOKEN 2026-09-02]]
- relates_to [[Cursor logout forensics + CLI reauth via API key 2026-09-02]]
See also [[Cursor lockout deeper research 2026-09-02]].
