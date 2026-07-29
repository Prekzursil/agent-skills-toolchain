---
paths:
  - "**/hooks/**"
  - "**/settings*.json"
  - "**/.claude/**"
---
# Hooks System

## Hook Types

These three are the ones you will reach for most:

- **PreToolUse**: Before tool execution (validation, parameter modification)
- **PostToolUse**: After tool execution (auto-format, checks)
- **Stop**: When session ends (final verification)

They are NOT the whole surface. The shared harness registers **sixteen** events —
`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PermissionDenied`,
`PostToolUse`, `PostToolUseFailure`, `PreCompact`, `PostCompact`, `ConfigChange`,
`SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `TeammateIdle`, `Stop`
(plus `WorktreeCreate` / `WorktreeRemove` on the Claude provider). The authoritative list is
`EVENTS` in `agent-self/harness/registration.py` — read it rather than this prose, which is a
summary and can lag. Entry shape (three nesting levels, no `$FILE_PATH`): see
[web/hooks.md](../web/hooks.md).

## Auto-Accept Permissions

Use with caution:
- Enable for trusted, well-defined plans
- Disable for exploratory work
- Never use dangerously-skip-permissions flag
- Configure `permissions.allow` in `settings.json` instead

## TodoWrite Best Practices

Use TodoWrite tool to:
- Track progress on multi-step tasks
- Verify understanding of instructions
- Enable real-time steering
- Show granular implementation steps

Todo list reveals:
- Out of order steps
- Missing items
- Extra unnecessary items
- Wrong granularity
- Misinterpreted requirements
