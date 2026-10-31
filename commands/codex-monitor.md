---
title: codex-monitor
type: note
permalink: dqverify-repo-20261013/commands/codex-monitor
---

Launch the codex-monitor — a live dashboard of OpenAI Codex threads (the Codex-side counterpart to /agent-monitor, which shows Claude Code subagents).

Usage: /codex-monitor [--once] [--since-min N] [--idle N] [--max-threads N] [--width N]

Shows every recent Codex thread — from native `mcp__codex__codex` fan-out, `codex exec`, or an interactive TUI session — with its prompt, live tool-call / command-execution list, running elapsed + idle timers, token usage (+ context-window %), turn count, and typed status (running / idle / done / aborted). It merges two sources: Codex rollouts (`~/.codex/sessions/.../rollout-*.jsonl`) and Component-A relay stream files (`%TEMP%\codex-streams\*.jsonl`). Read-only — it never launches, steers, or kills Codex, so it is safe to leave running while a Workflow fans out Codex threads.

This is the **monitorcore** codex board (`mon codexmon`, PR-B3), fronted by a single-instance guard so repeated launches do not accumulate orphaned boards (a real incident on 2026-07-18: three orphaned monitors resident on a RAM-tight box). The guard also reaps strays, including the retired mingle-era monitor.

Run this Bash command to open the board (new console window, live self-refreshing):
```bash
powershell -NoProfile -File "C:/Users/Prekzursil/.local/bin/codexmon.ps1" --since-min 120
```

One frame then exit (piping / a quick programmatic check — renders inline, no window):
```bash
powershell -NoProfile -File "C:/Users/Prekzursil/.local/bin/codexmon.ps1" --once --since-min 120
```

Clear stray / orphaned boards (current monitorcore + retired mingle-era):
```bash
powershell -NoProfile -File "C:/Users/Prekzursil/.local/bin/codexmon.ps1" -Reap
```

Force a second board even if one is already open:
```bash
powershell -NoProfile -File "C:/Users/Prekzursil/.local/bin/codexmon.ps1" -Force --since-min 120
```

Prerequisites: Python 3 on PATH (the monitor is stdlib-only — no venv needed). Quit the dashboard with `q` or Ctrl-C.

Notes:
- The guard wrapper lives in `~/.local/bin/codexmon.ps1` (outside `~/.agents/skills`, so a future sync-skills run cannot clobber it); deleting that one file is a complete rollback to the raw `mon codexmon`.
- The wrapper launches via `Start-Process` in a plain new console rather than `wt new-tab`: the board's interactive loop was observed to exit under wt's ConPTY. The underlying wt/ConPTY interaction is a monitorcore-level issue tracked in the monitor-consolidation work, not in this launcher.
- This is a terminal dashboard — it cannot render inside the Claude chat interface. For the board to show a thread's *prompt*, the Component-A relay (`~/.local/opt/mingle/relay/codex_stream.py`) tees its `codex exec --json` stream with the `monitor.meta` header line; threads without it still render (minus the captured prompt).