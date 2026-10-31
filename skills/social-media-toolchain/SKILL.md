---
name: social-media-toolchain
description: Use when working with the user's personal social-media MCP servers (Instagram
  live, Facebook Messenger groups/pages, WhatsApp proof-of-concept, TikTok public
  read-only) - which server does what, their auth and setup, the per-platform tool
  inventory, residential-proxy and account-state guidance, and the hard limits (E2EE,
  client-version gotchas, ToS and ban risk).
permalink: dqverify-repo-20261013/skills/social-media-toolchain/skill
---

# Social Media MCP Toolchain

## Overview

The user has self-hosted, private-API MCP servers for their own personal accounts. Each lives in `~/source/repos/` with its own `SETUP.md`. Status today: **Instagram = DORMANT — session-only heritage, no credentials, do NOT disturb the account (see the Instagram row)**, **Facebook = live/expanded (Messenger incl. E2EE DMs + Page + IG-Graph, 33 tools)**, **WhatsApp = built but proof-of-concept ONLY (do not register or use for routine tasks)**. **TikTok = built: a read-only public scraper (trending works keyless, the other tools need an ms_token).** All use **private/unofficial APIs**, so each carries **Terms-of-Service and account-ban risk** — keep usage human-paced (especially anything that writes/sends), and never commit credentials. Secrets (cookies, sessions, tokens, `auth_info/`, `*.db`, `.env`) are `.gitignore`d in every repo.

| Platform | Repo (`~/source/repos/`) | Runtime | Auth | Reads | Status / Hard limit |
|---|---|---|---|---|---|
| **Instagram** | `insta-mcp` | Node (JS) | session.json from a 2FA login (`login.mjs`); real password not stored | saved, posts, feed, search, **DMs**, liked, stories | **DORMANT — session-only heritage (2026-09-30).** The saved session is the ONLY credential that exists; the account must not be disturbed (no re-login, no logout, no unwiring). **NEVER start/re-register insta-mcp for this account** unless the `auth.ts` session-only guard is in place; **NEVER run `login.mjs` / `challenge_flow.mjs` / `stage*_challenge.mjs` / `retry_version.mjs` / `diag_checkpoint.mjs`** for it (all password-dependent dead ends). Any request must first re-pin `IG_APP_VERSION`/`IG_APP_VERSION_CODE` to the phone's current app version. Playbook + kill switches: `D:\ig-rotate\docs\research-2026-09-30.md` |
| **Facebook** (Messenger + Page + IG-Graph) | `fb-messenger-mcp` | Python (venv) | facebook.com **cookies** (`data/cookies.json`, C3C export; **+ `fr` cookie** for E2EE) + optional `FB_PAGE_ACCESS_TOKEN` | Messenger (groups/rooms + **E2EE 1:1 DMs**), Page posts/insights/moderation, IG-Graph (business IG) | **LIVE / expanded to 33 tools.** E2EE personal DMs now readable via the fbchat-v2 bridge (needs the `fr` cookie); FB has no personal-profile post API → personal Reels via the Playwright `fbreels` path |
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

- **Instagram** (`insta-mcp`): `get_saved_posts`, `get_recent_posts`, `get_timeline`, `get_discover`, `search_instagram`, `get_liked_posts`, `get_inbox`, `get_direct_messages`, `get_stories`, `get_account_overview`, `get_followers`, `get_following` (+ `upload_reel`/`upload_photo`/`upload_video`/`upload_album`, `send_direct_message`, `follow_user`/`unfollow_user`, `like_post`/`add_comment`, `get_post_insights`, `get_highlights`, `get_tag_feed`, `edit_profile`, `set_privacy` — 36 total).
  - **Two IG paths (best-of-both, no collision):** the `insta-mcp` tools above are for a **personal** account (private API, ToS-risky). For a **business/creator** IG account linked to a FB Page, use the official Graph API path on the `fb` backend — `ig_graph_publish` / `ig_graph_insights` / `ig_graph_moderate_comments` (durable, official; needs `FB_PAGE_ACCESS_TOKEN`). Distinct names → both always exposed; **pick by account type**, don't remove either.
- **Facebook** (`fb-messenger`, 33 tools): **Messenger** `whoami`/`list_threads`/`read_thread`/`thread_info`/`search_messages`/`fb_send_message`/`fb_send_file`/`fb_react_to_message`/`fb_unsend_message`/`fb_forward_message`/`fb_mark_read`/`fb_send_typing`/`fb_create_group`; **E2EE 1:1 DMs** `fb_dm_list`/`fb_dm_read`/`fb_dm_send`/`fb_dm_react`/`fb_dm_status` (needs the `fr` cookie, via the fbchat-v2 bridge); **Page** `fb_page_post`/`fb_page_schedule_post`/`fb_page_upload_photo`·`video`·`reel`·`story`/`fb_page_read_posts`·`read_comments`/`fb_page_moderate`/`fb_page_insights`/`fb_page_message`/`fb_graph_token_info`; **IG-Graph (business/creator IG)** `ig_graph_publish`/`ig_graph_insights`/`ig_graph_moderate_comments`.
- **WhatsApp** (`whatsapp`) — **POC ONLY, not for routine use:** `search_contacts`, `list_chats`, `get_chat`, `list_messages`, `get_message_context`, `search_messages`, `send_message`. (Built, but do not register/use for real tasks — see the status table.)
- **Facebook feed / posts / saved** (no API): drive `facebook.com` in the user's logged-in browser (Claude-in-Chrome / Playwright) — there is no FB app on their BlueStacks.
- **Facebook Reels posting** (`fb-reels-uploader`, `tools/mcp/fb-reels-uploader/`): now an **MCP backend** (`fbreels` in social-hub) wrapping the Playwright uploader — `fb_upload_reel`, `fb_upload_reels_from_folder`, `fb_reels_status`. Bulk-uploads local vertical videos to Facebook **as Reels, in order, one per post**. FB's official Graph API can't post to a personal profile, so it drives the browser (`/reels/create/` flow) with a persistent-login profile, `.fb-posted.json` resume, and fail-safe ordering; a **one-time human FB login** primes the profile, after which the tools run headless + non-blocking (return a `jobId`; poll `fb_reels_status(jobId)`). (A copy also lives in the opus-bulk-downloader repo.)
- **TikTok** (`tiktok`) — **BUILT, read-only public scraper:** `tiktok_trending` (keyless), `tiktok_user_info`, `tiktok_user_posts`, `tiktok_user_liked`, `tiktok_hashtag`, `tiktok_video_details`, `tiktok_comments`, `tiktok_related_videos`, `tiktok_search_users`. All public + read-only. The non-trending tools need an `ms_token` (anti-bot cookie); `TIKTOK_PROXY` only on cloud egress. **No own feed, no saved, no DMs, no posting.** Full reference: [[tiktok-public-research]].

## Operating rules

- **Read before write.** These are the user's real accounts. Never send/post/react without explicit confirmation.
- **Re-auth when sessions expire:** IG → `node login.mjs`; FB → re-export cookies; WhatsApp → re-scan QR.
- **Account safety:** if a platform starts returning checkpoints/challenges, STOP — repeated attempts raise ban risk. Surface it; don't hammer.
- **Egress + flagged-account discipline:** on a cloud host, route IG/FB via the residential proxy (WhatsApp direct); on a flagged IG account keep calls minimal and never hammer a checkpoint. See the "Egress: residential proxy + account state" section and the SETUP-GUIDE.
- **Related skills:** [[social-find-post]] (locate a post/saved item), [[social-dm-search]] (search messages/chats), [[tiktok-public-research]] (read public TikTok data).