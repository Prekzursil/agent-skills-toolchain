---
description: Live Claude↔Codex peer channel over mcp_agent_mail (always-on, 127.0.0.1:8812)
  — register, first-contact handshake, send/fetch messages + advisory file leases.
  Wraps the multi-ai-mingle skill.
permalink: dqverify-repo-20261013/commands/multi-ai-mingle
---

# multi-ai-mingle — local Claude↔Codex live channel

Open/use the shared **agent-mail** HTTP channel (kept always-on by the
`MCPAgentMailSupervisor` task on `127.0.0.1:8812`) for real-time peer messaging and
advisory file-lease coordination between Claude and Codex. This is the peer-chat rail
(Rail 2); the Codex fan-out rail (Rail 1, `mcp__codex__codex`) is separate.

## Usage

```
/multi-ai-mingle [hello | send <msg> | inbox | lease <path> | <free-form intent>]
```

- `hello` — run the verify-then-hello handshake probe (health_check → ensure_project →
  register → contact handshake → a test message round-trip).
- `send <msg>` / `inbox` / `lease <path>` — send a message, drain the inbox, or take an
  advisory file lease.
- No/other args → surface channel status and the mingle options.

$ARGUMENTS

## What to Do

Invoke the **`multi-ai-mingle`** skill (via the Skill tool), passing `$ARGUMENTS` as the
intent. Follow the skill's verified API sequence exactly — the agent-mail tools are live
MCP tools (`mcp__agent-mail__*`):

1. `health_check` — confirm the server answers (expect `status:ok`).
2. `ensure_project(human_key=<abs path>)` FIRST — creates the namespace.
3. `register_agent(project_key, program=<role>, model)` — **bare `claude`/`codex` are
   rejected**; capture the server-assigned codename AND the `registration_token`.
4. First contact is gated: `request_contact` then `respond_contact(accept=true)`.
5. Then `send_message(sender_name, sender_token, to=[...])` / `fetch_inbox(agent_name,
   registration_token)` / `file_reservation_paths(...)` — each call carries the agent's token.

## Notes

- One shared `serve-http` on `127.0.0.1:8812` (canonical port; 8765 = basic-memory — never collide).
- If health_check fails: `Start-ScheduledTask -TaskName MCPAgentMailSupervisor` re-spawns it within ~10s.
- **Portability caveat:** the live-channel MCP is fully wired only from the home dir until
  `promote-mcp-userscope.ps1` runs with Claude closed (user-scope registration otherwise
  points at the stale 8811). Rail 1 (codex fan-out) is user-scope and works everywhere.

## Related

- Skill: `skills/multi-ai-mingle/SKILL.md` — the two rails, the verified API, guardrails.
- `/codex-monitor` — live dashboard of Codex fan-out threads (Rail 1 observability).