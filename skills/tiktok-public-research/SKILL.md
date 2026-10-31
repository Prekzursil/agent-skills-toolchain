---
name: tiktok-public-research
description: Use when the user wants to read PUBLIC TikTok data - trending videos,
  a creator's public posts or likes, a hashtag feed, a single video's metadata or
  comments, related videos, or a user search - through the self-hosted tiktok MCP
  server. Covers the read-only tool inventory, the ms_token and residential-proxy
  reliability knobs, and the hard limits (no own feed, no saved, no DMs, no posting).
permalink: dqverify-repo-20261013/skills/tiktok-public-research/skill
---

# TikTok public-research MCP (`tiktok`)

Read-only access to **public** TikTok data via the self-hosted `tiktok` MCP server
(`~/source/repos/tiktok-mcp`, a FastMCP wrapper over `davidteather/TikTok-Api` 7.3.3).
Same self-hosted ethos as the other social MCPs — but **public-scrape only, no login**.

## Core principle
There is **no authentication**. The server logs into nothing and exposes nothing about
your account. An optional `ms_token` (an anti-bot cookie copied from a logged-in
`tiktok.com` session) and an optional residential proxy only make the *scraper* look less
bot-like — they are **not** credentials and do **not** unlock private data. Everything this
server reads is data any logged-out visitor could see.

## Tools (all read-only, public data)
| Tool | Reads | Notes |
|---|---|---|
| `tiktok_trending(count)` | trending feed | works **keyless**; geo-localized to the egress IP/proxy |
| `tiktok_user_info(username)` | a creator's public profile + stats | needs `ms_token` (keyless 403s) |
| `tiktok_user_posts(username, count)` | a creator's public posts | needs `ms_token` |
| `tiktok_user_liked(username, count)` | a creator's public likes | only if that user made likes public (usually empty) |
| `tiktok_hashtag(tag, count)` | recent videos for a hashtag | needs `ms_token` |
| `tiktok_video_details(url_or_id)` | one video's metadata | URL preferred over numeric id |
| `tiktok_comments(url_or_id, count)` | top-level comments on a video | needs `ms_token` |
| `tiktok_related_videos(url_or_id, count)` | videos TikTok relates to one video | needs `ms_token` |
| `tiktok_search_users(query, count)` | public user accounts by name | **user search only** — 7.x has no generic video search |

`count` is clamped to `[1, 50]`. Errors come back structured (`{error, detail, hint}`),
never as a crash.

## Reliability — the real constraint (not code, bot-detection)
- **`tiktok_trending` works with no setup.** Every other tool typically returns
  `EmptyResponseException` **until an `ms_token` is set** — TikTok bot-walls user/hashtag/
  video/comment endpoints for an unauthenticated scraper. This is expected, not a bug.
- **`TIKTOK_MS_TOKEN`** — copy the `msToken` cookie value from a logged-in `tiktok.com`
  browser session into the gitignored `.env` (or pass via `claude mcp add -e`). Refresh it
  if calls start returning empty. It is a nonce, not a login — but treat it as private
  (gitignored, never logged, never committed).
- **`TIKTOK_PROXY`** (a residential proxy URL) — **required on a datacenter/cloud egress IP**
  (TikTok blocks datacenter IPs almost instantly). **Not needed on a home residential IP.**
  Same rule and same Byteful sticky-RO endpoint used for IG/FB on cloud egress.
- **`TIKTOK_BROWSER`** — `chromium` (default), `webkit`, or `firefox`. A different engine
  sometimes evades detection; webkit alone did **not** fix the keyless user/hashtag block in
  testing, so reach for `ms_token` first.

## Hard limits (state them, never imply otherwise)
- **No own-account data:** your feed, your saved/favorites, your following, your likes — none
  are reachable (there's no session). For your *own* posts/profile use the official Display
  API instead, not this scraper.
- **No DMs** — no unofficial library exposes the TikTok message inbox; do not imply DM search.
- **No writes** — no posting, liking, following, commenting. Read-only by construction.
- **Unofficial-API risk:** heavy scraping from one IP gets that **IP** blocked
  (`EmptyResponseException`); it does **not** ban a TikTok *account* (nothing is logged in).
  Keep usage human-paced.

## Setup
Server: `~/source/repos/tiktok-mcp` (Python 3.12 `.venv`, `TikTokApi` + `mcp[cli]`, Playwright
chromium/webkit installed). Registered user-scope as `tiktok`:
```
claude mcp add tiktok --scope user -e TIKTOK_MS_TOKEN=<msToken> -- ^
  C:\source\repos\tiktok-mcp\.venv\Scripts\python.exe C:\source\repos\tiktok-mcp\server.py
```
Tools load on the next Claude Code restart. Per the toolchain's MCP policy, consider adding
`tiktok` to each project's `disabledMcpServers` and enabling it only where needed (same as the
drug MCPs). Full build/setup detail: `docs/social/TIKTOK-MCP.md`.

Pairs with the broader social MCP reference: [[social-media-toolchain]].