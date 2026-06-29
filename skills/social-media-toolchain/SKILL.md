---
name: social-media-toolchain
description: "Use when working with the user's personal social-media MCP servers (Instagram live, Facebook Messenger groups/pages, WhatsApp proof-of-concept, TikTok public read-only) - which server does what, their auth and setup, the per-platform tool inventory, residential-proxy and account-state guidance, and the hard limits (E2EE, client-version gotchas, ToS and ban risk). TikTok is built as a read-only public scraper."
---

# Social Media MCP Toolchain

## Overview

The user has self-hosted, private-API MCP servers for their own personal accounts. Each lives in `~/source/repos/` with its own `SETUP.md`. Status today: **Instagram = live/registered**, **Facebook Messenger = built (groups/rooms/pages only)**, **WhatsApp = built but proof-of-concept ONLY (do not register or use for routine tasks)**. **TikTok = built: a read-only public scraper (trending works keyless, the other tools need an ms_token).** All use **private/unofficial APIs**, so each carries **Terms-of-Service and account-ban risk** — keep usage human-paced (especially anything that writes/sends), and never commit credentials. Secrets (cookies, sessions, tokens, `auth_info/`, `*.db`, `.env`) are `.gitignore`d in every repo.

| Platform | Repo (`~/source/repos/`) | Runtime | Auth | Reads | Status / Hard limit |
|---|---|---|---|---|---|
| **Instagram** | `insta-mcp` | Node (JS) | session.json from a 2FA login (`login.mjs`); real password not stored | saved, posts, feed, search, **DMs**, liked, stories | **LIVE / registered.** Library spoofs a stale app version → IG `unsupported_version` checkpoint; **fixed** by impersonating the device's current IG app version (`src/index.ts`, env `IG_APP_VERSION`) |
| **FB Messenger** | `fb-messenger-mcp` | Python (venv) | facebook.com **cookies** (`data/cookies.json`, exported via the C3C extension) | **group / room / page** threads + message search | **Built (groups/rooms/pages only).** Personal 1:1 DMs are **E2EE** → unreadable by any unofficial API |
| **WhatsApp** | `whatsapp-mcp` | Node (TS, Baileys) | **QR link** (phone → WhatsApp → Linked Devices) | chats, messages, contacts, search; can **send** | **PROOF-OF-CONCEPT ONLY — do NOT register or use for routine tasks.** Built + vetted clean, but kept as a POC: Baileys is unofficial → WhatsApp can ban (would need a secondary number); incoming group history is thin |
| **TikTok** | `tiktok-mcp` | Python (TikTok-Api 7.3.3) | none (public scrape); optional `ms_token` cookie | trending, user info/posts/likes, hashtag, video details/comments/related, user search — read-only | **BUILT — public read-only only.** No own feed, no saved, no DMs, no posting. `trending` keyless; other tools need an `ms_token`. See [[tiktok-public-research]] |

## Registering / loading

Each MCP is registered with `claude mcp add <name> -- <command>` (see each repo's `SETUP.md` and the companion SETUP-GUIDE for the exact command). **MCP tools only load when Claude Code restarts.** When tools are not yet loaded, the same capability can be exercised directly via the repo's scripts (e.g. a Node one-shot against the saved Instagram session).

## Egress: residential proxy + account state

Some setups need a **residential proxy** in front of the IG / FB egress; some do not. The rule is about **where the MCP is running**, not which tool you call:

- **Running locally** (on the user's own residential IP) → **no proxy.** IG/FB see a normal home IP.
- **Running on a cloud / datacenter host** (e.g. an always-on VM) → route IG and FB through the **Byteful sticky-Romania residential proxy** so a datacenter IP does not trigger an instant ban. **WhatsApp goes direct** (tolerant of a cloud IP). The endpoints live (gitignored) at `source/repos/social-mcp-deploy/proxy-endpoints.secret` — never inline or echo the credential string.

**Account-state dimensions that change the setup (social only):**

- **Instagram clean vs FLAGGED.** A flagged account (this one was flagged during the `unsupported_version` work) needs the residential proxy + **minimal call volume** + extra caution: it can re-checkpoint even via the proxy. Keep reads light; avoid bursts; surface any challenge instead of retrying.
- **Facebook personal 1:1 vs groups/pages.** 1:1 Messenger is E2EE and unreadable here; only group / room / page threads are accessible.
- **WhatsApp primary vs secondary number.** POC only — if it were ever used for real, prefer a **secondary** number (ban risk on the primary).
- **Local vs cloud egress.** Drives the proxy decision above.

**Setup details:** see the companion social MCP SETUP-GUIDE (`docs/SETUP-GUIDE.md`) for the per-platform auth, registration commands, proxy wiring, and the cloud-deploy steps. This skill is the quick reference; the SETUP-GUIDE is the runbook.

## Tool inventory (logical names)

- **Instagram** (`insta-mcp`): `get_saved_posts`, `get_recent_posts`, `get_timeline`, `get_discover`, `search_instagram`, `get_liked_posts`, `get_inbox`, `get_direct_messages`, `get_stories`, `get_account_overview`, `get_followers`, `get_following`.
- **FB Messenger** (`fb-messenger`): `whoami`, `list_threads`, `read_thread`, `search_messages`, `thread_info`.
- **WhatsApp** (`whatsapp`) — **POC ONLY, not for routine use:** `search_contacts`, `list_chats`, `get_chat`, `list_messages`, `get_message_context`, `search_messages`, `send_message`. (Built, but do not register/use for real tasks — see the status table.)
- **Facebook feed / posts / saved** (no API): drive `facebook.com` in the user's logged-in browser (Claude-in-Chrome / Playwright) — there is no FB app on their BlueStacks.
- **Facebook Reels posting** (`fb-reels-uploader`, `tools/mcp/fb-reels-uploader/`): a **standalone Playwright script** (NOT yet an MCP) that bulk-uploads local vertical videos to Facebook **as Reels, in order, one per post**. FB's official Graph API can't post to a personal profile, so it drives the browser (`/reels/create/` flow), with persistent-login profile, `.fb-posted.json` resume, and fail-safe ordering. Its README carries a roadmap to promote it into a full MCP mirroring `insta-mcp`'s connector/worker/oracle layering. (A copy also lives in the opus-bulk-downloader repo as a side tool.)
- **TikTok** (`tiktok`) — **BUILT, read-only public scraper:** `tiktok_trending` (keyless), `tiktok_user_info`, `tiktok_user_posts`, `tiktok_user_liked`, `tiktok_hashtag`, `tiktok_video_details`, `tiktok_comments`, `tiktok_related_videos`, `tiktok_search_users`. All public + read-only. The non-trending tools need an `ms_token` (anti-bot cookie); `TIKTOK_PROXY` only on cloud egress. **No own feed, no saved, no DMs, no posting.** Full reference: [[tiktok-public-research]].

## Operating rules

- **Read before write.** These are the user's real accounts. Never send/post/react without explicit confirmation.
- **Re-auth when sessions expire:** IG → `node login.mjs`; FB → re-export cookies; WhatsApp → re-scan QR.
- **Account safety:** if a platform starts returning checkpoints/challenges, STOP — repeated attempts raise ban risk. Surface it; don't hammer.
- **Egress + flagged-account discipline:** on a cloud host, route IG/FB via the residential proxy (WhatsApp direct); on a flagged IG account keep calls minimal and never hammer a checkpoint. See the "Egress: residential proxy + account state" section and the SETUP-GUIDE.
- **Related skills:** [[social-find-post]] (locate a post/saved item), [[social-dm-search]] (search messages/chats), [[tiktok-public-research]] (read public TikTok data).
