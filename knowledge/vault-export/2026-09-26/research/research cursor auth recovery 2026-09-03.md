---
title: research cursor auth recovery 2026-09-03
type: report
permalink: main/research/research-cursor-auth-recovery-2026-09-03
status: active
valid_as_of: '2026-09-03'
tags:
- research-report
- High
- cursor
- workos
- okta
---

# research cursor auth recovery 2026-09-03

- [fact] Deep-research report (Grok, CS on cooldown): `C:/Users/Prekzursil/Cowork/private/cyberstrike-engagements/cursor-auth-recovery-2026-09-02/docs/deep-research-cursor-auth-recovery_2026-09-03.md`
- [fact] Live `%APPDATA%/Cursor/auth.json` JWTs are `type=api_key_token` (no `sid`, ~1h TTL). Synthesizing `WorkosCursorSessionToken={userId}%3A%3A{jwt}` from that JWT: `GET cursor.com/api/auth/me` = 204, `GET /api/usage-summary` = 401 not_authenticated. Same JWT as Bearer on api2: `GetPlanInfo.planName=Free`. Probe: `docs/_crsr_cookie_synth_probe_2026-09-03.json`.
- [decision] The surviving `crsr_` key is a Free-plan CLI identity, not the Bolt SSO team session. Do not treat cookie-synthesis from it as dashboard recovery.
- [fact] WorkOS revokeSession / password-reset / sign-out-everywhere kills the refresh family (`invalid_grant` / shouldLogout). Client converters (token.cursorpro.com.cn) need a live cookie; do not send owner cookies there.
- [fact] Okta Password/IdP forces password every time (FastPass off). Official SSPR is a separate password-policy Forgot-password link — untested on bolt.okta.com this pass.
- [fact] Onion index-only (Ahmia/Vormweb, no Tor, no .onion fetch): exact `WorkosCursorSessionToken` / `loginDeepControl` = 0 hits. Other hits = PayPal cookie-spam / Debian collisions. UNVERIFIED.
- [decision] Next recovery: Okta Forgot password if the widget shows it; else Bolt IT reset; then fresh loginDeepControl poll; Cursor `hi@cursor.com` / `security@cursor.com` if IdP cannot. Do not hammer revoked refresh.
- relates_to [[CyberStrike full-aggressive resume 2026-09-03]]
- relates_to [[Phone forensic recovery 2026-09-03 — no Okta session on phone, but Okta Verify fresh-installed during lockout window]]
See also [[Cursor shared-chat harvest 2026-09-02 + Edge cookie replay vs Databricks Okta]].
