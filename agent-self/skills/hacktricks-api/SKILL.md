---
name: hacktricks-api
description: Query the HackTricks AI for a synthesized, curated answer when the local
  hacktricks corpus search is not enough. Cached (repeat queries cost nothing) and
  rate-limit-aware (weekly RAG quota). Covers the same broad domains as HackTricks
  — security, cloud, web, network, forensics, AI, and general dev. Prefer the local
  hacktricks skill first; use this to escalate.
license: MIT
permalink: dqverify-repo-20261013/agent-self/skills/hacktricks-api/skill
---

# HackTricks AI API (cached, rate-limited)

Escalation layer over the local `hacktricks` skill. Talks to the HackTricks AI RAG/chat API.
**Always try the local `hacktricks` search first** — this endpoint has a weekly RAG quota.

## Setup (one-time)

Key lives in env `HACKTRICKS_API_KEY` (already set). Never pass it on the command line or print it.
Optional: `HACKTRICKS_CACHE` (default `D:\knowledge\hacktricks\.cache`), `HACKTRICKS_USAGE_FLOOR` (default 2).

## Usage

```
python scripts/htk_query.py usage                      # check remaining weekly quota (free, no spend)
python scripts/htk_query.py rag "AWS IAM privilege escalation" --max-results 5
python scripts/htk_query.py chat "explain SeImpersonate abuse"     # conversational (shares the weekly cap)
```

- `rag` returns the top `results[]` (content + score + filename) plus a `cached` flag.
- Identical `rag` queries are served from a content-hash cache (0 HTTP, 0 quota).
- Before any spend the client checks `GET /rag/usage` and **refuses** if `remaining <= floor` — it tells you
  to use the local `hacktricks` skill instead.
- The API key is read only from the env and is redacted from all output/errors (including HTTP error bodies).

## Notes

- `/chat` shares the same weekly cap and is not cached (conversational); use `rag` for repeatable lookups.
- Content is HackTricks (CC BY-NC-SA) — personal reference only.