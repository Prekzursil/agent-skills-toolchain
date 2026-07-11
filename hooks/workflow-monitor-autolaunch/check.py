#!/usr/bin/env python3
r"""workflow-monitor-autolaunch/check.py — PreToolUse hook (matcher: Workflow).

When Claude launches a Workflow (an "ultracode" fan-out), auto-open the **wfmon** whole-fleet
cockpit ONCE per session (singleton — a per-session lockfile, so it never spams windows), so the
user actually watches their parallel agents live instead of forgetting the monitor exists. Either
way it injects a one-line reminder that wfmon is available.

READ-ONLY monitor (it never touches the run). FAIL-OPEN (any error -> exit 0, no output, never
blocks the Workflow). Opt-out: `WFMON_AUTOLAUNCH=off` in env, or a `.disabled` file beside this script.

settings.json wiring is via the _dispatch manifest (PreToolUse, matcher "Workflow"); the live
PreToolUse matcher is `.*`, so the dispatcher already fires on the Workflow tool.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
MONITOR = (
    Path(os.path.expanduser("~"))
    / ".agents"
    / "skills"
    / "workflow-monitor"
    / "workflow_monitor.py"
)
_DETACHED = 0x00000008  # DETACHED_PROCESS — don't tie the launched window to the hook


def _launch() -> bool:
    """Open the cockpit in a reusable named Windows-Terminal window; fall back to a plain console."""
    py = sys.executable or "python"
    for cmd in (
        ["wt", "-w", "wfmon", "new-tab", "--title", "wfmon", py, str(MONITOR)],
        ["cmd", "/c", "start", "wfmon", py, str(MONITOR)],
    ):
        try:
            subprocess.Popen(cmd, creationflags=_DETACHED, close_fds=True)
            return True
        except Exception:  # noqa: BLE001 — try the next launcher
            continue
    return False


def _emit(msg: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": msg,
                }
            }
        )
    )


def main() -> None:
    try:
        if DISABLED.exists() or os.environ.get("WFMON_AUTOLAUNCH", "").lower() == "off":
            return
        payload = json.loads(sys.stdin.read() or "{}")
        if str((payload or {}).get("tool_name") or "") != "Workflow":
            return
        if not MONITOR.exists():
            return
        sid = "".join(
            c for c in str((payload or {}).get("session_id") or "x") if c.isalnum()
        )[:16]
        lock = Path(tempfile.gettempdir()) / f"wfmon-autolaunch-{sid}.lock"
        if lock.exists():
            _emit(
                "🛰 wfmon is watching this Workflow live (whole-fleet cockpit already opened this session · `wfmon` to reopen)."
            )
            return
        launched = _launch()
        try:
            lock.write_text("1", encoding="utf-8")
        except OSError:
            pass
        if launched:
            _emit(
                "🛰 Opened the **wfmon** cockpit (whole-fleet, read-only) in a 'wfmon' window/tab — watch this Workflow's agents fan out live. `wfmon` reopens it; `WFMON_AUTOLAUNCH=off` disables."
            )
        else:
            _emit(
                "🛰 Tip: run `wfmon` to watch this Workflow's agents live (whole-fleet monitor)."
            )
    except Exception:  # noqa: BLE001 — fail-open
        return


if __name__ == "__main__":
    main()
