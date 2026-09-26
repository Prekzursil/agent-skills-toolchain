---
name: Never destroy MCP enabled/disabled state by default
description: User-curated MCP enable/disable lists are intentional and load-bearing
  — never empty, convert, or "schema-fix" them without explicit per-occurrence permission,
  even when a validator complains
type: feedback
originSessionId: 174a3e5e-8ec8-4b41-8953-de3f1a677d12
permalink: main/claude-memory/root/feedback-mcp-enabled-state
---

Never erase, empty, or convert MCP enabled/disabled state without explicit per-occurrence approval. This includes (non-exhaustive):

- `mcpServers` lists/objects inside `projects[<path>]` in `~/.claude.json` (per-project allowlists)
- `enabledMcpjsonServers` / `disabledMcpjsonServers` (per-project)
- `disabledMcpServers` (global plugin disablement, often patched by SessionStart hooks)
- `~/.mcp.json` and any `.mcp.json` walked up from a project directory
- Any plugin manifest's `enabled`/`disabled` flag at user or project scope

**Why:** The user has deliberately curated which MCPs are active so they don't have to manually disable the dozens they don't use. There's a SessionStart hook (`[mcp-defaults] Patched disabledMcpServers ... 71 servers disabled`) plus per-project allowlists, working together. A schema validator warning ("does not adhere to MCP server configuration schema") is *not* license to wipe data — the data may predate the schema or be load-bearing for the user's harness even if Claude Code's validator rejects it.

**How to apply:** Before any change that empties, deletes, or shape-converts these fields:
1. Stop and ASK with `AskUserQuestion`, presenting the exact data at risk and offering at least: (a) preserve verbatim and accept the validator warning, (b) migrate to a schema-compliant shape that preserves all names (e.g., array `["a","b"]` → object `{"a":{}, "b":{}}`), (c) wipe (only with explicit consent).
2. Default to option (a) when in doubt.
3. Always back up the file first; the backup is the only undo.
4. After any change, spot-check that the user's curated names are still present in some form and tell them where.

This rule outranks "schema correctness" — fixing a doctor warning is never worth silently dropping intentional configuration.