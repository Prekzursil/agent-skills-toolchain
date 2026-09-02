---
name: run-agent-monitor
description: Run, drive, and smoke-test the monitorcore agent tail + discovery — the read-only per-agent tailer and flat/workflow subagent discovery for Claude Code Task subagents. Use when asked to run, start, monitor, watch, or smoke-test the agent monitor / subagent dashboard, tail a subagent transcript, or verify agent-monitor works.
---

# Run: agent-monitor (monitorcore)

The former standalone `agent-monitor` tool has been **consolidated into the shared
`monitorcore` package** (vendored inside the sibling `workflow-monitor` skill). This skill is
the read-only driver for its two agent-domain surfaces:

- **`monitorcore.agent_tail`** — a live, colored **tail** of one agent's transcript
  (`python -m monitorcore.agent_tail <agent-*.jsonl>`), plus the one-shot `tail_once.py` here
  (backfill N events, then exit — headless-safe).
- **`monitorcore.discovery`** — **flat + workflow subagent discovery** (`find_subagent_dirs`,
  `scan`, `pick_active_dir`): every `agent-*.jsonl` under
  `~/.claude/projects/<project>/<session>/subagents/` (including `subagents/workflows/<wf>/…`),
  each summarised with a cheap last-event line.

Everything is **read-only** — it only ever reads each subagent's own JSONL transcript, so it
never disturbs the monitored session. (For the whole-fleet Workflow cockpit, use the
`workflow-monitor` skill; for freeze detection, `python -m monitorcore.watchdog`.)

> **Windows-native, system Python (no venv).** The `monitorcore` package is stdlib-only, so
> any Python 3.11+ works (this machine: 3.14.3). `monitorcore` is vendored in the sibling
> `workflow-monitor` skill; `tail_once.py` adds that dir to `sys.path` automatically, and
> `smoke.ps1` sets `PYTHONPATH` to it.

## Run (agent path) — START HERE

Deterministic, side-effect-free smoke of BOTH surfaces against a committed fixture transcript
(no live Claude session, no windows opened):

### Run: per-agent tail
### Non-interactive: render the last N events of a transcript, then EXIT.
### Run: discovery
### From the sibling workflow-monitor dir on PYTHONPATH:
### -> fixture-agent True general-purpose
### (prints ASCII fields only: a bare `python -c` skips the UTF-8 stdout reconfigure, so don't
### print the 'last' field — its ↳ glyph crashes a cp1252 pipe.)
### Spawn one terminal per agent (power user)
### Gotchas
### Troubleshooting
