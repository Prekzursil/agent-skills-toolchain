#!/usr/bin/env python3
r"""codex-monitor-autolaunch/check.py — PreToolUse hook (CLI-launch complement).

Opens the out-of-repo **mingle codex-monitor** dashboard when Claude starts Codex work from the
COMMAND LINE — a `codex exec` / `codex mcp` command run through Bash or PowerShell. The native
`mcp__codex__codex` MCP tool is owned by the registry-driven `monitor-autolaunch` hook (→ `mon
codexmon`), so this hook deliberately does NOT fire on it: keeping the two paths disjoint avoids a
double launch (the codexmon board AND this dashboard) on a single Codex call. A `monitors.toml`
`trigger_tool` is a single tool name and cannot express "a codex CLI command inside a
Bash/PowerShell call", so this hook stays as the CLI-launch complement. It opens ONCE per session
(a per-session lockfile, so it never spams windows) in its own `codexmon-cli` window — distinct
from codexmon's window so the two boards never dock into each other — and injects a one-line
reminder.

READ-ONLY monitor (it never launches/steers/kills Codex). FAIL-OPEN (any error -> exit 0, no
output, never blocks the tool). Opt-out: `CODEX_MONITOR_AUTOLAUNCH=off` in env, or a `.disabled`
file beside this script.

Wire via the _dispatch manifest (PreToolUse, matcher `Bash|PowerShell`); the dispatcher fires on
Bash/PowerShell tools and this hook self-filters to `codex exec` / `codex mcp` command text.
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
# Repointed 2026-07-18: was ~/.local/opt/mingle/monitor/launch.ps1 (the RETIRED legacy
# monitor — it accumulated one orphan per session across ~27 sessions AND cleared the main
# terminal buffer, destroying scrollback). Now the guarded monitorcore wrapper: its
# machine-wide single-instance guard caps the fleet at ONE board total, and it launches
# monitorcore (the merged PR-B3 board), not the legacy fork. MASTER-QUEUE T0-2.
LAUNCH = Path(os.path.expanduser("~")) / ".local" / "bin" / "codexmon.ps1"
_DETACHED = 0x00000008  # DETACHED_PROCESS — don't tie the launched window to the hook


def _is_codex_launch(payload: dict) -> bool:
    """True iff this is a CLI Codex launch — ``codex exec`` / ``codex mcp`` via Bash/PowerShell.

    The native ``mcp__codex__codex`` tool is intentionally NOT matched here (the registry-driven
    ``monitor-autolaunch`` hook owns that path → ``mon codexmon``), so the two never double-fire.
    """
    tn = str((payload or {}).get("tool_name") or "")
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
            "codexmon-cli",
            "new-tab",
            "--title",
            "codexmon-cli",
            "powershell",
            "-NoProfile",
            "-File",
            str(LAUNCH),
        ],
        [
            "cmd",
            "/c",
            "start",
            "codexmon-cli",
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
                "🛰 Opened **codex-monitor** (read-only Codex thread dashboard) in a 'codexmon-cli' window — watch your Codex threads' prompt/tools/tokens/status live. `/codex-monitor` reopens it; `CODEX_MONITOR_AUTOLAUNCH=off` disables."
            )
        else:
            _emit(
                "🛰 Tip: run `/codex-monitor` to watch your Codex threads live (thread prompt/tools/tokens/status)."
            )
    except Exception:  # noqa: BLE001 — fail-open
        return


if __name__ == "__main__":
    main()
