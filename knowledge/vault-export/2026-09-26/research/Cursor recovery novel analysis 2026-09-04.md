---
title: Cursor recovery novel analysis 2026-09-04
type: report
permalink: main/research/cursor-recovery-novel-analysis-2026-09-04
status: active
valid_as_of: '2026-09-04'
tags:
- cursor
- recovery
- okta
- workos
---

Novel leftover analysis of owner Cursor/WorkOS/Okta recovery. Relates to [[research cursor auth recovery 2026-09-03]] and [[Phone forensic recovery 2026-09-03 — no Okta session on phone, but Okta Verify fresh-installed during lockout window]].

- [fact] Live Cursor state.vscdb on 04.09.2026 holds cursorAuth/refreshToken JWT type=api_key_token, no sid, expired 03.09.2026 06:06:48Z; accessToken empty; cachedEmail domain bolt.eu; cachedSignUpType auth_0; stripeMembershipType free. Snapshot from 02.09 lacked this refreshToken.
- [fact] That refreshToken is not a WorkOS web session and cannot mint WorkosCursorSessionToken.
- [fact] Two identities must not be collapsed: Bolt SSO userId 380943398 / team 10939257 vs personal Google userId 11908301.
- [fact] Okta Verify v9.4.0 was fresh-installed on the phone 02.09.2026 15:04; enrollment UNKNOWN; adb empty on 04.09; no Windows Okta Verify.
- [fact] Only client-invisible session mint in portal JS is CreateSupportImpersonationSessionInternal (Cursor support). Draft ticket not sent.
- [decision] Highest remaining non-rotation owner action: check Okta Verify enrollment / FastPass on the phone, then P1 password if known, then authorize sending the support impersonation draft. Do not password-reset (NEVER-ROTATE). Do not replay the expired api_key_token.
- relates_to [[research cursor auth recovery 2026-09-03]]
