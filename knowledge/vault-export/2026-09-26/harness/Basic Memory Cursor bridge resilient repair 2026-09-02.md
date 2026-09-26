---
title: Basic Memory Cursor bridge resilient repair 2026-09-02
type: note
permalink: main/harness/basic-memory-cursor-bridge-resilient-repair-2026-09-02
valid_as_of: '2026-09-02'
status: active
tags:
- basic-memory
- cursor
- mcp
- repair
- tdd
---

- [bug] Cursor Basic Memory MCP stdio bridge used LSP Content-Length output framing; Cursor expects MCP newline-delimited JSON-RPC.
- [fact] The repaired bridge emits NDJSON, accepts NDJSON and legacy Content-Length input, validates message objects and lengths, returns JSON-RPC errors for malformed input, and survives transient HTTP transport errors.
- [fact] Twelve canonical framing, refresh, and resilience tests pass; pytest collection, Ruff, and strict mypy pass.
- [fact] End-to-end initialize and tools/list expose 21 Basic Memory tools, including search_notes and write_note.
- [fact] A real write_note followed by hybrid search_notes returned the repair note as the top result.
- [decision] Keep the shared Basic Memory daemon at http://127.0.0.1:8765/mcp; never spawn a duplicate daemon or disable semantic search.
- [decision] Cursor sessions must reload MCP configuration after bridge repair because the current session tool catalog does not hot-load missing namespaces.
- relates_to [[Basic Memory Cursor bridge NDJSON repair 2026-09-01]]
- relates_to [[Memory contract SSOT]]
- relates_to [[Cursor MCP integration]]