---
name: re-ensure
description: Bring up the reverse-engineering MCP backends (IDA / Ghidra) on demand
  so mcp__ida-pro-mcp / mcp__ghidra-mcp calls "just work" without manually opening
  the GUI apps. Use when asked to start/ensure the RE stack, or before a batch of
  RE tool calls. Cold-starts ONLY the requested backend, prefers an already-running
  GUI IDA on :13337, and reports that Binary Ninja (Personal) cannot run headless.
permalink: dqverify-repo-20261013/skills/re-ensure/skill
---

# re-ensure Skill

Explicit, on-demand bring-up of the reverse-engineering MCP backends. The RE MCPs
are **bridge proxies** — each `mcp__<x>__*` call forwards over a local socket to a
plugin/server that must be running:

| MCP bridge | backend port(s) | headless launch? |
|---|---|---|
| `mcp__ida-pro-mcp` | GUI **:13337** (preferred) or headless idalib **:8745** | yes (idalib_server) |
| `mcp__ghidra-mcp` | GhidraMCP headless **:8089** | yes (true no-GUI) |
| `mcp__binary-ninja-mcp` | BN GUI plugin **:9009** | **NO** — Personal license has no headless; open the GUI manually |

If the backend isn't running the bridge connects to nothing and the call fails
("not reachable" / "connection refused" / `list_instances → []`).

## You usually don't need this skill

A **PreToolUse hook** (`~/.claude/hooks/re-autolaunch/`) already auto-launches the
right backend the moment you invoke a matching RE tool and its port is down. This
skill is for **explicit** control: "make sure Ghidra is up before I start", or
bringing up a backend ahead of a batch so the first real call doesn't have to wait.

## Mechanism (the launcher)

`C:/Users/Prekzursil/.claude/hooks/re-autolaunch/autolaunch.py` wraps the
re-harness (`C:/Users/Prekzursil/.local/opt/re-harness/re_launch.py`):

```bash
# Probe all backends (no launch) — fast, safe, prints SUCCESS/FAILED + free RAM.
python C:/Users/Prekzursil/.claude/hooks/re-autolaunch/autolaunch.py probe

# Cold-start ONE backend on-demand (detached; idempotent; prefers existing).
python C:/Users/Prekzursil/.claude/hooks/re-autolaunch/autolaunch.py ensure ghidra
python C:/Users/Prekzursil/.claude/hooks/re-autolaunch/autolaunch.py ensure ida
python C:/Users/Prekzursil/.claude/hooks/re-autolaunch/autolaunch.py ensure bn    # -> manual hint (no headless)

# Bring up every LAUNCHABLE backend (IDA + Ghidra). Heavier — only when asked.
python C:/Users/Prekzursil/.claude/hooks/re-autolaunch/autolaunch.py ensure all
```

`ensure` kicks a **detached** `re_launch.py` (which itself spawns the heavy server
detached, polls it ready, registers it) and briefly waits for the port. It prints a
terminal-state marker per backend:

- `SUCCESS:re-ensure <x> already-up …` / `… now listening …`
- `STARTING:re-ensure <x> cold-start launched …` — analysis still running in the background
- `MANUAL:re-ensure binary-ninja-mcp …` — open the BN GUI yourself
- `FAILED:re-ensure …` — launcher couldn't start

## Poll until ready (cold-start can take 1–3 min)

A backend's **port** binds quickly, but full MCP readiness (idalib auto-analysis /
Ghidra program open) can take minutes. After `STARTING`, poll `probe` until UP
rather than firing a doomed call. Because this can exceed 60s, run the poll in the
background (longrun / `run_in_background`), per the >60s rule — never a blocking
foreground sleep loop:

```bash
# bounded poll: stop as soon as ghidra:8089 listens (or give up after ~3 min)
for i in $(seq 1 36); do
  if python -c "import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1',8089))==0 else 1)"; then
    echo "ghidra UP"; break
  fi
  sleep 5
done
```

Inspect a stuck launch via the logs:
`~/.claude/hooks/re-autolaunch/state/<tool>-spawn.log` and the re-harness
`~/.local/opt/re-harness/state/<tool>.log`.

## Safety / RAM

- **On-demand & single-backend** — IDA and Ghidra are heavy; `ensure <tool>` starts
  only that one. Use `ensure all` only when you really want both.
- **Never duplicates the live GUI IDA** — if `:13337` is up, IDA is treated as up and
  no headless server is started.
- **OOM guard** — the auto-launch hook refuses to launch when free RAM is below
  `min_free_ram_mb` (default 2048) and tells you to free memory or launch manually.
  `ensure` is explicit, so it still launches; check `probe` (it prints `free_ram_mb`)
  first if RAM is tight.
- **Never touches port 13337 / the GUI** beyond probing; teardown stays the
  re-harness's job (`re_launch.py <tool> --teardown`, registry-gated).
- **Binary Ninja** cannot be headless-launched on a Personal license — `ensure bn`
  reports the manual step (open GUI, load binary, start the MCP plugin on :9009).

## Configuration

`~/.claude/hooks/re-autolaunch/backends.json` — ports per backend, the pre-loaded
`binary` (default: the BC `libnative-lib.so` for 15.4.1), `min_free_ram_mb`,
`brief_wait_seconds`, and `deny_while_starting` / `deny_when_unlaunchable` (set
false for inject-only, never-block behavior). Disable everything with
`RE_AUTOLAUNCH=off` or a `.disabled` file in that directory.

## Verify

```bash
python C:/Users/Prekzursil/.claude/hooks/re-autolaunch/test_autolaunch.py   # unit/decision/fail-open tests
python C:/Users/Prekzursil/.claude/hooks/re-autolaunch/autolaunch.py probe  # live backend status
```