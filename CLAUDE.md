## Multi-Agent Collaboration — RETIRED (AgentBridge is gone)

**AgentBridge is retired.** Its budget-pacing tools (`get_budget` / `check_budget`), the
`reply` / `get_messages` bridge, and the `system_budget_pause` / `system_budget_handoff`
directives no longer exist — ignore any instruction (here or elsewhere) to use them.

The canonical Codex ↔ Claude collaboration model now lives in the user's global
**`~/.claude/CLAUDE.md`** (see its "Multi-AI Collaboration" section), on two rails:

- **Layer 1 — fan-out:** the official `codex mcp-server`, mounted at user scope and called as
  native `mcp__codex__codex` / `mcp__codex__codex_reply` tools — spawn parallel Codex coding
  threads from Claude; results return as native tool results.
- **Layer 2 — live channel:** `mcp_agent_mail`, the always-on peer-chat + advisory file-lease
  server on `127.0.0.1:8812` (`/api/health` → `{"status":"ok"}`), wrapped by the
  `multi-ai-mingle` skill.

Refer to that global doc for the authoritative setup, rails, budget guidance, and troubleshooting.
