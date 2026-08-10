---
name: social-media-toolchain
description: "Use when working with the user's personal social-media MCP servers (Instagram live, Facebook Messenger groups/pages, WhatsApp proof-of-concept, TikTok public read-only) - which server does what, their auth and setup, the per-platform tool inventory, residential-proxy and account-state guidance, and the hard limits (E2EE, client-version gotchas, ToS and ban risk). TikTok is built as a read-only public scraper."
---

# Social Media MCP Toolchain

## Overview

The user has self-hosted, private-API MCP servers for their own personal accounts. Each lives in `~/source/repos/` with its own `SETUP.md`. Status today: **Instagram = live/registered**, **Facebook = live/expanded (Messenger incl. E2EE DMs + Page + IG-Graph, 33 tools)**, **WhatsApp = built but proof-of-concept ONLY (do not register or use for routine tasks)**. **TikTok = built: a read-only public scraper (trending works keyless, the other tools need an ms_token).** All use **private/unofficial APIs**, so each carries **Terms-of-Service and account-ban risk** — keep usage human-paced (especially anything that writes/sends), and never commit credentials. Secrets (cookies, sessions, tokens, `auth_info/`, `*.db`, `.env`) are `.gitignore`d in every repo.

| Platform | Repo (`~/source/repos/`) | Runtime | Auth | Reads | Status / Hard limit |
|---|---|---|---|---|---|
| **Instagram** | `insta-mcp` | Node (JS) | session.json from a 2FA login (`login.mjs`); real password not stored | saved, posts, feed, search, **DMs**, liked, stories | **LIVE / registered.** Library spoofs a stale app version → IG `unsupported_version` checkpoint; **fixed** by impersonating the device's current IG app version (`src/index.ts`, env `IG_APP_VERSION`) |
| **Facebook** (Messenger + Page + IG-Graph) | `fb-messenger-mcp` | Python (venv) | facebook.com **cookies** (`data/cookies.json`, C3C export; **+ `fr` cookie** for E2EE) + optional `FB_PAGE_ACCESS_TOKEN` | Messenger (groups/rooms + **E2EE 1:1 DMs**), Page posts/insights/moderation, IG-Graph (business IG) | **LIVE / expanded to 33 tools.** E2EE personal DMs now readable via the fbchat-v2 bridge (needs the `fr` cookie); FB has no personal-profile post API → personal Reels via the Playwright `fbreels` path |

### Registering / loading
### Egress: residential proxy + account state
### Tool inventory (logical names)
### Operating rules
