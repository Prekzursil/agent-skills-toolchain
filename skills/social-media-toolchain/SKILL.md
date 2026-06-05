---
name: social-media-toolchain
description: "Use when working with the user's personal social-media MCP servers (Instagram, Facebook Messenger, WhatsApp) - which server does what, their auth and setup, the per-platform tool inventory, and the hard limits (E2EE, client-version gotchas, ToS and ban risk)."
---

# Social Media MCP Toolchain

## Overview

The user runs three self-hosted, private-API MCP servers for their own personal accounts. Each lives in `~/source/repos/` with its own `SETUP.md`. All use **private/unofficial APIs**, so each carries **Terms-of-Service and account-ban risk** — keep usage human-paced (especially anything that writes/sends), and never commit credentials. Secrets (cookies, sessions, tokens, `auth_info/`, `*.db`, `.env`) are `.gitignore`d in every repo.

| Platform | Repo (`~/source/repos/`) | Runtime | Auth | Reads | Hard limit |
|---|---|---|---|---|---|
| **Instagram** | `insta-mcp` | Node (JS) | session.json from a 2FA login (`login.mjs`); real password not stored | saved, posts, feed, search, **DMs**, liked, stories | Library spoofs a stale app version → IG `unsupported_version` checkpoint; **fixed** by impersonating the device's current IG app version (`src/index.ts`, env `IG_APP_VERSION`) |
| **FB Messenger** | `fb-messenger-mcp` | Python (venv) | facebook.com **cookies** (`data/cookies.json`, exported via the C3C extension) | **group / room / page** threads + message search | **Personal 1:1 DMs are E2EE** → unreadable by any unofficial API |
| **WhatsApp** | `whatsapp-mcp` | Node (TS, Baileys) | **QR link** (phone → WhatsApp → Linked Devices) | chats, messages, contacts, search; can **send** | Baileys is unofficial → WhatsApp can ban (prefer a secondary number); incoming group history is thin |

## Registering / loading

Each MCP is registered with `claude mcp add <name> -- <command>` (see each repo's `SETUP.md` for the exact command). **MCP tools only load when Claude Code restarts.** When tools are not yet loaded, the same capability can be exercised directly via the repo's scripts (e.g. a Node one-shot against the saved Instagram session).

## Tool inventory (logical names)

- **Instagram** (`insta-mcp`): `get_saved_posts`, `get_recent_posts`, `get_timeline`, `get_discover`, `search_instagram`, `get_liked_posts`, `get_inbox`, `get_direct_messages`, `get_stories`, `get_account_overview`, `get_followers`, `get_following`.
- **FB Messenger** (`fb-messenger`): `whoami`, `list_threads`, `read_thread`, `search_messages`, `thread_info`.
- **WhatsApp** (`whatsapp`): `search_contacts`, `list_chats`, `get_chat`, `list_messages`, `get_message_context`, `search_messages`, `send_message`.
- **Facebook feed / posts / saved** (no API): drive `facebook.com` in the user's logged-in browser (Claude-in-Chrome / Playwright) — there is no FB app on their BlueStacks.

## Operating rules

- **Read before write.** These are the user's real accounts. Never send/post/react without explicit confirmation.
- **Re-auth when sessions expire:** IG → `node login.mjs`; FB → re-export cookies; WhatsApp → re-scan QR.
- **Account safety:** if a platform starts returning checkpoints/challenges, STOP — repeated attempts raise ban risk. Surface it; don't hammer.
- **Related workflow skills:** [[social-find-post]] (locate a post/saved item), [[social-dm-search]] (search messages/chats).
