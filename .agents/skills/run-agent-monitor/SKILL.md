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

```powershell
pwsh -NoProfile -File .\smoke.ps1
```

It asserts on OUTPUT CONTENT: `discovery.scan` discovers a `fixture-agent` row marked RUNNING,
and `tail_once.py` renders the transcript backfill (`📝 …`, `🔧 Bash command=echo hello`, `↳ hello`).

## Run: per-agent tail

```powershell
# Live tail (interactive — never self-exits; Ctrl-C to quit). Run UNBUFFERED (-u) when piped.
python -u -m monitorcore.agent_tail <path-to-agent-*.jsonl> --backfill 8

# Non-interactive: render the last N events of a transcript, then EXIT.
python tail_once.py <path-to-agent-*.jsonl> 8
```

`tail_once.py` wraps `agent_tail.header` / `read_tail_entries` / `render` — the same rendering
code, minus the infinite loop.

## Run: discovery

```powershell
# From the sibling workflow-monitor dir on PYTHONPATH:
$env:PYTHONPATH = (Resolve-Path ..\workflow-monitor).Path
python -c "import monitorcore.discovery as d; r = d.scan(r'.\fixture\subagents', 99999, 120)[0]; print(r['name'], r['running'], r['type'])"
# -> fixture-agent True general-purpose
# (prints ASCII fields only: a bare `python -c` skips the UTF-8 stdout reconfigure, so don't
#  print the 'last' field — its ↳ glyph crashes a cp1252 pipe.)
```

`monitorcore.discovery.scan(subdir, active_secs, width)` returns one row per transcript
(`jsonl` / `name` / `type` / `desc` / `wf` / `size` / `age` / `running` / `last`),
most-recently-active first. `wf` is `""` for a flat Task agent, or the workflow id for a
workflow agent. A row is **running** iff its `.jsonl` mtime is within `active_secs`.

## Spawn one terminal per agent (power user)

`monitorcore.spawn.spawn(rows, use_wt, tabs)` opens one window per discovered agent, each
running `python -m monitorcore.agent_tail <jsonl>` (Windows-Terminal → PowerShell → bare
Python ladder). **Real side effects** (opens OS windows) — never in a headless/driver run.

## Gotchas

- **Data source + "running" rule.** Reads `~/.claude/projects/<proj>/<session>/subagents/agent-*.jsonl`
  (+ `agent-*.meta.json`). RUNNING = `.jsonl` mtime within `active_secs`. The smoke driver
  `touch`es the fixture mtime to now so it reads as running deterministically.
- **`python -m monitorcore.agent_tail` never self-exits**, and prints without `flush` on open —
  use `python -u`, or `tail_once.py`, when piping.
- **`spawn` has real side effects** — it launches OS windows. Never in a driver/headless run.
- **UTF-8 / VT.** The tail self-enables VT + `reconfigure(stdout, utf-8, errors="replace")`, so
  box-drawing/emoji degrade to `?` rather than crash a cp1252 console. `smoke.ps1` sets
  `PYTHONUTF8=1`.
- **100% read-only.** Nothing here writes to or signals the monitored Claude Code session.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: monitorcore` | Ensure the sibling `workflow-monitor` skill (which vendors `monitorcore`) is present. `tail_once.py` adds it to `sys.path`; for a bare `python -c`, set `PYTHONPATH` to the `workflow-monitor` dir. |
| `not found: <path>` from `tail_once.py` | The transcript path doesn't exist. Use `discovery.scan` to find a real `agent-*.jsonl`. |
| Garbled box/glyph characters | Console isn't UTF-8. `$env:PYTHONUTF8 = '1'` (the smoke driver sets this). |
