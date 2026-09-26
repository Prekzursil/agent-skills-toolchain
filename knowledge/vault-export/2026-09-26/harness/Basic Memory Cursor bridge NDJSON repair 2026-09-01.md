---
title: Basic Memory Cursor bridge NDJSON repair 2026-09-01
type: note
permalink: main/harness/basic-memory-cursor-bridge-ndjson-repair-2026-09-01
valid_as_of: '2026-09-02'
status: superseded
tags:
- basic-memory
- cursor
- mcp
- repair
superseded_by: '[[Basic Memory Cursor bridge resilient repair 2026-09-02]]'
---

- [bug] Cursor Basic Memory discovery failed because bm_cursor_http_session.py used LSP Content-Length framing instead of MCP newline-delimited JSON-RPC.
- [fact] The daemon remained healthy at http://127.0.0.1:8765/mcp; TCP and MCP initialize both succeeded on 01.09.2026.
- [decision] The bridge now emits NDJSON and retains legacy Content-Length input compatibility; framing tests and an end-to-end tools/list probe pass.
- [fact] The repaired bridge exposes 21 Basic Memory tools including search_notes and write_note.
- relates_to [[Memory contract SSOT]]
- relates_to [[Cursor MCP integration]]

- superseded_by [[Basic Memory Cursor bridge resilient repair 2026-09-02]]