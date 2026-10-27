---
description: Live Claude↔Codex peer channel over mcp_agent_mail (always-on, 127.0.0.1:8812) — register, first-contact handshake, send/fetch messages + advisory file leases. Wraps the multi-ai-mingle skill.
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
