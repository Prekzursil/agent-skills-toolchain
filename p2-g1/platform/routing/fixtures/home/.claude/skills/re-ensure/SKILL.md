---
name: re-ensure
description: Bring up the reverse-engineering MCP backends (IDA / Ghidra) on demand so mcp__ida-pro-mcp / mcp__ghidra-mcp / mcp__binary-ninja-mcp calls "just work" without manually opening or navigating the GUI apps. Use when explicitly asked to start/ensure the RE stack, or before a batch of RE tool calls. Cold-starts ONLY the requested backend (RAM-conscious), prefers an already-running GUI IDA on :13337 (never duplicates), and reports honestly that Binary Ninja (Personal license) cannot run headless. Companion to the automatic PreToolUse re-autolaunch hook.
origin: user
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

`C:/Users/agentuser/.claude/hooks/re-autolaunch/autolaunch.py` wraps the
re-harness (`C:/Users/agentuser/.local/opt/re-harness/re_launch.py`):

```bash
# Probe all backends (no launch) — fast, safe, prints SUCCESS/FAILED + free RAM.
python C:/Users/agentuser/.claude/hooks/re-autolaunch/autolaunch.py probe

# Cold-start ONE backend on-demand (detached; idempotent; prefers existing).

### Bring up every LAUNCHABLE backend (IDA + Ghidra). Heavier — only when asked.
### Poll until ready (cold-start can take 1–3 min)
### bounded poll: stop as soon as ghidra:8089 listens (or give up after ~3 min)
### Safety / RAM
### Configuration
### Verify
