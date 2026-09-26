---
name: agent-monitor-tool
description: D:\agent-monitor — realtime per-terminal monitor for Claude Code Task
  subagents; plus where Claude Code stores subagent transcripts
metadata:
  node_type: memory
  type: reference
  originSessionId: 5cba01b0-b7c2-4f65-96a6-d44199963f4c
permalink: main/claude-memory/root/agent-monitor-tool
---

Realtime monitor for Claude Code **Task subagents** (the inline TUI agent list glitches; user wanted one-agent-per-terminal). Lives at **D:\agent-monitor\** (stdlib-only Python, read-only):

- `agent_monitor.py` — auto-detects active session, dashboard (`--watch`) + spawner (`--spawn`, one terminal per running agent). Flags: `--all`, `--tabs`, `--no-wt`, `--dir`, `--session`, `--active-secs` (default 150), `--interval`.
- `agent_tail.py <agent-*.jsonl>` — live colored one-line-per-event feed (🔧 tool / ↳ result / 📝 text / 💭 thinking). Flags: `--backfill`, `--poll`, `--idle`, `--width`.
- `monitor.cmd` (double-click) and `Monitor-Agents.ps1` (`-All/-Tabs/-DashboardOnly/-SpawnOnly`) launchers.

**Where Claude Code stores subagents (non-obvious):** NOT inline in the parent session JSONL (that has zero sidechain entries). Each subagent is its own append-only transcript:
`~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl` + sidecar `agent-<id>.meta.json` = `{agentType, description, name, toolUseId}`. Entries are normal CC messages: `message.content` blocks of type text/thinking/tool_use/tool_result, ISO-UTC `timestamp`.
- "RUNNING" = `.jsonl` **mtime recency** (append-only, flushed live); active session = subagents dir with newest agent-*.jsonl.

**Windows gotchas baked in (apply to any console tool here):** (1) enable VT via `SetConsoleMode(...|0x4)` for ANSI color; (2) `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` or emoji/box-draw glyphs crash on the default cp1252. Spawns own window per agent via `wt.exe` else `subprocess.CREATE_NEW_CONSOLE` (never `shell=True` — semgrep PostToolUse hook blocks it; see [[bcsfe_save_roundtrip]] sibling tooling). System python here = `C:\Python314\python.exe`.