---
title: research Cursor effort restrictions vs user API key 2026-08-28
type: report
permalink: main/research/research-cursor-effort-restrictions-vs-user-api-key-2026-08-28
status: active
valid_as_of: '2026-08-28'
---

# research Cursor effort restrictions vs user API key 2026-08-28

- [fact] User key `CURSOR_API_TOKEN` (dashboard name Cursor) cannot read or write team Model Access. Live GET/PUT `/teams/model-access/*` → 401 Invalid Team API Key; org PUTs → 401 Invalid Organization API Key.
- [fact] There is no personal settings HTTP API on this key. `/v1/settings`, `/v1/me/settings`, `/v1/preferences`, `PATCH /v1/me` → 404. `GET /v1/me` is identity only.
- [fact] Effort/reasoning *policy* (`allowedValues`) is Team Admin / Org only (`models:*` or `admin:*`). Writes audit as `team_settings`.
- [fact] Cloud Agents/SDK can pass per-run `model.params` from `GET /v1/models`. This key's catalog includes grok-4.6 effort xhigh (default xhigh), gpt-5.6-terra xhigh, gpt-5.6-luna xhigh+max. Claude Fable 5 / Opus 5 effort stops at high.
- [fact] Omitting `model` on create-agent resolves user default → team default → system default (docs). Team policy can still apply when model is omitted.
- [fact] Catalog listing xhigh/max is not proof of a team-policy bypass. Runtime 400/403 on POST /v1/agents was not fired.
- [decision] Do not create a Cloud Agent solely to test xhigh vs Bolt allowedValues unless the owner asks (spend).
- relates_to [[research CURSOR_API_TOKEN full options tree 2026-08-28]]
- relates_to [[research Cursor API key capabilities 2026-08-28]]

Receipt: `C:/Users/Prekzursil/Cowork/output/cursor-effort-restrictions-api_2026-08-28.md`