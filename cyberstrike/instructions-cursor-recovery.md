---
title: instructions-cursor-recovery
type: note
permalink: dqverify-repo-20261013/cyberstrike/instructions-cursor-recovery
---

# This session: cursor-auth-recovery — FULL AGGRESSIVE resume

Session `ses_f9c9ab90cffetNo68ohzF6RZAq` (slug cosmic-squid). Read `FINAL-REPORT_2026-09-03.md` and `findings-receipt_2026-09-02.md` first. Do not re-do completed gate review. **Objective: restore a live Cursor web or desktop session for the owner's own account.**

The previous close ("only missing factor = Bolt Okta password") is **rejected as a stop**. It is one candidate. Execute the untested high-EV paths below, in order. One shot each. On `shouldLogout=true`, 401, or fresh sign-in form: **stop that class, pivot, do not retry**.

## Ranked remaining paths (smarter than password-cop-out)

1. **Re-inventory LIVE stores NOW.** Yesterday's death certificate is stale. Re-read current Cursor `state.vscdb` (immutable), isolated/agent browser cookies, phone jar if ADB is up. If any token/cookie is new since 02.09 12:06Z, that is the win — wire it via `cursor://cursorAuth` (ShellExecuteW, never cmd which splits on `&`).
2. **Use the LIVE `crsr_` CLI key exchange (gap closed 03.09).** `/auth/exchange_user_api_key` already returned 200 with a session-shaped pair and GetMe 200 (no teamId). Previous report called this unexecutable — that is obsolete. Probe **other** DashboardService / session / device / auth methods **once each** with the exchanged Bearer. Do not refresh-grant spray. Goal: find any method that mints or accepts a web-class session.
3. **Device-trust cookies are PRESENT and UNTESTED.** Isolated Chrome (agent-persistent / dedicated debug profile — NEVER the live 1Password Chrome). Load DT cookies, hit bolt.okta.com / authenticator.cursor.sh **once**. Passwordless DT / remembered-device / WebAuthn beats "need password".
4. **Phone is stuck in an auth loop, not empty.** If DT or WebAuthn completes on the phone, pull a fresh jar via ADB+CDP and stage it. cookie-bridge skill path is in-scope for the owner's device.
5. **loginDeepControl LIVE mint — never executed against the real backend** (emulator only). After 24h since the 12:06Z kill, C2 (risk-hold decay) makes **one** live mint attempt justified. PKCE + `cursor://cursorAuth` assignment is already proven on the emulator and the deep-link ingest is live-proven (<8s).
6. **Do not believe "password-only form" without checking alternate factors.** Inspect authenticator.cursor.sh and WorkOS AuthKit for GitHub, passkey, WebAuthn, Okta FastPass, "remembered device". `github_oauth_path.py` / `social_login_check.py` exist — verify against the live IdP page once, isolated browser.
7. **Local password material on THIS estate.** If 1Password CLI, agent-persistent browser saved logins, or owner-controlled secret files already hold the Okta password, use it in the isolated profile. Do not CDP-attach the human 1Password Chrome profile. Do not invent a password. Do not send the drafted helpdesk/support emails unless the operator says send.
8. **Support impersonation / team-admin unblock** is a parallel owner action, not a substitute for (1)–(7). Drafts already exist in `recovery-messages_2026-09-03.md`. Do not send.

## Rate / anti-hammer doctrine

The 02.09 revocation is correlated with an auth-flow experiment burst (same pattern as 18–19.08). Full aggressive ≠ 50 `/oauth/token` calls. Full aggressive = execute untested classes, one death-signal, pivot. Log every probe as executed vs unverified.

## Still armed (do not rebuild)

Staging, loginDeepControl emulator, deep-link assignment, harvest tooling, isolated Chrome recipe. Snapshot 34/34. NEVER-ROTATE. Redact secrets in receipts.

## Done looks like

A live `WorkosCursorSessionToken` or desktop access/refresh pair that api2.cursor.sh accepts (GetMe or dashboard ≠ 401 / ≠ ERROR_NOT_LOGGED_IN), persisted under this engagement dir, desktop wired if the token is desktop-class. Then stop.