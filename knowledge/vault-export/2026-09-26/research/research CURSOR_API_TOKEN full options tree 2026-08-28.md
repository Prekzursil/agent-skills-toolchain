---
title: research CURSOR_API_TOKEN full options tree 2026-08-28
type: report
permalink: main/research/research-cursor-api-token-full-options-tree-2026-08-28
tags:
- research-report
- cursor-api
- high
---

type: report
status: active
valid_as_of: 2026-08-28

# research CURSOR_API_TOKEN full options tree 2026-08-28

- [fact] `CURSOR_API_TOKEN` **is** the dashboard-minted user key named Cursor (created 2026-07-25, userId 380943398). There is no second dashboard key in env.
- [fact] Live 200: `/v1/me`, `/v1/models` (36 ids), `/v1/agents` (5 IDLE), runs, usage (~$11.06 on one agent), artifacts list, `/v0/agents`, `/v1/repositories`.
- [fact] POST `/v1/agents` `{}` returned 400 Required (authorized to create). POST `/v1/sub-tokens` 403 service_account_required. Chat completions/messages/responses 404.
- [fact] Admin/analytics/bugbot/org all 401 Invalid Team/Organization API Key on this user key.
- [fact] Stock CLI/SDK read `CURSOR_API_KEY`, which is unset; this box has TOKEN in Process+User+Machine.
- relates_to [[research Cursor API key capabilities 2026-08-28]]
- relates_to [[auth2api]]

Disk: `C:\Users\Prekzursil\Cowork\output\cursor-api-token-options-tree_2026-08-28.md`
