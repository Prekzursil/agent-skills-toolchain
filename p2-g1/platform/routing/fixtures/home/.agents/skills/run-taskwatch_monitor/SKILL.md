---
name: run-taskwatch_monitor
description: Use when running, launching, or smoke-testing taskwatch_monitor — the general-purpose long-task progress monitor (the FEP dashboard generalized) — to watch a long-running job (build, download, CI run, FEP/BPMD driver, LLM generation, rclone transfer) with an honest, BLIND-aware status, p50/p90 ETA, and no fabricated percentages. Covers register/list/status, the live watch TUI, the MCP server, install/launch, and the offline smoke test. Do NOT use for editing the taskwatch source (that is the cov-gated build), and do NOT expect the live TUI to render inside chat (use status --json for readable output).
---

# Run taskwatch_monitor

## Overview

`taskwatch_monitor` polls any long-running job through one uniform adapter and
renders an honest status. It is engineered to avoid the two FEP-dashboard bug
classes: **no hidden clamps** (an out-of-range reading widens the ETA band and
shows a `!` marker, never a silent clamp) and **whole-record reads** (monotonic
`seq`, never a fixed tail that undercounts after log rolloff). Unknown total ⇒
`--%` and elapsed+rate only; a poll error goes **BLIND** (last verdict held with
an age stamp, never relabelled `DONE`).

Tool dir: `tools/taskwatch_monitor` (in this repo). CLI runs as a module
(`python -m cli.app`) because it uses relative imports.

## Quick Workflow

1. **Install once** (creates the venv + a `taskwatch` PATH shim):
   ```powershell
   cd tools/taskwatch_monitor
   .\install.ps1
   ```

2. **Register a task** from a template (see the template table in the tool
   README). The `generic-logfile` fallback handles any `N/M` or `NN%` log:
   ```powershell
   taskwatch register generic-logfile mybuild --config path=C:\logs\build.log
   ```

3. **Check status** — one-shot report, or JSON you can read back in chat:
   ```powershell
   taskwatch status            # honest text report
   taskwatch status --json     # BLIND-aware status views
   ```

4. **Watch live** — the rich TUI (leg/stage grid, GPU sparkline, p50/p90 ETA,
   BLIND banner, stall flag):
   ```powershell
   .\launch.ps1 -Inline                     # current console
   .\launch.ps1 -Registry runs\a2d.toml     # a specific registry, new window

### MCP server (agent host)
### Smoke test
### Common Mistakes
