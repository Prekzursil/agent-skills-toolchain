---
title: Codex use_agent_identity pinned false 2026-09-07
type: note
permalink: main/notes/codex-use-agent-identity-pinned-false-2026-09-07
status: active
valid_as_of: '2026-09-07'
---

- [fact] Codex CLI 0.153.4 with `use_agent_identity=true` hard-fails TUI turns: `agent identity registration failed for https://auth.openai.com/api/accounts/v1/agent/register` (`codex_error_info: other`). Evidence: `~/.codex/sessions/2026/09/07/rollout-2026-09-07T21-13-16-01a07d13-0e6f-7a43-9806-d24bf804e810.jsonl`.
- [fact] `codex login status` was already ChatGPT-healthy; `auth.json` not wiped; no credential rotation.
- [decision] Pin `[features].use_agent_identity = false` (default for this under-development flag). Feature does not work on this ChatGPT login + 0.153.4 pair.
- [fact] MCP remap kept: McpHub `http://127.0.0.1:24680/sse` + headers (no mcp-remote); CS hubs 311xx; BM :18765; mail :18812.
- Receipt: `C:\Users\Prekzursil\Cowork\output\codex-agent-identity-register_2026-09-07.md`
- Backup: `~/.codex/config.toml.bak-agent-identity-20260907`
- relates_to [[Codex CLI max-power]]
- See also [[WHERE-map pointer]]