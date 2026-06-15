---
name: run-agent-monitor
description: Run, drive, and smoke-test agent-monitor - the read-only dashboard + per-agent tailer for Claude Code Task subagents. Use when asked to run, start, monitor, watch, or smoke-test the agent monitor / subagent dashboard, tail a subagent transcript, or verify agent-monitor works.
---

# Run: agent-monitor

`agent-monitor` is a **read-only, stdlib-only** monitor for the background `Task`
subagents a Claude Code session spawns. Two binaries:

- **`agent_monitor.py`** — an overview **dashboard** (one-shot table or live `--watch`),
  and a spawner (`--spawn`) that opens one terminal per agent.
- **`agent_tail.py`** — a live, colored **tail** of one agent's transcript.

It reads each subagent's own JSONL transcript under
`~/.claude/projects/<project>/<session>/subagents/`, so it never disturbs the
monitored session.

> **All paths below are relative to the unit root `D:\agent-monitor`.** Commands
> are PowerShell. **Windows-native, system Python (no venv), not a git repo** —
> the skill lives on disk only. The scripts are stdlib-only, so any Python 3.8+
> works (this machine: 3.14.3).

## Prerequisites

System Python on PATH. No venv, no `pip install` — the two scripts import only
the standard library.

```powershell
python --version
# -> Python 3.14.3   (any 3.8+ works)
```

## Run (agent path) — START HERE

Deterministic, side-effect-free smoke of **both** binaries against a committed
fixture transcript (no live Claude session, no windows opened):

```powershell
pwsh -NoProfile -File .claude\skills\run-agent-monitor\smoke.ps1
```

Verified this session (exit 0): the dashboard prints a `● fixture-agent ... 1 running`
row, and `tail_once.py` renders the transcript backfill (`📝 …`, `🔧 Bash command=echo hello`,
`↳ hello`). The script asserts on that output, not just the exit code.

## Run: agent_monitor.py (dashboard)

```powershell
# One-shot table of the most-recently-active LIVE session (auto-picked). Verified.
python agent_monitor.py

# One-shot table against the committed fixture (no live session needed). Verified.
python agent_monitor.py --dir .claude\skills\run-agent-monitor\fixture\subagents --active-secs 99999

# Live-refreshing dashboard in THIS window (loops; Ctrl-C to quit).
python agent_monitor.py --watch
```

Key flags (full table in `README.md`): `--dir <subagents>` point at a specific
dir · `--session <id>` match a session substring · `--all` include finished
agents · `--active-secs N` recency window counted as "running" (default 150) ·
`--watch` live loop · `--spawn` open a terminal per agent.

**`--spawn` opens real OS windows** (Windows Terminal tabs/windows, or PowerShell
consoles) — see Gotchas. Don't run it in a headless/automated context.

## Run: agent_tail.py (per-agent tail)

`agent_tail.py` is a **live poll loop — it never exits on its own** (Ctrl-C to
quit). Two headless-safe ways to use it:

```powershell
# Non-interactive: render the last N events of a transcript, then EXIT. Verified.
python .claude\skills\run-agent-monitor\tail_once.py <path-to-agent-*.jsonl> 8

# Live tail (interactive). Headless: run UNBUFFERED (-u) and bound it, else the
# header/backfill sit in a block buffer until you kill it (they print without flush):
python -u agent_tail.py <path-to-agent-*.jsonl> --backfill 8
```

`tail_once.py` (this skill dir) wraps `agent_tail.header` / `read_tail_entries` /
`render` — the same rendering code, minus the infinite loop.

## Direct invocation (auth-free internals)

Both modules import without side effects (`main()` is guarded; the VT/ctypes
setup is inside a function). From the repo root (or with the repo root on
`PYTHONPATH`):

```powershell
python -c "import agent_monitor; rows = agent_monitor.scan(r'.claude\skills\run-agent-monitor\fixture\subagents', 99999, 120); print(rows[0]['name'], rows[0]['running'], rows[0]['type'])"
# -> fixture-agent True general-purpose
# (prints ASCII fields only: the bare `python -c` skips the scripts' UTF-8 stdout
#  reconfigure, so don't print the 'last' field - its ↳ glyph crashes a cp1252 pipe.)
```

`tail_once.py` is the same pattern for `agent_tail` (it puts the repo root on
`sys.path` itself, so it runs from any cwd).

## Gotchas

- **Data source + "running" rule.** Reads `~/.claude/projects/<proj>/<session>/subagents/agent-*.jsonl`
  (+ `agent-*.meta.json`). An agent is **RUNNING** iff its `.jsonl` mtime is within
  `--active-secs` (default 150s); a stale mtime = finished/idle. The fixture
  driver `touch`es the mtime to now so it reads as running deterministically.
- **No live subagents → exit 1.** With no `--dir` and nothing recent under
  `~/.claude/projects`, `agent_monitor.py` prints `No subagents directory found`
  and returns 1. Pass `--dir <fixture\subagents>` or spawn a `Task` subagent first.
- **`--spawn` has real side effects.** It launches OS windows (prefers `wt.exe`
  tabs/windows; falls back to classic PowerShell consoles via `CREATE_NEW_CONSOLE`).
  Never run it in a driver/headless run — it litters windows. Use `--dir`/no-arg
  table or `tail_once.py` instead.
- **`agent_tail.py` never self-exits**, and `header()`/backfill `print()` **without
  `flush`** — so if you redirect its stdout and kill it, the buffer is lost (block-
  buffered when piped). Use `python -u`, or just use `tail_once.py`.
- **System Python, no venv.** This repo has no `.venv` (unlike sibling projects).
  Don't hunt for one; `python` off PATH is correct. Stdlib-only → no install step.
- **UTF-8 / VT.** Both scripts self-enable VT processing and `reconfigure(stdout,
  utf-8, errors="replace")`, so box-drawing/emoji degrade to `?` rather than crash
  on a cp1252 console. `smoke.ps1` also sets `PYTHONUTF8=1`.
- **100% read-only.** It never writes to or signals the monitored Claude Code session.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No subagents directory found under ...` (exit 1) | No live Task subagents on disk. Pass `--dir .claude\skills\run-agent-monitor\fixture\subagents`, or spawn a subagent in a Claude Code session first. |
| `agent_tail.py` prints `Waiting for <path> …` then nothing | The transcript path doesn't exist yet; it waits ~120s then exits 1. Check the path (use the dashboard to copy a real `agent-*.jsonl`). |
| Garbled box/glyph characters | Console isn't UTF-8. `$env:PYTHONUTF8 = '1'` (the driver sets this). |
| `--spawn` opened no windows | No RUNNING agents matched. Add `--all`, or `--match <substr>` to target a finished one. |
| `ModuleNotFoundError: agent_tail` from `tail_once.py` | Only if the skill dir was moved away from the repo. `tail_once.py` expects the repo root three dirs up. |
