Launch the agent-monitor — a live dashboard of Claude Code subagents, including agents running inside Workflows.

Usage: /agent-monitor [--inline] [--spawn]

Shows every Task subagent AND every Workflow agent (each tagged with its `[wf_id]`) for the most
recently active session, with live RUNNING status (by transcript mtime). The header reports total /
running / "in workflows" counts. `--spawn` opens one terminal per agent, each live-tailing it.

Run this Bash command to start it (new window, live --watch dashboard):
```bash
powershell -NoProfile -File "D:/agent-monitor/launch.ps1"
```

Inline (current shell, e.g. for debugging):
```bash
powershell -NoProfile -File "D:/agent-monitor/launch.ps1" -Inline
```

One terminal per agent (tail each running agent):
```bash
powershell -NoProfile -File "D:/agent-monitor/launch.ps1" -Spawn
```

Prerequisites: Python 3 on PATH (the monitor is stdlib-only — no venv needed).
