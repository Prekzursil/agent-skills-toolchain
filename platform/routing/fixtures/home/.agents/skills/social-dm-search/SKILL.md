---
name: social-dm-search
description: "Use when the user wants to search, read, or recall direct messages and chats across Instagram DMs, Facebook Messenger group/room/page threads, or WhatsApp chats (proof-of-concept, off by default). Pairs with the social-media-toolchain MCPs."
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

### Workflow
### Guardrails
