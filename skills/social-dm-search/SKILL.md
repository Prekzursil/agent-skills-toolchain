---
name: social-dm-search
description: Use when the user wants to search, read, or recall direct messages and
  chats across Instagram DMs, Facebook Messenger group/room/page threads, or WhatsApp
  chats (proof-of-concept, off by default). Pairs with the social-media-toolchain
  MCPs.
permalink: dqverify-repo-20261013/skills/social-dm-search/skill
---

# Search Social DMs / Chats

## Overview

Find or read messages across the user's connected messaging accounts. Pick the platform(s) the user means; run them in parallel when the target is unknown. See [[social-media-toolchain]] for servers, tools, and limits.

## Instagram DMs (`insta-mcp`)

- `get_inbox` → list DM threads (id, participants, last message).
- `get_direct_messages(thread_id)` → read a thread's history.
- For a keyword across DMs, fetch the inbox then scan threads (no native DM full-text search), or narrow by participant first.

## Facebook Messenger (`fb-messenger`) — groups / rooms / pages ONLY

- `list_threads` → recent threads.
- `read_thread(thread_id)` → message history.
- `search_messages(thread_id, text)` → keyword search within a group thread.
- ⛔ **Personal 1:1 Messenger DMs are end-to-end encrypted and are NOT accessible** here. If the user needs a 1:1 Messenger conversation, the only path is the official Messenger app (driven on-device) — say so plainly; don't pretend the MCP can read it.

## WhatsApp (`whatsapp`) — PROOF-OF-CONCEPT ONLY

⚠️ The WhatsApp MCP is **built but kept as a proof-of-concept** — it is **not registered for routine use**. Do **not** reach for it for a real DM/chat search unless the user explicitly asks to bring the POC online (and accepts the ban-risk to their number). For a normal request, tell the user WhatsApp search is not an active path here.

If it is ever brought online, the capability shape is:
- `list_chats` → recent chats. `search_contacts(query)` → resolve a person.
- `list_messages(chat)` / `get_message_context(message)` → read history around a point.
- `search_messages(query)` → full-text search across stored messages.
- Note: incoming **group** history is thin (Baileys doesn't persist it); 1:1 chats are more reliable. Prefer a **secondary** number if used.

## Workflow

1. Identify platform + person/thread + what they're looking for.
2. Resolve the thread/contact (inbox/list/search-contacts).
3. Read or search that thread; return matches with sender + timestamp + a short quote.
4. If multiple platforms are in scope and the target is unknown, query them in parallel and label results by platform. **Default the fan-out to Instagram DMs + FB Messenger groups/pages only; WhatsApp is POC-only and excluded unless the user explicitly opts in.**

## Guardrails

- **Never send a message** (`send_message`) without explicit, per-message user confirmation of recipient + content.
- Report honestly what was searched (which platforms/threads) vs. not — don't imply exhaustive coverage.
- Stop and surface any checkpoint/ban signal rather than retrying.