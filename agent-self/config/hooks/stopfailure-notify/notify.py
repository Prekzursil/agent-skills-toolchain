#!/usr/bin/env python3
"""stopfailure-notify/notify.py — StopFailure hook: log + desktop notification.

Fires when Claude Code terminates a turn due to an API error (rate_limit, overloaded,
billing_error, server_error, etc.). Useful for unattended overnight runs so the user
knows the session died and why rather than finding a stalled terminal in the morning.

StopFailure behavior:
  - CC ignores this hook's exit code and stdout entirely.
  - FIRE-AND-FORGET: wrap ALL logic in try/except; never raise; always exit 0.

Stdin JSON fields used (StopFailure payload):
  session_id     str   - session identifier
  cwd            str   - working directory at time of failure
  hook_event_name str  - always "StopFailure"
  error_type     str   - one of: rate_limit, overloaded, authentication_failed,
                         oauth_org_not_allowed, billing_error, invalid_request,
                         model_not_found, server_error, max_output_tokens, unknown
  error_message  str   - human-readable message from the API
  model          str   - model in use when the error occurred
  turn_number    int   - which turn failed

Configuration (env vars):
  STOPFAILURE_NOTIFY=0   Disable Windows desktop notification (default: enabled).
  STOPFAILURE_LOG        Override log file path (default: %TEMP%\\claude-stopfailure.log
                         or ~/.claude/event-ledger/stopfailures.log as fallback).

Windows 11 / Python 3 — encoding="utf-8", errors="replace" on all I/O.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _log_path() -> Path:
    """Determine the log file location.

    Preference order:
      1. STOPFAILURE_LOG env var (explicit override)
      2. %TEMP%\\claude-stopfailure.log   (matches the Windows temp convention)
      3. ~/.claude/event-ledger/stopfailures.log  (under the ledger tree as fallback)
    """
    override = os.environ.get("STOPFAILURE_LOG", "").strip()
    if override:
        return Path(override)

    tmp = tempfile.gettempdir()
    if tmp:
        return Path(tmp) / "claude-stopfailure.log"

    # Fallback: ledger directory
    ledger_root = Path(
        os.environ.get(
            "EVENT_LEDGER_ROOT", str(Path.home() / ".claude" / "event-ledger")
        )
    )
    ledger_root.mkdir(parents=True, exist_ok=True)
    return ledger_root / "stopfailures.log"


def _notify_enabled() -> bool:
    """Return True unless STOPFAILURE_NOTIFY is explicitly set to '0' or 'false'."""
    val = os.environ.get("STOPFAILURE_NOTIFY", "1").strip().lower()
    return val not in ("0", "false", "no", "off")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _append_log(log_path: Path, line: str) -> None:
    """Append a single line to the log file. Fail-open."""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _build_log_line(
    error_type: str,
    error_message: str,
    cwd: str,
    session_id: str,
    model: str,
    turn_number: int | str,
) -> str:
    """Build the timestamped log line.

    Format:
      <ISO-ts> StopFailure: <error_type> | <short_msg> | cwd=<cwd> session=<id>
    """
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    # Truncate long messages to keep the log readable
    short_msg = (error_message or "").strip().replace("\n", " ")[:120]
    short_session = str(session_id)[:16]
    short_cwd = str(cwd)[:80]
    parts = [
        f"{ts} StopFailure: {error_type}",
        f"msg={short_msg!r}" if short_msg else "",
        f"model={model}" if model else "",
        f"turn={turn_number}" if turn_number not in (None, "", 0) else "",
        f"cwd={short_cwd}",
        f"session={short_session}",
    ]
    return " | ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Windows desktop notification (non-blocking balloon/toast)
# ---------------------------------------------------------------------------

# PowerShell script using System.Windows.Forms NotifyIcon balloon — this is
# entirely non-blocking: we fire-and-forget the PowerShell process and do NOT
# wait for it. A balloon tooltip appears in the system tray for ~5 seconds.
#
# Why NotifyIcon instead of BurntToast / WinRT:
#   - No extra module required (Windows.Forms is in the .NET 4.x GAC on every
#     Win10/11 system; pwsh can also load it).
#   - Non-blocking: the balloon auto-dismisses; no modal dialog.
#   - Works in a headless/background service context as long as there is a
#     desktop session (which there is for an unattended user session).
#
# Fallback: if the PowerShell process fails (e.g. headless server), we just
# skip the notification — the log file is always written regardless.
#
# String-safety approach:
#   We pass title and body as PS variables set via -Command's variable assignment
#   syntax ($title = "..."; $body = "...") using PS double-quoted strings, where
#   the only characters that need escaping are backtick (the PS escape char),
#   double-quote, and dollar sign.  We do NOT use single-quoted PS strings because
#   the only escape in a single-quoted PS string is '' for a literal quote, which
#   makes it harder to handle the general case.


def _escape_ps_dq(s: str) -> str:
    """Escape a string for safe embedding in a PowerShell double-quoted string.

    In PS double-quoted strings:
      - ` is the escape character → must be doubled: ``
      - $ triggers variable expansion → escape as `$
      - " closes the string → escape as `"
    All other characters are literal. We also cap length for readability.
    """
    return (
        str(s)
        .replace("`", "``")  # escape the escape character first
        .replace("$", "`$")  # prevent variable expansion
        .replace('"', '`"')[
            # escape embedded double-quotes
            :200
        ]  # cap length so the balloon is readable
    )


def _build_ps_script(title: str, body: str) -> str:
    """Build the PS balloon script with properly escaped title and body."""
    safe_title = _escape_ps_dq(title)
    safe_body = _escape_ps_dq(body)
    # Variables are set as PS double-quoted strings then referenced unquoted
    # in the property assignments (which accept string expressions).
    return (
        "Add-Type -AssemblyName System.Windows.Forms | Out-Null; "
        "$icon = [System.Drawing.SystemIcons]::Warning; "
        "$notify = New-Object System.Windows.Forms.NotifyIcon; "
        "$notify.Icon = $icon; "
        "$notify.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Warning; "
        f'$notify.BalloonTipTitle = "{safe_title}"; '
        f'$notify.BalloonTipText = "{safe_body}"; '
        "$notify.Visible = $true; "
        "$notify.ShowBalloonTip(8000); "
        "Start-Sleep -Milliseconds 9000; "
        "$notify.Dispose()"
    )


def _send_notification(error_type: str, error_message: str, cwd: str) -> None:
    """Fire a non-blocking Windows balloon notification.

    Spawns powershell.exe in a detached process. We do NOT wait for it to
    complete — this function returns immediately. The balloon appears in the
    notification area and auto-dismisses after ~9 seconds.

    If the spawn fails or PowerShell is unavailable, this function silently
    returns (fail-open).
    """
    try:
        short_msg = (error_message or "").strip().replace("\n", " ")[:100]
        short_cwd = str(cwd)[:60]
        balloon_parts = []
        if short_msg:
            balloon_parts.append(short_msg)
        if short_cwd:
            balloon_parts.append(f"cwd: {short_cwd}")
        balloon_body = (
            " | ".join(balloon_parts) if balloon_parts else "See log for details."
        )
        title = f"Claude Code stopped: {error_type or 'unknown'}"

        ps_script = _build_ps_script(title=title, body=balloon_body)

        # Spawn detached — we do NOT call .wait() or check return code.
        # DETACHED_PROCESS (0x00000008) + CREATE_NO_WINDOW (0x08000000) on Windows
        # prevents a console window from flashing.
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    # ── parse stdin ──────────────────────────────────────────────────────────
    try:
        raw = sys.stdin.read() or "{}"
    except Exception:
        raw = "{}"

    try:
        data = json.loads(raw)
    except Exception:
        data = {}

    # ── extract fields ───────────────────────────────────────────────────────
    try:
        error_type = str(data.get("error_type") or "unknown")
        error_message = str(data.get("error_message") or "")
        session_id = str(data.get("session_id") or "")
        cwd = str(data.get("cwd") or "")
        model = str(data.get("model") or "")
        turn_number = data.get("turn_number", "")
    except Exception:
        error_type = "unknown"
        error_message = ""
        session_id = ""
        cwd = ""
        model = ""
        turn_number = ""

    # ── write log line ───────────────────────────────────────────────────────
    try:
        log_path = _log_path()
        line = _build_log_line(
            error_type=error_type,
            error_message=error_message,
            cwd=cwd,
            session_id=session_id,
            model=model,
            turn_number=turn_number,
        )
        _append_log(log_path, line)
    except Exception:
        pass  # fail-open: log write must never crash the hook

    # ── desktop notification (toggleable) ────────────────────────────────────
    try:
        if _notify_enabled():
            _send_notification(
                error_type=error_type,
                error_message=error_message,
                cwd=cwd,
            )
    except Exception:
        pass  # fail-open: notification is best-effort

    # CC ignores exit code for StopFailure, but we exit 0 by convention.
    return 0


if __name__ == "__main__":
    sys.exit(main())
