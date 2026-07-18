#!/usr/bin/env python3
r"""codex-monitor-autolaunch/check.py — PreToolUse hook.

The Codex-side counterpart to workflow-monitor-autolaunch (which opens wfmon on a Workflow).
When Claude launches Codex work — the native `mcp__codex__codex` MCP tool, or a `codex exec`
command via Bash/PowerShell — auto-open the **codex-monitor** thread dashboard ONCE per session
(a per-session lockfile, so it never spams windows), so the user watches their Codex threads
(prompt / tool-calls / tokens / status) live instead of forgetting the monitor exists. Either
way it injects a one-line reminder that codex-monitor is available.

READ-ONLY monitor (it never launches/steers/kills Codex). FAIL-OPEN (any error -> exit 0, no
output, never blocks the tool). Opt-out: `CODEX_MONITOR_AUTOLAUNCH=off` in env, or a `.disabled`
file beside this script.

Wire via the _dispatch manifest (PreToolUse; the live PreToolUse matcher is `.*`, so the
dispatcher fires on every tool and this hook self-filters to Codex launches).
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
LAUNCH = (
    Path(os.path.expanduser("~"))
    / ".local"
    / "opt"
    / "mingle"
    / "monitor"
    / "launch.ps1"
)
_DETACHED = 0x00000008  # DETACHED_PROCESS — don't tie the launched window to the hook


def _is_codex_launch(payload: dict) -> bool:
    """True iff this tool call is starting Codex work (native tool or codex exec)."""
    tn = str((payload or {}).get("tool_name") or "")
    low = tn.lower()
    if "codex" in low and "monitor" not in low:  # mcp__codex__codex (not this monitor)
        return True
    if tn in ("Bash", "PowerShell"):
        cmd = str(((payload or {}).get("tool_input") or {}).get("command") or "")
        if "codex exec" in cmd or "codex mcp" in cmd:
            return True
    return False


def _launch() -> bool:
    """Open codex-monitor in a reusable named Windows-Terminal window; fall back to a console."""
    for cmd in (
        [
            "wt",
            "-w",
            "codexmon",
            "new-tab",
            "--title",
            "codexmon",
            "powershell",
            "-NoProfile",
            "-File",
            str(LAUNCH),
        ],
        [
            "cmd",
            "/c",
            "start",
            "codexmon",
            "powershell",
            "-NoProfile",
            "-File",
            str(LAUNCH),
        ],
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
        if (
            DISABLED.exists()
            or os.environ.get("CODEX_MONITOR_AUTOLAUNCH", "").lower() == "off"
        ):
            return
        payload = json.loads(sys.stdin.read() or "{}")
        if not _is_codex_launch(payload):
            return
        if not LAUNCH.exists():
            return
        sid = "".join(
            c for c in str((payload or {}).get("session_id") or "x") if c.isalnum()
        )[:16]
        lock = Path(tempfile.gettempdir()) / f"codexmon-autolaunch-{sid}.lock"
        if lock.exists():
            _emit(
                "🛰 codex-monitor is watching your Codex threads live (already opened this session · `/codex-monitor` to reopen)."
            )
            return
        launched = _launch()
        try:
            lock.write_text("1", encoding="utf-8")
        except OSError:
            pass
        if launched:
            _emit(
                "🛰 Opened **codex-monitor** (read-only Codex thread dashboard) in a 'codexmon' window — watch your Codex threads' prompt/tools/tokens/status live. `/codex-monitor` reopens it; `CODEX_MONITOR_AUTOLAUNCH=off` disables."
            )
        else:
            _emit(
                "🛰 Tip: run `/codex-monitor` to watch your Codex threads live (thread prompt/tools/tokens/status)."
            )
    except Exception:  # noqa: BLE001 — fail-open
        return


if __name__ == "__main__":
    main()
