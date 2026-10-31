---
title: taskwatch_monitor
type: note
permalink: dqverify-repo-20261013/agent-self/config/commands/taskwatch-monitor
---

Launch taskwatch_monitor — a general-purpose long-task progress monitor (the FEP dashboard, generalized).

Usage: /taskwatch_monitor [--inline] [--registry PATH]

Opens the taskwatch live watch dashboard (a rich TUI) over a declarative task
registry. The dashboard shows, for every registered long-running job:
  - An honest, BLIND-aware status badge (PEND / RUN / STALL / DONE / FAIL / BLIND)
  - A progress bar that renders `--%` when the total is unknown and a full bar
    with a `!` marker on overshoot (never a silent clamp)
  - A p50/p90 ETA range with measured|prior provenance (never a fabricated clock)
  - A GPU-utilisation sparkline and a stall flag
  - A BLIND banner with an age stamp for any task whose poll went dark

Run this Bash command to start it (watches taskwatch.toml in the tool dir):
```bash
powershell -NoProfile -File "D:/source/agent-skills-toolchain/tools/taskwatch_monitor/launch.ps1" -Inline
```

Watch a specific registry:
```bash
powershell -NoProfile -File "D:/source/agent-skills-toolchain/tools/taskwatch_monitor/launch.ps1" -Inline -Registry "runs/a2d.toml"
```

For a new window instead of inline, omit -Inline.

One-shot (non-TUI) status you CAN read in chat — JSON status views:
```bash
powershell -NoProfile -File "D:/source/agent-skills-toolchain/tools/taskwatch_monitor/launch.ps1" -Inline -PassThru status --json
```

Register a task first (if the registry is empty):
```bash
powershell -NoProfile -File "D:/source/agent-skills-toolchain/tools/taskwatch_monitor/launch.ps1" -Inline -PassThru register generic-logfile mybuild --config path=C:/logs/build.log
```

Prerequisites: uv is installed at {{USER_HOME}}/.local/bin/uv.exe and the venv
has been created (run install.ps1 once if not).

Note: `--watch` launches a live rich TUI in your terminal — it cannot render
inside the Claude chat interface itself. Use `-PassThru status --json` when you
need output you can read back in chat. The Bash command above opens the
dashboard in your current shell (with -Inline) or a new PowerShell window.