---
title: Grill IDs G-32 G-36 and BM session refresh
type: note
permalink: main/harness/grill-ids-g-32-g-36-and-bm-session-refresh
status: active
valid_as_of: 2026-08-29
tags:
- harness
- grill
- basic-memory
---

# Grill IDs and Basic Memory session refresh

- [fact] G-32 and G-36 are grill bank slot numbers, not a protocol. The prefix G- comes from the skill grill-me-extensive: STRUCTURE writes a decision queue; ONE-AT-A-TIME numbers questions (example: G-7 of 35). The 26-27.08.2026 Fabric/Goose/Cursor grill produced a ~100-question bank. Owner locked 75 answers on 27.08.2026 in Cowork/output/grill-proposed-answers_2026-08-27.md.
- [fact] G-32 was the bank question "Persistent Cursor-bridge mode vs process-local wrappers" (answer: wrappers forever; no ambient auth2api :8317 env). G-36 was "Headless concurrency cap" (answer: one cursor-agent process).
- [bug] Cursor CallDynamicTool to basic-memory returned JSON-RPC -32600 Session not found while GET http://127.0.0.1:8765/mcp was HTTP 406 (healthy) and a fresh initialize returned Basic Memory 4.0.0b1. Root cause: Cursor's HTTP MCP client keeps a stale mcp-session-id after the watchdog restarts :8765.
- [decision] Session not found is not "memory is down." Probe initialize; if the daemon answers, write through a new HTTP session. Cursor merge now points basic-memory at bm_cursor_http_session.py --stdio (refresh session; do not bind :8765; do not add a fifth restarter).
- relates_to [[estate-locks-2026-08-27]]
- relates_to [[WHERE-map pointer]]
See also [[memory-contract]] and [[hosted-model-agents]].
