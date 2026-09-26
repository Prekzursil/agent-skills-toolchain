---
title: Cursor lockout deeper research 2026-09-02
type: report
permalink: main/research/cursor-lockout-deeper-research-2026-09-02
status: active
valid_as_of: '2026-09-02'
tags:
- cursor
- auth
- lockout
---

valid_as_of: 2026-09-02

- [fact] Official Cursor CLI docs: two auth methods — `agent login` (browser) **or** `CURSOR_API_KEY` / `--api-key` (no browser). https://cursor.com/docs/cli/reference/authentication.md
- [fact] Live `CURSOR_API_KEY`/`CURSOR_API_TOKEN` (`crsr_`, 69) still exchanges 200 and `cursor-agent --api-key … status` is Logged in as costin.ionescu@bolt.eu. `agent login` is the waiter that cleared the store; it is not required when the key is present.
- [fact] Every saved `type:session` JWT (desktop backup 2026-09-02, 2026-08-24 refresh, clone-pack, rail `app.cursor.com` cookie, 51–58d local exp) GetMe **401 ERROR_NOT_LOGGED_IN**. Live `POST api2.cursor.sh/oauth/token` returned **shouldLogout:true** (no new access token).
- [fact] Phone `type:web` cookie is a **different** Google account and also 401.
- [fact] Authenticator `Continue with email` for this Bolt domain **immediately 302s to bolt.okta.com SAML**. Email-OTP no-Okta fallback is **closed** (SSO hard-enforced). Measured 2026-09-02 on authenticator.cursor.sh with authorization_session_id 01M1GXXQMREBPVS2209PGMHBF3.
- [decision] Do not keep driving loginDeepControl/authenticator from the agent — it lands on Okta. Owner must complete FastPass once in that window for desktop/web, **or** Ctrl+C `agent login` and use the API key for CLI.
- [fact] Exchange JWT is `type:api_key_token` (~1h), GetMe 200 but `isEnterpriseUser=false` / Free tier. Reconstructing it as WorkosCursorSessionToken does not skip authenticator.
- relates_to [[Cursor logout forensics + CLI reauth via API key 2026-09-02]]
- relates_to [[Cursor session-persistence 2026-08-27]]
