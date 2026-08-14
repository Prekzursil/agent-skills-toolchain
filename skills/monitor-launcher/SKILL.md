---
name: monitor-launcher
description: The generalized `mon <name>` launcher for the unified monitoring platform - opens any registered monitor (wfmon fleet cockpit, agentmon per-agent tails) from monitors.toml. Use when asked to launch, open, or wire a monitor, add one to the registry, or reasoning about the `mon`/wfmon/agentmon launch flow and the monitor-autolaunch hook. NOT for driving the tail itself (use run-agent-monitor).
---

# monitor-launcher — `mon <name>` + the monitors.toml registry

`mon <name> [args]` launches any registered monitor in a reusable, named Windows-Terminal window
(with a plain `cmd /c start` console fallback). It is the generalized successor to the old
wfmon-only launcher; **wfmon** and **agentmon** are thin aliases that delegate to `mon`.

All the real logic — parsing `monitors.toml`, matching a monitor's `trigger_tool` to a tool, and
building the launch argv — lives in the 100%-gated `monitorcore.monitors` core (vendored inside
the sibling `workflow-monitor` skill). The `.cmd` files here and the `monitor-autolaunch` hook are
**thin shims** over it.

## Files

- **`mon.cmd`** — puts the vendored `monitorcore` on `PYTHONPATH` and runs
  `python -m monitorcore.monitors %*`.
- **`agentmon.cmd`** — `mon agentmon` alias (per-agent tail terminals).
- **`monitors.toml`** — the registry. One `[table]` per monitor:
  `dir` (deployed skill dir), `entry` (launchable script), `trigger_tool` (the Claude tool that
  auto-opens it via the hook; omit for launch-by-hand-only).

## Run

```bat
mon wfmon           :: whole-fleet workflow cockpit (skills/workflow-monitor/workflow_monitor.py)
mon agentmon        :: one live tail terminal per active subagent
mon codexmon        :: live board of OpenAI Codex threads (relay streams + ~/.codex rollouts)
```

## PATH / deploy

`scripts/sync-skills.ps1` copies this whole dir to `~/.agents/skills/monitor-launcher/` (a file
copy — the `monitors.toml` sync mirrors `hooks/mcp-userscope-sync/heal.py`, never a TOML rewrite).
Add `~/.agents/skills/monitor-launcher` to `PATH` so `mon` / `agentmon` resolve; `mon.cmd` finds
`monitorcore` via the sibling `workflow-monitor` skill, and finds the registry at
`~/.agents/skills/monitor-launcher/monitors.toml` (override with `MONITORCORE_MONITORS_TOML`).

## Add a monitor

Add a `[table]` to `monitors.toml` with `dir` / `entry` / `trigger_tool`, and (if it should
auto-open) ensure the outer PreToolUse matcher in `hooks/_dispatch/manifest.json` covers the new
`trigger_tool`. No code change — the loader/matcher/builder are generic.
