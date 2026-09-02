---
name: tiktok-public-research
description: Use when the user wants to read PUBLIC TikTok data - trending videos, a creator's public posts or likes, a hashtag feed, a single video's metadata or comments, related videos, or a user search - through the self-hosted tiktok MCP server. Covers the read-only tool inventory, the ms_token and residential-proxy reliability knobs, and the hard limits (no own feed, no saved, no DMs, no posting; unofficial-API ban and IP-block risk).
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

### Reliability — the real constraint (not code, bot-detection)
### Hard limits (state them, never imply otherwise)
### Setup
