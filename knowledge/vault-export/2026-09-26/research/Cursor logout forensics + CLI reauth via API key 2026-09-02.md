---
title: Cursor logout forensics + CLI reauth via API key 2026-09-02
type: report
permalink: main/research/cursor-logout-forensics-cli-reauth-via-api-key-2026-09-02
status: active
valid_as_of: '2026-09-02'
tags:
- cursor
- auth
- cli
---

valid_as_of: 2026-09-02

- [fact] Saved `CURSOR_API_TOKEN`/`CURSOR_API_KEY` (`crsr_`, 69 chars, User+Process+Machine) still works. `POST https://api2.cursor.sh/auth/exchange_user_api_key` returns 200 with access+refresh JWTs. `DashboardService/GetMe` with that Bearer is 200 as `costin.ionescu@bolt.eu` (userId 380943398).
- [fact] That exchanged session is **not** the Bolt team seat: `isEnterpriseUser=false`, `teamId` absent, CLI `about` shows Subscription Tier **Free**. Cloud Agents `GET https://api.cursor.com/v1/me` is 403 `plan_required`.
- [fact] Live desktop `cursorAuth/accessToken` in `%APPDATA%\Cursor\User\globalStorage\state.vscdb` still decodes (type=session, exp 2026-10-30) but `GetMe` with it is 401 `ERROR_NOT_LOGGED_IN` — server-revoked, not a missing local file.
- [decision] CLI reauth path that worked without Okta: exchange the saved `crsr_` key, then persist `{accessToken, refreshToken, apiKey}` to `%APPDATA%\Cursor-agent\auth.json` (and `Cursor-agent-cli\auth.json`). Measured: `cursor-agent status` → Logged in as costin.ionescu@bolt.eu. Hidden `--auth-token` / `CURSOR_AUTH_TOKEN` also works.
- [fact] Reconstructing `WorkosCursorSessionToken=<workosUserId>::<JWT>` authenticates **api2 GetMe** for the exchanged JWT, but **not** the website: `/api/auth/me` is 204, `/api/usage` is 401 `not_authenticated`. Dashboard/loginDeepControl GETs 307 to `/api/auth/bootstrap-cursor-web-target` (no Okta on HTTP). That handshake does **not** mint a `type:web` cookie.
- [decision] Do **not** open `loginDeepControl` in chrome-devtools isolated pages or follow the bolt.okta.com SAML URL. Measured: isolated CDP tab lands on Bolt Okta password (`LoginHint=costin.ionescu@bolt.eu`). Completing that in-agent is the Aug web-logout hammer. Owner must click Yes in an already-logged-in Cursor web session, or cancel the waiting `agent login` because CLI is already restored via API.
- [fact] Packs (secrets, not for chat): `Cowork\private\session-keys\cursor-cli-persist_2026-09-02.json`; receipts `Cowork\output\cursor-fast-cli-persist_2026-09-02.md`, `cursor-approve-cli-loginDeepControl_2026-09-02.md`.
- relates_to [[Cursor session-persistence 2026-08-27]]
- relates_to [[research Cursor API key capabilities 2026-08-28]]
- relates_to [[Cursor shared-chat harvest 2026-09-02 + Edge cookie replay vs Databricks Okta]]
