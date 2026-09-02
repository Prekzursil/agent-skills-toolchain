#!/usr/bin/env python3
"""notify-idle/notify.py — Notification hook: desktop balloon + terminal BEL.

Fires on Notification events from Claude Code (idle_prompt when CC is waiting
on the user, permission_prompt when approval is needed during an autonomous run).

Two-channel alert:
  (a) Windows desktop toast balloon via a detached NotifyIcon PowerShell process
      (title "Claude Code needs you", body = the notification message).
      Reuses the same balloon pattern as stopfailure-notify/notify.py — non-blocking,
      fire-and-forget, DETACHED_PROCESS | CREATE_NO_WINDOW.
  (b) terminalSequence BEL (\x07) emitted in the hookSpecificOutput JSON response
      so the terminal pings even if the desktop balloon is suppressed.

CC reads stdout for the JSON response:
  {"hookSpecificOutput": {"hookEventName": "Notification", "terminalSequence": "\x07"}}

Notification payload fields (stdin JSON):
  session_id, cwd, message, hook_event_name

Opt-out: NOTIFY_IDLE=off  OR  create hooks/notify-idle/.disabled
Fail-open: any exception at any layer → exit 0.

Note: register this hook under "Notification" with matcher "idle_prompt|permission_prompt".
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"

# BEL character — ASCII 7, fires the terminal bell when embedded in output.
_BEL = "\x07"


# ── opt-out ───────────────────────────────────────────────────────────────────


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("NOTIFY_IDLE", "").lower() in (
        "off",
        "0",
        "false",
    )


# ── PowerShell balloon helpers (inlined from stopfailure-notify conventions) ──


def _escape_ps_dq(s: str) -> str:
    """Escape a string for safe embedding in a PowerShell double-quoted string.

    In PS double-quoted strings the escape character is backtick (`):
      ` → ``   (escape the escaper first)
      $ → `$   (prevent variable expansion)
      " → `"   (prevent string close)
    Length-capped so balloon text is readable.
    """
    return str(s).replace("`", "``").replace("$", "`$").replace('"', '`"')[:200]


def _build_ps_script(title: str, body: str) -> str:
    """Build a one-liner PS script that shows a balloon tooltip and exits."""
    safe_title = _escape_ps_dq(title)
    safe_body = _escape_ps_dq(body)
    return (
        "Add-Type -AssemblyName System.Windows.Forms | Out-Null; "
        "$icon = [System.Drawing.SystemIcons]::Information; "
        "$notify = New-Object System.Windows.Forms.NotifyIcon; "
        "$notify.Icon = $icon; "
        "$notify.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info; "
        f'$notify.BalloonTipTitle = "{safe_title}"; '
        f'$notify.BalloonTipText = "{safe_body}"; '
        "$notify.Visible = $true; "
        "$notify.ShowBalloonTip(8000); "
        "Start-Sleep -Milliseconds 9000; "
        "$notify.Dispose()"
    )


def _send_balloon(title: str, body: str) -> None:
    """Fire a non-blocking Windows balloon notification. Fail-open."""
    try:
        ps_script = _build_ps_script(title=title, body=body)
        # Flags: DETACHED_PROCESS prevents the child from sharing our console;
        # CREATE_NO_WINDOW suppresses any flashing cmd window.
        CREATE_NO_WINDOW = 0x08000000
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                ps_script,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
        )
        # Deliberately NOT calling .wait() — fire and forget.
    except Exception:
        pass  # fail-open: notification is best-effort


# ── terminal bell ─────────────────────────────────────────────────────────────


def _emit_bell() -> None:
    """Print the hookSpecificOutput JSON that instructs CC to emit a terminal bell."""
    try:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "Notification",
                        "terminalSequence": _BEL,
                    }
                }
            ),
            flush=True,
        )
    except Exception:
        pass  # fail-open


# ── core logic ────────────────────────────────────────────────────────────────


def run(data: dict) -> int:
    """Process a parsed Notification payload. Always returns 0."""
    message = str(data.get("message") or "").strip()
    session_id = str(data.get("session_id") or "")

    # Build human-readable balloon body: prefer the actual message, fall back to generic.
    body = message[:200] if message else f"Session {session_id[:8]} needs attention."
    title = "Claude Code needs you"

    # (a) Desktop balloon (fire-and-forget, detached PowerShell process).
    try:
        _send_balloon(title=title, body=body)
    except Exception:
        pass  # fail-open

    # (b) Terminal bell via hookSpecificOutput (CC reads stdout).
    try:
        _emit_bell()
    except Exception:
        pass  # fail-open

    return 0


def main(data: dict | None = None) -> int:
    """Entry point. Accepts pre-parsed dict (tests) or reads stdin (production)."""
    try:
        if _disabled():
            return 0
        if data is None:
            try:
                raw = sys.stdin.read() or "{}"
            except Exception:
                raw = "{}"
            try:
                data = json.loads(raw)
            except Exception:
                data = {}
        return run(data)
    except Exception:
        return 0  # fail-open: outer catch-all


if __name__ == "__main__":
    sys.exit(main())
