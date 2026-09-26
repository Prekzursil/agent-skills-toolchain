---
name: Never destroy MCP enable/disable state without explicit confirmation
description: User-curated MCP server enable/disable lists (per-project and global)
  are intentional and must not be cleared, reset, or "schema-fixed" by default — even
  when a validator flags them
type: feedback
originSessionId: 174a3e5e-8ec8-4b41-8953-de3f1a677d12
permalink: main/claude-memory/root/feedback-mcp-state-preservation
---

Do not clear, reset, or convert-to-empty any of these MCP-related fields without explicit confirmation, even if a schema validator (`/doctor`, lint, etc.) flags them as malformed:

- Top-level `mcpServers` in `~/.claude.json`
- Top-level `mcpServers` in `~/.mcp.json` (or any nested `.mcp.json`)
- `projects[*].mcpServers` (any shape — array of names, object, or other)
- `projects[*].enabledMcpjsonServers`
- `projects[*].disabledMcpjsonServers`
- `projects[*].disabledMcpServers`
- The global `disabledMcpServers` (touched by the SessionStart `mcp-defaults` hook)

**Why:** The user maintains a hand-curated set of enabled vs disabled MCP servers (currently ~28 enabled, ~71 disabled across plugin/built-in/.mcp.json sources). The intent is "set it once, never have to manually disable again." Clearing these lists silently re-enables every server the user previously rejected, breaking that contract. This memory was created after I converted `projects[].mcpServers: [28 names]` to `{}` to satisfy the schema validator on 2026-05-04 — the schema warning was preferable to the data loss.

**How to apply:**
- If a schema validator flags one of these fields, **first ask the user** how to resolve. Offer choices: keep the warning (preserve intent), or migrate the names to a different field that satisfies the schema (e.g., `enabledMcpjsonServers`).
- If editing one of these fields for an unrelated reason (renaming a server, adding a new one), do NOT take the opportunity to "clean up" or normalize the list shape.
- Always make a timestamped backup of `~/.claude.json` and `~/.mcp.json` before touching any MCP-related field.
- The two project keys `C:/Users/Prekzursil` (forward slash) and `C:\Users\Prekzursil\.claude` (backslash) are duplicate project entries Claude Code wrote during a migration — both contain the same enable/disable lists. Treat them as a pair.
- If the user explicitly says "reset disabled list" or similar, that's the green light. Ambiguous "fix the doctor errors" is NOT — clarify which errors first.