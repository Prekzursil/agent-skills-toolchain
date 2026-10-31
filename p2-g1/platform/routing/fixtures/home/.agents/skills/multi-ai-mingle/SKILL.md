---
name: multi-ai-mingle
description: Use when the user wants seamless local collaboration between Claude Code and OpenAI Codex on the same machine - fanning out parallel Codex coding threads from Claude as native MCP tool calls via the official codex mcp-server, and running a live symmetric two-way chat and file-lease channel between the two agents through mcp_agent_mail. Covers mounting codex-as-MCP at user scope, standing up the shared agent-mail http channel, verifying it before use, and the sequenced adoption waves. Triggers include mingle Claude and Codex, run Codex from Claude in parallel, set up the agent mail channel, replace AgentBridge, or coordinate the two local AI agents. Not for single-agent work or remote or cloud multi-agent orchestration.
---

# multi-ai-mingle

Seamless LOCAL mingling of Claude Code and OpenAI Codex on one Windows 11 machine. Two
complementary rails:

- **Fan-out rail (Claude drives Codex):** the official `codex mcp-server` (stdio) mounted into
  Claude at user scope. Claude subagents call `mcp__codex__codex` / `mcp__codex__codex_reply` as
  native tools, so one Claude orchestrator can run several parallel Codex coding threads.
- **Live channel rail (peer chat + coordination):** `mcp_agent_mail` (2k-star, maintained;
  FastMCP + Git + SQLite) as a shared http server both agents connect to — symmetric inboxes,
  threads, and advisory file leases. This replaces the Windows-broken AgentBridge.

Keep the two rails distinct: fan-out is command-and-control (Claude tasks Codex); the channel is
peer messaging + file-lease coordination that either side reads and writes.

## When to use
- The user wants Claude and Codex to collaborate locally, in parallel, with a real back-channel.
- The user asks to "run Codex from Claude", "set up the agent-mail channel", or "replace AgentBridge".

## When NOT to use
- Single-agent tasks (just use Claude, or Codex, directly).
- Remote / cloud multi-agent fleets (different tooling).

---

## Real mcp_agent_mail API sequence (VERIFIED 2026-07-11 — the prep draft under-specified this)
The channel is not "just send_message". The working order, proven by the verify probe on Windows:
1. `ensure_project(human_key=<abs path>)` FIRST — creates the namespace. (The **other** tools take

### Wave A — mount + channel (STATUS: DONE + VERIFIED 2026-07-11)
### Wave B — teammate shim (LATER)
### Wave C — GUI tab (LATER)
### Wave D — upstream contribution (LATER)
### Files in this skill
### Guardrails
### License + adoption posture (owner directive 2026-07-11)
