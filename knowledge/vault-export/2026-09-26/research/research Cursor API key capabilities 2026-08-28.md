---
title: research Cursor API key capabilities 2026-08-28
type: report
permalink: main/research/research-cursor-api-key-capabilities-2026-08-28
tags:
- research-report
- high
- firecrawl
- context7
- cursor-api
---

type: report
status: active
valid_as_of: 2026-08-28

# research Cursor API key capabilities 2026-08-28

- [fact] A dashboard `crsr_` API key is an agent/CLI/SDK credential, not an OpenAI chat-completions key and not a `type:web` dashboard login.
- [fact] Minting a key requires the interactive dashboard; the key does not restore a dead web session. `/auth/exchange_user_api_key` mints only `type:session` JWTs.
- [fact] User keys (Cloud Agents API, `agent` CLI, `@cursor/sdk`, Notion) vs Admin keys (`admin:*` for Admin/Analytics/AI-code-tracking/Bugbot) vs Enterprise service-account keys (team-pool Cloud Agents/CLI). SDK rejects Team Admin keys.
- [fact] Origin uses a different credential family (Ed25519 app JWT → `oit_` installation tokens), not `crsr_`.
- [fact] This Bolt identity is `isTeamAdmin: false`; realistic official wins if a user key can be minted: Cloud Agents + CLI + SDK + Notion. Admin APIs would 403. Chicken-egg: web SSO login still required to mint.
- [decision] Keep auth2api `:8317` on app/PKCE session. Do not treat a user API key as a drop-in for `api2.cursor.sh` (raw key 401s).
- relates_to [[Cursor session-persistence 2026-08-27]]
- relates_to [[Cursor sign-in longevity 2026-08-27]]
- relates_to [[auth2api]]

Full inventory: `C:\Users\Prekzursil\Cowork\output\cursor-api-key-capability-inventory_2026-08-28.md`
See also [[CURSOR-SESSION-KNOWLEDGE]].
