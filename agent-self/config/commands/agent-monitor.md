Launch the agent-monitor — a friendly desktop UI showing every Claude Code subagent (Task agents AND agents running inside Workflows), so you can pick one and watch its full, verbose, timestamped log live.

Usage: /agent-monitor

Opens a native Tkinter window (zero extra dependencies — Python stdlib only):
  - **Left:** a selectable list of agents for the active session, each tagged with its `[wf_id]`, with a live status — running / working / done / stalled — derived from the TRANSCRIPT (not a fragile mtime cutoff). Defaults to active + recently-finished agents; tick **All history** for the whole session. A **Session** dropdown switches sessions.
  - **Right:** the selected agent's ENTIRE log from creation, RETAINED after it finishes, verbose (full assistant text, full tool calls, full results — oversized results capped inline with the complete text in the saved `.log`), with `HH:MM:SS` timestamps. A formatted copy is persisted under `agent-monitor/logs/<session>/` so logs survive restarts and transcript retries. **Open .log** opens it; **Auto-scroll** toggles follow.

Launch (new window):
```bash
powershell -NoProfile -File "D:/agent-monitor/launch.ps1"
```
Or just **double-click `monitor.cmd`** in the install folder — no CLI needed.

Power-user terminal modes (legacy, optional):
```bash
powershell -NoProfile -File "D:/agent-monitor/launch.ps1" -Watch    # terminal overview dashboard
powershell -NoProfile -File "D:/agent-monitor/launch.ps1" -Spawn    # one tail terminal per agent
```

Prerequisites: Python 3 on PATH (stdlib Tkinter — no venv, no pip).
Source is vendored in this repo at `tools/agent-monitor/`.

Note: this opens a desktop window — it cannot render inside the Claude chat interface.
