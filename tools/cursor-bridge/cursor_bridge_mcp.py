#!/usr/bin/env python3
"""cursor-bridge MCP server — exposes the cursorctl bridge as native MCP tools.

Transport: stdio. Registered in .agents/agents.json (targets: claude, cursor); versioned at agent-skills-toolchain tools/cursor-bridge/.
All tools shell into cursorctl.py (single enforcement point for G-36/67/68).

Tools:
  bridge_status()                          auth, processes, queue depth
  bridge_sessions(limit, source, search)   desktop + cloud conversation index
  bridge_session_detail(id)                one session: runs/ record or FTS body
  bridge_worktrees()                       cursor-managed + key-repo git worktrees
  bridge_models()                          account model list
  bridge_dispatch(prompt, workspace, worktree, model, timeout_s, async_)  -> run
  bridge_dispatch_async(...)               always queued; returns run_id immediately
  bridge_queue()                           queued/running/done runs
  bridge_drain(max_runs)                   process queued runs (serial, G-36 safe)
"""

import json
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

CTL = [r"C:\Python314\python.exe", r"D:\opt\cursor-bridge\cursorctl.py"]
mcp = FastMCP("cursor-bridge")


def _ctl(*args, timeout=1800):
    p = subprocess.run(
        CTL + list(args),
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    out = (p.stdout or "") + (("\n[stderr] " + p.stderr) if p.stderr.strip() else "")
    return out.strip() or "(no output)"


@mcp.tool()
def bridge_status() -> str:
    """Auth state, running cursor-agent processes, queue depth, session/worktree counts."""
    return _ctl("status", timeout=120)


@mcp.tool()
def bridge_sessions(limit: int = 25, source: str = "", search: str = "") -> str:
    """List Cursor conversations (desktop 'local' + cloud agents 'cloud-cache').
    Use source='cloud-cache' to watch autonomous cloud sessions."""
    args = ["sessions", "--limit", str(limit)]
    if source:
        args += ["--source", source]
    if search:
        args += ["--search", search]
    return _ctl(*args, timeout=120)


@mcp.tool()
def bridge_session_detail(id: str) -> str:
    """Fetch one session's detail (runs/ archive record or indexed body head)."""
    return _ctl("session-detail", id, timeout=120)


@mcp.tool()
def bridge_worktrees() -> str:
    """List Cursor-managed worktrees and git worktrees of key estate repos."""
    return _ctl("worktrees", timeout=120)


@mcp.tool()
def bridge_models() -> str:
    """List models available to the Cursor account (routing decisions)."""
    return _ctl("models", timeout=180)


@mcp.tool()
def bridge_dispatch(
    prompt: str,
    workspace: str = "",
    worktree: str = "",
    model: str = "",
    timeout_s: int = 900,
    async_: bool = True,
) -> str:
    """Dispatch a headless cursor-agent task. G-68 enforced: prompt auto-wrapped
    no-commit/diff-report. async_=True (default) queues and returns run_id;
    async_=False runs synchronously (refuses if an agent is already running)."""
    args = ["dispatch", "--prompt", prompt, "--timeout", str(timeout_s)]
    if workspace:
        args += ["--workspace", workspace]
    if worktree:
        args += ["--worktree", worktree]
    if model:
        args += ["--model", model]
    if async_:
        args += ["--async"]
    return _ctl(*args, timeout=timeout_s + 120)


@mcp.tool()
def bridge_dispatch_async(
    prompt: str,
    workspace: str = "",
    worktree: str = "",
    model: str = "",
    timeout_s: int = 900,
) -> str:
    """Queue-only dispatch — returns run_id immediately. Completion lands in
    D:\\opt\\cursor-bridge\\INBOX.md and runs\\<run_id>.done."""
    args = ["dispatch", "--prompt", prompt, "--timeout", str(timeout_s), "--async"]
    if workspace:
        args += ["--workspace", workspace]
    if worktree:
        args += ["--worktree", worktree]
    if model:
        args += ["--model", model]
    return _ctl(*args, timeout=120)


@mcp.tool()
def bridge_queue() -> str:
    """Show queued/running/done bridge runs."""
    return _ctl("queue", timeout=120)


@mcp.tool()
def bridge_drain(max_runs: int = 1) -> str:
    """Process queued runs serially (G-36: stops if a cursor-agent is already active).
    The scheduled CursorBridgeDrainer task calls this every 5 minutes."""
    return _ctl("drain", "--max", str(max_runs), timeout=3600)


if __name__ == "__main__":
    mcp.run()
