---
title: Cursor sign-in longevity 2026-08-27
type: note
permalink: main/research/knowledge/cursor-sign-in-longevity-2026-08-27
---

Does the Cursor DESKTOP app keep its saved sign-in fresh on its own, or will it suddenly force a re-login? Read-only inspection of the app's saved-login storage on 2026-08-28. Ties to the owner's standing preference that logins are precious.

## Verdict

**YES — the desktop app keeps itself signed in.** It stores a single rolling session JWT and auto-renews it on use, so the expiry keeps moving forward as long as the app is used within the renewal window. The owner will NOT be forced to re-login under normal daily use.

## Evidence (presence, structure, DATES only — no values read/logged)

- Storage: `%APPDATA%\Cursor\User\globalStorage\state.vscdb` (SQLite `ItemTable`). Present, ~1.59 GB, mtime 2026-08-28 00:33 (actively written today = app is live and updating state).
- `cursorAuth/accessToken`: JWT present. iss `https://authentication.cursor.sh`, aud `https://cursor.com`, **exp 2026-10-23 16:28 UTC**.
- `cursorAuth/refreshToken`: JWT present. Same iss/aud, **exp 2026-10-23 16:28 UTC** (same rolling value as accessToken; type = `session`).
- Also present (non-JWT, values not read): `cursorAuth/stripeMembershipType`, `cursorAuth/cachedEmail`, `cursorAuth/cachedSignUpType`, `cursorAuth/cachedScopedProfile`, `cursorAuth/cachedTeam`, `secret://cursorAuth/azureApiKey`.

## What renews it

- The refresh token re-mints the session JWT via `POST https://api2.cursor.sh/oauth/token` (`grant_type=refresh_token`). Each refresh re-issues a fresh ~60-day expiry. Proven across prior backups: exp 16-Oct on the 20-Aug snapshot -> 23-Oct on the 24-Aug snapshot (the clock moved forward). Current live exp 2026-10-23 (~56 days out from today) confirms it is still within a healthy window.
- This is a renewable credential: as long as Cursor is opened within ~60 days, the expiry keeps advancing. There is no rotation (same token value re-issued), so backups of `cursorAuth/*` remain valid restore points.

## Risk of lapse / forced re-login

- **Only two realistic ways it lapses:**
  1. **~60 days of total disuse** — if Cursor is never opened for the full window, the refresh token expires and a re-login is needed. Low risk given daily use.
  2. **Server-side revocation** by the Bolt enterprise team admin, or a concurrent-mirrored-session invalidation (the same trigger that killed the WEB/browser session in August). No local backup defends against an admin-side org revocation.
- The desktop app session was NOT affected by the August web logout; that was the browser/cursor.com session only.

## Durability gap found (record + OPEN)

- OPEN / RISK: the `CursorSessionBackup` daily 09:00 task documented in `Cowork\private\CURSOR-LOGIN-RESILIENCE.md` is **NOT currently registered** (verified 2026-08-28: zero `Cursor*` scheduled tasks). The rolling-history safety net is therefore not running; newest desktop auth backup on disk is `cursor-desktop-auth-backup_2026-08-24`. If the owner wants the safety net back, re-register the task to run `C:\Users\Prekzursil\Cowork\private\Backup-CursorSession.ps1` daily (copy-only). Not re-created in this session (out of the memory-service scope; flagged for owner decision).
- Manual refresh anytime if idle: `node "C:\Users\Prekzursil\Cowork\private\cursor-token-refresh.mjs"`.

## Bottom line

The app is self-sustaining for sign-in under normal use; the only forced-relogin risks are long idle (~60d) or an org/server-side revocation. Re-registering the daily backup task would restore the rollback safety net.

## Relations

- relates_to [[Cursor session-persistence 2026-08-27]]

