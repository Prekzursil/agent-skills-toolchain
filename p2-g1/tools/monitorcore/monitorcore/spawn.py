"""Per-agent terminal spawner (ported from agent_monitor.py, F4 injectable-runner).

Opens ONE terminal window per discovered subagent, each live-tailing that agent via the
vendored ``python -m monitorcore.agent_tail <jsonl>`` (one-agent-per-terminal, because the
inline TUI list glitched). :func:`spawn` walks a 3-way launch ladder —
Windows-Terminal (``wt``) → PowerShell console (``CREATE_NEW_CONSOLE``) → bare Python — and
BUILDS the argv for each rung with the pure ``build_*_argv`` helpers.

F4: the ``subprocess.Popen`` boundary is injected as ``runner`` (default ``subprocess.Popen``)
so tests drive every rung with a FAKE runner that records argv WITHOUT opening a real window.
``CREATE_NEW_CONSOLE`` (0 on non-Windows) is read from a module attribute tests can monkeypatch,
so both the Windows and the non-Windows value are exercised deterministically on any platform.
"""

from __future__ import annotations

import subprocess
import sys
import time

__all__ = [
    "build_ps_argv",
    "build_py_argv",
    "build_wt_argv",
    "spawn",
]

# The vendored tail, run as a module so it resolves wherever ``monitorcore`` is importable.
_TAIL_MODULE = "monitorcore.agent_tail"

# Child gets its own console window (Windows); 0 (ignored) on other platforms.
_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def _py() -> str:
    """The current interpreter, falling back to bare ``python`` if unresolved."""
    return sys.executable or "python"


def build_wt_argv(
    jsonl: str, title: str, *, tabs: bool, py: str | None = None
) -> list[str]:
    """Windows-Terminal argv: a new tab in the shared ``agentmon`` window, or a new window."""
    py = py or _py()
    if tabs:
        return [
            "wt",
            "-w",
            "agentmon",
            "new-tab",
            "--title",
            title,
            py,
            "-m",
            _TAIL_MODULE,
            jsonl,
        ]
    return ["wt", "-w", "new", "--title", title, py, "-m", _TAIL_MODULE, jsonl]


def build_ps_argv(jsonl: str, title: str, *, py: str | None = None) -> list[str]:
    """PowerShell console argv: sets the window title then tails via the vendored module."""
    py = py or _py()
    t = title.replace("'", "''")
    p = py.replace("'", "''")
    j = jsonl.replace("'", "''")
    inner = f"$host.UI.RawUI.WindowTitle='{t}'; & '{p}' -m {_TAIL_MODULE} '{j}'"
    return ["powershell", "-NoExit", "-NoProfile", "-Command", inner]


def build_py_argv(jsonl: str, *, py: str | None = None) -> list[str]:
    """Bare-Python fallback argv (no shell) — the tailer directly in a new console."""
    py = py or _py()
    return [py, "-m", _TAIL_MODULE, jsonl]


def spawn(
    rows, use_wt: bool, tabs: bool, *, runner=subprocess.Popen, sleep=time.sleep
) -> int:
    """Open one terminal per row via ``runner``; return the number spawned.

    ``wt`` is tried first when ``use_wt``; on any ``wt`` failure it degrades to a PowerShell
    console for the rest, and if PowerShell itself is absent (``FileNotFoundError``) it runs
    the tailer directly. A small ``sleep`` staggers windows so they don't race the window
    manager (injectable for tests).
    """
    n = 0
    for r in rows:
        title = f"{r['name']}"
        if use_wt:
            try:
                runner(build_wt_argv(r["jsonl"], title, tabs=tabs), close_fds=True)
            except Exception as e:
                print(f"wt spawn failed ({e}); falling back to powershell")
                use_wt = False
        if not use_wt:
            try:
                runner(
                    build_ps_argv(r["jsonl"], title),
                    creationflags=_NEW_CONSOLE,
                    close_fds=True,
                )
            except FileNotFoundError:
                runner(
                    build_py_argv(r["jsonl"]),
                    creationflags=_NEW_CONSOLE,
                    close_fds=True,
                )
        n += 1
        sleep(0.35)
    return n
