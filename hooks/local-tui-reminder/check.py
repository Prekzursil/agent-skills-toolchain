#!/usr/bin/env python3
r"""local-tui-reminder/check.py — SessionStart hook.

A gentle ONCE-PER-DAY reminder of the local terminal tools that are easy to forget because
nothing else surfaces them (the incident: the mcp GUI was forgotten for weeks). Injects a single
line naming `wfmon` (the live whole-fleet Workflow cockpit) and `mcp-manager` (the MCP-server GUI),
each with its one-word launcher. Fires at most once per calendar day (dated marker), so it reminds
without nagging every session.

FAIL-OPEN (any error -> exit 0, no output). Opt-out: `LOCAL_TUI_REMINDER=off` in env, or a
`.disabled` file beside this script. Standalone settings.json SessionStart entry (the live
harness dispatcher does not render the toolchain capability-catalog, so a manifest/card is inert).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
LINE = (
    "🛰 Local TUIs you have (easy to forget): `wfmon` — live whole-fleet Workflow/ultracode cockpit "
    "(auto-opens on a Workflow; `wfmon board` = plain text) · `mcp-manager` — cross-plane MCP-server "
    "GUI. (daily reminder · `LOCAL_TUI_REMINDER=off` or a .disabled file to stop)"
)


def main() -> None:
    try:
        if (
            DISABLED.exists()
            or os.environ.get("LOCAL_TUI_REMINDER", "").lower() == "off"
        ):
            return
        today = (
            _dt.date.today().isoformat()
        )  # local hook (not the Workflow sandbox) — date is fine
        marker = THIS / f".shown-{today}"
        if marker.exists():
            return
        # prune older markers so the dir doesn't grow
        for old in THIS.glob(".shown-*"):
            if old.name != marker.name:
                try:
                    old.unlink()
                except OSError:
                    pass
        try:
            marker.write_text("1", encoding="utf-8")
        except OSError:
            pass
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": LINE,
                    }
                }
            )
        )
    except Exception:  # noqa: BLE001 — fail-open
        return


if __name__ == "__main__":
    main()
