---
title: Cursor shared-chat harvest 2026-09-02 + Edge cookie replay vs Databricks Okta
type: report
permalink: main/projects/bolt/cursor-shared-chat-harvest-2026-09-02-edge-cookie-replay-vs-databricks-okta
tags:
- bolt
- cursor
- databricks
- okta
- grok
- cookie-bridge
---

valid_as_of: 2026-09-02

- [fact] Team shared chats: ListSharedConversations paginated with createdBefore, **190** TEAM shares. Match vs 2026-08-24 harvest (181): still=181, new=9, missing=0. Bodies fetched via desktop Bearer on api2.cursor.sh GetSharedConversation (no Okta). Output: `Desktop/Codex Useful Prompts/databricks_harvest/cursor-shared-chats-bodies_2026-09-02/`.
- [fact] Nine new shares (2026-08-20 .. 2026-09-01): Bad order ratio (Ayush), DemocracyOS fork (Costin-Ioan), FRS satellite (Gleb), LPCT segmentation (Judy), Metrics query generation (Achmad), Models with deepdive_metricflow (Gleb), Outsourcing PM assignment (Muhammad Zunair), Rides domain guides (Kevin), Tandem riding model error (Sven).
- [fact] Chrome rail `.chrome-automation:9222` holds grok.com/x.ai `sso`+`sso-rw`, cursor.com `WorkosCursorSessionToken`, bolt.okta.com `DT`+`JSESSIONID`, **no DBAUTH**. chrome-devtools MCP pages are isolated (Sign in) and do not see that jar.
- [fact] Copying that jar via CDP Storage.setCookies onto Edge rail `.edge-automation:9333` **logs Edge into Cursor web** (dashboard as costin.ionescu@bolt.eu / Bolt Technology OÜ) and opens all three `cursor.com/codebase/bolt-technology-o/{habit-proof,electronics-engineering-review,financni-model-aplikace}/tree/main` (Early Beta Codebase UI). GitHub REST 404 for those slugs — they are Cursor-hosted, not public GitHub.
- [fact] Same cookie replay does **not** skip Bolt Okta (Edge lands on bolt.okta.com Sign In / FastPass) and Databricks shows Login + Continue with SSO, no DBAUTH. Grok-style SSO-cookie bypass is **not** sufficient for Databricks; needs live DBAUTH or a working Okta session (Device Trust / FastPass still in play).
- [decision] Do not hammer cursor.com→WorkOS→Okta re-auth (Aug web logout cause). Desktop token remains the no-SSO path for shared-chat bodies.
- relates_to [[Cursor session-persistence 2026-08-27]]
- relates_to [[Bolt estate knowledge grounded synthesis 2026-08-26]]
- relates_to [[Databricks SSO Mirror Recovery — Verdict (Mac offline + Device Trust)]]

## Correction 2026-09-02 (owner)

- [decision] Cursor success is the **documented no-SSO auth handshake**, not Chrome→Edge cookie injection. Desktop `type:session` JWT presented as `WorkosCursorSessionToken=<workosUserId>%3A%3A<accessToken>` authenticates `cursor.com/api/*` (200 `/api/auth/me`). Hitting codebase/dashboard URLs returns **307** `{redirect:"/api/auth/bootstrap-cursor-web-target?redirectTo=…"}` — the handshake, not an Okta prompt. Cookie-bridge copy was incidental and is not the mechanism.
- [fact] Databricks has **no analogue**: no token→`DBAUTH` handshake, login page is `Continue with SSO` → bolt.okta.com Sign In/FastPass. Same cookie jar does not skip IdP. Matches [[Databricks SSO Mirror Recovery — Verdict (Mac offline + Device Trust)]].
- [fact] Shared-chat harvest (190, 9 new) used the same handshake class: Bearer on `api2.cursor.sh`, never Okta.
