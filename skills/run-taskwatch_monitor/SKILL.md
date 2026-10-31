---
name: run-taskwatch_monitor
description: Use when running, launching, or smoke-testing taskwatch_monitor - the
  general-purpose long-task progress monitor - to watch a long-running job (build,
  download, CI run, FEP/BPMD driver, LLM generation, rclone transfer) with an honest,
  BLIND-aware status, p50/p90 ETA, and no fabricated percentages. Covers register/list/status,
  the live watch TUI, the MCP server, and the smoke test.
permalink: dqverify-repo-20261013/skills/run-taskwatch-monitor/skill
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
   ```

## MCP server (agent host)

Expose the same surface over stdio for an agent host:

```powershell
uv run taskwatch-mcp
```

Tools: `register_task`, `list_tasks`, `status`, `attach_watch`, `set_notify`.
Every tool returns a terminal-state `{"ok": ...}` envelope and never raises.
`attach_watch` is where you flip the per-task tier-2 `remediate` opt-in;
observation is the default and nothing acts on a job unless you asked for it.

## Smoke test

`smoke.ps1` proves the `register -> list -> status` round-trip offline against
the bundled `fixtures/demo.log` (a `Compiling 37/40 crates` build log). It ends
with the longrun §4 terminal marker:

```powershell
.\smoke.ps1
# → SUCCESS:taskwatch-smoke register+list+status round-trip verified (37/40 = 92%, blind-aware)
```

Use it as a fast post-install sanity check or a CI gate for the launcher glue.

## Common Mistakes

- **Expecting the `--watch` TUI to render in chat.** It is a live terminal
  surface; it cannot display inside the Claude chat interface. Use
  `status --json` (or `launch.ps1 -PassThru status --json`) for readable output.
- **Running the CLI by file path** (`python cli/app.py`). It uses relative
  imports — always run it as a module: `python -m cli.app` (the shim and
  launcher already do this).
- **Reading a fake percentage.** When `total` is unknown the tool shows `--%` on
  purpose. That is honesty, not a bug — look at the liveness signal (is it
  moving?) and the elapsed/rate instead.
- **Confusing BLIND with DONE.** A BLIND banner with an age stamp means the poll
  went dark; the last frontier is held, not completed.