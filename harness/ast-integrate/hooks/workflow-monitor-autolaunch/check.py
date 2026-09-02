#!/usr/bin/env python3
r"""workflow-monitor-autolaunch/check.py — PreToolUse hook (matcher: Workflow).

When Claude launches a Workflow (an "ultracode" fan-out), auto-open the **wfmon** whole-fleet
cockpit ONCE per session (singleton — a per-session lockfile, so it never spams windows), so the
user actually watches their parallel agents live instead of forgetting the monitor exists. Either
way it injects a one-line reminder that wfmon is available.

READ-ONLY monitor (it never touches the run). FAIL-OPEN (any error -> exit 0, no output, never
blocks the Workflow). Opt-out: `WFMON_AUTOLAUNCH=off` in env, or a `.disabled` file beside this script.

SUPERSEDED / UNWIRED (A087). This hook is the wfmon-only PREDECESSOR of the registry-driven
`monitor-autolaunch` hook, which owns the `Workflow` trigger through `monitors.toml`
(`monitor-autolaunch/check.py:1-24`; `_dispatch/manifest.json` PreToolUse, matcher
`Task|Workflow|mcp__codex__codex`). It is no longer registered in the tracked deploy mirror
`agent-self/config/settings.json`, for two measured reasons: (1) running BOTH on one Workflow
call opens wfmon twice, and (2) this file honours only `WFMON_AUTOLAUNCH` while the successor
also honours the per-monitor `MONITOR_AUTOLAUNCH_WFMON` -- so with
`MONITOR_AUTOLAUNCH_WFMON=off` and `WFMON_AUTOLAUNCH` unset the successor opts out
(`monitor-autolaunch/check.py:65-69`) and this one still launches (`:65-70` below).
The retired comment here claimed "settings.json wiring is via the _dispatch manifest
(PreToolUse, matcher \"Workflow\"); the live PreToolUse matcher is `.*`". Both halves were
FALSE and are recorded rather than deleted so the dead end is not re-walked: this script was
never a manifest check (it ran as its own standalone settings group), and the tracked
PreToolUse dispatcher matcher was never `.*` -- it did not contain `Workflow` at all, which is
exactly what kept the successor unreachable. Kept on disk (not deleted) so an older deploy that
still references it keeps working.
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
    # The console rung's title slot is an EMPTY string ("" once list2cmdline quotes it):
    # `start` treats a BARE first token as the COMMAND, so the previous "wfmon" literal made
    # this rung ShellExecute bare `wfmon` (error dialog when ~/.local/bin is off PATH)
    # instead of `python <MONITOR>`. The named window lives in the wt rung.
    for cmd in (
        ["wt", "-w", "wfmon", "new-tab", "--title", "wfmon", py, str(MONITOR)],
        ["cmd", "/c", "start", "", py, str(MONITOR)],
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
